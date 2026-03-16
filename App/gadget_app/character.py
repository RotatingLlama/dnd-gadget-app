# Character-specific data and logic
#
# T. Lloyd
# 16 Mar 2026

# Builtin libraries
import os
from micropython import const
from gc import collect as gc_collect
import json
import errno

# Our stuff
from .pathlib import Path # Not a builtin in MicroPython (but mirrors CPython)
from . import menu
from . import _ui
from . import gfx
from .common import DeferredTask, CHAR_STATS, INTERNAL_SAVEDIR, HAL_PRIORITY_MENU, HAL_PRIORITY_IDLE

# When loading from file, load no more than this many of each item
_MAX_SPELLS = const(9)
_MAX_CHARGES = const(16)
_CHG_NAME_MAXLEN = const(45) # 360/8

_SAVE_TIMEOUT = const(30000) # Save contdown, in ms

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
    self.stats = {
      'hp' : [0,0,0,0], # Current, max, temp, orig_temp
      'hd' : [0,0], # Current, max
      'spells' : [],
      'charges' : [],
      'death' : {},
    }
    
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
    
    # Get and validate hit dice
    hdf = fs.get('hitdice')
    if hdf is None:
      raise CharacterError('Missing hitdice')
    if type(hdf) is not dict:
      raise CharacterError('Invalid hitdice')
    try:
      hd = [
        int( hdf.get('current') ),
        int( hdf.get('max') ),
      ]
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid hitdice')
    if hd[1] <= 0:
      raise CharacterError('Invalid max hitdice')
    if not ( 0 <= hd[0] <= hd[1] ):
      raise CharacterError('Invalid hitdice')
    
    # Get and validate HP
    hpf = fs.get( 'hp' )
    if hpf is None:
      raise CharacterError('Missing hp')
    if type(hpf) is not dict:
      raise CharacterError('Invalid hp')
    try:
      hp = [
        int( hpf.get('current') ),
        int( hpf.get('max') ),
        int( hpf.get('temporary') ),
        int( hpf.get('temporary') ),
      ]
    except ( ValueError, TypeError ) as e:
      raise CharacterError('Invalid hp')
    if hp[1] <= 0:
      raise CharacterError('Invalid max hp')
    if not ( 0 <= hp[0] <= hp[1] ):
      raise CharacterError('Invalid current hp')
    if hp[2] < 0:
      raise CharacterError('Invalid temporary hp')
    
    # Get and validate spells
    spf = fs.get( 'spells', [] )
    if type(spf) is not list:
      raise CharacterError('Invalid spell slots list')
    sp = [None] * min( _MAX_SPELLS, len(spf) )
    for i, s in enumerate( spf[:_MAX_SPELLS] ):
      if type(s) is not dict:
        raise CharacterError( f'Bad spell slot #{i+1}' )
      try:
        sp[i] = [ int( s.get('current',-1) ), int( s.get('max') ) ]
      except ( ValueError, TypeError ) as e:
        raise CharacterError( f'Bad spell slot #{i+1}' )
      if sp[i][1] <= 0: # max
        raise CharacterError( f'Bad spell slot #{i+1}' )
      if sp[i][0] == -1: # Wasn't specified
        sp[i][0] = sp[i][1] # Start at full (max)
      if not ( 0 <= sp[i][0] <= sp[i][1] ):
        raise CharacterError( f'Bad spell slot #{i+1}' )
    
    # Get and validate charges
    chf = fs.get( 'charges', [] )
    if type(chf) is not list:
      raise CharacterError( 'Invalid charges list' )
    ch = [None] * min( _MAX_CHARGES, len(chf) )
    for i, c in enumerate( chf[:_MAX_CHARGES] ):
      if type(c) is not dict:
        raise CharacterError( f'Bad charge #{i+1}' )
      try:
        ch[i] = {
          'name' : str( c.get('name') )[:_CHG_NAME_MAXLEN],
          'curr' : int( c.get('current',-1) ),
          'max'  : int( c.get('max') ),
          'reset' : [],
        }
      except ( ValueError, TypeError ) as e:
        raise CharacterError( f'Bad charge #{i+1}' )
      if ch[i]['max'] <= 0:
        raise CharacterError( f'Bad charge #{i+1}' )
      if ch[i]['curr'] == -1: # Wasn't specified
        ch[i]['curr'] = ch[i]['max'] # Start at full (max)
      if not ( 0 <= ch[i]['curr'] <= ch[i]['max'] ):
        raise CharacterError( f'Bad charge #{i+1}' )
      rst = c.get( 'reset', [] )
      if type(rst) is not list:
        raise CharacterError( f'Charge #{i+1} has invalid reset' )
      for r in rst:
        if r in ( 'lr', 'sr', 'dawn' ):
          ch[i]['reset'].append( r )
    
    # Get and validate death
    df = fs.get( 'death', {} )
    if type(df) is not dict:
      raise CharacterError( 'Invalid death section' )
    try:
      d = {
        'status' : str( df.get('status','stable') ),
        'successes' : int( df.get('successes',0) ),
        'failures' : int( df.get('failures',0) ),
      }
    except ( ValueError, TypeError ) as e:
      raise CharacterError( 'Invalid death section' )
    if d['status'] not in ('stable','saves','dead'):
      raise CharacterError( 'Invalid death status' )
    if not 0<= d['successes'] <= 3:
      raise CharacterError( 'Invalid number of successful death saves' )
    if not 0<= d['failures'] <= 3:
      raise CharacterError( 'Invalid number of failed death saves' )
    
    # Assemble
    self.stats = { k: PARAMS[k][0] for k in PARAMS }
    self.stats.update({
      'hd' : hd,
      'hp' : hp,
      'spells' : sp,
      'charges' : ch,
      'death' : d,
    })
  
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
    ds = self.stats['death']['status']
    
    # Eink and needle
    if show:
      self.draw_eink()
      self.show_curr_hp()
    
    # Root Menu
    rootmenu = menu.RootMenu( hal, HAL_PRIORITY_MENU )
    
    # Set up matrix menu variables based on death status
    if ds == 'stable':
      mm = _ui.make_matrix_menu_stable( hal, self )
      rootmenu.menus.append(mm)
      mtx_cb = self.draw_mtx_stable
    
    elif ds == 'saves':
      mm = _ui.make_matrix_menu_saves( hal, self )
      rootmenu.menus.append(mm)
      mtx_cb = self.draw_mtx_saves
      
    elif ds == 'dead':
      mtx_cb = self.draw_mtx_dead
    
    # Create default/idle HAL registration
    self._mtx_idle = hal.register(
      priority=HAL_PRIORITY_IDLE,
      features=('mtx',),
      callback=mtx_cb,
      name='MtxIdle'
    )
    
    # Oled menu
    om = _ui.make_oled_menu( hal, self, rootmenu )
    rootmenu.menus.append(om)
    
    # Add the System menu to the end of the Oled menu
    om.items.append( self._sysmenu_factory(om) )
    
    # Link up the inputs to the root menu
    if ds == 'dead':
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
    s = self.stats
    sf = { k: s[k] for k in PARAMS }
    sf.update({
      'hitdice' : dict(zip( ['current','max'], s['hd'] )),
      'hp'      : dict(zip( [ 'current', 'max', 'temporary' ], s['hp'][:3] )),
      'spells'  : [ dict(zip(['current','max'],[ sp[0], sp[1] ])) for sp in s['spells'] ],
      'charges' : [ {
        'name'    : c['name'],
        'current' : c['curr'],
        'max'     : c['max'],
        'reset'   : c['reset']
        } for c in s['charges'] ],
      'death' : s['death'],
    })
    
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
    st = self.stats
    
    # Apply hit dice reduction.
    # Silently clamp overspend
    st['hd'][0] = max( st['hd'][0] - hit_dice, 0 )
    
    # Option to do spell slots here?
    
    # Reset all short-rest charges to max
    for c in st['charges']:
      if 'sr' in c['reset']:
        c['curr'] = c['max']
    
    self.save()
    
    self.draw_mtx_stable( show=show )
  
  def long_rest(self, show=True):
    
    # https://www.dndbeyond.com/sources/dnd/phb-2014/adventuring#Resting
    # Regain HP up to max
    # Regain up to half total number of hit dice
    
    # Localise
    st = self.stats
    h = st['hp']
    sps = st['spells']
    cgs = st['charges']
    
    # Will we need to update the eink after this?
    e:bool = ( h[2] != 0 ) # If we had temp hp, they're being reset and we need to update
    
    # Reset HP
    h[0] = h[1] # Reset current to max
    h[2] = 0    # Reset temp to zero
    h[3] = 0    # Reset max temp to zero
    
    # Reset hit dice
    hd_rst:int = max( st['hd'][1] // 2, 1 ) # Half, rounding down.  Minimum of 1
    st['hd'][0] = min( st['hd'][0] + hd_rst, st['hd'][1] )
    del hd_rst
    
    # Reset spell slots
    for s in sps:
      s[0] = s[1]
    
    # Reset all long-rest charges to max
    for c in cgs:
      if 'lr' in c['reset']:
        c['curr'] = c['max']
    
    self.save()
    
    if e:
      self.draw_eink( show=show )
    
    self.draw_mtx_stable( show=show )
    
    if show:
      self.show_curr_hp()
  
  def dawn_reset(self, show=True):
    
    for c in self.stats['charges']:
      if 'dawn' in c['reset']:
        c['curr'] = c['max']
    
    self.save()
    
    self.draw_mtx_stable( show=show )
  
  # Gain HP
  # DOES validate
  def heal( self, amt, show=True ):
    
    # Localise
    hp = self.stats['hp']
    death = self.stats['death']
    
    assert type(amt) is int
    assert amt >= 0
    
    # Allow but silently exit if incrementing by zero
    if amt == 0:
      return
    
    # Can't heal if we're dead
    if death['status'] == 'dead' or death['failures'] >= 3:
      return
    
    # Add the HP
    hp[0] += amt
    
    # Can't heal past max
    if hp[0] > hp[1]:
      hp[0] = hp[1]
    
    # If we were in death saves, stabilise
    if death['status'] == 'saves':
      self.stabilise(show=show)
      return
    
    self.save()
    
    if hp[2] > 0:
      self.draw_eink( show=show )
    
    if show:
      self.show_curr_hp()
  
  # Returns ( new_hp, new_temp )
  def damage_calc( self, amt ):
    
    # Get the current levels
    new_hp = self.stats['hp'][0]
    new_temp = self.stats['hp'][2]
    
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
    hp = self.stats['hp']
    
    assert type(amt) is int
    assert amt >= 0
    
    # If we're in death saves, or dead - don't accept damage.
    # Expect user to apply extra failures manually.
    if self.stats['death']['status'] != 'stable':
      return
    
    # Affects whether we need to update eink
    tmp_cache = hp[2]
    
    # Update HP and Temp HP
    hp[0], hp[2] = self.damage_calc( amt )
    
    # If Temp HP is zero, set max temp hp to zero too
    if hp[2] == 0:
      hp[3] = 0
    
    # Extract any overdamage, clamp HP to zero
    od = 0
    if hp[0] < 0:
      od = -hp[0]
      hp[0] = 0
    
    # Is the overdamage >= max HP?
    if od >= hp[1]:
      self.die()
      return
    
    # Do we need to enter death saves?
    if hp[0] == 0:
      self.deathsaves()
      return
    
    self.save()
    
    # Only way damage can cause eink redraw is by dropping temp hp to zero
    if tmp_cache > 0 and hp[2] == 0:
      self.draw_eink( show=show )
    
    if show:
      # Update the needle
      self.show_curr_hp()
  
  # Sets the current temporary hit points
  # DOES validate
  def set_temp_hp( self, val, show=True ):
    
    assert type(val) is int
    assert val >= 0
    
    # Prevent accidental fires from triggering e-ink refresh
    if self.stats['hp'][2] == 0 and val == 0:
      return
    
    # eink update needed?
    e = False
    
    self.stats['hp'][2] = val # Current temp
    
    # Are we setting a different level from current?
    if val != self.stats['hp'][3]:
      self.stats['hp'][3] = val # Update max temp
      e = True # eink update required
    
    self.save()
    
    if e:
      self.draw_eink( show=show )
      
    if show:
      self.show_curr_hp()
  
  # Set the death status, reset death saves to zero, save, update playscreen
  def _death_status(self, status:str, show=True ):
    
    # Sanity
    if status not in ('stable','saves','dead'):
      raise ValueError('Invalid status')
    
    # Localise
    d = self.stats['death']
    
    # Are we already in this status?
    if d['status'] == status:
      return
    
    # Update the object
    d['status'] = status
    d['successes'] = 0
    d['failures'] = 0
    print('Set status to',status)
    self.save()
    
    # Go
    self._playscreen(show=show)
  #
  # Conveience functions to trigger status change.  All use _death_status()
  def stabilise(self, show=True ):
    self._death_status('stable',show=show)
  def deathsaves(self, show=True ):
    self._death_status('saves',show=show)
  def die(self, show=True ):
    self._death_status('dead',show=show)
  
  # success determines which track to edit
  # val sets the value.  ABSOLUTE, not incremental.
  # DOES validate
  def set_deathsaves(self, success:bool, val:int, show=True ):
    
    # Localise
    d = self.stats['death']
    
    # Sanity
    if d['status'] != 'saves':
      raise RuntimeError('Attempted to enter death save result when not in death saves!')
    
    # Validate
    if not 0 <= val <= 3:
      return
    
    if success: # Try to change the number of successes
      
      # Can't change successes if we're already dead
      if d['failures'] >= 3:
        return
      
      d['successes'] = val
      
    else: # Try to change the number of failures
      
      # Can't change failures if we've already succeeded
      if d['successes'] >= 3:
        return
      
      # Are we setting xor unsetting a failure state?
      update_menu = bool( (d['failures']==3) ^ (val==3) )
      
      # Update the value
      d['failures'] = val
      
      # Do we need to change what's in the oled menu?
      if update_menu:
        # Regenerate the menus without refreshing the eink
        self._playscreen(show=False)
    
    self.save()
    self.draw_mtx_saves(show=show)
    
  # Sets the max hit points
  # DOES validate
  def set_max_hp( self, val, show=True ):
    
    assert type(val) is int
    assert val >= 1
    
    # Set the max
    self.stats['hp'][1] = val
    
    # Clamp current to new max
    if self.stats['hp'][0] > val:
      self.stats['hp'][0] = val
    
    self.save()
    
    self.draw_eink( show=show )
    
    if show:
      self.show_curr_hp()
  
  # Sets the current hit dice
  # DOES validate
  def set_hit_dice( self, val ):
    
    assert type(val) is int
    
    # Is the new number valid?
    if not 0 <= val <= self.stats['hd'][1]:
      return
    
    self.stats['hd'][0] = val
    
    self.save()
  
  # Set a spell level to a given number of slots
  # DOES validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_spell( self, spl, val, show=True ):
    
    # Get the spell object
    s = self.stats['spells'][spl]
    
    # Is the new number valid?
    if not 0 <= val <= s[1]:
      return
    
    s[0] = val
    self.save()
    self.draw_mtx_stable(show=show)
  
  # Set a charge item to a given number of charges
  # DOES validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_charge( self, chg, val, show=True ):
    
    # Get the charge object
    c = self.stats['charges'][chg]
    
    # Is the new number valid?
    if not 0 <= val <= c['max']:
      return
    
    c['curr'] = val
    self.save()
    self.draw_mtx_stable(show=show)
  
  # Helper function for these numeric-only things
  # Does NOT validate
  def set_numeric_item(self, k, v ):
    self.stats[k] = v
    self.save()
  
  # Sets the needle to the current HP
  def show_curr_hp(self):
    hp = self.stats['hp']
    self.show_hp( hp[0] + hp[2] )
  
  # Sets the needle to an arbitrary HP value within range (clamps at min/max)
  def show_hp(self,hp):
    max_range = gfx.needle_max_range(self.stats['hp'])
    arg = min( hp / max_range, 1)
    arg = max( arg, 0 )
    self.hal.needle.position( arg )
  
  # Resets the matrix buffer with current spells, charges
  # Optionally updates display
  def draw_mtx_stable(self, show=True):
    
    stats = self.stats
    fb = self.hal.mtx.bitmap
    
    # Given a line and a number, will light up that many lights from the right
    # LSB is at left of display
    def draw_spell_charge( line, curr, max ):
      fb[ line ] = 256 - ( 1 << (8-curr) ) # Draw the line of lights
    
    self.hal.mtx.clear()
    
    # Go through all charges to update the matrix fb
    for i,c in enumerate(stats['charges']):
      draw_spell_charge( i, c['curr'], c['max'] )
    
    # Go through all spell slots to update the matrix fb
    for i,s in enumerate(stats['spells']):
      draw_spell_charge( 15-i, s[0], s[1] )
    
    if show:
      self.hal.mtx.update()
  
  def draw_mtx_saves(self, show=True):
    
    death = self.stats['death']
    mtx = self.hal.mtx
    
    mtx.clear()
    
    # LSB is at left of display
    mtx.bitmap[0] = 256 - ( 1 << (8-death['successes']) )
    mtx.bitmap[1] = 256 - ( 1 << (8-death['failures']) )
    
    if show:
      mtx.update()
  
  # Draw a skull on the matrix
  def draw_mtx_dead(self, show=True):
    mtx = self.hal.mtx
    mtx.clear()
    #mtx.bitmap[:8] = bytes((0x00,0x3e,0x7f,0x49,0x49,0x77,0x3e,0x2a)) # 7x7 skull
    mtx.bitmap[:8] = bytes((0x7e,0xff,0x81,0x99,0xe7,0x7e,0x24,0x24)) # 8x8 skull
    if show:
      mtx.update()
  
  def draw_eink(self,show=True):
    lowbatt = self.hal.batt_low.is_set() and self.hal.batt_discharge.is_set()
    gfx.draw_play_screen( fb=self.hal.eink, char=self, lowbatt=lowbatt )
    if show and self._enable_eink:
      self.hal.eink_send_refresh()
    gc_collect()
