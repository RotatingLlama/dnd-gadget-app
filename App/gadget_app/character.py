# Character-specific data and logic
#
# T. Lloyd
# 29 Mar 2026

# Builtin libraries
import os
from micropython import const
from gc import collect as gc_collect
import json
import errno

from array import array

# Our stuff
from .pathlib import Path # Not a builtin in MicroPython (but mirrors CPython)
from . import menu
from . import _char_menus as _cm
from . import _char_gfx as gfx
from .common import DeferredTask, CHAR_STATS, INTERNAL_SAVEDIR, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE

# Constants
_SIZE_MPY_SMALLINT = const(0x3fffffff) # https://github.com/orgs/micropython/discussions/10315#discussioncomment-4490600
_SIZE_UINT8 = const(0xff)
_SIZE_UINT16 = const(0xffff)

# Config
_SAVE_TIMEOUT = const(30000) # Save contdown, in ms

# Global maximums
_MAX_NAMELEN = const(16) # Most that'll fit on the screen
_MAX_TITLELEN = const(16) # Most that'll fit on the screen
_MAX_XP = const(_SIZE_MPY_SMALLINT) # Kept in memory as a Python integer.  
_MAX_CURRENCY = const(_SIZE_UINT16) # (array H) Highest value for all currency counters
_MAX_HITDICE = const(_SIZE_UINT8) # (bytearray) Max possible number of hit dice
_MAX_HP = const(_SIZE_UINT16) # (array H) Highest value for hit points
_MAX_TEMPHP = const(_SIZE_UINT16) # (array H) Highest value for hit points
_MAX_SPELL_LEVELS = const(9) # 5e SRD
_MAX_SPELLSLOTS = const(6) # (MatrixMenu display limitation) Max number of spell slots at each level
_MAX_CHARGE_ITEMS = const(16) # (MatrixMenu display limitation) When loading from file, load no more than this many of each item
_MAX_CHARGENAME_LEN = const(45) # The most characters that will fit on the eink: 360/8
_MAX_CHARGE_LEVEL = const(_SIZE_MPY_SMALLINT) # (Python integer) The most charges an item can have
_MAX_DEATH_SAVES = const(3) # (5e SRD) How many successes or failures can we have?

# Indexes into the Character.data object
_NAME = const(0)
_TITLE = const(1)
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
_HP_ORIGTEMP = const(3)
#
_HD_CURR = const(0)
_HD_MAX = const(1)
#
_SPELLS_CURR = const(0)
_SPELLS_MAX = const(1)
#
_CHARGES_CURR = const(0)
_CHARGES_MAX = const(1)
_CHARGES_RESET = const(2)
_CHARGES_NAME = const(3)
#
_DEATH_STATUS = const(0)
_DEATH_OK = const(1)
_DEATH_NG = const(2)

# Codes for Character.data objects
_CHARGE_RESET_SR = const(0x01)
_CHARGE_RESET_LR = const(0x02)
_CHARGE_RESET_DAWN = const(0x04)
#
_DEATH_STATUS_OK = const(0)
_DEATH_STATUS_SV = const(1)
_DEATH_STATUS_DD = const(2)
_DEATH_STATUS_TUPLE = ('stable','saves','dead')

class CharacterError( RuntimeError ):
  pass

# Calls os.sync(), but wrapped for compatibility with different Python behaviours
# https://github.com/micropython/micropython/issues/11449
# Return true/false to indicate success
def try_sync() -> bool:
  
  ok = True
  
  # Convert OSError (CPython behaviour) into bool
  try:
    r = os.sync()
  except OSError:
    ok = False
  
  # Integrate the return value, if we have one
  if type(r) is bool:
    ok = ok and r
  
  return ok
"""
# Check a string: correct type and has length
def val_str(s,t):
  if type(s) is not str:
    return 'Bad '+t
  if len(s) == 0:
    return 'Empty '+t

# Check a string: correct type
def val_zstr(s,t):
  if type(s) is not str:
    return 'Bad '+t

# Check an integer: correct type and >= 0
def val_zpint(v,t):
  try:
    v = int(v)
  except ValueError:
    return t+' must be integer'
  if v < 0:
    return t+' must be >= 0'
"""
# Individual params.  HP, Spells and Charges are treated differently.
# load() will check:
# 1. Does the parameter name in the file match an entry here?
# 2. Does its value validate against the function here?
# 3. Pass it through the conversion function here
# 4. Store it here
# 5. Later, load from here into main stats dictionary
# Complex parameters (HP, spells/charges, hit dice) are dealt with separately.
# If default value is None, param is mandatory
# [ value, validation function, conversion function, default value ]
'''
PARAMS = {
  'name'    : [None, lambda s: val_str(s,'name'),      lambda x:x, None],
  'title'   : [None, lambda s: val_zstr(s,'title'),    lambda x:x, ''],
  'xp'      : [None, lambda v: val_zpint(v,'XP'),      int,        0],
  'gold'    : [None, lambda v: val_zpint(v,'Gold'),    int,        0],
  'silver'  : [None, lambda v: val_zpint(v,'Silver'),  int,        0],
  'copper'  : [None, lambda v: val_zpint(v,'Copper'),  int,        0],
  'electrum': [None, lambda v: val_zpint(v,'Electrum'),int,        0],
  'platinum': [None, lambda v: val_zpint(v,'Platinum'),int,        0],
}
'''

