from . import sdcard
import vfs
from gc import collect
from machine import disable_irq, enable_irq
from time import sleep_ms

# TODO:
# Run deinit_card() on unplug

class SD_Socket:
  
  def __init__( self, spi, cs, det ):
    
    self.spi = spi
    self.cs = cs
    self.det = det
    self.det.init( mode=det.IN, pull=det.PULL_UP )
    
    # self.det is low when card is present, high when it's not
    
    self.card = None
    self.vfs = None
    
    # IRQ stuff, debouncing
    self.present = not self.det.value()
    self.irq_state = 0
    self.deinit_ref = self.deinit_card # Need to do this for the ISR to work
    self.det.irq( handler=self._isr_det, trigger=(det.IRQ_FALLING | det.IRQ_RISING) )#, wake=None)#, hard=True )
    
    # If there's a card, set it up now
    if self.present:
      self.init_card()
    
  
  def mount( self, *args, **kwargs ):
    
    # Sanity
    if not self.present:
      raise OSError('No card')
    
    # Make sure we're set up
    if self.vfs is None:
      self.init_card()
    
    # Do
    vfs.mount ( self.vfs, *args, **kwargs )
  
  def umount(self):
    
    # Sanity
    if self.vfs is None:
      raise OSError('Nothing to unmount')
    
    # Catch 'already unmounted' errors
    try:
      vfs.umount( self.vfs )
    except OSError: # EINVAL
      pass
      
  # Set the card up when it's plugged
  def init_card(self):
    
    # Sanity
    if not self.present:
      raise OSError('No card')
    
    # Initialise the card
    if self.card is None:
      self.card = sdcard.SDCard( self.spi, self.cs )
    
    # Set up the filesystem object
    if self.vfs is None:
      self.vfs = vfs.VfsFat(self.card)
  
  # Prepare the card to be unplugged
  def deinit_card(self,unused=None):
    
    # Try to umount, regardless of card status
    try:
      self.umount()
    except OSError:
      pass
    
    # Tidy up the card if we have a ref to it
    if self.card is not None:
      
      # If the card is still here
      if self.present:
        
        # Sync
        self.card.ioctl(3,None)
        
        # Add a 200ms wait here for card to finish write op?
        # https://forum.arduino.cc/t/how-long-time-does-is-take-to-write-to-an-sd/107499
        
      # Shut down
      self.card.ioctl(2,None)
    
    # Destroy objects
    self.vfs = None
    self.card = None
    collect()
  
  # Interrupt service routine for plug/unplug event
  def _isr_det(self, pin):
    self.irq_state = disable_irq()
    sleep_ms(40)
    enable_irq( self.irq_state )
    self.present = not pin.value()
    
    # This causes MP to lock up.  Unclear why.
    # https://docs.micropython.org/en/latest/library/micropython.html#micropython.schedule
    # https://docs.micropython.org/en/latest/reference/isr_rules.html#creation-of-python-objects
    # https://docs.micropython.org/en/latest/library/micropython.html#micropython.alloc_emergency_exception_buf
    #if not self.present:
    #  micropython.schedule(self.deinit_ref, 0)