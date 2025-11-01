# Logic to drive Waveshare e-ink displays
#
# 02 Feb 2025

from machine import Pin, SPI
from struct import unpack
import time
import gc

# PUBLIC METHODS:
# init_panel()  Start up display
# clear()       Send white to the display's framebuffer
# send()        Update the display's framebuffer
# border()      Set the border colour
# refresh()     Update the display with what's been sent
# sleep()       Power down display

# Most driver code is in here
class _HWIF:
  
  def __init__( self, width, height ):
    
    # Setup SPI
    # I originally had 400 kHz - not sure where this came from
    # Python examples from Waveshare use 4 MHz - seems to work ok
    # Datasheet says read cycle time is 350ns = 2.8 MHz
    #               write cycle time is 70ns = 14.2 MHz
    # RP2040 can go up to 62.5 MHz in theory, but without careful PCB design above a few MHz the signal quality may degrade
    self.spi = SPI(0, polarity=0, phase=0, baudrate=4000000, sck=Pin(2), mosi=Pin(3), miso=Pin(4))

    # Define the pins
    self.Reset = Pin( 5,  mode=Pin.OUT, value=1 )
    self.DC    = Pin( 21, mode=Pin.OUT, value=0 )
    self.CS    = Pin( 20, mode=Pin.OUT, value=1 )
    self.Busy  = Pin( 15, mode=Pin.IN  )
    
    # Keep track of display's power state
    self.power = 0
    
    # Geometry
    self.width = width
    self.height = height
    
    # Set up the (dumb) framebuffers
    self.fb_size = self.width * self.height // 8

  # Toggle Reset pin
  def _reset(self):
    self.Reset(1) # Reset high
    time.sleep_ms(20) 
    self.Reset(0) # Reset low (active)
    time.sleep_ms(2)
    self.Reset(1) # Reset high
    time.sleep_ms(20)   
  
  # Send a command
  def _send_command(self, cmd):
    self.DC(0)
    self.CS(0)
    self.spi.write( bytes([cmd]) )
    self.CS(1)
  
  # Send a data byte
  def _send_data(self, data):
    self.DC(1)
    self.CS(0)
    self.spi.write( bytes([data]) )
    self.CS(1)
  
  # Send a buffer
  def _send_buffer(self,buf):
    self.DC(1)
    self.CS(0)
    self.spi.write( buf )
    self.CS(1)
  
  # Blocks until the Busy pin goes high
  def _wait_busy(self,msg='e-paper'):
    print( 'Waiting for {}... '.format(msg), end='' )
    while( self.Busy.value() == 0 ):      # 0: busy, 1: idle
      time.sleep_ms(5)
    time.sleep_ms(200)
    print('Done.')
  
  # Updates the display
  # Slightly slower than the default (auto) version.
  # Allows control over BTST.
  def _refresh_manual(self):
    
    self._send_command(0x04) # PON - Power ON
    self._wait_busy('power on')
    self.power = 1
    
    self._send_command(0x06) # BTST - Booster Soft Start
    self._send_buffer(bytes([
      0x6f, # BT_PHA = 01 101 111 : 20ms / S6 / 6.58us
      0x1f, # BT_PHB = 00 011 111 : 10ms / S4 / 6.58ms
      0x17, # BT_PHC = 00 010 111 : 10ms / S3 / 6.58us
      0x27  # What's this for??
    ]))
    '''
    self._send_data(0x6F)
    self._send_data(0x1F)
    self._send_data(0x17)
    self._send_data(0x27)
    '''
    time.sleep_ms(200)
    
    # Refresh display according to SRAM and LUT (update the picture)
    self._send_command(0x12) # DRF - Display Refresh
    self._send_data(0X00) # needed?
    self._wait_busy('refresh')
    
    self._send_command(0x02) # POF - Power OFF
    self._send_data(0X00) # needed?
    self._wait_busy('power off')
    self.power = 0
  
  # Send two separate buffers simultaneously
  def _send_kr(self, k, r):
    
    # Send the black buffer
    self._send_command(0x10) # DTM1 - Display Start Transmission 1 (black data)
    self._send_buffer(k)
    
    # Send the red buffer
    self._send_command(0x13) # DTM2 - Display Start Transmission 2 (red data)
    self._send_buffer(r)
  
  # Resets and configures the panel, ready for use
  def init_panel(self):
    
    # EPD hardware init start
    self._reset()
    self._wait_busy('hardware reset')
    time.sleep_ms(30)
    
    self._send_command(0x04) # PON - Power ON
    time.sleep_ms(100)  
    self._wait_busy('power on')
    self.power = 1
    
    self._send_command(0x00) # PSR - Panel Setting
    self._send_buffer(bytes([
      0x03, # 0b00000011 : RES=0b00, REG=0, KW/R=0, UD=0, SHL=0, SHD_N=1, RST_N=1
      0x0D  # 0b00001101 : VCMZ=0, TS_AUTO=1, TIEG=1, NORG=0, VCM_LUTZ=1
    ]))
    '''
    self._send_data(0x03)
    self._send_data(0x0D)
    '''
    
    self._send_command(0x61) # TRES - Resolution Setting
    self._send_buffer(bytes([
      0xf0, # HRES : 0xF0 = 240
      0x01, # VRES byte 0
      0x68 # VRES byte 1 : 0x0168 = 360
    ]))
    '''
    self._send_data(0xF0)
    self._send_data(0x01)
    self._send_data(0x68)
    '''
    
    # Soft start period = 00 = 10ms (default)
    # Driving strength = 101 = Strength 6 (default : 010 Strength 3)
    # Minimum OFF time = 111 = 6.58 us (default)
    # Datasheet default is 0x17 for all 3 : 10ms / S3 / 6.58us
    self._send_command(0x06) # BTST - Booster Soft Start
    self._send_buffer(bytes([
      0x2f, # BT_PHA = 0b00101111
      0x2f, # BT_PHB = 0b00101111
      0x2f, # BT_PHC = 0b00101111
    ]))
    '''
    self._send_data(0x2F)
    self._send_data(0x2F)
    self._send_data(0x2F)
    '''
    
    self._wait_busy('setup')
    return 0
  
  # Updates the display
  def refresh(self,sleep=False):
    
    # PON, DRF, POF, and optionally DSLP
    self._send_command(0x17) # AUTO - Auto Sequence
    
    # Turn off afterwards?
    if sleep:
      self._send_data(0Xa7) # PON, DRF, POF, DSLP
    else:
      self._send_data(0Xa5) # PON, DRF, POF
    
    # Wait
    self._wait_busy('refresh')
    
    # Update this
    self.power = 0
  
  # Puts panel into Deep Sleep
  def sleep(self):
    
    self._send_command(0x07) # DSLP - Deep sleep
    self._send_data(0xA5) # Check code, must be 0xA5
    
    time.sleep_ms(2000) # needed?
    
    # Reset low = active
    self.Reset(0)
    self.DC(0)
  
  # Sets the border colour
  def border(self,c=0):
    
    # Input validation
    assert type(c) is int
    assert c >= 0
    assert c <= 3
    
    # VCOM timings.  Leave as is (0x07 = binary .... 0111)
    CDI = 0x07
    
    # Data polarity, swaps colours around.  Leave as is (0x00 = binary ..00 ....)
    DDX = 0x00
    
    # Border colour list
    # 0 : VBD = 10.. ...., border = white
    # 1 : VBD = 11.. ...., border = black
    # 2 : VBD = 01.. ...., border = red
    # 3 : VBD = 00.. ...., border = floating
    VBD = bytes([128,192,64,0])
    
    self._send_command(0x50) # Set interval between VCOM and data
    self._send_data( VBD[c] | DDX | CDI )
  
  # Set display to partial update mode
  def setPartial(self, x0, y0, w, h ):
    
    raise NotImplementedError('Partial display functionality does not yet work properly')
    # Partial window is created, but in the wrong place
    # During refresh, the lines intersected by the window produce unexpected colours
    #
    # If these things can be fixed, the whole driver should be updated to become 'window-aware'
    # ie. update height and width properties to equal the window, only send a window-sized buffer, etc.
    
    # Input validation
    assert type(x0) is int
    assert x0 % 8 == 0
    assert x0 >= 0
    assert type(y0) is int
    assert y0 >= 0
    assert type(w) is int
    assert w % 8 == 0
    assert w > 0
    assert type(h) is int
    assert h > 0
    
    # Array we'll send
    data = bytearray(7) # hstart, hend, vstart1, vstart0, vend1, vend0, partial
    
    # Horizontal bounds (inclusive)
    data[0] = x0         # HRST
    data[1] = x0 + w - 1 # HRED
    
    # More validation
    assert data[1] < self.width
    assert (y0+h) < self.height
    
    # v uses two bytes
    data[2] = ( y0 & 256 ) >> 8
    data[3] = y0 & 255
    data[4] = ( (y0+h) & 256 ) >> 8
    data[5] = (y0+h) & 255
    
    # Set partial to true
    data[6] = 1
    
    # Send the parameters
    self._send_command(0x90) # PTL - Partial Window
    self._send_buffer( data )
    
    # Enable partial mode
    self._send_command(0x91) # PTIN - Partin IN
    self._wait_busy('partial setting')
  
  # Full display updating
  def unsetPartial(self):
    # See setPartial()
    raise NotImplementedError('Partial display functionality does not yet work properly')
    self._send_command(0x92) # PTOUT - Partial Out
    
