# SD Socket class
# Handles plug and unplug events
# Sets up SD card automatically when plugged
#
# T. Lloyd
# 24 Nov 2025

import asyncio
from time import ticks_ms, ticks_diff
from micropython import const, schedule
from . import sdcard

_DEBOUNCE_TIME = const(100) # In ms.  For card detect switch.  40 is not quite enough: 100 is safe choice.
_SETTLE_TIME = const(30) # In ms.  How long to wait after plug, before first attempting card init.  20 is borderline, 30 is ok if inserted quickly.
_INIT_TRIES = const(10) # How many times to try init before giving up
_INIT_RETRY_TIME = const(100) # In ms.  How long to wait after a failed init before trying again

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
    
      (none)
      
      
    PROPERTIES
      
      card - The SDCard object if a card is present and ready, otherwise None
      card_absent - asyncio Event that fires when the card is ejected
      card_present - asyncio Event that fires when the card is inserted
      card_ready - asyncio Event that fires when the card is initialised and ready to use
      card_state_known - asyncio Event that fires as soon as a plug/unplug event resolves to a known condition (ok or ng)
  '''
  
  def __init__( self, spi, cs, det, baudrate=1320000 ):
    
    # Record
    self._spi = spi
    self._cs = cs
    self._det = det
    self._baud = baudrate
    
    # Card state tracking
    self._plug_event_tsf = asyncio.ThreadSafeFlag()
    self.card_state_known = asyncio.Event()
    self.card_absent = asyncio.Event()
    self.card_present = asyncio.Event()
    self.card_ready = asyncio.Event()
    self._plug_tasks = asyncio.create_task(asyncio.gather(
      self._init_waiter(),
      self._plug_waiter()
    ))
    
    # Set up the detector pin
    self._det.init( mode=det.IN, pull=det.PULL_UP )
    self._det.irq( handler=self._isr_det, trigger=(det.IRQ_FALLING | det.IRQ_RISING), hard=True ) #, wake=None)
    
    # Last valid transition (of detector switch)
    self._lvt = ticks_ms()
    
    # Need this for the ISR to work
    self._plug_ref = self._plug 
    
    # Trigger the plug event once, to get the startup state
    self._plug(0)
  
  # Called by the card detect ISR, via schedule()
  # Sets _plug_event_tsf only.
  def _plug(self,x) -> None:
    self._plug_event_tsf.set()
  
  # Reacts to _plug_event_tsf, set by _plug()
  # Sets the card_present and card_absent events.
  async def _plug_waiter(self):
    while True:
      await self._plug_event_tsf.wait()
      self._plug_event_tsf.clear()
      self.card_state_known.clear()
      
      # Wait the debounce time before reading the switch
      # (We get triggered on the very first transition, and may still be bouncing)
      await asyncio.sleep_ms( _DEBOUNCE_TIME )
      
      # Set/clear the appropriate events
      if self._det_sw_state():
        #print('_PW PLUG')
        self.card_absent.clear()
        self.card_present.set()
      else:
        #print('_PW UNPLUG')
        self.card_present.clear()
        self.card_ready.clear()
        self.card_absent.set()
        self.card_state_known.set()
  
  # Reacts to card_present and card_absent events, set by _plug_waiter()
  # Sets the card_ready event.
  # Destroys the card object.
  async def _init_waiter(self):
    while True:
      await self.card_present.wait()
      
      # Wait for the interface to settle after being plugged
      await asyncio.sleep_ms( _SETTLE_TIME )
      
      # Try to init
      tries = 0
      while tries < _INIT_TRIES:
        
        # This will try to set up the card, and not complain if it fails
        self.try_init_card()
        tries += 1
        
        # If it worked, tell everyone and then exit this try-loop
        if self.card is not None:
          self.card_ready.set()
          break
        
        # Wait a little while before trying again
        await asyncio.sleep_ms( _INIT_RETRY_TIME )
      
      # At this point, either it's inited successfully or we've given up on it
      self.card_state_known.set()
      
      # Did it init successfully?
      if self.card is None:
        print(f'SD present but faulty, giving up after {_INIT_TRIES} tries :(')
      
      # Now wait for the card to go away before waiting again for it to appear
      await self.card_absent.wait()
      
      # Destroy the card object
      self.card = None
  
  # Sets up the SD card object.  Messes with SPI bus (before putting it back like it was)
  def try_init_card(self) -> None:
    try:
      self.card = sdcard.SDCard( spi=self._spi, cs=self._cs, baudrate=self._baud )
    except OSError:
      print('SD init attempt failed')
      self.card = None
  
  # Low-level card detect switch state.  Returns True when switch is closed (card present)
  def _det_sw_state(self) -> bool:
    # self._det is low when card is present, high when it's not
    return not self._det.value()
  
  # Interrupt Service Routine for the card detect switch
  def _isr_det(self, pin ):
    
    # Are we in a bounce?
    if ticks_diff( ticks_ms(), self._lvt ) < _DEBOUNCE_TIME:
      return
    
    # Record the new transition time
    self._lvt = ticks_ms()
    
    # Get out of this ISR
    # By the time this ISR runs, the switch may have already bounced - so we can't check its state here
    # Also MP (1.26) doesn't reveal which event (rising|falling) triggered the ISR
    schedule(self._plug_ref, 0 ) # Ref to self._plug()
  