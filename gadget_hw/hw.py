# Collects all hardware into one object
# Some original code in einktest.py
#
# T. Lloyd
# 12 Sep 2025

# Standard libraries
from machine import I2C, SPI, ADC, PWM, Pin
from micropython import const, schedule
import asyncio
from array import array

# Defs & drivers
from . import defs_rev1 as DEFS
from . import eink
from . import ssd1306
from . import sd_socket
#from . import sdcard
from . import max7219_rev1 as max7219

# Used by ISRs - declared here for speed of access
_rot = bytearray(3)
_rotv = bytearray(1)
_none_func = lambda x: None
_cb_input = _none_func

# Needle fine-tuning parameters
NEEDLE_OFFSET = const(0)
NEEDLE_FACTOR = const(0.975)
#
NEEDLE_DEF_FREQ = const(30000)
NEEDLE_DEF_DUTY = const(1)

# Battery monitoring
#   / 65535 normalises the ADC reading to a float between 0.0 and 1.0
#   x 3.3 scales the value up to the actual voltage read at the pin
#   x 3 scales up to the top of the voltage divider (to V_SYS)
#   Expect it to be a bit below 5v on USB due to presence of MBR120VLSFT1G Schottky (Vf=340 mV)
VSYS_MULTIPLIER = const(0.0001510643) # ( 3.3 * 3 ) / 65535
VSYS_HYST_VALUE = const(0.1) # Hysteresis voltage - normally 0.06 is ok, but fluctuates more during eink refresh (0.0797 observed)
BATT_MIN = const(3.5) # Consider this voltage (or less) to be 0%
BATT_LOW = const(3.6) # Battery is "low" below this voltage (about 14%)
BATT_MAX = const(4.2) # Consider this voltage (or more) to be 100%
BATT_USB = const(4.75) # If it's higher than this, assume we're plugged in

