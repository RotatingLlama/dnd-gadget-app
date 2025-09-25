# TTRPG Gadget
# For Micropython v1.26
#
# T. Lloyd
# 25 Sep 2025


# TO USE:
#
# from gadget_app import Gadget
# g = Gadget()
#
# Then either start an asyncio loop manually and await g.start_app()
# Or just call g.run()


# Builtin libraries
import asyncio
import gc
import vfs
from micropython import const
import time

# Other libraries
from . import pathlib

# Our stuff
from .common import CHAR_STATS, SD_ROOT, SD_DIR, CHAR_SUBDIR, CHAR_HEAD, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE, HAL_PRIORITY_SHUTDOWN
from . import menu
from .hal import HAL
from .character import Character
from . import gfx

_DEBUG_ENABLE_EINK = const(True)

# Character file info
MANDATORY_CHAR_FILES = [ # Files that must exist in a character directory for it to be recognised
  CHAR_STATS,
]

# In ms.  How often to redraw the OLED idle screen
_OLED_IDLE_REFRESH = const(500)

# Matrix adjust timeout, in ms
_MTX_TIMEOUT = const(3000)

# How long we expect the eink to take to blank out
_EINK_BLANK_MS = const(15700)

# Store this figure for future use
_MEM_TOTAL = gc.mem_alloc() + gc.mem_free()

# Used for memory history graph on idle screen
memlog = bytearray(33) # 32-long ring buffer, plus pointer

