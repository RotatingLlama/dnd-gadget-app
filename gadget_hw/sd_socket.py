
# SD Socket class
# Handles plug and unplug events
# Sets up SD card automatically when plugged
#
# T. Lloyd
# 03 Sep 2025

from . import sdcard
#import vfs
#from gc import collect
#from machine import disable_irq, enable_irq
from time import ticks_ms, ticks_diff #, sleep_ms
from micropython import const, schedule

_DEBOUNCE_TIME = const(40) # In ms

class SD_Socket:
  
  def __init__( self, spi, cs, det, baudrate=1320000, on_plug=lambda:None, on_unplug=lambda:None ):
    
    # Record
    self._spi = spi
    self._cs = cs
    self._det = det
    self._baud = baudrate
    self._f_plug = lambda:None
    self._f_unplug = lambda:None
    
    # Set up the detector pin
    self._det.init( mode=det.IN, pull=det.PULL_UP )
    self._det.irq( handler=self._isr_det, trigger=(det.IRQ_FALLING | det.IRQ_RISING) ) #, wake=None)#, hard=True )
    
    # Last valid transition (of detector switch)
    self._lvt = ticks_ms()
    
    # Need this for the ISR to work
    self._plug_ref = self._plug 
    
    # Set things up without calling ther callbacks
    self._plug(0)
    
    # Set up the callbacks (if any)
    self.init( on_plug, on_unplug )
  
  # Called by the card detect ISR, handles plug/unplug events
  def _plug(self,x) -> None:
    if self.has_card():
      self._init_card()
      self._f_plug()
    else:
      self.card = None
      self._f_unplug()
  
  # Set up callbacks
  def init(self, on_plug, on_unplug ) -> None:
    self._f_plug = on_plug
    self._f_unplug = on_unplug
  
  # Is there a card?
  def has_card(self) -> bool:
    # self._det is low when card is present, high when it's not
    return not self._det.value()
  
  # Sets up the SD card object.  Messes with SPI bus (before putting it back like it was)
  def _init_card(self) -> None:
    self.card = sdcard.SDCard( spi=self._spi, cs=self._cs, baudrate=self._baud )
  
  # Interrupt Service Routine for the card detect switch
  def _isr_det(self, pin ):
    
    # Are we in a bounce?
    if ticks_diff( ticks_ms(), self._lvt ) < _DEBOUNCE_TIME:
      return
    
    # Record the new transition time
    self._lvt = ticks_ms()
    
    # Get out of this ISR
    schedule(self._plug_ref, 0)
