# Character-specific data and logic
#
# T. Lloyd
# 19 Sep 2025

#import asyncio
import os
from micropython import const
from gc import collect as gc_collect
#import gc

from . import gfx
from .common import DeferredTask, CHAR_STATS

_SAVE_TIMEOUT = const(5000) # Save contdown, in ms

# Check a string: correct type and has length
def val_str(s,t):
  if type(s) is not str:
    return 'Bad '+t
  if len(s) == 0:
    return 'Empty '+t

# Check an integer: correct type and > 0
def val_pint(v,t):
  try:
    v = int(v)
  except ValueError:
    return t+' must be integer'
  if v <= 0:
    return t+' must be > 0'

# Check an integer: correct type and >= 0
def val_zpint(v,t):
  try:
    v = int(v)
  except ValueError:
    return t+' must be integer'
  if v < 0:
    return t+' must be >= 0'

# Checks the triplet of HP values
def val_hp(c,m,t):
  
  # Check we have a full complement
  if c is None:
    return 'Missing hp_current'
  if m is None:
    return 'Missing hp_max'
  if t is None:
    return 'Missing hp_temp'
  
  # Check all the values are ok
  e = val_zpint(c,'Current HP')
  if e:
    return e
  e = val_pint(m,'Max HP')
  if e:
    return e
  e = val_zpint(t,'Temp HP')
  if e:
    return e
  
  if int(c) > int(m):
    return 'HP is more than max'

# Checks the hit dice values
# STILL NEEDED?
def val_hd(c,m):
  
  # Check we have a full complement
  if c is None:
    return 'Missing hd_current'
  if m is None:
    return 'Missing hd_max'
  
  # Check the values are ok
  e = val_zpint(c,'Current HD')
  if e:
    return e
  e = val_pint(m,'Max HD')
  if e:
    return e
  
  if int(c) > int(m):
    return 'Hit dice are more than max'

# Checks a pair if Spell values
def val_spell(c,m,i):
  e = val_zpint(c,f'Spell slot {i}')
  if e:
    return e
  e = val_pint(m,f'Spell max {i}')
  if e:
    return e
  
  if int(c) > int(m):
    return f'Spell slots {i} > max'

# Checks a quad of Charge values
def val_charge(name,curr,max,reset,i):
  e = val_str(name, f'Item {i} name')
  if e:
    return e
  e = val_zpint(curr,f'Item {i} charges')
  if e:
    return e
  e = val_pint(max,f'Item {i} max')
  if e:
    return e
  # val_str() isn't useful for checking reset value
  
  if int(curr) > int(max):
    return f'Item {i} charges > max'
  
  if reset not in ( 'lr', 'sr' ):
    return f'Item {i} invalid reset'

# Individual params.  HP, Spells and Charges are treated differently.
# Temporary store for value, validation function, conversion function
PARAMS = {
  'name'    : [None, lambda s: val_str(s,'name'),      lambda x:x],
  'title'   : [None, lambda s: val_str(s,'title'),     lambda x:x],
  'subtitle': [None, lambda s: val_str(s,'subtitle'),  lambda x:x],
  'level'   : [None, lambda v: val_pint(v,'Level'),    int],
  'xp'      : [None, lambda v: val_zpint(v,'XP'),      int],
  'gold'    : [None, lambda v: val_zpint(v,'Gold'),    int],
  'silver'  : [None, lambda v: val_zpint(v,'Silver'),  int],
  'copper'  : [None, lambda v: val_zpint(v,'Copper'),  int],
  'electrum': [None, lambda v: val_zpint(v,'Electrum'),int],
}

