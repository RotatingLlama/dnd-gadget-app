# UI code for menus, etc.
# Consider as part of gadget.py
#
# T. Lloyd
# 31 Jan 2026

from micropython import const

from .common import SD_ROOT, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE
from . import menu

# Matrix adjust timeout, in ms
_MTX_TIMEOUT = const(3000)

# Sets up the playscreen (inc. all its menus)
def play_menus(self):
  hal = self.hal
  
  # Localisation
  rm = menu.RootMenu( self.hal, HAL_PRIORITY_MENU )
  char = self.character
  
  # Create default/idle HAL registration
  mtx_idle = hal.register(
    priority=HAL_PRIORITY_IDLE,
    features=('mtx',),
    callback=self.character.draw_mtx,
    name='MtxIdle'
  )
  
  # MATRIX MENU #
  
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
  
  # Tidy up
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
  
  mm = menu.MatrixMenu(
      hal,
      prio=HAL_PRIORITY_MENU+1,
      active_rows=activerows,
      inc=lambda r: adj( 1, r ),
      dec=lambda r: adj( -1, r ),
      buffer=self.hal.mtx.bitmap,
      redraw_buffer=lambda: char.draw_mtx( show=False ),
      send_buffer=self.hal.mtx.update,
      timeout=_MTX_TIMEOUT,
    )
  rm.menus.append(mm)
  
  
  # OLED MENU #
  
  om = menu.ScrollingOledMenu(
    parent=rm,
    hal=hal,
    prio=HAL_PRIORITY_MENU+1,
    wrap=0
  )
  rm.menus.append(om)
  omi = om.items
  
  # Health submenu
  #
  submenu = menu.SubMenu( om, self.hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Health'
  )
  smm = submenu.menu
  smi = smm.items
  omi.append( submenu )
  #
  smi.append(
    menu.DoubleAdjuster( smm, self.hal,
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
    menu.SimpleAdjuster( smm, self.hal,
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
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Temp HP',
      get_cur=lambda: 0, # Always starts at zero because we're always replacing
      set_abs=char.set_temp_hp
    )
  )
  
  ## Money submenu
  #
  submenu = menu.SubMenu( om, self.hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Currency'
  )
  smm = submenu.menu
  smi = smm.items
  omi.append( submenu )
  #
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Gold',
      get_cur=lambda: char.stats['gold'],
      set_abs=char.set_gold
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Silver',
      get_cur=lambda: char.stats['silver'],
      set_abs=char.set_silver
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Copper',
      get_cur=lambda: char.stats['copper'],
      set_abs=char.set_copper
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Electrum',
      get_cur=lambda: char.stats['electrum'],
      set_abs=char.set_electrum
    )
  )
  
  ## Rest/reset submenu
  #
  submenu = menu.SubMenu( om, self.hal,
    prio=HAL_PRIORITY_MENU+2,
    title='Rest & Reset'
  )
  smm = submenu.menu
  smi = smm.items
  omi.append( submenu )
  #
  smi.append(
    menu.FunctionConfirmer( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Long Rest',
      confirmation='Take long rest',
      con_func=char.long_rest
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
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
    menu.FunctionConfirmer( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Dawn Reset',
      #             x x x x x x x x
      confirmation='Dawn, no rest?',
      con_func=char.dawn_reset
    )
  )
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Hit Dice',
      get_cur=lambda: char.stats['hd'][0],
      set_abs=char.set_hit_dice,
      min=0,
      max=char.stats['hd'][1],
      allow_zero=True,
    )
  )
  
  # XP is its own thing
  omi.append(
    menu.SimpleAdjuster( om, self.hal,
      prio=HAL_PRIORITY_MENU+2,
      title='XP',
      get_cur=lambda: char.stats['xp'],
      set_abs=char.set_xp
    )
  )
  
  ## System submenu
  #
  submenu = menu.SubMenu( om, self.hal,
    prio=HAL_PRIORITY_MENU+2,
    title='System'
  )
  smm = submenu.menu
  smi = smm.items
  omi.append( submenu )
  #
  #
  smi.append(
    menu.SimpleAdjuster( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Brightness',
      # Get and set using the HAL function
      # Preview using the driver function, bypassing HAL's memory
      get_cur=self.hal.mtx.brightness,
      set_abs=self.hal.mtx.brightness,
      adj_abs=self.hal.mtx.matrix.brightness, # Daisy, Daisy, give me your answer do...
      min=0,
      max=15,
      allow_zero=True,
    )
  )
  smi.append(
    menu.FunctionConfirmer( smm, self.hal,
      prio=HAL_PRIORITY_MENU+3,
      title='Power Off',
      confirmation='Shut down',
      con_func=self.power_off
    )
  )
  
  # ROOT MENU #
  
  rm.init(
    cw  = mm.prev_item,
    ccw = mm.next_item,
    btn = om.next_item
  )
  
  
  #def plug():
  #  pass
  #
  #def unplug():
  #  pass
  
  # Tidies up things that were set by play_menus() and triggers a save, if needed
  def end():
    
    # Tidy up UI elements
    self.menu.destroy()
    self.hal.unregister( mtx_idle )
    
    # Make sure everything is saved
    if self.character.is_dirty():
      self.character.save_now( SD_ROOT )
    
    # Wipe the character object
    self.character = None
    
    # Nothing left to clean up
    self.cleanup = lambda : None
  
  # Assign
  #self.menu = rm
  #self.cleanup = end
  #self.sd_plug = plug
  #self.sd_unplug = unplug
  
  return rm, end
