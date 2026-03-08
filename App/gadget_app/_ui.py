# UI code for menus, etc.
# Consider as part of character.py
#
# T. Lloyd
# 08 Mar 2026

from micropython import const

from .common import SD_ROOT, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE
from . import menu

# Matrix adjust timeout, in ms
_MTX_TIMEOUT = const(3000)


def make_matrix_menu_stable( hal, char ) -> menu.MatrixMenu:
  
  # Calculate matrix geometry
  n_spls = len(char.stats['spells']) # Allow as many spells as we have
  n_chgs = min( 16-n_spls, len(char.stats['charges']) ) # Cut off charges if there are too many to fit
  n_rows = n_chgs + n_spls # Number of active rows
  gap = 16 - n_rows
  
  # Construct the active rows array for MatrixMenu
  activerows = bytearray( n_rows )
  for r in range(n_chgs): # Matrix is indexed from top down - so do the charges first
    activerows[r] = r
  for r in range(n_chgs,n_rows): # These are the spells
    activerows[r] = r + gap # Actual row the spells are on may be offset if there's a gap between them and the charges
  
  # Tidy up before we create the closure
  del n_spls, n_rows, gap, r
  
  # Adjust a spell or charge, based on what row of the matrix it's represented on
  def adj( n:int, row:int ) -> None:
    if row < n_chgs: # Charges
      char.set_charge(
        row,
        n + char.stats['charges'][row]['curr'],
        show=True
      )
    else: # Spells
      char.set_spell(
        15 - row,
        n + char.stats['spells'][15-row][0],
        show=True
      )
  
  return menu.MatrixMenu(
      hal,
      prio=HAL_PRIORITY_MENU+1,
      active_rows=activerows,
      inc=lambda r: adj( 1, r ),
      dec=lambda r: adj( -1, r ),
      buffer=hal.mtx.bitmap,
      redraw_buffer=lambda: char.draw_mtx_stable( show=False ),
      send_buffer=hal.mtx.update,
      timeout=_MTX_TIMEOUT,
    )

def make_matrix_menu_saves( hal, char ) -> menu.MatrixMenu:
  
  # Adjustment function.
  # n: The (relative) amount to adjust by
  # row: The row ID
  def adj( n:int, row:int ) -> None:
    
    # row 0: success
    # row 1: failure
    
    char.set_deathsaves(
      success = (not row), # Transform row number into success boolean
      val = n + char.stats['death'][ ('successes','failures')[row] ],
      show = True
    )
  
  return menu.MatrixMenu(
      hal,
      prio=HAL_PRIORITY_MENU+1,
      active_rows=bytes((0,1,)),
      inc=lambda r: adj( 1, r ),
      dec=lambda r: adj( -1, r ),
      buffer=hal.mtx.bitmap,
      redraw_buffer=lambda: char.draw_mtx_saves( show=False ),
      send_buffer=hal.mtx.update,
      timeout=_MTX_TIMEOUT,
    )


# Sets up the OLED menu (works for all states stable/saves/dead)
def make_oled_menu( hal, char, parent ) -> menu.ScrollingOledMenu:
  
  # Localise
  death = char.stats['death']
  
  # Root Oled menu
  om = menu.ScrollingOledMenu(
    parent=parent,
    hal=hal,
    prio=HAL_PRIORITY_MENU+1,
    wrap=0
  )
  omi = om.items
  
  # Health submenu
  if death['status'] == 'stable':
    # Use the normal damage/heal/temphp submenu
    omi.append( _submenu_health_stable( hal, char, om ) )
  elif death['status'] == 'saves':
    if death['failures'] < 3:
      # Use the reduced stabilise/heal submenu
      omi.append( _submenu_health_deathsaves( hal, char, om ) )
    else:
      # No menu.  Just a prompt to die
      omi.append(
        menu.FunctionConfirmer( om, hal,
          prio=HAL_PRIORITY_MENU+3,
          title='Die',
          confirmation='Die?',
          con_func=char.die
        )
      )
  elif death['status'] == 'dead':
    # Resurrection menu
    omi.append( _submenu_resurrection( hal, char, om ) )
  
  # Money submenu - always available
  omi.append( _submenu_money( hal, char, om ) )
  
  # Rest/reset submenu - only appplies when stable
  if death['status'] == 'stable':
    omi.append( _submenu_rest_reset( hal, char, om ) )
  
  # XP is its own thing - always available
  omi.append(
    menu.SimpleAdjuster( om, hal,
      prio=HAL_PRIORITY_MENU+2,
      title='XP',
      get_cur=lambda: char.stats['xp'],
      set_abs=lambda x : char.set_numeric_item( 'xp', x )
    )
  )
  
  return om

