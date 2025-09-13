
# SD Socket class
# Handles plug and unplug events
# Sets up SD card automatically when plugged
#
# T. Lloyd
# 13 Sep 2025

from . import sdcard
from time import ticks_ms, ticks_diff, sleep_ms
from micropython import const, schedule

# For card detect switch
_DEBOUNCE_TIME = const(100) # In ms.  Was 40, didn't seem to be enough
_SETTLE_TIME = const(30) # In ms.  How long to wait between plug and card init.  20 is borderline, 30 ok if inserted quickly.

class SD_Socket:
  '''
    INIT ARGS
    
      spi       - SPI object
      cs        - Pin for SPI chip select
      det       - Pin that will be pulled low when a card is present
      baudrate  - Set the SPI bus to this baud rate after card init
      on_plug   - Function that will be called when the card is plugged in.  It is not passed any args.
      on_unplug - Function that will be called when the card is unplugged.  It is not passed any args.
    
    
    METHODS
    
      init() - Sets the plug/unplug callbacks.  Called automatically by __init__().  Returns nothing.
        on_plug   - Function that will be called when the card is plugged in.  It is not passed any args.
        on_unplug - Function that will be called when the card is unplugged.  It is not passed any args.
        
      
      has_card() - Returns bool indicating card presense
      
      
    PROPERTIES
      
      card - SDCard object if present, else None
  '''
  
  def __init__( self, spi, cs, det, baudrate=1320000, on_plug=lambda:None, on_unplug=lambda:None ):#_event=lambda:None ):
    
    # Record
    self._spi = spi
    self._cs = cs
    self._det = det
    self._baud = baudrate
    #self._f_plug_event = lambda:None
    self._f_plug = lambda:None
    self._f_unplug = lambda:None
    self._badcard = False
    
    # Set up the detector pin
    self._det.init( mode=det.IN, pull=det.PULL_UP )
    self._det.irq( handler=self._isr_det, trigger=(det.IRQ_FALLING | det.IRQ_RISING), hard=True ) #, wake=None)
    
    # Last valid transition (of detector switch)
    self._lvt = ticks_ms()
    
    # Need this for the ISR to work
    self._plug_ref = self._plug 
    
    # Set things up without calling ther callbacks
    self._plug(0)
    
    # Set up the callbacks (if any)
    self.init( on_plug, on_unplug )#_event )
  
  # Called by the card detect ISR, via schedule(), handles plug/unplug events
  def _plug(self,x) -> None:
    #print(x)
    if self.has_card():
      print('sd_s: PLUG')
      sleep_ms(_SETTLE_TIME)
      self._init_card()
      self._f_plug()
    else:
      print('sd_s: UNPLUG')
      self.card = None
      self._badcard = False
      self._f_unplug()
    #self._f_plug_event()
  
  # Set up callback
  def init(self, on_plug, on_unplug ): #_event ) -> None:
    #self._f_plug_event = on_plug_event
    self._f_plug = on_plug
    self._f_unplug = on_unplug
  
  # Is there a card?
  def has_card(self) -> bool:
    # self._det is low when card is present, high when it's not
    return ( not self._det.value() ) and ( not self._badcard )
  
  # Sets up the SD card object.  Messes with SPI bus (before putting it back like it was)
  def _init_card(self) -> None:
    try:
      self.card = sdcard.SDCard( spi=self._spi, cs=self._cs, baudrate=self._baud )
    except OSError:
      print('Could not init SD card!')
      self._badcard = True
      self.card = None
      
  
  # Interrupt Service Routine for the card detect switch
  def _isr_det(self, pin ):
    
    # Are we in a bounce?
    if ticks_diff( ticks_ms(), self._lvt ) < _DEBOUNCE_TIME:
      return
    
    # Record the new transition time
    self._lvt = ticks_ms()
    
    # Get out of this ISR
    schedule(self._plug_ref, pin.value() ) # Ref to self._plug()
