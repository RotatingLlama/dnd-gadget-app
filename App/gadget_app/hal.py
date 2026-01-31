# Hardware abstraction functions, mainly
# Some original code in einktest.py
#
# T. Lloyd
# 31 Jan 2026

from micropython import const
import asyncio
from machine import deepsleep, RTC as _RTC
from time import mktime, gmtime
#from gc import collect as gc_collect

# Hardware drivers
from gadget_hw import HW

_DEBUG_VERBOSE_REGISTRATIONS = const(False)

# Colour for border of e-eink panel
_EINK_BORDER_COLOUR = const(0)

# Frequency to set the needle to for a wobbling effect
_NEEDLE_WOBBLE_SPEED = const(8) # Least freq supported by hardware

class HAL:
  
  def __init__(self):
    
    self.hw = HW()
    
    # Refs to hardware features
    self.mtx = Matrix( self.hw.mtx )
    self.needle = Needle( self.hw )
    self.rtc = RTC()
    self.eink = self.hw.eink
    self.oled = self.hw.oled
    self.sd = self.hw.sd
    
    # Input target, gets updated by _update_clients()
    self._it = lambda x:None
    
    # Get the hardware input stream - this lambda will be called by schedule()
    # i is an int indicating which input this was
    self.hw.init( cb=lambda i:self._it(i) )
    
    # Priority lock levels for each lockable feature
    self._features = {
      'mtx' : 0,
      'oled' : 0,
      'input' : 0,
      'needle' : 0,
    }
    
    # Software components using register()
    self._clients:set[_ClientRegistration] = set()
    
    # Pass these through
    self.batt_pc = self.hw.batt_pc
    self.batt_ok = self.hw.ok_battery
    self.batt_low = self.hw.low_battery
    self.batt_charge = self.hw.battery_charging
    self.batt_discharge = self.hw.battery_discharging
    self.batt_empty = self.hw.empty_battery
    
    # Support for triggering eink update from non-async code
    self._update_eink = asyncio.ThreadSafeFlag()
    self._eink_action = 0
    self._eink_task = asyncio.create_task( self._eink_updater() )
  
  # Register code that will use hardware features.
  # priority: int, higher number is higher priority
  # features: list of hardware features this code needs
  # callback: will be called when all features become available
  # input_target: function to receive input codes
  # name: An identifying string for this registration
  # register( priority, features, callback=None, input_target=None )
  def register(self, priority, features, **kwargs ):
    
    cr = _ClientRegistration( priority, features, **kwargs )
    
    # Check nothing illegal is going on
    for c in self._clients:
      if c.priority == priority:
        clash = False
        for f in features:
          if f in c.features:
            clash = True
        if clash:
          print('WARNING!  Priority clash detected!')
          print('  Existing:',c)
          print('       New:',cr)
          raise RuntimeError('Duplicate priorities attempted')
    
    # Add it in
    self._clients.add( cr )
    
    if _DEBUG_VERBOSE_REGISTRATIONS:
      print('Registered',cr)
    
    self._update_clients()
    return cr
  
  def unregister(self, cr ):
    self._clients.discard( cr )
    if _DEBUG_VERBOSE_REGISTRATIONS:
      print('Unregistered',cr)
    self._update_clients()
  
  def _update_clients(self):
    
    # List of hardware features
    feat = self._features
    
    # Reset the priorities to zero, we're about the re-write them
    for f in feat:
      feat[f] = 0
    
    # Get a list of clients, sorted by descending priority
    c_s = list(self._clients)
    c_s.sort( key=lambda c:c.priority, reverse=True ) # sort in place - uses less memory than sorted()
    
    # Step through the clients, highest priority first
    for c in c_s:
      
      # Client's priority number
      p = c.priority
      
      # Compare each of this client's needed features
      ready = True
      for f in c.features:
        # Is the priority of the thing currently using this feature more than this client's priority?
        if feat[f] > p:
          ready = False
          break
      
      # If this client doesn't have priority
      if not ready:
        
        # If the client is being deactivated
        if c.ready and _DEBUG_VERBOSE_REGISTRATIONS:
          print('Deactivating CR:',c)
        
        # Mark it as unready and move on to the next
        c.ready = False
        continue
      
      # Update the feature priority list
      for f in c.features:
        feat[f] = p
      
      # If the client is only now becoming ready
      if not c.ready:
        
        if _DEBUG_VERBOSE_REGISTRATIONS:
          print('Activating CR:',c)
        
        # Set the input target, if necessary
        if 'input' in c.features:
          self._it = c.input_target if callable( c.input_target ) else lambda x: None
        
        # Tell the client it's good to go
        c.ready = True
        if callable( c.callback ):
          c.callback()
    
    # If everything has abandoned input, reset the input director to null
    if feat['input'] == 0:
      self._it = lambda x: None
    
    if _DEBUG_VERBOSE_REGISTRATIONS:
      print('New priorities:',feat )
  
  # Queries low-level state of SD card.
  # Possible return values:
  # 0 : Card present and responding
  # 1 : Card not present
  # 2 : Card present, but not ready
  def get_sd_status(self) -> int:
    if self.sd.card_ready.is_set():
      return 0
    if self.sd.card_present.is_set():
      return 2
    return 1
  
  # Allows eink updates to be triggered from non-async code
  async def _eink_updater(self):
    
    # Set the border colour at startup
    await self.eink.border(c=_EINK_BORDER_COLOUR)
    
    while True:
      
      # Wait for the flag
      await self._update_eink.wait()
      
      # Reset the state
      a = self._eink_action
      self._eink_action = 0
      self._update_eink.clear()
      
      # Actions
      # 000 = 0 = noop
      # 001 = 1 = refresh only
      # 010 = 2 = clear (no refresh)
      # 011 = 3 = clear and refresh
      # 100 = 4 = send (no refresh)
      # 101 = 5 = send and refresh
      
      # Clear?
      if a & 2:
        await self.hw.eink.clear()
      
      # Send?
      if a & 4:
        await self.hw.eink.send()
      
      # Refresh?
      if a & 1:
        await self.hw.eink.refresh()
  
  # Eink actions to be called from non-async code
  # Return immediately, will not block
  # (just set a flag and async takes it from there)
  def eink_refresh(self):
    self._eink_action = 1
    self._update_eink.set()
  #
  def eink_send_refresh(self):
    self._eink_action = 5
    self._update_eink.set()
  #
  def eink_clear_refresh(self):
    self._eink_action = 3
    self._update_eink.set()
  
  def poweroff(self):
    
    print('Powering off...')
    print(' OLED')
    self.oled.poweroff()
    print(' Matrix')
    self.mtx.power(0)
    print(' Needle')
    self.needle.position(0)
    # Eink is always in deep sleep unless updating
    
    print(' CPU')
    deepsleep()
  