class Gadget:
  
  def __init__(self):
    
    # Load modules
    self.hal = HAL()
    
    # Things we want to keep track of
    self.file_root = pathlib.Path( SD_ROOT ) / SD_DIR
    self.character = None
    self._sd_mounted = asyncio.Event()
    
    # Phase triggers
    self.phase_select_char = asyncio.Event()
    self.phase_play = asyncio.Event()
    self.phase_reset = asyncio.Event()
    self.phase_exit = asyncio.Event()
    #
    self._shutdown = asyncio.Event()
    self._exit_loop = asyncio.Event()
    #
    self.play_wait_ani = asyncio.Event()
  
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
      await s(_OLED_IDLE_REFRESH)
  
  # Render all the idle screen stuff
  def _oled_idle_render(self):
    
    # Localisation
    oled = self.hal.oled
    v = oled.vline
    h = oled.hline
    r = oled.rect
    p = oled.pixel
    t = oled.text
    
    oled.fill(0)
    
    
    ### SD PROBLEMS ###
    #
    # If there's an SD problem, override the rest of this screen
    #
    e = self.hal.get_sd_status()
    if e > 0:
      gfx.render_sd_error( e, oled )
      return
    
    
    ### BATTERY MONITOR ###
    
    # Top-left point
    x = 127
    y = 0
    #
    # Draw the battery outline             xxxxxxxxxxxx+
    v( x-1,  y,     6, 1 ) # Right wall    x          x
    v( x,    y+2,   3, 1 ) # Nub           x          xx
    h( x-1,  y,   -12, 1 ) # Top wall      x          xx
    v( x-12, y,     6, 1 ) # Left wall     x          xx
    h( x-1,  y+6, -12, 1 ) # Bottom wall   x          x
    #                                      xxxxxxxxxxxx
    
    pc = self.hal.batt_pc()
    if pc is None:
      # If we didn't get a percentage, we probably have VBUS
      txt = 'USB'
    else:
        
      # How full is the battery?
      bars = ( pc // 10 )
      
      # Draw the bars
      for i in range(bars):
        v( x-11+i, y+1, 5, 1 )
      
      # Percentage text
      txt = f'{pc}%'
    
    t( txt, x - 12 -( 8*len(txt) ), y, 1 )
    t( f'{round(self.hal.hw.voltage_stable(),4)}v', x-47, y+8, 1 )
    
    
    ### EINK BUSY INDICATOR ###
    #
    # Icon to indicate eink busy, direct from Pin
    if self.hal.eink.Busy.value() == 0:
      t( 'e', 120,24, 1 )
    
    
    ### MEMORY USAGE % ###
    #
    ma = gc.mem_alloc
    t( f'M: { ( ma() * 100 ) // _MEM_TOTAL }%', 0,0, 1 )
    
    
    ### MEMORY HISTORY GRAPH ###
    #
    mlen = len(memlog) - 1
    mptr = memlog[mlen] # Pointer is last element of memlog
    
    # Record current mem usage (on a scale of 0-16) at mptr
    memlog[mptr] = ( ma() << 4 ) // _MEM_TOTAL
    
    # Set up the graph
    r( 0,16, 32,16, 0, True ) # Blank out our rectangle
    v( 33,16, 16, 1 ) # axis line
    
    # Start at the beginning
    mptr = ( mptr+1 ) % mlen
    
    # Loop through memlog
    for i in range(mlen):
      p( i, mlen-memlog[mptr], 1 )
      mptr = ( mptr+1 ) % mlen
    
    # Store the updated mptr
    memlog[mlen] = mptr
    
    
    ### SAVE INDICATOR ###
    #
    # Displays whenever a save is pending
    #
    if self.character is not None:
      # Top left corner
      x = 35
      y = 16
      if not self.character.is_saving():
        r(x,y, 12,12, 0, True ) # Blank out the area
      else:
        # Draw a 12x12 floppy disk icon
        v(x,    y+1,   10, 1 ) # Left wall
        h(x+1,  y+11,  10, 1 ) # Bottom
        v(x+11, y+10,  -9, 1 ) # Right wall
        p(x+10, y+1, 1 )       # Corner
        h(x+9,  y,     -9, 1 ) # Top
        r(x+2, y+7, 8,5, 1, False ) # Label
        r(x+3, y,   6,4, 1, False ) # Shield outline
        r(x+4, y+1, 2,2, 1, False ) # Shield fill
    
    
    ### DONE ###
    oled.show()
  
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
      if _DEBUG_ENABLE_EINK:
        self.hal.eink_send_refresh()
      #print(chars)
      
      # This will hold the Character object
      cobj:Character = [0]
      
      # Gets called when a character is chosen
      # Gets given an index into the list from _find_chars()
      def set_char( charid ):
        
        # Ignore character choice if the SD card has gone away
        if not self._sd_mounted.is_set():
          return
        
        # Turn off the wait screen
        self.play_wait_ani.clear()
        
        # Set it up
        cobj[0] = Character( self.hal, chars[ charid ]['dir'] )
        if _DEBUG_ENABLE_EINK:
          cobj[0].draw_eink()
        cobj[0].draw_mtx()
        cobj[0].show_curr_hp()
        
        # Let everything else know
        done.set()
      
      # Set up the character chooser needle
      nm = menu.NeedleMenu(
        hal = self.hal,
        prio = HAL_PRIORITY_MENU,
        n = len(chars),
        btn = set_char,
        back = lambda x: self.hal.needle.wobble() # self.power_off() # self.hal.hw.empty_battery.set()
      )
      
      # Wait until the character is chosen
      await done.wait()
      
      # Make sure this is ready in case of next loop
      done.clear()
      
      # Destroy the NeedleMenu (this unregisters its CR)
      nm.destroy()
      
      # Assign the character
      self.character = cobj[0]
      
      # Trigger Play phase
      self.phase_play.set()
      
      # Tidy up
      del cobj, chars, nm, set_char
      gc.collect()
      
      # Wait for any reset
      await self.phase_reset.wait()
  
  #
  async def _play_screen(self):
    hal = self.hal
    while True:
      await self.phase_play.wait()
      
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
      
      om = menu.OledMenu(
        parent=rm,
        hal=hal,
        prio=HAL_PRIORITY_MENU+1,
        wrap=True
      )
      rm.menus.append(om)
      
      omi = om.items
      
      omi.append(
        menu.DoubleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='Damage',
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
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
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
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='TEMP HP',
          get_cur=lambda: 0, # Always starts at zero because we're always replacing
          set_abs=char.set_temp_hp
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='GOLD',
          get_cur=lambda: char.stats['gold'],
          set_abs=char.set_gold
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='SILVER',
          get_cur=lambda: char.stats['silver'],
          set_abs=char.set_silver
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='COPPER',
          get_cur=lambda: char.stats['copper'],
          set_abs=char.set_copper
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='ELECTRUM',
          get_cur=lambda: char.stats['electrum'],
          set_abs=char.set_electrum
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='XP',
          get_cur=lambda: char.stats['xp'],
          set_abs=char.set_xp
        )
      )
      omi.append(
        menu.FunctionConfirmer( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='LONG REST',
          confirmation='Take long rest',
          con_func=char.long_rest
        )
      )
      omi.append(
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='SHORT REST',
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
        menu.SimpleAdjuster( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
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
      omi.append(
        menu.FunctionConfirmer( om, self.hal,
          prio=HAL_PRIORITY_MENU+2,
          title='POWER OFF',
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
      
      # Assign
      self.menu = rm
      
      # Tidy up
      del rm, mm, om, omi # , char
      gc.collect()
      
      # Wait for a reset
      await self.phase_reset.wait()
      
      # Tidy up
      del self.menu # RootMenu's __del__() method handles the HAL deregistration... maybe
      hal.unregister( mtx_idle )
      gc.collect()
      
  
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
    earlytasks = asyncio.create_task(asyncio.gather(
      self._shutdown_batt(),
      #self._battery_charge_waiter(),
      self._battery_low_waiter(),
      self.wait_ani(),
    ))
    
    # Loading screen
    self.play_wait_ani.set()
    
    # Oled idle stuff
    oledcr = self.hal.register(
      priority=HAL_PRIORITY_IDLE,
      features=('oled',),
      callback=self._oled_idle_render,
      name='OledIdle'
    )
    oled_idle = asyncio.create_task( self._oled_runner(oledcr) )
    
    # Set up the SD manager and wait for the card to be ready
    sd = asyncio.create_task( self._wait_mount_sd() )
    await self._sd_mounted.wait()
    
    # Kick off the main stuff
    phases = asyncio.create_task(asyncio.gather(
      self._select_character(),
      self._play_screen(),
      self._phase_controller(),
      self._shutdown_clean(),
    ))
    
    # Now wait until we want to stop
    print('Startup complete.')
    await self._exit_loop.wait()
    print('Exiting.  Adios!')
  
  # Handles mounting/unmounting the SD card in response to un/plug events from the driver.
  # Sets/clears the _sd_mounted event.
  async def _wait_mount_sd(self):
    while True:
      
      # Do we need to wait for the SD card?
      if self.hal.get_sd_status() > 0: # yes
        await self.hal.sd.card_ready.wait() # Wait for it to be fixed
      
      # SD card should now be ready
      
      # Try to mount the SD card
      if self._try_mount_sd() == 0:
        self._sd_mounted.set()
      
      # Wait for the card to be unplugged
      await self.hal.sd.card_absent.wait()
      
      # Tidy up the mountpoint
      if self._sd_is_mounted():
        vfs.umount( SD_ROOT )
      
      # Clear this flag
      self._sd_mounted.clear()
  
  # Attempt to mount the SD.  Does all checks and returns result.
  # 0 = Success
  # Ref _SD_ERRORS (in gfx.py) for other codes
  def _try_mount_sd(self) -> int:
    
    # Check if there's an SD, otherwise die
    e = self.hal.get_sd_status()
    if e > 0:
      return e
    
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
  
  # Check if the SD filesystem is OK
  # 0 = OK
  # Ref _SD_ERRORS (in gfx.py) for other codes
  def _sd_fs_valid(self) -> int:
    
    # If it's not mounted then we definitely don't have a valid fs
    if not self._sd_is_mounted():
      return 2
    
    # Is the characters directory  where we expect it to be?
    if not ( self.file_root / CHAR_SUBDIR ).is_dir():
      return 3
    
    # Success
    return 0
  
  # Do we have some filesystem mounted at the SD mountpoint?
  def _sd_is_mounted(self) -> bool:
    ok = False
    for mp in vfs.mount():
      if mp[1] == SD_ROOT:
        ok = True
        break
    return ok
  
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
  
  # Moves the needle while clearing the e-ink
  async def _clear_eink_needle(self):
    start = time.ticks_ms()
    self.hal.eink_clear_refresh()
    pos = self.hal.needle.position
    not_busy = self.hal.eink.unbusy.is_set
    t = 0
    while t < 3000 or not not_busy(): # While eink is busy (flag may flicker between send and refresh)
      t = time.ticks_diff( time.ticks_ms(), start ) # Time elapsed
      pos( min( 1, t / _EINK_BLANK_MS ) ) # Set the needle
      await asyncio.sleep_ms(30)
    pos(0) # Needle to zero
    
  # Waits for _shutdown event and tidies everything up
  # Sets the _exit_loop event
  async def _shutdown_clean(self):
    await self._shutdown.wait()
    
    self.phase_exit.set()
    
    print('Shutting down...')
    
    # Blank eink
    #t1 = time.ticks_ms()
    et = asyncio.create_task( self._clear_eink_needle() )
    m = asyncio.create_task( self.ani( ani_squares, 100 ) )
    
    # Wait message
    cr = self.hal.register(
      priority=HAL_PRIORITY_SHUTDOWN,
      features=('oled',),
      name='Shutdown'
    )
    oled = self.hal.oled
    oled.fill(0)
    oled.text( 'Please wait...', 0,0, 1 )
    oled.show()
    
    # Unmount SD
    if self._sd_is_mounted():
      vfs.umount( SD_ROOT )
    
    # Wait for the eink to actually finish
    await et
    #print( time.ticks_diff( time.ticks_ms(), t1 ))
    
    # Turn out the lights
    self.hal.oled.poweroff()
    self.hal.mtx.power(0)
    
    # Stop
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
    if self._sd_is_mounted():
      vfs.umount( SD_ROOT )
    
    # Wait for the eink to actually finish
    await et
    
    # Stop
    self._exit_loop.set()
  
  async def wait_ani(self):
    buf = self.hal.mtx.bitmap
    send = self.hal.mtx.matrix.show
    wait = asyncio.sleep_ms
    #top = bytes([ 0x3e, 0x7c, 0xc1, 0x83 ])
    #btm = bytes([ 0x9f, 0x3f, 0x40, 0x80 ])
    top = bytes([ 0x83, 0xc1, 0x7c, 0x3e ])
    btm = bytes([ 0x80, 0x40, 0x3f, 0x9f ])
    while True:
      f = 0
      while f < 4: # 4 frames
        await wait(80)
        await self.play_wait_ani.wait()
        i=0
        while i < 4: # 4 lines per frame
          t = top[ (f+i)%4 ]
          b = btm[ (f+i)%4 ]
          buf[i] = t
          buf[i+4] = t
          buf[i+8] = b
          buf[i+12] = b
          i += 1
        send()
        f += 1
          
  # Full bitmap animation on the matrix
  # a = bytes of length 16.f, where f is the number of frames
  # p = int ms to wait in between frames
  async def ani(self, a:bytes, p:int=40):
    buf = self.hal.mtx.bitmap
    send = self.hal.mtx.matrix.show
    wait = asyncio.sleep_ms
    f:int = len(a)
    i:int
    j:int
    while True:
      i = 0
      while i < f:
        j = 0
        while j < 16:
          buf[j] = a[ i+j ]
          j += 1
        send()
        await wait(p)
        i += 16
    
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

# Matrix animation data
ani_squares = bytes([
  0xff, 0x81, 0x81, 0x99, 0x99, 0x81, 0x81, 0xff, 0xff, 0x81, 0x81, 0x99, 0x99, 0x81, 0x81, 0xff,
  0xff, 0xff, 0xc3, 0xc3, 0xc3, 0xc3, 0xff, 0xff, 0x00, 0x00, 0x3c, 0x3c, 0x3c, 0x3c, 0x00, 0x00,
  0x00, 0x7e, 0x7e, 0x66, 0x66, 0x7e, 0x7e, 0x00, 0x00, 0x7e, 0x7e, 0x66, 0x66, 0x7e, 0x7e, 0x00,
  0x00, 0x00, 0x3c, 0x3c, 0x3c, 0x3c, 0x00, 0x00, 0xff, 0xff, 0xc3, 0xc3, 0xc3, 0xc3, 0xff, 0xff,
])
ani_diag = bytes([
  128,  64,  32,  16,   8,   4,   2,   1,    128,  64,  32,  16,   8,   4,   2,   1,
   64,  32,  16,   8,   4,   2,   1, 128,     64,  32,  16,   8,   4,   2,   1, 128,
   32,  16,   8,   4,   2,   1, 128,  64,     32,  16,   8,   4,   2,   1, 128,  64,
   16,   8,   4,   2,   1, 128,  64,  32,     16,   8,   4,   2,   1, 128,  64,  32,
    8,   4,   2,   1, 128,  64,  32,  16,      8,   4,   2,   1, 128,  64,  32,  16,
    4,   2,   1, 128,  64,  32,  16,   8,      4,   2,   1, 128,  64,  32,  16,   8,
    2,   1, 128,  64,  32,  16,   8,   4,      2,   1, 128,  64,  32,  16,   8,   4,
    1, 128,  64,  32,  16,   8,   4,   2,      1, 128,  64,  32,  16,   8,   4,   2,
])