# Used by stable and deathsaves submenus
def _menuitem_heal( hal, char, parent ) -> menu.SimpleAdjuster:
  return menu.SimpleAdjuster( parent, hal,
    prio=HAL_PRIORITY_MENU+3,
    title='Heal',
    get_cur=lambda: char.stats['hp'][0],
    set_rel=char.heal,
    adj_rel = lambda d : char.show_hp( char.stats['hp'][0] + char.stats['hp'][2] + d ),
    min_d=0,
    max_d=None,
    min=0,
    max=char.stats['hp'][1]
  )

# Normal health menu.  Damage, Heal, Temp HP
def _submenu_health_stable( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Health'
  )
  smm = submenu.menu
  smi = smm.items
  
  #
  smi.append(
    menu.DoubleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Damage',
      preview=lambda d: char.damage_calc(-d),
      get_cur=lambda: ( char.stats['hp'][0], char.stats['hp'][2] ),
      set_new=lambda d: char.damage(-d),
      a='     HP',
      b='Temp HP',
      adj_rel = lambda d : char.show_hp( char.stats['hp'][0] + char.stats['hp'][2] + d ),
      min_d=None,
      max_d=lambda: 0,
    )
  )
  smi.append(
    _menuitem_heal( hal, char, smm )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Temp HP',
      get_cur=lambda: 0, # Always starts at zero because we're always replacing
      set_abs=char.set_temp_hp
    )
  )
  
  return submenu

# Reduced health menu:  Stabilise or Heal.
def _submenu_health_deathsaves( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Health'
  )
  smm = submenu.menu
  smi = smm.items
  
  # Stabilise
  smi.append(
   menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Stabilise',
      confirmation='Stabilise?',
      con_func=char.stabilise
    )
  )
  
  # Heal
  smi.append(
    _menuitem_heal( hal, char, smm )
  )
  
  return submenu

# Resurrection menu (used instead of health if char is dead)
def _submenu_resurrection( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Resurrection'
  )
  smm = submenu.menu
  smi = smm.items
  
  # Restore
  def r(full:bool):
    
    # Restore at full HP?
    if full:
      hp = char.stats['hp'][1]
    else:
      hp = 1
    
    # Do it
    char.stats['hp'][0] = hp
    char.stabilise()
    
  smi.append(
   menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Restore 1 HP',
      confirmation='Restore 1 HP?',
      con_func=lambda : r(False)
    )
  )
  smi.append(
   menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Restore Full HP',
      confirmation='Restore full HP?',
      con_func=lambda : r(True)
    )
  )
  
  return submenu

def _submenu_money( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Currency'
  )
  smm = submenu.menu
  smi = smm.items
  
  #
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Gold',
      get_cur=lambda: char.stats['gold'],
      set_abs=lambda x : char.set_numeric_item( 'gold', x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Silver',
      get_cur=lambda: char.stats['silver'],
      set_abs=lambda x : char.set_numeric_item( 'silver', x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Copper',
      get_cur=lambda: char.stats['copper'],
      set_abs=lambda x : char.set_numeric_item( 'copper', x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Platinum',
      get_cur=lambda: char.stats['platinum'],
      set_abs=lambda x : char.set_numeric_item( 'platinum', x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Electrum',
      get_cur=lambda: char.stats['electrum'],
      set_abs=lambda x : char.set_numeric_item( 'electrum', x )
    )
  )
  
  return submenu

def _submenu_rest_reset( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Rest & Reset'
  )
  smm = submenu.menu
  smi = smm.items
  
  #
  smi.append(
    menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Long Rest',
      confirmation='Take long rest',
      con_func=char.long_rest
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Short Rest',
      #       x x x x x x x x
      prompt='Use hit dice?',
      get_cur=lambda: char.stats['hd'][0],
      set_rel=lambda dice: char.short_rest(-dice),
      min=0,
      max_d=0,
      allow_zero=True,
    )
  )
  smi.append(
    menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Dawn Reset',
      #             x x x x x x x x
      confirmation='Dawn, no rest?',
      con_func=char.dawn_reset
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Hit Dice',
      get_cur=lambda: char.stats['hd'][0],
      set_abs=char.set_hit_dice,
      min=0,
      max=char.stats['hd'][1],
      allow_zero=True,
    )
  )
  
  return submenu