# The object that hal.register() gives you
class _ClientRegistration:
  def __init__(self, priority:int, features:tuple[str], callback=None, input_target=None, name:str='(anon)' ):
    self.priority = priority
    self.features = features
    self.callback = callback
    self.input_target = input_target
    self.name=name
    self.ready = False
    #self.ready_event = asyncio.Event() # Needs to be called from non-async code, use TSF instead
    #self.unready_event = asyncio.Event()
  
  def __str__(self):
    return f'{self.name} ( priority={self.priority}, features={str(self.features)}  )'

class Matrix:
  def __init__(self, mtx ):
    self.matrix = mtx # self.matrix = ui.hw.mtx = max7219.Matrix8x8
    self.bitmap = mtx.buffer
    self.power = mtx.power
    self.brightness(1)
  
  def update(self):
    
    # hw.show() sends and displays all at once.  This hardware doesn't have a 'refresh' concept.
    self.matrix.show()
  
  # Gets/sets the matrix LED brightness
  def brightness(self, b=None ):
    
    if b is None:
      return self._bright
    
    if type(b) is not int:
      raise TypeError('Brightness value must be integer')
    if b < 0:
      raise ValueError('Brightness value must be positive')
    if b > 15:
      raise ValueError('Max brightness is 15')
    
    self._bright = b
    self.matrix.brightness(b)
    
    return self._bright
  
  def clear(self):
    self.matrix.fill(0)

# Method position():
#  No args: Returns position (float 0.0 - 1.0)
#  pos:float: Sets postion.  Takes float 0.0-1.0
# Method wobble():
#  No args: Toggle wobble
#  wob:bool: Set wobble on/off
class Needle:
  def __init__(self,hw):
    self.hw = hw
    self._wob = False
  
  def position(self, pos:float=None ):
    if pos is None:
      return self.hw.get_needle_position()
    else:
      self.hw.set_needle_position(pos)
  
  def wobble(self, wob:bool|None=None ):
    
    # No arg means toggle wobble
    if wob is None:
      wob = not self._wob
    
    # Remember the wobble
    self._wob = wob
    
    # Enact the wobble
    if wob == True:
      self.hw.set_needle_frequency( _NEEDLE_WOBBLE_SPEED )
    else:
      self.hw.set_needle_frequency()

class RTC(_RTC):
  
  def uts(self, ts=None ):
    if ts is None:
      return self._getuts()
    else:
      self._setuts(ts)
  
  def _getuts(self):
    
    #  0     1      2    3        4      5        6        7
    # (year, month, day, weekday, hours, minutes, seconds, subseconds)
    t = self.datetime()
    
    #             ( year, month, mday, hour, minute, second, weekday, yearday)
    return mktime(( t[0], t[1],  t[2], t[4], t[5],   t[6],   t[3],    0      ))
  
  def _setuts(self, ts ):
    
    #  0     1      2     3     4       5       6        7
    # (year, month, mday, hour, minute, second, weekday, yearday)
    t = gmtime(ts)
    
    #             (year, month, day, weekday, hours, minutes, seconds, subseconds)
    self.datetime(( t[0], t[1], t[2], t[6],   t[3],  t[4],    t[5],    0         ))