# Hardware abstraction functions, mainly
# Some original code in einktest.py
#
# T. Lloyd
# 15 Sep 2025

from micropython import const
import asyncio
#from gc import collect as gc_collect

# Hardware drivers
from gadget_hw import HW

# Colour for border of e-eink panel
_EINK_BORDER_COLOUR = const(0)

# Frequency to set the needle to for a wobbling effect
_NEEDLE_WOBBLE_SPEED = const(8) # Least freq supported by hardware

class HAL:
  
  def __init__(self):
    
    self.hw = HW()
    
    # Refs to hardware features
    self.mtx = Matrix( self.hw.mtx )
    self.input = Input()
    self.needle = Needle( self.hw )
    self.eink = self.hw.eink
    self.oled = self.hw.oled
    self.sd = self.hw.sd
    
    # Set up the input link
    self.hw.init( cb=self.input.receiver )
    
    # Priority lock levels for each lockable feature
    self._features = {
      'mtx' : 0,
      'oled' : 0,
      'input' : 0,
      'needle' : 0,
    }
    
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
    
    # Software components using register()
    self._clients = set()
  
  # Register code that will use hardware features.
  # priority: int, higher number is higher priority
  # features: list of hardware features this code needs
  # callback: will be called when all features become available
  # input_target: function to receive input codes
  # register( priority, features, callback=None, input_target=None )
  def register(self, *args, **kwargs ):
    cr = _ClientRegistration( *args, **kwargs )
    #print('Registered',cr)
    self._clients.add( cr )
    self._update_clients()
    return cr
  
  def unregister(self, cr ):
    self._clients.discard( cr )
    #print('Unregistered',cr)
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
        c.ready = False
        continue
      
      # If the client is only now becoming ready
      if not c.ready:
        
        # Update the feature priority list
        for f in c.features:
          feat[f] = p
        
        # Set the input target, if necessary
        if 'input' in c.features:
          self.input.target = c.input_target if callable( c.input_target ) else lambda x: None
        
        # Tell the client it's good to go
        c.ready = True
        if callable( c.callback ):
          c.callback()
        
    #print('New priorities:',feat )
  
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

# The object that hal.register() gives you
class _ClientRegistration:
  def __init__(self, priority, features, callback=None, input_target=None ):
    self.priority = priority
    self.features = features
    self.callback = callback
    self.input_target = input_target
    self.ready = False
    #self.ready_event = asyncio.Event() # Needs to be called from non-async code, use TSF instead
    #self.unready_event = asyncio.Event()
  
  def __str__(self):
    return f'CR( priority={self.priority}, features={str(self.features)}  )'

class Matrix:
  def __init__(self, mtx ):
    self.matrix = mtx # self.matrix = ui.hw.mtx = max7219.Matrix8x8
    self.bitmap = mtx.buffer
    self.power = mtx.power
    #self._renderers = set()
    
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

class Input:
  def __init__(self):
    self.target = lambda x: None
  def receiver(self,i): # This gets called directly by the ISR
    self.target(i)

class Needle:
  def __init__(self,hw):
    self.hw = hw
    self._wob = False
  
  def position(self, pos=None ):
    if pos is None:
      return self.hw.get_needle_position()
    else:
      self.hw.set_needle_position(pos)
  
  def wobble(self, wob=None ):
    
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
