# TTRPG Gadget
# For Micropython v1.26
#
# T. Lloyd
# 24 Nov 2025


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
import micropython
import time

# Other libraries
from .pathlib import Path

# Our stuff
from .common import CHAR_STATS, SD_ROOT, SD_DIR, CHAR_SUBDIR, CHAR_HEAD, INTERNAL_SAVEDIR, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE, HAL_PRIORITY_SHUTDOWN
from . import menu
from .hal import HAL
from .character import Character, CharacterError
from . import gfx

_DEBUG_DISABLE_EINK = const(False)

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

# How long to ignore SD errors for, after initial startup
_STARTUP_TIMEOUT_MS = const(300)

# Store this figure for future use
_MEM_TOTAL = gc.mem_alloc() + gc.mem_free()

# Used for memory history graph on idle screen
memlog = bytearray(33) # 32-long ring buffer, plus pointer

# Make this object here because it's used in a few places
INTERNAL_SAVEDIR = Path(INTERNAL_SAVEDIR)

class Gadget:
  
  def __init__(self, x=None ):
    
    self.boot_arg = x
    
    # Load modules
    self.hal = HAL()
    
    # Things we want to keep track of
    self.file_root = Path( SD_ROOT ) / SD_DIR
    self.menu = None
    self.character = None
    self.sd_ok = asyncio.Event()
    self.sd_gone = asyncio.Event()
    self._sd_mount_attempted = asyncio.Event() # Fires after attempting to mount a present SD, regardless of success
    self._sd_err = 1 # Start off with 'card not present' until we determine otherwise (gfx.py: _SD_ERRORS)
    self._show_splash = True
    
    # Event triggers
    self._shutdown = asyncio.ThreadSafeFlag()
    self._exit_loop = asyncio.Event()
    #
    self.play_wait_ani = asyncio.Event()
    
    # Cleans up whatever we're currently doing, ready to do the next thing
    self.cleanup = lambda : None
    
    # Functions to call when the SD is un/plugged
    self.sd_plug = lambda : None
    self.sd_unplug = lambda : None
    
    # Make sure this exists
    INTERNAL_SAVEDIR.mkdir(parents=True, exist_ok=True)
  
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
    
    # Draw a startup logo (hides spurious sd errors)
    if self._show_splash:
      
      # Randomise which version of the logo we get
      if time.ticks_cpu() & 1:
        # Shaded version
        gfx.render_boot_logo(oled)
        return
      
      # Lineart version
      h( 8,5, 65, 1 )
      v( 72,5, 11, 1 )
      h( 72,16, 48, 1 )
      v( 119,16, 11, 1 )
      h( 119,26, -65, 1 )
      v( 55,26, -11, 1 )
      h( 55,15, -48, 1 )
      v( 8,15, -11, 1 )
      oled.show()
      return
    
    ### SD PROBLEMS ###
    #
    # If there's an SD problem, override the rest of this screen
    #
    # Hardware errors get priority
    e = self.hal.get_sd_status()
    if e > 0:
      gfx.render_sd_error( e, oled )
      return
    # If the card's fine but there's something else wrong
    if self._sd_err > 0:
      gfx.render_sd_error( self._sd_err, oled )
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
    
    
    ### BOOT ARG ###
    #t( str(self.boot_arg) ,40,16,1)
    
    
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
      if self.character.is_dirty():
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
  
  # Triggers a clean shutdown
  def power_off(self):
    print('Called power_off()')
    self._shutdown.set()
  
  # Looks at the directory and generates a list of available Character objects
  def _find_chars(self):
    
    # Directory of character directories
    cd = self.file_root / CHAR_SUBDIR
    
    # If the character dir doesn't exist, use the internal savedir instead
    if not cd.is_dir():
      cd = INTERNAL_SAVEDIR
    
    print( f'Looking for character directories in {str(cd)} ...' )
    # No iterdir() in pathlib.py from [https://github.com/micropython/micropython-lib/blob/master/python-stdlib/pathlib/pathlib.py]
    dirs = sorted( cd.glob('*'), key=lambda p: str(p) )
      
    del cd
    
    chars = []
    #for x in self.file_root.iterdir():
    for x in dirs:
      
      # Have we found a directory?
      if not x.is_dir():
        continue
      
      # Is everything present that should be?
      ok = True
      for f in MANDATORY_CHAR_FILES:
        if not ( x / f ).is_file():
          print( f'{f} is not present in /{x.name}/' )
          ok = False
      if not ok:
        continue
      
      # Try to load the directory as a Character object
      # Each one takes approx 1 to 1.5kB memory
      try:
        c = Character(
          hal = self.hal,
          sd_mounted = self.sd_ok.is_set,
          chardir = x
        )
      except CharacterError as e:
        print( f'Failed to load from /{x.name}/: {str(e)}' )
        continue
      
      # If we're here, we're good
      print(f'Found: {c.stats['name']} ({c.stats['title']}) in /{x.name}/')
      chars.append( c )
      
    return chars
  
  # Sets up the selector
  def _select_character(self):
    
    # Loading screen
    self.play_wait_ani.set()
    
    # Takes a framebuffer and a list of chars to show
    # Returns as many chars as it actually did show
    chars = gfx.draw_char_select( self.hal.eink, self._find_chars() )
    
    if not _DEBUG_DISABLE_EINK:
      self.hal.eink_send_refresh()
    #print(chars)
    
    # If we have *no* characters, don't try to index into an empty list
    if len(chars) > 0:
      btn = lambda i: self._set_char( chars[i] )
    else:
      btn = lambda i: None
    
    # Set up the character chooser needle
    self.menu = menu.NeedleMenu(
      hal = self.hal,
      prio = HAL_PRIORITY_MENU,
      n = len(chars),
      btn = btn,
      back = lambda x: self.power_off() # lambda x: self.hal.needle.wobble() # self.hal.hw.empty_battery.set()
    )
    
    # If the SD card is unplugged, wiggle the needle to indicate
    # self._set_char() will exit silently if it's triggered with no SD card in place
    def unplug():
      self.hal.needle.wobble(True)
    
    # If the SD card is replugged
    # Clean up this character picker instance and then start a new one
    # (because the newly-plugged card may well have different char data)
    def plug():
      self.hal.needle.wobble(False)
      self.cleanup()
      self._select_character()
    
    # Function to clean up this character picker instance
    def end():
      self.menu.destroy()
      self.play_wait_ani.clear()
      self.cleanup = lambda : None
      self.sd_plug = lambda : None
      self.sd_unplug = lambda : None
    
    # Set these hooks
    self.cleanup = end
    self.sd_plug = plug
    self.sd_unplug = unplug
  
  # Gets called when a character is chosen
  # Gets given the selected character object
  def _set_char(self, char ):
    
    # Ignore call if the SD card has gone away
    if not self.sd_ok.is_set():
      return
    
    # Clean up the char select screen
    self.cleanup()
    
    # Set it up
    self.character = char
    print( char.stats )
    gc.collect()
    
    if not _DEBUG_DISABLE_EINK:
      char.draw_eink()
    char.draw_mtx()
    char.show_curr_hp()
    
    self._playscreen()
  
  # Sets up the playscreen (inc. all its menus)
  def _playscreen(self):
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
        title='HIT DICE',
        get_cur=lambda: char.stats['hd'][0],
        set_abs=char.set_hit_dice,
        min=0,
        max=char.stats['hd'][1],
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
    
    #def plug():
    #  pass
    #
    #def unplug():
    #  pass
    
    # Tidies up things that were set by _playscreen() and triggers a save, if needed
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
    self.menu = rm
    self.cleanup = end
    #self.sd_plug = plug
    #self.sd_unplug = unplug
  
  # Start everything, keep refs to looping tasks
  async def start_app(self):
    
    # Indicate progress, through the medium of shading
    self.show_shade(2,0)
    
    # async tasks
    tasks = asyncio.create_task(asyncio.gather(
      self._shutdown_batt(),
      self._shutdown_clean(),
      self._battery_low_waiter(),
      self._sd_controller(),
      self.wait_ani(),
    ))
    
    # Oled idle stuff
    oledcr = self.hal.register(
      priority=HAL_PRIORITY_IDLE,
      features=('oled',),
      callback=self._oled_idle_render,
      name='OledIdle'
    )
    oled_idle = asyncio.create_task( self._oled_runner(oledcr) )
    
    # Gets called once the SD card is a known state (good or bad)
    # If good, load characters as normal
    # If bad, load whatever character may be in internal storage
    # Will lead to blank selector if nothing there
    # Character select screen reloads when a valid card with valid character files appears
    def finish_startup():
      self.show_shade(2,1)
      self._show_splash = False
      print('Startup complete.')
      self._select_character()
    
    # Wait until the card is either ready, or definitely not ready
    await self.hal.sd.card_state_known.wait()
    if not self.hal.sd.card_ready.is_set():
      finish_startup()
    else: # Card is present and we're still processing
      
      # Wait for the mount to either pass/fail
      await self._sd_mount_attempted.wait()
      finish_startup()
    
    await self._exit_loop.wait()
    print('Exiting.  Adios!')
  
  # Handles mounting/unmounting the SD card in response to un/plug events from the driver.
  # Sets/clears the sd_ok and sd_gone events.
  async def _sd_controller(self):
    while True:
      
      # Do we need to wait for the SD card?
      if self.hal.get_sd_status() > 0: # yes
        await self.hal.sd.card_ready.wait() # Wait for it to be fixed
      
      # SD card should now be ready
      
      # Try to mount the SD card
      self._sd_err = self._try_mount_sd()
      if self._sd_err == 0:
        self.sd_gone.clear()
        self.sd_ok.set()
        self.sd_plug()
      
      # Set this to flag the attempt (regardless of pass/fail)
      self._sd_mount_attempted.set()
      
      # Wait for the card to be unplugged
      await self.hal.sd.card_absent.wait()
      
      # Tidy up the mountpoint
      if self._sd_is_mounted():
        vfs.umount( SD_ROOT )
      
      # Flags, hooks
      self._sd_mount_attempted.clear()
      self.sd_ok.clear()
      self.sd_gone.set()
      self.sd_unplug()
  
  # Attempt to mount the SD.  Does all checks and returns result.
  # Attempts to move internal saves out to SD, if applicable
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
    
    # Try to move any internal saves out to the SD
    try:
      self._move_intern_to_sd()
    except ( RuntimeError, OSError ) as e:
      # If we failed to move, there's probably something wrong with the card
      return 3 # Could not mount SD
    
    # Check everything looks ok
    err = self._sd_fs_valid()
    if err > 0:
      return err
    
    print('Mounted SD card on',SD_ROOT)
    return 0
  
  # Move all internal save data onto the SD card (assumes valid, mounted SD card)
  def _move_intern_to_sd(self):
    
    # Target directory on the SD
    char_dir = self.file_root / CHAR_SUBDIR
    
    # Sanity
    if not char_dir.is_dir():
      raise RuntimeError('Character directory on SD card does not exist!')
    
    # Should be either zero or one of these source directories
    # No iterdir() in pathlib.py from [https://github.com/micropython/micropython-lib/blob/master/python-stdlib/pathlib/pathlib.py]
    for src_d in INTERNAL_SAVEDIR.glob('*'):
      
      # Find a directory on the SD that doesn't already exist
      i = 1
      dest_d = src_d.name
      while ( char_dir / dest_d ).exists():
        dest_d = f'{src_d.name}_{i}'
        i += 1
      dest_d = ( char_dir / dest_d )
      dest_d.mkdir()
      
      # Move all files from internal dir to new sd dir
      print(f'Moving internal directory {src_d.name}/ to SD as {dest_d.name}/')
      src_files = src_d.glob('*')
      for src_f in src_files:
        
        # Check that the source file really is a file
        if not src_f.is_file():
          continue
        
        # Copy the file
        dest_f = ( dest_d / src_f.name )
        with src_f.open('rb') as fd:
          buf = fd.read()
        with dest_f.open('wb') as fd:
          fd.write(buf)
        del buf
        
        # Check that they're the same size
        if src_f.stat()[6] != dest_f.stat()[6]:
          raise RuntimeError('Could not copy file from internal memory to SD')
        
        # Delete the source file (this is a move, not a copy)
        src_f.unlink()
        
        print(f'Moved file {src_f.name}')
      
      # If we have a current character, 
      if self.character is not None:
        
        # and we've just moved its directory
        if self.character.dir == src_d:
          
          # Update its directory
          self.character.dir = dest_d
          
          # Force it to save out
          self.character.save_now()
          
          # Character.save_now() will change the directory back if it hits problems
          if self.character.dir != dest_d:
            raise RuntimeError('Error moving current character out to SD card!')
          
          print(f'Moved current save location from internal to SD')
      
      # Delete internal dir
      src_d.rmdir()
  
  # Check if the SD filesystem is OK
  # 0 = OK
  # Ref _SD_ERRORS (in gfx.py) for other codes
  def _sd_fs_valid(self) -> int:
    
    # If it's not mounted then we definitely don't have a valid fs
    if not self._sd_is_mounted():
      return 3
    
    # Is the characters directory  where we expect it to be?
    if not ( self.file_root / CHAR_SUBDIR ).is_dir():
      return 4
    
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
    pos = self.hal.needle.position
    if not _DEBUG_DISABLE_EINK:
      start = time.ticks_ms()
      self.hal.eink_clear_refresh()
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
    print('Someone triggered _shutdown Event')
    
    self.cleanup()
    
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
    
    self.cleanup()
    
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
  
  # Display a monotone shading to the matrix
  # s     The shade to use.  Accepts 0 thru 4
  # flip  Variant of the selected shade.  Accepts 0 or 1
  @micropython.viper
  def show_shade(self, s:int, flip:int ):
    shades = ptr8(bytearray([ 0x00, 0x00, 0x44, 0x11, 0xaa, 0x55, 0xbb, 0xee, 0xff, 0xff ]))
    i:int = s * 2
    if flip == 0:
      a:int = shades[ i ]
      b:int = shades[ i + 1 ]
    else:
      a:int = shades[ i + 1 ]
      b:int = shades[ i ]
    i = 0
    buf = ptr8(self.hal.mtx.bitmap)
    while i < 16:
      buf[i] = a
      i += 1
      buf[i] = b
      i += 1
    self.hal.mtx.matrix.show()
  
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
  
  def run(self):
    """ Start the app. This function function returns only after the app shuts down.

        Example::

            from gadget_app import Gadget
            
            g = Gadget()
            
            g.run()
            
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