class HW:
  
  def __init__(self,*args,**kwargs):
    
    # Set all CS lines high
    DEFS.CS_SD1.init( Pin.OUT, value=1 )
    DEFS.CS_SD2.init( Pin.OUT, value=1 )
    DEFS.CS_MTX.init( Pin.OUT, value=1 )
    DEFS.CS_EINK.init( Pin.OUT, value=1 )
    DEFS.CS_SRAM.init( Pin.OUT, value=1 )
    
    # Set up the Vsys ADC (and associated battery things)
    self._vsys = ADC(DEFS.VSYS)
    self._vsys_val:int = 0
    self._vsys_task = asyncio.create_task( self._vsys_hyst() )
    self.low_battery = asyncio.Event()
    self.ok_battery = asyncio.Event()
    self.ok_battery.set()  # Need to have one of these set to begin with
    self.battery_charging = asyncio.Event()
    self.battery_discharging = asyncio.Event()
    self.battery_discharging.set() # Need to have one of these set to begin with
    self.empty_battery = asyncio.Event()
    
    # Set up busses
    self.i2c = I2C( DEFS.I2C_ID, scl=DEFS.I2C_SCL, sda=DEFS.I2C_SDA, freq=DEFS.I2C_FREQ )
    self.spi = SPI( DEFS.SPI_ID, sck=DEFS.SPI_CLK, mosi=DEFS.MOSI, miso=DEFS.MISO, baudrate=DEFS.SPI_FREQ, polarity=0, phase=0)
    self.spi.init()
    
    #
    # Buttons rise when pushed
    # Connected to gnd, fed through inverter
    #
    DEFS.SW1.init( Pin.IN, Pin.PULL_UP )
    DEFS.ROT_BTN.init( Pin.IN, Pin.PULL_UP )
    DEFS.ROT_A.init( Pin.IN, Pin.PULL_UP )
    DEFS.ROT_B.init( Pin.IN, Pin.PULL_UP )
    #
    DEFS.SW1.irq( handler=self._isr_sw, trigger=Pin.IRQ_RISING)
    DEFS.ROT_BTN.irq( handler=self._isr_btn, trigger=Pin.IRQ_RISING)
    DEFS.ROT_A.irq( handler=self._isr_rot, trigger=(Pin.IRQ_RISING|Pin.IRQ_FALLING) )
    DEFS.ROT_B.irq( handler=self._isr_rot, trigger=(Pin.IRQ_RISING|Pin.IRQ_FALLING) )
    
    # External SD
    self.sd = sd_socket.SD_Socket( spi=self.spi, cs=DEFS.CS_SD1, det=DEFS.SD1_DET, baudrate=DEFS.SPI_FREQ )
    
    # Internal SD
    #self.sd2 = sd_socket.SD_Socket( self.spi, DEFS.CS_SD2 )
    
    # Needle
    DEFS.NEEDLE.init( Pin.OUT, value=0 )
    self.needle = PWM( DEFS.NEEDLE, freq=NEEDLE_DEF_FREQ, duty_u16=NEEDLE_DEF_DUTY )
    self._needle_val = NEEDLE_DEF_DUTY
    
    # Eink
    self.eink = eink.EInk(
      width=360, height=240, rot=3, # Landscape
      spi=self.spi, cs=DEFS.CS_EINK, dc=DEFS.EINK_DC, busy=DEFS.EINK_BUSY, reset=DEFS.EINK_RST
    )
    self.eink.init_panel()
    
    # OLED
    self.oled = ssd1306.SSD1306_I2C(128, 32, self.i2c, addr=60)
    
    # Matrices
    # Large is #1
    # Small is #2
    # Large needs to be rotated 90 degrees anticlockwise
    self.mtx = max7219.Matrix8x8( self.spi, DEFS.CS_MTX)
    self.mtx.fill(0)
    self.mtx.show()
    
    # SRAM
    # Do something with this?
    # DEFS.CS_SRAM
    
    # UART is set up in boot.py
    # DEFS.UART_TX
    # DEFS.UART_RX
    
    # Do the optional stuff that can get set/reset later
    self.init(*args,**kwargs)
  
  def init(self, cb=None ):
    global _cb_input
    if callable(cb):
      _cb_input = cb
  
  # Set needle position.  Takes a float 0.0 to 1.0
  def set_needle_position( self, pc ):
    
    # Sanity
    assert type(pc) is float or type(pc) is int
    assert pc >= 0
    assert pc <= 1
    
    # Conversion
    val = round( 65535 * pc * NEEDLE_FACTOR ) + NEEDLE_OFFSET
    
    # Doesn't like zeroes
    if val == 0:
      val = 1
    
    # Commit
    self._needle_val = val
    self.needle.duty_u16( val )
  def get_needle_position(self):
    return self._needle_val / 65535
  
  # Get/set needle frequency
  def set_needle_frequency( self, freq=NEEDLE_DEF_FREQ ):
    self.needle.freq(freq)
  def get_needle_frequency( self ):
    return self.needle.freq()
  
  # UI ISR
  def _isr_sw(self,pin):
    schedule( _cb_input, 0 )
  
  def _isr_btn(self,pin):
    schedule( _cb_input, 1 )
  
  # Left  = 0 1 3 2
  # Right = 3 1 0 2
  @micropython.native
  def _isr_rot_old(self,pin):
    
    # Move the buffer up
    _rot[0] = _rot[1]
    _rot[1] = _rot[2]
    
    # Calc latest value
    _rot[2] = DEFS.ROT_A.value()<<1 | DEFS.ROT_B.value()
    
    # A valid pattern is 1 - x - 2, where x is 3 or 0
    if _rot[0] == 1 and _rot[2] == 2:
      if _rot[1] == 3:
        # Left / anticlockwise
        schedule( _cb_ccw, None )
      elif _rot[1] == 0:
        # Right / clockwise
        schedule( _cb_cw, None )
  
  @micropython.viper
  def _isr_rot(self,pin):
    
    rot = ptr8(_rotv)
    
    # Shift the buffer down and add the latest value
    #rot[0] = int(DEFS.ROT_A.value()) << 5 | int(DEFS.ROT_B.value()) << 4 | rot[0] >> 2
    rot[0] >>= 2 # Shift the values down
    rot[0] |= int(DEFS.ROT_A.value()) << 5
    rot[0] |= int(DEFS.ROT_B.value()) << 4
    
    # Valid patterns (in time) are 3 1 0 2 and 0 1 3 2
    # In memory the latest value is inserted at MSb and we only keep most recent 3 bit pairs
    # So valid patterns are 2 3 1 and 2 0 1
    
    if rot[0] == 0x21: # 0x21 = 00100001 = 2 0 1 = clockwise
      schedule( _cb_input, 2 )
      #print('cw')
    elif rot[0] == 0x2D: # 0x2D = 00101101 = 2 3 1 = anticlockwise
      schedule( _cb_input, 3 )
      #print('ccw')
  
  # Runs in an endless loop.
  # Keeps self._vsys_val updated with raw uint16 values from the ADC,
  # but via some hysteresis to filter the noisy reading
  async def _vsys_hyst(self) -> None:
    
    # Hysteresis value, converted to ADC uint16 numbers
    h:int = round( VSYS_HYST_VALUE / VSYS_MULTIPLIER )
    
    # Low battery value
    empty:int = BATT_MIN // VSYS_MULTIPLIER
    low:int = BATT_LOW // VSYS_MULTIPLIER
    
    # Localisation
    adc = self._vsys.read_u16 # Function to get raw ADC value
    
    inc:bool = True
    new:int
    while True:
      
      new = adc()
      
      if inc: # If we're incrementing
        if new < ( self._vsys_val - h ): # But the value has dropped enough
          inc = False # Then we're decrementing
      
      else: # If we're decrementing
        if new > ( self._vsys_val + h ): # But the value has risen enough
          inc = True # Then we're incrementing
      
      if inc: # If we're incrementing
        if new > self._vsys_val: # and the value has risen at all
          self._vsys_val = new # keep the new value
      
      else: # If we're decrementing
        if new < self._vsys_val: # and the value has dropped at all
          self._vsys_val = new # keep the new value
      
      # Manage the dis/charging flags
      if inc:
        if self.battery_discharging.is_set():
          self.battery_discharging.clear()
          self.battery_charging.set()
      else:
        if self.battery_charging.is_set():
          self.battery_charging.clear()
          self.battery_discharging.set()
      
      # Manage the low/ok battery flags
      if new <= low:
        if self.ok_battery.is_set():
          self.ok_battery.clear()
          self.low_battery.set()
      else:
        if self.low_battery.is_set():
          self.low_battery.clear()
          self.ok_battery.set()
      
      # Kick off the dead battery sequence
      if new <= empty:
        self.empty_battery.set()
        print('hw triggered battery shutdown at',new)
        break
      
      # Voltage value doesn't change very quickly.  Could even run this less frequently and prob wouldn't matter
      await asyncio.sleep_ms(1000)
  
  # Returns the supply voltage value
  def voltage_raw(self) -> float:
    return ( self._vsys.read_u16() * VSYS_MULTIPLIER )
  
  # Returns a voltage figure with some hysteresis to stop it fluctuating
  def voltage_stable(self) -> float:
    return ( self._vsys_val * VSYS_MULTIPLIER )
  
  # Returns an integer 0-100 representing current battery level
  # Returns None if this can't be read right now (eg. due to VBUS)
  def batt_pc(self) -> int:
    v = self.voltage_stable()
    
    # Are we powered via VBUS (Pico USB)?
    if v >= BATT_USB:
      return None
    
    # Clamp to limits
    if v >= BATT_MAX:
      v = BATT_MAX
    elif v <= BATT_MIN:
      v = BATT_MIN
    
    # Return a percentage
    return round( 100 * ( v - BATT_MIN ) / ( BATT_MAX - BATT_MIN ) )
  
  # Start a loop, clear the eink, exit
  # Only used to clear the display without running the app
  # 
  # from gadget_hw import HW
  # hw = HW()
  # hw.clear_eink()
  #
  def clear_eink(self):
    asyncio.run( self._clear_eink() )
  
  # Only used by clear_eink() above
  # NOT FOR USE within the app
  async def _clear_eink(self):
    await self.eink.clear() # Send a white framebuffer
    await self.eink.refresh() # Update the display
