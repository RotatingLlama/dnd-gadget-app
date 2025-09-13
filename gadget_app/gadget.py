# TTRPG Gadget
# For Micropython v1.26
#
# T. Lloyd
# 13 Sep 2025


# TO USE:
#
# from gadget_app import Gadget
# g = Gadget()
#
# Then either start an asyncio loop manually and await g.start_app()
# Or just call g.run()


# Builtin libraries
import asyncio
from array import array
#import os
#import time
import gc
from micropython import const
import vfs

# Other libraries
from . import pathlib

# Our stuff
from .common import *
from . import menu
from .hal import HAL
from . import gfx
import img # Export this to gfx?

_DEBUG_DISABLE_EINK = const(False)

# Character file info
MANDATORY_CHAR_FILES = [ # Files that must exist in a character directory for it to be recognised
  CHAR_STATS,
]

# HAL priority levels
_HAL_PRIORITY_IDLE = const(0)
_HAL_PRIORITY_NOSD = const(5)
_HAL_PRIORITY_MENU = const(10)
_HAL_PRIORITY_SHUTDOWN = const(100)

# Error text for SD problems
_SD_ERRORS = {
  #    123456789  123456789
  1 : 'Card not \npresent!',
  2 : 'Could not\nmount SD!',
  3 : 'No chars \non SD :(',
}

