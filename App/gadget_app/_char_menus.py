# UI code for menus, etc.
# Consider as part of character.py
#
# T. Lloyd
# 07 Apr 2026

from micropython import const

from .common import HAL_PRIORITY_MENU #, SD_ROOT, HAL_PRIORITY_IDLE
from . import menu

# Matrix adjust timeout, in ms
_MTX_TIMEOUT = const(3000)

# Indexes into the Character.data object
#_NAME = const(0)
#_TITLE = const(1)
_XP = const(2)
_CURRENCY = const(3)
_HP = const(4)
_HD = const(5)
_SPELLS = const(6)
_CHARGES = const(7)
_DEATH = const(8)
#
_CURRENCY_COPPER = const(0)
_CURRENCY_SILVER = const(1)
_CURRENCY_ELECTRUM = const(2)
_CURRENCY_GOLD = const(3)
_CURRENCY_PLATINUM = const(4)
#
_HP_CURR = const(0)
_HP_MAX = const(1)
_HP_TEMP = const(2)
#_HP_ORIGTEMP = const(3)
#
_HD_CURR = const(0)
_HD_MAX = const(1)
#
_SPELLS_CURR = const(0)
#_SPELLS_MAX = const(1)
#
_CHARGES_CURR = const(0)
#_CHARGES_MAX = const(1)
#_CHARGES_RESET = const(2)
#_CHARGES_NAME = const(3)
#
_DEATH_STATUS = const(0)
_DEATH_OK = const(1)
_DEATH_NG = const(2)
#
_DEATH_STATUS_OK = const(0)
_DEATH_STATUS_SV = const(1)
_DEATH_STATUS_DD = const(2)

# Index into the Levels tuples
# ( name, hp, hd, spells, items )
_LV_NAME = const(0)
_LV_HP = const(1)
_LV_HD = const(2)
_LV_SPELLS = const(3)
_LV_ITEMS = const(4)