# Save helper function
# Converts charge's reset bitarray to a string tuple
def _rst_to_list(bf:int) -> list:
  # Strings appear in savefiles.
  # Order corresponds to _CHARGE_RESET_SR, _CHARGE_RESET_LR etc.
  a = ( 'sr', 'lr', 'dawn' )
  b = []
  i = 0
  while i < len(a):
    if bf & 1:
      b.append( a[i] )
    bf = bf >> 1
    i += 1
  return b

# Given number, returns a byte to send to the matrix to represent that number
# LSB is at left of display
num2mtx = lambda x : 256 - ( 1 << (8-x) )


# hal: The HAL object from hal.py
# sd_mounted: A callable which will return a boolean indicating whether the SD card is ready for read/write
# chardir: Path object to the character directory
# sysmenu_factory: A function that returns a menu.SubMenu object for appending to the oled menu
# enable_eink: bool indicating whether to (ever) refesh the eink display.  Useful to save time during debugging.
class Character:
  def __init__(self, hal, sd_mounted, chardir:Path, sysmenu_factory, enable_eink=True ):
    
    # Where are my files
    if not chardir.is_dir():
      raise CharacterError('Directory does not exist!')
    self.dir:Path = chardir
    
    # Top-level ref
    self.hal = hal
    
    # Ability to check if we have an SD card
    self._sd_mounted = sd_mounted
    
    # Takes a menu parent.  Returns a menu.SubMenu
    self._sysmenu_factory = sysmenu_factory
    
    # Debug purposes
    self._enable_eink = enable_eink
    
    # Stats
    # This will get populated during load() with all the simple PARAMS (above) so they don't need to be defined here
    # But hp/hd/spell/cherge/death structures need to pre-exist
    #self.stats = {}
    
    # Whenever anything updates self.stats, it also calls self.save()
    # self.save() calls self._saver.touch() and sets self._dirty
    # self._dirty indicates whether we have unsaved data
    
    # Save tracking
    self._saver = None # The actual saver will get added later
    self._dirty = False
    
    # UI tracking
    self._active = False # Are we in play?
    self._rootmenu = None
    self._mtx_idle = None # Holder for the CR
    
    self._load()
  
  def _load(self):
    
    # File operations
    try:
      
      # The stats file
      f = self.dir / CHAR_STATS
      
      # Update the RTC based on the file time (if newer)
      uts = self.hal.rtc.uts
      ts = max( f.stat()[7:10] )
      if ts > uts():
        uts( ts )
        print(f'Set RTC based on {self.dir.name}: {ts}')
      
      # Load the file
      with f.open( 'r' ) as fd:
        fs = json.load( fd )
      
    except OSError as e:
      if e.errno == errno.ENOENT:
        raise CharacterError('Savefile does not exist!')
      else:
        raise CharacterError(f'Could not open save file: {errno.errorcode[e.errno]}')
    
    del uts, ts, f, fd
    gc_collect()
    '''
    # Step through the expected simple parameters
    for k in PARAMS:
      
      # Get the parameter object (list)
      p = PARAMS[k]
      
      # Reset the value container - needed?
      p[0] = None
      
      # Try to get the value
      v = fs.get( k, p[3] )
      if v is None:
        raise CharacterError( f'Missing {k}' )
      
      # Validate the value
      e = p[1]( v )
      if e:
        raise CharacterError(e)
      
      # Convert and temporarily store the value
      p[0] = p[2]( v )
    '''
    
    # Name
    try:
      name = str( fs.get('name') )[:_MAX_NAMELEN]
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid name')
    if len(name) == 0:
      raise CharacterError('No name given')
    
    # Title
    try:
      title = str( fs.get('title') )[:_MAX_TITLELEN]
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid title')
    
    # XP
    try:
      xp = int( fs.get('xp',0) )
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid XP')
    if not 0 <= xp <= _MAX_XP:
      raise CharacterError('Invalid XP')
    
    # Get and validate currency
    #gpf = 
    try:
      gp = (
        int( fs.get('copper',0) ),
        int( fs.get('silver',0) ),
        int( fs.get('electrum',0) ),
        int( fs.get('gold',0) ),
        int( fs.get('platinum',0) ),
      )
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid currency')
    if not all([ 0 <= x <= _MAX_CURRENCY for x in gp ]):
      raise CharacterError('Invalid currency value')
    currency = array( 'H', gp )# Unsigned short (2 bytes)
    del gp
    
    # Get and validate hit dice
    hdf = fs.get('hitdice')
    if hdf is None:
      raise CharacterError('Missing hitdice')
    if type(hdf) is not dict:
      raise CharacterError('Invalid hitdice')
    try:
      mx = int( hdf.get('max') )
      cur = int( hdf.get('current',mx) )
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid hitdice')
    if not 0 <= cur <= mx <= _MAX_HITDICE:
      raise CharacterError('Invalid hitdice')
    hd = bytearray(( cur, mx ))
    del hdf
    
    # Get and validate HP
    hpf = fs.get( 'hp' )
    if hpf is None:
      raise CharacterError('Missing hp')
    if type(hpf) is not dict:
      raise CharacterError('Invalid hp')
    try:
      mx = int( hpf.get('max') )
      cur = int( hpf.get('current',mx) )
      temp = int( hpf.get('temporary',0) )
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid hp')
    if not 0 <= cur <= mx <= _MAX_HP:
      raise CharacterError('Invalid hp')
    if not 0 <= temp <= _MAX_HP:
      raise CharacterError('Invalid temporary hp')
    hp = array('H', ( # Unsigned short (2 bytes)
      cur,
      mx,
      temp,
      temp,
    ))
    del hpf
    
    # Get and validate spells
    spf = fs.get( 'spells', [] )
    if type(spf) is not list:
      raise CharacterError('Invalid spell slots list')
    num_spells = min( _MAX_SPELL_LEVELS, len(spf) )
    sp_curr = bytearray(num_spells)
    sp_max = bytearray(num_spells)
    #sp = [None] * min( _MAX_SPELL_LEVELS, len(spf) )
    #for i, s in enumerate( spf[:_MAX_SPELL_LEVELS] ):
    for i in range(num_spells):
      if type(spf[i]) is not dict:
        raise CharacterError( f'Bad spell slot #{i+1}' )
      try:
        mx = int( spf[i].get('max') )
        cur = int( spf[i].get( 'current', mx ) ) # Default to full if not specified
        #sp[i] = [ int( s.get('current',-1) ), int( s.get('max') ) ]
      except ( ValueError, TypeError ) as e:
        raise CharacterError( f'Bad spell slot #{i+1}' )
      if not 0 <= mx <= _MAX_SPELLSLOTS:
        raise CharacterError( f'Bad spell slot #{i+1}' )
      #if sp[i][0] == -1: # Wasn't specified
      #  sp[i][0] = sp[i][1] # Start at full (max)
      #if not ( 0 <= sp[i][0] <= sp[i][1] ):
      if not ( 0 <= cur <= mx ):
        raise CharacterError( f'Bad spell slot #{i+1}' )
      sp_curr[i] = cur
      sp_max[i] = mx
    del spf
    
    # Get and validate charges
    chf = fs.get( 'charges', [] )
    if type(chf) is not list:
      raise CharacterError( 'Invalid charges list' )
    ch = [None] * min( _MAX_CHARGE_ITEMS, len(chf) )
    for i, c in enumerate( chf[:_MAX_CHARGE_ITEMS] ):
      if type(c) is not dict:
        raise CharacterError( f'Bad charge #{i+1}' )
      try:
        nm = str( c.get('name') )[:_MAX_CHARGENAME_LEN]
        mx = int( c.get('max',0) )
        cur = int( c.get('current',mx) )
      except ( ValueError, TypeError ) as e: # Invalid datatype
        raise CharacterError( f'Bad charge format #{i+1}' )
      if not 0 <= mx <= _MAX_CHARGE_LEVEL: # Max level is ok?
        raise CharacterError( f'Bad charge max level #{i+1}' )
      if not 0 <= cur <= _MAX_CHARGE_LEVEL: # Current level is ok?
        raise CharacterError( f'Bad charge current level #{i+1}' )
      if mx and cur > mx: # Current is not more than max (if max is set)?
        raise CharacterError( f'Bad charge #{i+1}' )
      #if ch[i]['curr'] == -1: # Wasn't specified
      #  ch[i]['curr'] = ch[i]['max'] # Start at full (max)
      #if not ( 0 <= ch[i]['curr'] <= ch[i]['max'] ):
      #  raise CharacterError( f'Bad charge #{i+1}' )
      rstf = c.get( 'reset', [] )
      if type(rstf) is not list:
        raise CharacterError( f'Charge #{i+1} has invalid reset' )
      r = {
        'sr' : _CHARGE_RESET_SR,
        'lr' : _CHARGE_RESET_LR,
        'dawn' : _CHARGE_RESET_DAWN,
      }
      rst = sum([ r.get( x, 0 ) for x in rstf ])
      
      #for r in rst:
      #  if r in ( 'lr', 'sr', 'dawn' ):
      #    ch[i]['reset'].append( r )
      ch[i] = [
        cur,
        mx,
        rst,
        nm
      ]
    del chf, r, rstf
    
    # Get and validate death
    df = fs.get( 'death', {} )
    di = { 'stable':_DEATH_STATUS_OK, 'saves':_DEATH_STATUS_SV, 'dead':_DEATH_STATUS_DD }
    if type(df) is not dict:
      raise CharacterError( 'Invalid death section' )
    try:
      d = bytearray([
        di.get( df.get('status','stable'), _DEATH_STATUS_OK ),
        int( df.get('successes',0) ),
        int( df.get('failures',0) ),
      ])
    except ( ValueError, TypeError ) as e:
      raise CharacterError( 'Invalid death section' )
    if not 0<= d[ _DEATH_OK ] <= 3:
      raise CharacterError( 'Invalid number of successful death saves' )
    if not 0<= d[ _DEATH_NG ] <= 3:
      raise CharacterError( 'Invalid number of failed death saves' )
    del df, di
    
    # Assemble
    self.data = [
      name,
      title,
      xp,
      currency,
      hp,
      hd,
      ( sp_curr, sp_max ),
      ch,
      d,
    ]
    '''
    self.stats = { k: PARAMS[k][0] for k in PARAMS }
    self.stats.update({
      'hd' : hd,
      'hp' : hp,
      'spells' : 
      'charges' : ch,
      'death' : d,
    })
    '''
  
  # Constructs the play screen and menus
  def activate(self):
    
    # Sanity
    if self._active:
      raise RuntimeError('Tried to activate an already-active character')
    
    # Set up the saver (continuously runs as an async task)
    self._saver = DeferredTask( timeout=_SAVE_TIMEOUT, callback=self.save_now )
    
    # We are active
    self._active = True
    
    # Go
    self._playscreen()
  
  # Undoes things that were done by activate() and triggers a save, if needed
  def destroy(self):
    
    # Make sure everything is saved
    if self._dirty:
      self.save_now()
    
    # Shut this down cleanly and permit GC
    if self._saver is not None:
      self._saver.destroy()
      self._saver = None
    
    # Tidy up UI elements
    self._cleanup_ui()
    
    # Deactivate
    self._active = False
  
  # Constructs menus for stable playstate
  def _playscreen(self, show=True ):
    
    # Clean up previous playstate
    self._cleanup_ui()
    
    # Localise
    hal = self.hal
    #ds = self.stats['death'][_DEATH_STATUS]
    ds = self.data[_DEATH][_DEATH_STATUS]
    
    # Eink and needle
    if show:
      self.draw_eink()
      self.show_curr_hp()
    
    # Root Menu
    rootmenu = menu.RootMenu( hal, HAL_PRIORITY_MENU )
    
    # Set up matrix menu variables based on death status
    if ds == _DEATH_STATUS_OK:
      mm = _cm.make_matrix_menu_stable( hal, self )
      rootmenu.menus.append(mm)
      mtx_cb = self.draw_mtx_stable
    
    elif ds == _DEATH_STATUS_SV:
      mm = _cm.make_matrix_menu_saves( hal, self )
      rootmenu.menus.append(mm)
      mtx_cb = self.draw_mtx_saves
      
    elif ds == _DEATH_STATUS_DD:
      mtx_cb = self.draw_mtx_dead
    
    # Create default/idle HAL registration
    self._mtx_idle = hal.register(
      priority=HAL_PRIORITY_IDLE,
      features=('mtx',),
      callback=mtx_cb,
      name='MtxIdle'
    )
    
    # Oled menu
    om = _cm.make_oled_menu( hal, self, rootmenu )
    rootmenu.menus.append(om)
    
    # Add the System menu to the end of the Oled menu
    om.items.append( self._sysmenu_factory(om) )
    
    # Link up the inputs to the root menu
    if ds == _DEATH_STATUS_DD:
      rootmenu.init(
        btn = om.next_item
      )
    else:
      rootmenu.init(
        cw  = mm.prev_item,
        ccw = mm.next_item,
        btn = om.next_item
      )
    
    # Assign
    self._rootmenu = rootmenu
    
    # We used a lot of memory setting everything up.  Free now what we can.
    gc_collect()
  
  # Tidies up things that were set by _playscreen()
  def _cleanup_ui(self):
    
    if self._rootmenu is not None:
      self._rootmenu.destroy()
      self._rootmenu = None
    
    if self._mtx_idle is not None:
      self.hal.unregister( self._mtx_idle )
      self._mtx_idle = None
  
  def is_dirty(self):
    return self._dirty
  
  # Blindly overwrites f with the save data
  # Return bool indicating success/failure
  def _save_file(self, f ) -> bool:
    s = self.data
    sf = {
      'name'    : s[_NAME],
      'title'   : s[_TITLE],
      'xp'      : s[_XP],
      'copper'  : s[_CURRENCY][_CURRENCY_COPPER],
      'silver'  : s[_CURRENCY][_CURRENCY_SILVER],
      'electrum': s[_CURRENCY][_CURRENCY_ELECTRUM],
      'gold'    : s[_CURRENCY][_CURRENCY_GOLD],
      'platinum': s[_CURRENCY][_CURRENCY_PLATINUM],
      'hp'      : dict(zip( ( 'current', 'max', 'temporary' ), s[_HP][:3] )),
      'hitdice' : dict(zip( ('current','max'), s[_HD] )),
      'spells'  : [
        dict(zip( ('current','max'), sp )) for sp in 
        zip( s[_SPELLS][_SPELLS_CURR], s[_SPELLS][_SPELLS_MAX] )
      ],
      'charges' : [ {
        'name'    : c[_CHARGES_NAME],
        'current' : c[_CHARGES_CURR],
        'max'     : c[_CHARGES_MAX],
        'reset'   : _rst_to_list( c[_CHARGES_RESET] ),
        } for c in s[_CHARGES] ],
      'death' : {
        'status'    : _DEATH_STATUS_TUPLE[ s[_DEATH][_DEATH_STATUS] ],
        'successes' :s[_DEATH][_DEATH_OK],
        'failures'  :s[_DEATH][_DEATH_NG],
      },
    }
    print(sf)
    
    try:
      with open( f, 'w') as fd:
        # Micropython (1.26) doesn't support the indent argument for pretty printing
        json.dump( sf, fd ) #, separators=(',\n', ': ') )
        
    except OSError:
      return False
    
    return True
  
  # Save now, wherever we can, regardless of whether we need to
  def save_now(self) -> bool:
    
    # If the proper directory is missing, switch to the internal directory
    if not self.dir.is_dir():
      self.dir = Path(INTERNAL_SAVEDIR) / self.dir.name
      self.dir.mkdir(parents=True, exist_ok=True)
      print(f'Moved save location to internal because SD went bad')
    
    # If the SD card comes back, gadget.py will update our .dir property directly
    
    # The file path to save to, as a string
    f = str( self.dir / CHAR_STATS )
    
    # Success/failure tracker
    ok  = True
    
    # Save out the file, temporarily preserving the previous one
    ok = ok and self._save_file( f + '.new' )
    
    # Ensure the new file is saved
    ok = ok and try_sync()
    
    # Replace the old file
    ok = ok and self._save_file( f )
    ok = ok and try_sync()
    
    if not ok:
      return False
    
    self._saver.untouch()
    self._dirty = False
    
    print('Saved.')
    return True
  
  def save(self):
    self._saver.touch()
    self._dirty = True
  
  # DOES NOT VALIDATE hit dice
  def short_rest(self, hit_dice=0, show=True):
    
    # Localise
    st = self.data
    
    # Apply hit dice reduction.
    # Silently clamp overspend
    st[_HD][_HD_CURR] = max( st[_HD][_HD_CURR] - hit_dice, 0 )
    
    # Option to do spell slots here?
    
    # Reset all short-rest charges to max
    for c in st[_CHARGES]:
      
      # Zero-max means no maximum.  Don't reset.
      if c[_CHARGES_MAX] == 0:
        continue
      
      # If it resets on a short rest, reset it
      if c[_CHARGES_RESET] & _CHARGE_RESET_SR:
        c[_CHARGES_CURR] = c[_CHARGES_MAX]
    
    self.save()
    
    self.draw_mtx_stable( show=show )
  
  def long_rest(self, show=True):
    
    # https://www.dndbeyond.com/sources/dnd/phb-2014/adventuring#Resting
    # Regain HP up to max
    # Regain up to half total number of hit dice
    
    # Localise
    st = self.data
    h = st[_HP]
    sps = st[_SPELLS]
    cgs = st[_CHARGES]
    
    # Will we need to update the eink after this?
    e:bool = ( h[_HP_TEMP] != 0 ) # If we had temp hp, they're being reset and we need to update
    
    # Reset HP
    h[_HP_CURR] = h[_HP_MAX] # Reset current to max
    h[_HP_TEMP] = 0          # Reset temp to zero
    h[_HP_ORIGTEMP] = 0      # Reset max temp to zero
    
    # Reset hit dice
    hd_rst:int = max( st[_HD][_HD_MAX] // 2, 1 ) # Half, rounding down.  Minimum of 1
    st[_HD][_HD_CURR] = min( st[_HD][_HD_CURR] + hd_rst, st[_HD][_HD_MAX] )
    del hd_rst
    
    # Reset spell slots
    for s in sps:
      s[_SPELLS_CURR] = s[_SPELLS_MAX]
    
    # Reset all long-rest charges to max
    for c in cgs:
      if c[_CHARGES_MAX] and c[_CHARGES_RESET] & _CHARGE_RESET_LR:
        c[_CHARGES_CURR] = c[_CHARGES_MAX]
    
    self.save()
    
    if e:
      self.draw_eink( show=show )
    
    self.draw_mtx_stable( show=show )
    
    if show:
      self.show_curr_hp()
  
  def dawn_reset(self, show=True):
    
    for c in self.data[_CHARGES]:
      if c[_CHARGES_MAX] and c[_CHARGES_RESET] & _CHARGE_RESET_DAWN:
        c[_CHARGES_CURR] = c[_CHARGES_MAX]
    
    self.save()
    
    self.draw_mtx_stable( show=show )
  
  # Gain HP
  # DOES validate
  def heal( self, amt, show=True ):
    
    # Localise
    hp = self.data[_HP]
    death = self.data[_DEATH]
    
    assert type(amt) is int
    assert amt >= 0
    
    # Allow but silently exit if incrementing by zero
    if amt == 0:
      return
    
    # Can't heal if we're dead
    if death[_DEATH_STATUS] == _DEATH_STATUS_DD or death[_DEATH_NG] >= _MAX_DEATH_SAVES:
      return
    
    # Add the HP, silently capping at HP_MAX
    hp[_HP_CURR] = min( hp[_HP_CURR]+amt, hp[_HP_MAX] )
    
    # If we were in death saves, stabilise
    if death[_DEATH_STATUS] == _DEATH_STATUS_SV:
      self.save()
      self.stabilise(show=show) # stablise() will also call save() if it needs to
      return
    
    self.save()
    
    if hp[_HP_TEMP] > 0:
      self.draw_eink( show=show )
    
    if show:
      self.show_curr_hp()
  
  # Returns ( new_hp, new_temp ).  Just a calculator, doesn't change anything
  # Guarantees that new_temp will be zero or positive, but allows new_hp to be negative
  def damage_calc( self, amt ):
    
    # Get the current levels
    new_hp = self.data[_HP][_HP_CURR]
    new_temp = self.data[_HP][_HP_TEMP]
    
    # First reduce the temp HP
    new_temp -= amt
    
    # If temp hp is negative after this,
    if new_temp < 0:
      new_hp += new_temp # Transfer the excess damage to the normal HP
      new_temp = 0       # Set temp hp to zero
    
    # Results
    return ( new_hp, new_temp )
    
  def damage( self, amt, show=True ):
    
    # Current, max, temp, orig_temp
    hp = self.data[_HP]
    
    assert type(amt) is int
    assert amt >= 0
    
    # If we're in death saves, or dead - don't accept damage.
    # Expect user to apply extra failures manually.
    if self.data[_DEATH][_DEATH_STATUS] != _DEATH_STATUS_OK:
      return
    
    # Affects whether we need to update eink
    tmp_cache = hp[_HP_TEMP]
    
    # Get new HP and Temp HP (note cur might be -ve)
    cur, hp[_HP_TEMP] = self.damage_calc( amt )
    
    # Assign clamped HP value (array uses unsigned ints and can't handle negatives)
    hp[_HP_CURR] = max( cur, 0 )
    
    # If Temp HP is zero, set max temp hp to zero too
    if hp[_HP_TEMP] == 0:
      hp[_HP_ORIGTEMP] = 0
    
    # We've now assigned all necessary HP changes
    self.save()
    
    # Is the overdamage >= max HP?
    if -cur >= hp[_HP_MAX]:
      self.die() # die() will also call save() if it needs to
      return
    
    # Do we need to enter death saves?
    if hp[_HP_CURR] == 0:
      self.deathsaves() # deathsaves() will also call save() if it needs to
      return
    
    # Only way damage can cause eink redraw is by dropping temp hp to zero
    if tmp_cache > 0 and hp[_HP_TEMP] == 0:
      self.draw_eink( show=show )
    
    if show:
      # Update the needle
      self.show_curr_hp()
  
  # Sets the current temporary hit points
  # DOES validate
  def set_temp_hp( self, val, show=True ):
    
    assert type(val) is int
    assert val >= 0
    
    # Localise
    hp = self.data[_HP]
    
    # Prevent accidental fires from triggering e-ink refresh
    if hp[_HP_TEMP] == 0 and val == 0:
      return
    
    # Assign the new value (clamped to max)
    hp[_HP_TEMP] = min( val, _MAX_TEMPHP )
    
    # Are we setting a different level from current?
    if hp[_HP_TEMP] != hp[_HP_ORIGTEMP]:
      hp[_HP_ORIGTEMP] = hp[_HP_TEMP] # Update max temp
      self.draw_eink( show=show ) # Update eink
    
    self.save()
    
    if show:
      self.show_curr_hp()
  
  # Set the death status, reset death saves to zero, save, update playscreen
  def _death_status(self, status:int, show=True ):
    
    # Sanity
    if status not in ( _DEATH_STATUS_OK, _DEATH_STATUS_SV, _DEATH_STATUS_DD ):
      raise ValueError('Invalid status')
    
    # Localise
    d = self.data[_DEATH]
    
    # Are we already in this status?
    if d[_DEATH_STATUS] == status:
      return
    
    # Update the object
    d[_DEATH_STATUS] = status
    d[_DEATH_OK] = 0
    d[_DEATH_NG] = 0
    print('Set status to', _DEATH_STATUS_TUPLE[status] )
    self.save()
    
    # Go
    self._playscreen(show=show)
  #
  # Conveience functions to trigger status change.  All use _death_status()
  def stabilise(self, show=True ):
    self._death_status(_DEATH_STATUS_OK,show=show)
  def deathsaves(self, show=True ):
    self._death_status(_DEATH_STATUS_SV,show=show)
  def die(self, show=True ):
    self._death_status(_DEATH_STATUS_DD,show=show)
  
  # success determines which track to edit
  # val sets the value.  ABSOLUTE, not incremental.
  # DOES validate
  def set_deathsaves(self, success:bool, val:int, show=True ):
    
    # Localise
    d = self.data[_DEATH]
    
    # Sanity
    if d[_DEATH_STATUS] != _DEATH_STATUS_SV:
      raise RuntimeError('Attempted to enter death save result when not in death saves!')
    
    # Validate
    if not 0 <= val <= _MAX_DEATH_SAVES:
      return
    
    if success: # Try to change the number of successes
      
      # Can't change successes if we're already dead
      if d[_DEATH_NG] >= _MAX_DEATH_SAVES:
        return
      
      d[_DEATH_OK] = val
      
    else: # Try to change the number of failures
      
      # Can't change failures if we've already succeeded
      if d[_DEATH_OK] >= _MAX_DEATH_SAVES:
        return
      
      # Are we setting xor unsetting a failure state?
      update_menu = bool( (d[_DEATH_NG]==_MAX_DEATH_SAVES) ^ (val==_MAX_DEATH_SAVES) )
      
      # Update the value
      d[_DEATH_NG] = val
      
      # Do we need to change what's in the oled menu?
      if update_menu:
        # Regenerate the menus without refreshing the eink
        self._playscreen(show=False)
    
    self.save()
    self.draw_mtx_saves(show=show)
  
  # Come back from death
  # full: HP to max?  or to 1
  def undie(self, full:bool ):
    
    # Do nothing if we're not dead
    if self.data[_DEATH][_DEATH_STATUS] != _DEATH_STATUS_DD:
      return
    
    # Restore at full HP?
    if full:
      hp = self.data[_HP][_HP_MAX]
    else:
      hp = 1
    
    # Do it
    self.data[_HP][_HP_CURR] = hp
    self.stabilise()
  
  # Sets the max hit points
  # DOES validate
  # NOT USED ANYWHERE
  '''
  def set_max_hp( self, val, show=True ):
    raise NotImplementedError
    
    assert type(val) is int
    assert val >= 1
    
    # Set the max
    self.data[_HP][_HP_MAX] = val # TODO: Clamp to max value
    
    # Clamp current to new max
    if self.data[_HP][_HP_CURR] > val:
      self.data[_HP][_HP_CURR] = val
    
    self.save()
    
    self.draw_eink( show=show )
    
    if show:
      self.show_curr_hp()
  '''
  
  # Sets the current hit dice
  # DOES validate
  def set_hit_dice( self, val ):
    
    assert type(val) is int
    
    # Is the new number valid?
    if not 0 <= val <= self.data[_HD][_HD_MAX]:
      return
    
    self.data[_HD][_HD_CURR] = val
    
    self.save()
  
  # Set a spell level to a given number of slots
  # DOES validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_spell( self, spl, val, show=True ):
    
    # Get the spell object
    s = self.data[_SPELLS]
    
    # Is the new number valid?
    if not 0 <= val <= s[_SPELLS_MAX][spl]:
      return
    
    s[_SPELLS_CURR][spl] = val
    self.save()
    self.draw_mtx_stable(show=show)
  
  # Set a charge item to a given number of charges
  # DOES validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_charge( self, chg, val, show=True ):
    
    assert type(val) is int
    assert val >= 0
    
    # Get the charge object
    c = self.data[_CHARGES][chg]
    
    # Is there a max level for _this_ charge, and does the new val violate it?
    if c[_CHARGES_MAX] and not 0 <= val <= c[_CHARGES_MAX]:
      return
    
    # Clamp to (max level for _any_ charge)
    c[_CHARGES_CURR] = min( val, _MAX_CHARGE_LEVEL )
    
    self.save()
    self.draw_mtx_stable(show=show)
  
  # Helper function for these numeric-only things
  # Does NOT validate
  '''
  def set_numeric_item(self, k, v ):
    self.data[k] = v
    self.save()
  '''
  
  # Simple convenience function getters
  def get_name(self) -> str:
    return self.data[_NAME]
  def get_title(self) -> str:
    return self.data[_TITLE]
  
  # DOES validate
  def set_xp(self, xp:int ):
    assert type(xp) is int
    assert xp >= 0
    self.data[_XP] = min( xp, _MAX_XP )
    self.save()
  
  # DOES validate
  def set_currency(self, c:int, val:int ):
    assert type(val) is int
    assert val >= 0
    self.data[_CURRENCY][c] = min( val, _MAX_CURRENCY )
    self.save()
  
  # Sets the needle to the current HP
  def show_curr_hp(self):
    self.show_hp( self.data[_HP][_HP_CURR] + self.data[_HP][_HP_TEMP] )
  
  # Gets the max displayable HP value
  def max_displayable_hp(self):
    hp = self.data[_HP]
    return max( hp[_HP_MAX], hp[_HP_CURR] + hp[_HP_ORIGTEMP] )

  # Sets the needle to an arbitrary HP value within range (clamps at min/max)
  def show_hp(self,hp):
    max_range = self.max_displayable_hp()
    arg = min( hp / max_range, 1)
    arg = max( arg, 0 )
    self.hal.needle.position( arg )
  
  # Resets the matrix buffer with current spells, charges
  # Optionally updates display
  def draw_mtx_stable(self, show=True):
    
    data = self.data
    mtx = self.hal.mtx
    
    mtx.clear()
    
    # Go through all charges to update the matrix fb
    for i,c in enumerate(data[_CHARGES]):
      mtx.bitmap[i] = num2mtx( c[_CHARGES_CURR] )
    
    # Go through all spell slots to update the matrix fb
    for i,s in enumerate(data[_SPELLS][_SPELLS_CURR]):
      mtx.bitmap[ 15-i ] = num2mtx(s)
    
    if show:
      mtx.update()
  
  def draw_mtx_saves(self, show=True):
    
    death = self.data[_DEATH]
    mtx = self.hal.mtx
    
    mtx.clear()
    
    # LSB is at left of display
    mtx.bitmap[0] = num2mtx( death[_DEATH_OK] )
    mtx.bitmap[1] = num2mtx( death[_DEATH_NG] )
    
    if show:
      mtx.update()
  
  # Draw a skull on the matrix
  def draw_mtx_dead(self, show=True):
    mtx = self.hal.mtx
    #mtx.clear()
    #mtx.bitmap[:8] = bytes((0x00,0x3e,0x7f,0x49,0x49,0x77,0x3e,0x2a)) # 7x7 skull
    mtx.bitmap[:8] = bytes((0x7e,0xff,0x81,0x99,0xe7,0x7e,0x24,0x24)) # 8x8 skull
    mtx.bitmap[8:] = bytes((0,)*8) # Blank
    if show:
      mtx.update()
  
  def draw_eink(self,show=True):
    lowbatt = self.hal.batt_low.is_set() and self.hal.batt_discharge.is_set()
    gfx.draw_play_screen( fb=self.hal.eink, char=self, lowbatt=lowbatt )
    if show and self._enable_eink:
      self.hal.eink_send_refresh()
    gc_collect()