# Normal version
class Eink(_HWIF):
  
  def __init__(self,width,height):
    
    # Do the base class init()
    super().__init__(width,height)
    
    # Set up the black and red framebuffers
    self.fb_k = bytearray( self.fb_size )
    self.fb_r = bytearray( self.fb_size )
  
  # Send an image from a GS2_HMSB (2bit) buffer.
  def send(self,buf):
    
    # Order of pixels in two bytes
    po = bytes([3,2,1,0,7,6,5,4])
    
    # Step through the output buffers, one byte at a time
    for i in range( self.fb_size ):
      
      # Two bytes of the image will become one byte per buffer
      data = unpack( '>H', buf[ (i*2) : (i*2) +2 ] )[0]
      
      # Step through per pixel
      for j in range(8):
        
        # 2-bit pixel value
        px = ( data >> (14-(po[j]*2)) ) & 3
        
        # 00 = both off  = white
        # 01 = red off   = black
        # 10 = black off = red
        # 11 = both on (invalid)
        
        # Prevent invalid condition
        if px == 3:
          px = 0
        
        # Extract both channels from the pixel
        px_k = px & 1         # 1 = black
        px_r = ( px & 2 ) //2 # 2 = red
        
        # Update the output buffers
        self.fb_k[i] = self.fb_k[i] | ( px_k << (7-j) )
        self.fb_r[i] = self.fb_r[i] | ( px_r << (7-j) )
    
    # Send the data
    self._send_kr( self.fb_k, self.fb_r )
  
  # Fill white
  def clear(self):
    
    # Fill the framebuffer with zeroes
    for i in range( len(self.fb_k) ):
      self.fb_k[i] = 0
    
    # Send to both channels
    self._send_kr( self.fb_k, self.fb_k )