def make_matrix_menu_stable( hal, char ) -> menu.MatrixMenu:
  
  # Calculate matrix geometry
  n_spls = len(char.data[_SPELLS][_SPELLS_CURR]) # Allow as many spells as we have
  n_chgs = min( 16-n_spls, len(char.data[_CHARGES]) ) # Cut off charges if there are too many to fit
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
        n + char.data[_CHARGES][row][_CHARGES_CURR],
        show=True
      )
    else: # Spells
      char.set_spell(
        15 - row,
        n + char.data[_SPELLS][_SPELLS_CURR][15-row],
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
      val = n + char.data[_DEATH][ ( _DEATH_OK, _DEATH_NG )[row] ],
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
  death = char.data[_DEATH]
  
  # Root Oled menu
  om = menu.ScrollingOledMenu(
    parent=parent,
    hal=hal,
    prio=HAL_PRIORITY_MENU+1,
    wrap=0
  )
  omi = om.items
  
  # Health submenu
  if death[_DEATH_STATUS] == _DEATH_STATUS_OK:
    # Use the normal damage/heal/temphp submenu
    omi.append( _submenu_health_stable( hal, char, om ) )
  elif death[_DEATH_STATUS] == _DEATH_STATUS_SV:
    if death[_DEATH_NG] < 3:
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
  elif death[_DEATH_STATUS] == _DEATH_STATUS_DD:
    # Resurrection menu
    omi.append( _submenu_resurrection( hal, char, om ) )
  
  # Rest/reset submenu - only appplies when stable
  if death[_DEATH_STATUS] == _DEATH_STATUS_OK:
    omi.append( _submenu_rest_reset( hal, char, om ) )
  
  # Character submenu
  omi.append( _submenu_char( hal, char, om ) )
  
  # Money submenu - always available
  omi.append( _submenu_money( hal, char, om ) )
  
  return om

# Used by stable and deathsaves submenus
def _menuitem_heal( hal, char, parent ) -> menu.SimpleAdjuster:
  return menu.SimpleAdjuster( parent, hal,
    prio=HAL_PRIORITY_MENU+3,
    title='Heal',
    get_cur=lambda: char.data[_HP][_HP_CURR],
    set_rel=char.heal,
    adj_rel = lambda d : char.show_hp( char.data[_HP][_HP_CURR] + char.data[_HP][_HP_TEMP] + d ),
    min_d=0,
    max_d=None,
    min=0,
    max=char.data[_HP][_HP_MAX]
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
      get_cur=lambda: ( char.data[_HP][_HP_CURR], char.data[_HP][_HP_TEMP] ),
      set_new=lambda d: char.damage(-d),
      a='     HP',
      b='Temp HP',
      adj_rel = lambda d : char.show_hp( char.data[_HP][_HP_CURR] + char.data[_HP][_HP_TEMP] + d ),
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
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Max HP',
      get_cur=lambda: char.data[_HP][_HP_MAX],
      set_abs=char.set_max_hp
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
  
  smi.append(
   menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Restore 1 HP',
      confirmation='Restore 1 HP?',
      con_func=lambda : char.undie(False)
    )
  )
  smi.append(
   menu.FunctionConfirmer( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Restore Full HP',
      confirmation='Restore full HP?',
      con_func=lambda : char.undie(True)
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
      get_cur=lambda: char.data[_CURRENCY][_CURRENCY_GOLD],
      set_abs=lambda x : char.set_currency( _CURRENCY_GOLD, x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Silver',
      get_cur=lambda: char.data[_CURRENCY][_CURRENCY_SILVER],
      set_abs=lambda x : char.set_currency( _CURRENCY_SILVER, x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Copper',
      get_cur=lambda: char.data[_CURRENCY][_CURRENCY_COPPER],
      set_abs=lambda x : char.set_currency( _CURRENCY_COPPER, x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Platinum',
      get_cur=lambda: char.data[_CURRENCY][_CURRENCY_PLATINUM],
      set_abs=lambda x : char.set_currency( _CURRENCY_PLATINUM, x )
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Electrum',
      get_cur=lambda: char.data[_CURRENCY][_CURRENCY_ELECTRUM],
      set_abs=lambda x : char.set_currency( _CURRENCY_ELECTRUM, x )
    )
  )
  
  return submenu

def _submenu_char( hal, char, parent ) -> menu.SubMenu:
  
  submenu = menu.SubMenu( parent, hal,
    prio=HAL_PRIORITY_MENU+2,
    title=char.name
  )
  smm = submenu.menu
  smi = smm.items
  
  # XP
  smi.append(
    menu.SimpleAdjuster( smm, hal,
      prio=HAL_PRIORITY_MENU+3,
      title='XP',
      get_cur=lambda: char.data[_XP],
      set_abs=char.set_xp
    )
  )
  
  # Level
  lvmenu = menu.SubMenu( smm, hal,
    prio=HAL_PRIORITY_MENU+3,
    title='Change Level'
  )
  lvmm = lvmenu.menu
  lvmi = lvmm.items
  smi.append(lvmenu)
  #
  for i, lv in enumerate(char.levels):
    
    # Don'gt offer to switch to current level
    if i == char.current_level:
      continue
    
    # Add level to menu
    lvmi.append(
      menu.FunctionConfirmer( lvmm, hal,
        prio=HAL_PRIORITY_MENU+4,
        title=lv[_LV_NAME],
        confirmation='Change level?',
        con_func=lambda q=i: char.switch_level(q) # Have to do this thing with default values because creating lambdas inside a loop
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
      get_cur=lambda: char.data[_HD][_HD_CURR],
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
      get_cur=lambda: char.data[_HD][_HD_CURR],
      set_abs=char.set_hit_dice,
      min=0,
      max=char.data[_HD][_HD_MAX],
      allow_zero=True,
    )
  )
  
  return submenu