class Gadget:
  
  def __init__(self):
    
    # Load modules
    self.hal = HAL()
    
    # Things we want to keep track of
    self.file_root = pathlib.Path( SD_ROOT ) / SD_DIR
    self.character = None
    self._nosdcr = None
    
    # Phase triggers
    self.phase_select_char = asyncio.Event()
    self.phase_play = asyncio.Event()
    self.phase_reset = asyncio.Event()
    self.phase_exit = asyncio.Event()
    #
    self._shutdown = asyncio.Event()
    self._exit_loop = asyncio.Event()
  
  # Looks at the directory and returns a list of objects:
  # {
  #   'dir' (Path): Character directory,
  #   'head' (String): Head image,
  # }
  def _find_chars(self):
    
    chars = []
    # No iterdir() in pathlib.py from [https://github.com/micropython/micropython-lib/blob/master/python-stdlib/pathlib/pathlib.py]
    #for x in self.file_root.iterdir():
    for x in ( self.file_root / CHAR_SUBDIR ).glob('*'):
      
      # Have we found a directory?
      if not x.is_dir():
        continue
      
      # Is everything present that should be?
      ok = True
      for f in MANDATORY_CHAR_FILES:
        if not ( x / f ).is_file():
          print( f, 'is not present for', x.name)
          ok = False
      if not ok:
        continue
      
      # Is there a headshot?
      head = ( x / CHAR_HEAD )
      if head.is_file():
        head = str(head)
      else:
        head = None
      
      # If we're here, we're good
      chars.append({
        'dir'  : x,
        'head' : head,
      })
    
    return chars
  
  # Regularly updates the oled with idle stuff
  async def _oled_runner(self,cr):
    o = self._oled_idle_render
    s = asyncio.sleep_ms
    while True:
      if cr.ready:
        o()
      await s(500)
  #
  def _oled_idle_render(self):
    oled = self.hal.oled
    oled.fill(0)
    for item in self._oled_idle:
      item( oled )
    oled.show()
  
  # Define and register the functions that draw oled updates (run ONCE)
  def _setup_oled_renderers(self):
    
    # Canary so we can see if this ever happens more than once
    print('Registering OLED functions...')
    
    # Containers for persistent values
    #uint = array( 'I', [0] ) # Unsigned int (2 bytes)
    long = array( 'L', [0]*2 ) # Unsigned long (4 bytes)
    
    # Battery monitor on default OLED screen
    pc = self.hal.batt_pc
    def batt(disp):
      v = disp.vline
      h = disp.hline
      p = pc()
      
      # Top-left point
      x = 127
      y = 0
      
      # Draw the battery outline             xxxxxxxxxxxx+
      v( x-1,  y,     6, 1 ) # Right wall    x          x
      v( x,    y+2,   3, 1 ) # Nub           x          xx
      h( x-1,  y,   -12, 1 ) # Top wall      x          xx
      v( x-12, y,     6, 1 ) # Left wall     x          xx
      h( x-1,  y+6, -12, 1 ) # Bottom wall   x          x
      #                                      xxxxxxxxxxxx
      
      if p is None:
        # If we didn't get a percentage, we probably have VBUS
        t = 'USB'
      else:
          
        # How full is the battery?
        bars = ( p // 10 )
        
        # Draw the bars
        for i in range(bars):
          v( x-11+i, y+1, 5, 1 )
        
        # Percentage text
        t = f'{p}%'
      
      disp.text( t, x - 12 -( 8*len(t) ), y, 1 )
      disp.text( f'{round(self.hal.hw.voltage_stable(),4)}v', x-47, y+8, 1 )
    self._oled_idle.add( batt )
    
    # Corner pixel to indicate eink busy, direct from Pin
    bv = self.hal.eink.Busy.value
    def eb(disp):
      if bv() == 0:
        disp.text( 'e', 120,24, 1 )
    self._oled_idle.add( eb )
    
    # Memory usage monitor
    ma = gc.mem_alloc
    mf = gc.mem_free
    memlog = bytearray(32)
    mptr = bytearray(1) # has to be object to be visible by function
    def mem(disp):
      long[0] = ma() # Need longs.  233664 > 65535
      long[1] = mf()
      disp.text( f'M: {round( ( long[0] / ( long[0]+long[1] ) ) * 100 )}%', 0,0, 1 )
    def mem2(disp):
      
      # Record current mem at mptr
      memlog[mptr[0]] = gc.mem_alloc() // 14604
      
      disp.rect( 0,16, 32,16, 0, True ) # Blank out our rectangle
      disp.vline( 33,16, 16, 1 ) # axis line
      
      # Start at the beginning
      mptr[0] += 1
      mptr[0] %= 32
      
      # Loop through memlog
      for i in range(32):
        disp.pixel( i, 32-memlog[mptr[0]], 1 )
        mptr[0] += 1
        mptr[0] %= 32
    self._oled_idle.add( mem )
    self._oled_idle.add( mem2 )
    
    # Add renderer for outstanding save action
    def save(disp):
      
      if self.character is None:
        return
      
      # Where? (top left)
      x = 35
      y = 16
      
      # If we aren't showing the icon
      if not self.character.is_saving():
        disp.rect(x,y, 12,12, 0, True ) # Blank out the area
        return
      
      # Localisation
      v = disp.vline
      h = disp.hline
      r = disp.rect
      p = disp.pixel
      
      # Draw a 12x12 floppy disk icon
      v(x,    y+1,   10, 1 ) # Left wall
      h(x+1,  y+11,  10, 1 ) # Bottom
      v(x+11, y+10,  -9, 1 ) # Right wall
      p(x+10, y+1, 1 )       # Corner
      h(x+9,  y,     -9, 1 ) # Top
      r(x+2, y+7, 8,5, 1, False ) # Label
      r(x+3, y,   6,4, 1, False ) # Shield outline
      r(x+4, y+1, 2,2, 1, False ) # Shield fill
    self._oled_idle.add( save )
  
  # Triggers shutdown
  def power_off(self):
    self._shutdown.set()
  
  # Sets up the selector, returns the Character object
  async def _select_character(self):
    
    # This gets set when the Character object is created
    done = asyncio.ThreadSafeFlag()
    
    while True:
      await self.phase_select_char.wait()
      
      # Takes a framebuffer and a list of chars to show
      # Returns as many chars as it actually did show
      chars = gfx.draw_char_select( self.hal.eink, self._find_chars() )
      if not _DEBUG_DISABLE_EINK:
        self.hal.eink_send_refresh()
      #print(chars)
      
      # This will hold the Character object
      cobj = [0]
      
      # Gets called when a character is chosen
      # Gets given an index into the list from _find_chars()
      def set_char( charid ):
        
        # Ignore character choice if the SD card has gone away
        if not self.hal.sd.has_card():
          return
        
        # Set it up
        from .character import Character
        cobj[0] = Character( self.hal, chars[ charid ]['dir'] )
        if not _DEBUG_DISABLE_EINK:
          cobj[0].draw_eink()
        cobj[0].draw_mtx()
        cobj[0].show_curr_hp()
        
        # Let everything else know
        done.set()
      
      # Set up the character select UI
      csm = menu.NeedleMenu(
        hal = self.hal,
        n = len(chars),
        btn = set_char,
        back = lambda x: self.hal.needle.wobble() # self.power_off() # self.hal.hw.empty_battery.set()
      )
      cr = self.hal.register( priority=_HAL_PRIORITY_MENU, features=('needle','input',), input_target=csm.input_target )
      #self.hw.init( cw=csm.cw, ccw=csm.ccw, btn=csm.btn, sw=csm.back )
      
      # Wait until the character is chosen
      await done.wait()
      
      # Make sure this is ready in case of next loop
      done.clear()
      
      # Unregister with the HAL
      self.hal.unregister(cr)
      
      # Assign the character
      self.character = cobj[0]
      
      # Trigger Play phase
      self.phase_play.set()
      
      # Tidy up
      del cobj, cr, chars, set_char, csm
      gc.collect()
      
      # Wait for any reset
      await self.phase_reset.wait()
  
  #
  async def _play_screen(self):
    hal = self.hal
    while True:
      await self.phase_play.wait()
      
      # Localisation
      rm = menu.RootMenu( self.hal, self.character )
      rmm = rm.menus
      char = self.character
      
      # MATRIX MENU #
      
      rmm.append(
        menu.ChargeMenu(
          rm,hal,char,
          startrow=0,
          indices = [ x for x in range( len(char.stats['charges']) ) ]
        )
      )
      
      rmm.append(
        menu.SpellMenu(
          rm,hal,char,
          startrow=16-len( char.stats['spells'] ),
          indices = [ x for x in range( len( char.stats['spells'] )-1, -1, -1 ) ]
        )
      )
      
      rmm[0].init( # Charges
        next_menu=rmm[1],
        prev_menu=None
      )
      rmm[1].init( # Spells
        next_menu=None,
        prev_menu=rmm[0]
      )
      
      # OLED MENU #
      
      rmm.append(
        menu.OledMenu(rm,hal,char)
      )
      rmm[2].init( # OLED
        next_menu=rmm[2],
        prev_menu=rmm[2]
      )
      
      omi = rmm[2].items
      
      omi.append(
        menu.DoubleAdjuster( rmm[2], self.hal, 'Damage',
          preview=lambda d: char.damage_calc(-d),
          get_cur=lambda: ( char.stats['hp'][0], char.stats['hp'][2] ),
          set_new=lambda d: char.damage(-d),
          a='     HP',
          b='Temp HP',
          adj_rel = lambda d : char.show_hp( char.stats['hp'][0] + char.stats['hp'][2] + d ),
          min_d=None,
          max_d=lambda: 0,
          min_a=None,
          min_b=lambda: 0,
          max_a=lambda: char.stats['hp'][1],
          max_b=lambda: char.stats['hp'][2]
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'Heal',
          get_cur=lambda: char.stats['hp'][0],
          set_rel=char.heal,
          adj_rel = lambda d : char.show_hp( char.stats['hp'][0] + char.stats['hp'][2] + d ),
          min_d=0,
          max_d=None,
          min=0,
          max=char.stats['hp'][1]
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'TEMP HP',
          get_cur=lambda: 0, # Always starts at zero because we're always replacing
          set_abs=char.set_temp_hp
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'GOLD',
          get_cur=lambda: char.stats['gold'],
          set_abs=char.set_gold
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'SILVER',
          get_cur=lambda: char.stats['silver'],
          set_abs=char.set_silver
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'COPPER',
          get_cur=lambda: char.stats['copper'],
          set_abs=char.set_copper
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'ELECTRUM',
          get_cur=lambda: char.stats['electrum'],
          set_abs=char.set_electrum
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'XP',
          get_cur=lambda: char.stats['xp'],
          set_abs=char.set_xp
        )
      )
      omi.append(
        menu.FunctionConfirmer( rmm[2], self.hal, 'LONG REST',
          confirmation='Take long rest',
          con_func=char.long_rest
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'SHORT REST',
          #       x x x x x x x x
          prompt='Use hit dice?',
          get_cur=lambda: char.stats['hd'][0],
          set_rel=lambda dice: char.short_rest(-dice),
          min=0,
          max_d=0,
          allow_zero=True,
        )
      )
      omi.append(
        menu.SimpleAdjuster( rmm[2], self.hal, 'Brightness',
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
      omi.append(
        menu.FunctionConfirmer( rmm[2], self.hal, 'POWER OFF',
          confirmation='Shut down',
          con_func=self.power_off
        )
      )
      
      # ROOT MENU #
      
      rm.init(
        cw  = rmm[1].prev_item,
        ccw = rmm[0].next_item,
        btn = rmm[2].next_item
      )
      #self.hw.init( cw=rm.cw, ccw=rm.ccw, btn=rm.btn, sw=rm.back )
      cr = self.hal.register( priority=_HAL_PRIORITY_MENU, features=('input',), input_target=rm.input_target )
      
      # Assign
      self.menu = rm
      
      # Tidy up
      del rm, rmm, omi # , char
      gc.collect()
      
      # Wait for a reset
      await self.phase_reset.wait()
      
      # If we've been reset, give up our HAL registration
      self.hal.unregister(cr)
  
  async def _phase_controller(self):
    print('Phase controller active')
    while True:
      
      # Start the first phase
      self.phase_select_char.set()
      
      # First phase starts second phase, and so on.
      # All wait for phase_reset when they're done
      
      # Await a reset
      await self.phase_reset.wait()
      
      # Stop here if we're shutting down
      if self.phase_exit.is_set():
        break
      
      # Tidy things up before looping
      self.character = None
  
  # Start everything, keep refs to looping tasks
  async def main_sequence(self):
    
    # Battery protection
    bp = asyncio.create_task(asyncio.gather(
      self._shutdown_batt(),
      #self._battery_charge_waiter(),
      self._battery_low_waiter(),
    ))
    
    def sd_plug():
      
      # Remove any existing SD error message
      if self._nosdcr is not None:
        self.hal.unregister(self._nosdcr)
        self._nosdcr = None
      
      # Try to mount
      e = self._try_mount_sd()
      if e > 0:
        self._nosdcr = self.hal.register(
          priority=_HAL_PRIORITY_NOSD,
          features=('oled',),
          callback=lambda:self._render_sd_error( _SD_ERRORS[e] )
        )
      
    def sd_unplug():
      
      # Tidy up the mountpoint
      if self._sd_is_mounted():
        vfs.umount( SD_ROOT )
      
      # Remove any existing SD error message
      if self._nosdcr is not None:
        self.hal.unregister(self._nosdcr)
      
      # Register the new error
      self._nosdcr = self.hal.register(
        priority=_HAL_PRIORITY_NOSD,
        features=('oled',),
        callback=lambda:self._render_sd_error( _SD_ERRORS[1] )
      )
    
    #sd = asyncio.create_task(self._sd_plug_waiter())
    # Set up triggers for hot plug/unplug
    self.hal.sd.init( sd_plug, sd_unplug )
    
    # Try to mount the SD card
    # TODO: Why does the oled warning get immediately overwritten by the idle screen?
    # Try to mount
    e = self._try_mount_sd()
    if e > 0:
      self._nosdcr = self.hal.register(
        priority=_HAL_PRIORITY_NOSD,
        features=('oled',),
        callback=lambda:self._render_sd_error( _SD_ERRORS[e] )
      )
      return
    
    # Oled idle stuff
    self._oled_idle = set()
    self._setup_oled_renderers()
    oledcr = self.hal.register( priority=_HAL_PRIORITY_IDLE, features=('oled',), callback=self._oled_idle_render )
    self._oled_idle_task = asyncio.create_task( self._oled_runner(oledcr) )
    
    # Kick off the main stuff
    phases = asyncio.create_task(asyncio.gather(
      self._select_character(),
      self._play_screen(),
      self._phase_controller(),
      self._shutdown_clean(),
    ))
    
    # Now wait until we want to stop
    print('Main loop done, waiting...')
    await self._exit_loop.wait()
    print('Exiting.  Adios!')
  
  # Do we have some filesystem mounted at the SD mountpoint?
  def _sd_is_mounted(self) -> bool:
    ok = False
    for mp in vfs.mount():
      if mp[1] == SD_ROOT:
        ok = True
        break
    return ok
  
  # Check if the SD filesystem is OK
  # 0 = OK
  # Ref _SD_ERRORS for other codes
  def _sd_fs_valid(self) -> int:
    
    # If it's not mounted then we definitely don't have a valid fs
    if not self._sd_is_mounted():
      return 2
    
    # Is the characters directory  where we expect it to be?
    if not ( self.file_root / CHAR_SUBDIR ).is_dir():
      return 3
    
    # Success
    return 0
  
  # Attempt to mount the SD.  Does all checks and returns result.
  # 0 = Success
  # Ref _SD_ERRORS for other codes
  def _try_mount_sd(self) -> int:
    
    # Check if there's an SD, otherwise die
    if not self.hal.sd.has_card():
      return 1
    
    # Mount, if necessary
    if not self._sd_is_mounted():
      vfs.mount( self.hal.sd.card, SD_ROOT )
    
    # Ensure our root directory exists
    #self.file_root.mkdir(parents=True, exist_ok=True)
    
    # Check everything looks ok
    err = self._sd_fs_valid()
    if err > 0:
      return err
    
    print('Mounted SD card on',SD_ROOT)
    return 0
  
  # TODO: Move this to gfx.py?
  def _render_sd_error(self,text):
      
      # Set up oled ref
      o = self.hal.oled
      o.fill(0)
      
      # No SD graphic
      # TODO: Replace with blit_onto()
      fb = img.load('/assets/nosd.pi')
      o.blit(fb,0,0)
      
      # Display message
      lines = text.split('\n')
      h = min( len(lines)*8, 32 )
      y = ( 32 - h ) // 2
      for line in lines:
        o.text( line, 58,y )
        y += 8
      
      o.show()
  
  '''
  async def _sd_plug_waiter(self):
    while True:
      await self.hal.sd_plug.wait()
      
      # Remove any existing SD error message
      if self._nosdcr is not None:
        self.hal.unregister(self._nosdcr)
        self._nosdcr = None
      
      # Try to mount
      e = self._mount_sd()
      if e > 0:
        self._nosdcr = self.hal.register(
          priority=_HAL_PRIORITY_NOSD,
          features=('oled',),
          callback=lambda:self._render_sd_error( _SD_ERRORS[e] )
        )
      
      await self.hal.sd_unplug.wait()
      
      # Tidy up the mountpoint
      if self._sd_is_mounted():
        vfs.umount( SD_ROOT )
      
      # Remove any existing SD error message
      if self._nosdcr is not None:
        self.hal.unregister(self._nosdcr)
      
      # Register the new error
      self._nosdcr = self.hal.register(
        priority=_HAL_PRIORITY_NOSD,
        features=('oled',),
        callback=lambda:self._render_sd_error( _SD_ERRORS[1] )
      )
  '''
  
  # Reacts to the "battery charging" status changing (currently empty)
  async def _battery_charge_waiter(self):
    while True:
      
      await self.hal.batt_charge.wait()
      
      await self.hal.batt_discharge.wait()
  
  # Reacts to "battery low" condition
  async def _battery_low_waiter(self):
    while True:
      
      # Wait for the battery to go low
      await self.hal.batt_low.wait()
      
      # Display a warning on the eink
      if self.character is not None: # Currently only have a way to redraw the play screen
        self.character.draw_eink()
        print('eink redraw triggered by _battery_low_waiter()')
      
      # Wobble the needle
      self.hal.needle.wobble(True)
      
      # Wait for the battery to start charging
      await self.hal.batt_charge.wait()
      
      # Remove the warning on the eink
      if self.character is not None: # Currently only have a way to redraw the play screen
        self.character.draw_eink()
        print('eink redraw triggered by _battery_low_waiter()')
      
      # Stop wobbling the needle
      self.hal.needle.wobble(False)
      
      # Wait for the battery to stop charging before looking again at its level
      await self.hal.batt_discharge.wait()
  
  # Waits for _shutdown event and tidies everything up
  # Sets the _exit_loop event
  async def _shutdown_clean(self):
    await self._shutdown.wait()
    
    self.phase_exit.set()
    
    print('Shutting down...')
    
    # Blank eink
    await self.hal.eink.clear()
    et = asyncio.create_task( self.hal.eink.refresh() )
    
    # Wait message
    cr = self.hal.register( priority=_HAL_PRIORITY_SHUTDOWN, features=('oled',) )
    oled = self.hal.oled
    oled.fill(0)
    oled.text( 'Please wait...', 0,0, 1 )
    oled.show()
    
    # Blank matrix
    # also send empty buffer first
    self.hal.mtx.power(0)
    
    # Unmount SD
    #sd = self.hw.sd1
    #sd.umount()
    
    # Wait for the eink to actually finish
    await et
    
    # Set needle to zero
    self.hal.needle.position(0)
    
    # Display final message
    oled = self.hal.oled
    oled.fill(0)
    oled.text( 'OK to turn off', 8,12, 1 )
    oled.show()
    
    self._exit_loop.set()
  
  # Waits for the hw.py empty_battery event
  # Turns everything off
  # Sets the _exit_loop event
  async def _shutdown_batt(self):
    await self.hal.batt_empty.wait()
    
    self.phase_exit.set()
    
    print('Battery empty!  Shutting down...')
    
    # Eink 'dead battery' graphic
    eink = self.hal.eink
    gfx.draw_dead_batt( eink )
    await eink.send()
    et = asyncio.create_task( eink.refresh() )
    
    # Turn these off
    self.hal.oled.poweroff()
    self.hal.mtx.power(0)
    self.hal.needle.position(0)
    
    # Unmount SD
    #sd = self.hw.sd1
    #sd.umount()
    
    # Wait for the eink to actually finish
    await et
    
    self._exit_loop.set()
  
  async def start_app(self):
    """ Start the app as a coroutine. This coroutine does
        not normally return, as the server enters an endless listening loop.

        This method is a coroutine.

        Example::

            import asyncio
            from wm import WM

            app = WM()

            async def main():
                await app.start_app()

            asyncio.run(main())
      """
    
    #log(f'Starting event loop...','INFO')
    await self.main_sequence()
  
  def run(self):
    """ Start the app. This function does not normally return, as
        the server enters an endless listening loop.

        Example::

            from wm import WM

            app = WM()
            
            app.run()
        """
    asyncio.run( self.start_app() )