# Memory-saving version
# Does not allocate its own buffers, so saves about 21 kB of memory
# The image buffer provided to show() will be used instead, and will not be preserved.
class Eink_lowmem(_HWIF):
  
  def __init__(self,width,height):
    
    # Do the base class init()
    super().__init__(width,height)
  
  # Send an image from a GS2_HMSB (2bit) buffer (must be type bytearray)
  # Low memory version.  Input buffer will get OVERWRITTEN!
  def send(self,buf):
    
    # Check this (must be mutable buffer type)
    assert type(buf) is bytearray
    
    # Order of pixels in two bytes
    po = bytes([3,2,1,0,7,6,5,4])
    
    # Temporary store for pixel values.  Avoids repeated mem allocation for each pixel.
    px = bytearray(3)
    
    # Step through the output buffers, one byte at a time
    for i in range( self.fb_size ):
      
      # Two bytes of the image will become one byte per buffer
      data = unpack( '>H', buf[ (i*2) : (i*2) +2 ] )[0]
      
      # We're going to reuse the input buffer to store the output images
      # Clear the part we've just read to zero, in preparation
      buf[i*2] = 0
      buf[(i*2)+1] = 0
      
      # Step through per pixel
      for j in range(8):
        
        # 2-bit pixel value
        px[0] = ( data >> (14-(po[j]*2)) ) & 3
        
        # 00 = both off  = white
        # 01 = red off   = black
        # 10 = black off = red
        # 11 = both on (invalid)
        
        # Prevent invalid condition
        if px[0] == 3:
          px[0] = 0
        
        # Extract both channels from the pixel
        px[1] = px[0] & 1         # 1 = black
        px[2] = ( px[0] & 2 ) //2 # 2 = red
        
        # Store the black byte
        buf[i*2] = buf[i*2] | ( px[1] << (7-j) )
        
        # Store the red byte
        buf[(i*2)+1] = buf[(i*2)+1] | ( px[2] << (7-j) )
    
    # Tidy up memory
    del po, px, j, data
    gc.collect()
    
    # Prevent repeated allocation during transmission
    onebyte = bytearray(1)
    
    # Send black data
    self._send_command(0x10) # DTM1 - Display Start Transmission 1 (black data)
    self.DC(1)
    self.CS(0)
    for i in range(0,len(buf),2):
      onebyte[0] = buf[i]
      self.spi.write( onebyte )
    self.CS(1)
    
    # Send the red data
    self._send_command(0x13) # DTM2 - Display Start Transmission 2 (red data)
    self.DC(1)
    self.CS(0)
    for i in range(1,len(buf),2):
      onebyte[0] = buf[i]
      self.spi.write( onebyte )
    self.CS(1)
    
    # Tidy up memory
    del onebyte, i
    gc.collect()
  
  # Fill white
  def clear(self):
    
    # 1-byte buffer to repeatedly send
    onebyte = bytes(1)
    
    # Send black zeroes
    self._send_command(0x10) # DTM1 - Display Start Transmission 1 (black data)
    self.DC(1)
    self.CS(0)
    for i in range(self.fb_size):
      self.spi.write( onebyte )
    self.CS(1)
    
    # Send red zeroes
    self._send_command(0x13) # DTM2 - Display Start Transmission 2 (red data)
    self.DC(1)
    self.CS(0)
    for i in range(self.fb_size):
      self.spi.write( onebyte )
    self.CS(1)
    
    # Tidy up memory
    del onebyte, i
    gc.collect()
      
  
  