# hal: The HAL object from hal.py
# chardir: Path object to the character directory
class Character:
  def __init__(self,hal,chardir):
    
    # Where are my files
    self.dir = chardir
    print(chardir)
    
    # TODO: Check the dir and its files at this point, raise an error if problems
    
    # Top-level ref
    self.hal = hal
    
    # Stats
    self.stats = {
      'title' : None,
      'subtitle' : None,
      'level' : None,
      'xp' : None,
      'gold' : None,
      'silver' : None,
      'copper' : None,
      'hp' : [0,0,0,0], # Current, max, temp, orig_temp
      'hd' : [0,0], # Current, max
      'spells' : [],
      'charges' : [],
    }
    
    #self.dirty = False
    #self._save_task = asyncio.create_task( self._save_watcher() )
    self._saver = DeferredTask( timeout=_SAVE_TIMEOUT, callback=self._save_now )
    self.is_saving = self._saver.is_dirty
    
    e = self.load()
    print(self.stats)
    if e:
      raise ValueError(e)
    
    gc_collect()
  
  def _save_now(self):
    
    # Blindly overwrites f with the save data
    # Allocates ~7kB memory every time it runs
    # Appears to scale with lines written, assume they're being buffered before write
    # ...except memory usage is ~7x eventual filesize
    def do_save( f ):
      st = self.stats
      #print(f'Writing file {f}')
      #print(type(f))
      with open( f, 'w') as fd:
        w = fd.write
        
        w( '# BASIC INFO\n#\n' )
        w( f'name={st["name"]}\n' )
        w( f'title={st["title"]}\n' )
        w( f'subtitle={st["subtitle"]}\n' )
        w( f'level={st["level"]}\n' )
        w( f'xp={st["xp"]}\n\n' )
        
        w('# CURRENCY\n#\n')
        w( f'gold={st["gold"]}\n' )
        w( f'silver={st["silver"]}\n' )
        w( f'copper={st["copper"]}\n' )
        w( f'electrum={st["electrum"]}\n\n' )
        
        w('# HIT POINTS\n#\n')
        w( f'hp_current={st["hp"][0]}\n' )
        w( f'hp_max={st["hp"][1]}\n' )
        w( f'hp_temp={st["hp"][2]}\n\n' )
        
        w('# HIT DICE\n#\n')
        w( f'hd_current={st["hd"][0]}\n' )
        w( f'hd_max={st["hd"][1]}\n\n' )
        #print(gc.mem_alloc())
        
        w('# SPELLS\n#\n')
        for i,s in enumerate(st['spells']):
          w( f'spell_curr:{i}={s[0]}\n' )
          w( f'spell_max:{i}={s[1]}\n#\n' )
        #print(gc.mem_alloc())
        
        w('\n# ITEMS/THINGS WITH CHARGES\n#\n')
        for i,c in enumerate(st['charges']):
          w( f'charge_name:{i}={c["name"]}\n' )
          w( f'charge_curr:{i}={c["curr"]}\n' )
          w( f'charge_max:{i}={c["max"]}\n' )
          w( f'charge_reset:{i}={c["reset"]}\n#\n' )
        #print(gc.mem_alloc())
    
    f = str( self.dir / CHAR_STATS )
    
    # Save out the file, temporarily preserving the previous one
    do_save( f + '.new' )
    
    # Ensure the new file is saved
    os.sync()
    
    # Replace the old file
    do_save( f )
    os.sync()
    print('Saved.')
  
  def save(self):
    self._saver.touch()
  
  def load(self):
    
    # Reset the param tracker
    for k in PARAMS:
      PARAMS[k][0] = None
    
    # Check here for directory / file presense
    # Alert user if error
    
    # Savefile
    f = str( self.dir / CHAR_STATS )
    
    # These will hold data from the savefile before it's validated
    file_hp = [None]*3
    file_hd = [None]*2
    file_spells = []
    file_charges = []
    for i in range(8):
      file_spells.append( [None,None] )
      file_charges.append({
        'name':None,
        'curr':None,
        'max':None,
        'reset':None
      })
    
    # Error tracker
    e = None
    
    # Step through the file line by line
    with open( f, 'r' ) as fd:
      while True:
        
        # Get the line
        line = fd.readline()
        
        # Stop at EoF
        if not line:
          break
        
        # Initial processing
        line = line.strip()
        #
        # Remove comments
        x = line.find('#')
        if x >= 0:
          line = line[:x]
        #
        # Find delimiter
        x = line.find('=')
        
        # No delimiter (-1) or no key (0)? skip
        if x <= 0:
          continue
        
        # Get the key and val from the line
        k = line[:x]
        v = line[x+1:]
        
        # For individual parameters
        p = PARAMS.get(k)
        if p is not None:
          
          # Validate the value
          e = p[1]( v )
          if e:
            break
          
          # Convert and temporarily store the value
          PARAMS[k][0] = p[2]( v )
          continue
        
        # If it's relating to HP, save it and check later
        if k == 'hp_current':
          file_hp[0] = v
          continue
        if k == 'hp_max':
          file_hp[1] = v
          continue
        if k == 'hp_temp':
          file_hp[2] = v
          continue
        
        # If it's relating to hit dice, save it and check later
        if k == 'hd_current':
          file_hd[0] = v
          continue
        if k == 'hd_max':
          file_hd[1] = v
          continue
        
        # Spells and charges
        x = k.find(':')
        if x <= 0:
          continue
        
        # Key and spell/charge index
        i = k[x+1:]
        k = k[:x]
        
        # Check key
        if k not in ('spell_curr','spell_max','charge_name','charge_curr','charge_max','charge_reset'):
          continue
        
        # Check index
        e = val_zpint(i,f'{k} index')
        if e:
          break
        i = int(i)
        if i >= 8:
          e = f'{k} index too high'
          break
        
        # Temporarily store the value for checking later
        if k[0] == 's': # Spell
          if k[6] == 'c': # Curr
            file_spells[i][0] = v
          else: # Max
            file_spells[i][1] = v
        else: # Charge
          if k[7] == 'n':
            file_charges[i]['name'] = v
          elif k[7] == 'c':
            file_charges[i]['curr'] = v
          elif k[7] == 'm':
            file_charges[i]['max'] = v
          else:
            file_charges[i]['reset'] = v
    
    # Report errors
    if e:
      return e
    
    # Individual params have already been validated
    # But did we get a full set?
    for k in PARAMS:
      if PARAMS[k][0] is None:
        return 'Missing '+k
      self.stats[k] = PARAMS[k][0]
    
    # Validate/ingest HP
    e = val_hp( *file_hp )
    if e:
      return e
    self.stats['hp'][0] = int( file_hp[0] )
    self.stats['hp'][1] = int( file_hp[1] )
    self.stats['hp'][2] = int( file_hp[2] )
    self.stats['hp'][3] = int( file_hp[2] ) # not a typo
    
    # Validate/ingest hit dice
    e = val_hd( *file_hd )
    if e:
      return e
    self.stats['hd'][0] = int( file_hd[0] )
    self.stats['hd'][1] = int( file_hd[1] )
    
    # Validate/ingest spells
    for i in range(8):
      
      # If we reach an empty slot, stop
      if file_spells[i][0] is None:
        break
      
      # If we were given a current but not a max
      if file_spells[i][1] is None:
        return f'Spell slot {i} has no max'
      
      # Validate
      e = val_spell( *file_spells[i], i )
      if e:
        return e
      
      # Record
      self.stats['spells'].append([ int(file_spells[i][0]), int(file_spells[i][1]) ])
    
    # Validate/ingest charges
    for i in range(8):
      
      # If we reach an empty slot, stop
      if file_charges[i]['name'] is None:
        break
      
      # Check we have a full set
      for k in file_charges[i]:
        if file_charges[i][k] is None:
          return f'Charge {i} has no charge_{k}'
      
      # Validate
      e = val_charge( **file_charges[i], i=i )
      if e:
        return e
      
      # Record
      self.stats['charges'].append({
        'name': file_charges[i]['name'],
        'curr': int( file_charges[i]['curr'] ),
        'max':  int( file_charges[i]['max'] ),
        'reset':file_charges[i]['reset'],
      })
  
  # DOES NOT VALIDATE hit dice
  def short_rest(self, hit_dice=0, show=True):
    
    # Localise
    cgs = self.stats['charges']
    
    # Apply hit dice reduction.
    # Silently clamp overspend
    self.stats['hd'][0] = max( self.stats['hd'][0] - hit_dice, 0 )
    
    # Option to do spell slots here?
    
    # Reset all short-rest charges to max
    for c in cgs:
      if c['reset'] == 'sr':
        c['curr'] = c['max']
    
    self.save()
    
    self.draw_mtx( show=show )
  
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
      if c['reset'] == 'lr':
        c['curr'] = c['max']
    
    self.save()
    
    if e:
      self.draw_eink( show=show )
    
    self.draw_mtx( show=show )
    
    if show:
      self.show_curr_hp()
  
  # Gain HP
  # DOES validate
  def heal( self, amt, show=True ):
    
    # Current, max, temp, orig_temp
    hp = self.stats['hp']
    
    assert type(amt) is int
    assert amt >= 0
    
    # Allow but silently exit if incrementing by zero
    if amt == 0:
      return
    
    # Add the HP
    hp[0] += amt
    
    # Can't heal past max
    if hp[0] > hp[1]:
      hp[0] = hp[1]
    
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
    
    self.save()
    
    # Only way damage can cause eink redraw is by dropping temp hp to zero
    if tmp_cache > 0 and hp[2] == 0:
      self.draw_eink( show=show )
    
    if show:
      # Update the needle
      self.show_curr_hp()
  
  # Do something when the character actually dies (not just knocked out)
  def die(self):
    pass
  
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
  # TO BE REMOVED
  def set_hit_dice( self, val ):
    raise NotImplementedError('Do not do this')
    assert type(val) is int
    assert val >= 0
    assert val <= self.stats['hd'][1]
    
    self.stats['hd'][0] = val
    
    self.save()
  
  # Set a spell level to a given number of slots
  # DOES validate, now           # Does NOT validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_spell( self, spl, val, show=True ):
    
    s = self.stats['spells'][spl]
    
    if 0 <= val <= s[1]:
      s[0] = val
    
    # Record the new value
    #self.stats['spells'][s][0] = val
    
    self.save()
    
    self.draw_mtx(show=show)
  
  # Set a charge item to a given number of charges
  # DOES validate, now        # Does NOT validate
  # Updates the matrix fb.  Optionally also sends the fb.
  def set_charge( self, chg, val, show=True ):
    
    c = self.stats['charges'][chg]
    
    if 0 <= val <= c['max']:
      c['curr'] = val
    
    # Record the new value
    #self.stats['charges'][chg]['curr'] = val
    
    self.save()
    
    self.draw_mtx(show=show)
  
  # Helper functions for these numeric-only things
  # These do NOT validate
  def set_xp(self,x):
    self.stats['xp'] = x
    self.save()
  def set_gold(self,x):
    self.stats['gold'] = x
    self.save()
  def set_silver(self,x):
    self.stats['silver'] = x
    self.save()
  def set_copper(self,x):
    self.stats['copper'] = x
    self.save()
  def set_electrum(self,x):
    self.stats['electrum'] = x
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
  def draw_mtx(self, show=True):
    
    stats = self.stats
    fb = self.hal.mtx.bitmap
    
    # Given a line and a number, will light up that many lights from the right
    # LSB is at left of display
    def draw_spell_charge( line, curr, max ):
      
      # Draw the line of lights
      fb[ line ] = 256 - ( 1 << (8-curr) )
    
    # Go through all charges to update the matrix fb
    for i,c in enumerate(stats['charges']):
      draw_spell_charge( i, c['curr'], c['max'] )
    
    # Go through all spell slots to update the matrix fb
    for i,s in enumerate(stats['spells']):
      draw_spell_charge( 15-i, s[0], s[1] )
    
    if show:
      self.hal.mtx.update()
  
  def draw_eink(self,show=True):
    lowbatt = self.hal.batt_low.is_set() and self.hal.batt_discharge.is_set()
    gfx.draw_play_screen( fb=self.hal.eink, char=self, lowbatt=lowbatt )
    if show:
      self.hal.eink_send_refresh()
  
  def draw_select(self):
    gfx.draw_char_select( fb=self.hal.eink, chars=[] )
    self.hal.eink_send_refresh()
