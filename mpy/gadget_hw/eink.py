# Logic to drive Waveshare e-ink displays
#
# T. Lloyd
# 07 Nov 2025

# Standard libraries
from machine import Pin
import micropython
from micropython import const
import asyncio
from gc import collect as gc_collect
from time import sleep_ms

# Our libraries
from img import FrameBuffer, GS2_HMSB

# PUBLIC METHODS:
# init_panel()  Start up display
# clear()       Send white to the display's framebuffer
# send()        Update the display's framebuffer
# border()      Set the border colour
# refresh()     Update the display with what's been sent
# sleep()       Power down display

_FB_FMT = GS2_HMSB # fb.GS2_HMSB #fb.framebuf.GS2_HMSB
_BPP = const(2)

# 
#class EInk(fb.FB):
class EInk(FrameBuffer):
  
  def __init__( self, width, height, spi, cs, dc, busy, reset, rot=0 ):
    
    # Record geometry
    self.width = width
    self.height = height
    #
    assert type(rot) is int
    assert rot >= 0
    assert rot < 4
    self.rot = rot
    
    # Setup SPI
    # I originally had 400 kHz - not sure where this came from
    # Python examples from Waveshare use 4 MHz - seems to work ok
    # Datasheet for eink controller chip says up to 20 MHz
    # Datasheet for eink display says read cycle time is 350ns = 2.8 MHz
    #                                write cycle time is 70ns = 14.2 MHz
    # RP2040 can go up to 62.5 MHz in theory, but without careful PCB design above a few MHz the signal quality may degrade
    #self.spi = SPI(0, polarity=0, phase=0, baudrate=4000000, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
    self.spi = spi

    # Define the pins
    self.CS    = cs
    self.DC    = dc
    self.Busy  = busy
    self.Reset = reset
    
    # Init the pins
    self.CS.init(  mode=Pin.OUT, value=1 )
    self.DC.init(    mode=Pin.OUT, value=0 )
    self.Busy.init(  mode=Pin.IN  )
    self.Reset.init( mode=Pin.OUT, value=1 )
    
    # Set up the return-from-busy handler
    self.unbusy = asyncio.Event()
    self.lock = asyncio.Lock()
    self.unbusy.set()
    self._busy_tsf = asyncio.ThreadSafeFlag()
    self._unbusy_tsf = asyncio.ThreadSafeFlag()
    self._busy_task = asyncio.create_task( self._busy_waiter() )
    self.Busy.irq( handler=self._isr_busy, trigger=(Pin.IRQ_RISING|Pin.IRQ_FALLING) ) # Triggers when eink stops being busy
    
    # Keep track of display's power state
    self.power = 0
    
    # Size, in bytes, of a monochrome fb
    #self.kr_fb_size = width * height // 8
    
    # Precaution before allocating buffer
    gc_collect()
    
    self.buf_size = ( width * height * _BPP ) // 8
    self.buf = bytearray( self.buf_size )
  
    # init the framebuffer
    super().__init__( self.buf, width, height, _FB_FMT )
  
  # ISR for busy pin, responds to both transitions
  # Sets/clears _busy_tsf and _unbusy_tsf
  def _isr_busy(self,pin):
    if pin.value() == 0: # busy
      #print('Eink is busy')
      self._unbusy_tsf.clear()
      self._busy_tsf.set()
    else:                # not busy
      #print('Eink is not busy')
      self._busy_tsf.clear()
      self._unbusy_tsf.set()
  
  # Waits for _busy_tsf and _unbusy_tsf
  # Sets/clears unbusy event
  # Runs as coro
  async def _busy_waiter(self):
    while True:
      await self._busy_tsf.wait()
      self.unbusy.clear()
      #print('async EInk Busy')
      await self._unbusy_tsf.wait()
      self.unbusy.set()
      #print('async Eink Unbusy')
  
  # Async waits for unbusy event to fire
  # Then async waits another 200ms
  async def wait_busy(self):
    
    # Make sure _busy_waiter() has time to update the flag before we check it
    if self.unbusy.is_set():
      await asyncio.sleep_ms(200)
    
    # Wait for the display to be unbusy
    await self.unbusy.wait()
    
    # Wait a little bit more
    await asyncio.sleep_ms(200)
  
  # Just polls the Busy pin until it goes high, then waits 200ms
  # Not async, so BLOCKS the whole time
  def _wait_busy_blocking(self):
    while( self.Busy.value() == 0 ): # 0: busy, 1: idle
      sleep_ms(5)
    sleep_ms(200)
  
  # Toggle Reset pin
  def _reset(self):
    self.Reset(1) # Reset high
    sleep_ms(20) 
    self.Reset(0) # Reset low (active)
    sleep_ms(2)
    self.Reset(1) # Reset high
    sleep_ms(20)   
  
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
  
  # Updates the display
  # Slightly slower than the default (auto) version.
  # Allows control over BTST.
  async def _refresh_manual(self):
    
    # Check we're not in the middle of something
    await self.unbusy.wait()
    
    self._send_command(0x04) # PON - Power ON
    await self.wait_busy()
    self.power = 1
    
    self._send_command(0x06) # BTST - Booster Soft Start
    self._send_buffer(bytes([
      0x6f, # BT_PHA = 01 101 111 : 20ms / S6 / 6.58us
      0x1f, # BT_PHB = 00 011 111 : 10ms / S4 / 6.58ms
      0x17, # BT_PHC = 00 010 111 : 10ms / S3 / 6.58us
      0x27  # What's this for??
    ]))
    # Individual commands per byte cycles CS pin, which is recommended by datasheet (p43)
    '''
    self._send_data(0x6F)
    self._send_data(0x1F)
    self._send_data(0x17)
    self._send_data(0x27)
    '''
    await asyncio.sleep_ms(200)
    
    # Refresh display according to SRAM and LUT (update the picture)
    self._send_command(0x12) # DRF - Display Refresh
    self._send_data(0X00) # needed?
    await self.wait_busy()
    
    self._send_command(0x02) # POF - Power OFF
    self._send_data(0X00) # needed?
    await self.wait_busy()
    self.power = 0
  
  # Resets and configures the panel, ready for use
  # Uses blocking waits because may be called before async loop is ready
  def init_panel(self):
    
    # EPD hardware init start
    self._reset()
    sleep_ms(30)
    self._wait_busy_blocking()
    
    self._send_command(0x04) # PON - Power ON
    sleep_ms(100)
    self._wait_busy_blocking()
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
    
    self._wait_busy_blocking()
    return 0
  
  # Updates the display
  # DSLP = Unwakeable without hw reset?  Datasheet p20
  # Should set all pins low.  Wake by toggling Reset - datasheet p54
  async def refresh(self,sleep=True):
    
    # Check we're not in the middle of something
    await self.lock.acquire()
    await self.unbusy.wait()
    
    # PON, DRF, POF, and optionally DSLP
    self._send_command(0x17) # AUTO - Auto Sequence
    
    # Turn off afterwards?
    if sleep:
      self._send_data(0Xa7) # PON, DRF, POF, DSLP
    else:
      self._send_data(0Xa5) # PON, DRF, POF
    
    # Wait
    await self.wait_busy()
    
    # Update this
    self.power = 0
    
    self.lock.release()
  
  # Puts panel into Deep Sleep
  # Unwakeable without hw reset?  Datasheet p20
  # Should set all pins low.  Wake by toggling Reset - datasheet p54
  async def sleep(self):
    
    # Check we're not in the middle of something
    await self.lock.acquire()
    await self.unbusy.wait()
    
    self._send_command(0x07) # DSLP - Deep sleep
    self._send_data(0xA5) # Check code, must be 0xA5
    
    await asyncio.sleep_ms(2000) # needed?
    
    # Reset low = active
    self.Reset(0)
    self.DC(0)
    
    self.lock.release()
  
  # Sets the border colour
  async def border(self,c=0):
    
    # Check we're not in the middle of something
    await self.lock.acquire()
    await self.unbusy.wait()
    
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
    
    self.lock.release()
  
  # Set display to partial update mode
  # TODO: Update in partial mode, leave partial, then refresh??
  async def setPartial(self, x0, y0, w, h ):
    
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
    await self.wait_busy()
  
  # Full display updating
  async def unsetPartial(self):
    # See setPartial()
    raise NotImplementedError('Partial display functionality does not yet work properly')
    self._send_command(0x92) # PTOUT - Partial Out
  
  # Send the framebuffer to the display
  async def send(self):
    
    # Check we're not in the middle of something
    await self.lock.acquire()
    await self.unbusy.wait()
    
    # Cache for speed
    r = self.rot
    
    # Select the appropriate sender
    if r == 0:
      self._send_0()
    elif r == 1:
      self._send_1()
    elif r == 2:
      self._send_2()
    else:
      self._send_3()
    
    # Tidy up
    del r
    gc_collect()
    
    self.lock.release()
  
  # Sends a blank white framebuffer to the display
  async def clear(self):
    
    # Check we're not in the middle of something
    await self.lock.acquire()
    await self.unbusy.wait()
    
    # 1-byte buffer to repeatedly send
    onebyte = bytes(1)
    
    # Send black zeroes
    self._send_command(0x10) # DTM1 - Display Start Transmission 1 (black data)
    self.DC(1)
    self.CS(0)
    for i in range(self.buf_size//2):
      self.spi.write( onebyte )
    self.CS(1)
    
    # Send red zeroes
    self._send_command(0x13) # DTM2 - Display Start Transmission 2 (red data)
    self.DC(1)
    self.CS(0)
    for i in range(self.buf_size//2):
      self.spi.write( onebyte )
    self.CS(1)
    
    # Tidy up memory
    del onebyte, i
    gc_collect()
    
    self.lock.release()
  
  # Send with portrait rotation 0
  @micropython.viper
  def _send_0(self):
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = ptr16(self.buf)
    spi_w = self.spi.write
    
    # Data length
    olen:int = int(self.width) * int(self.height) // 8
    
    # Output commands
    cmd = ptr8(bytes([ 0x10, 0x13 ]))
    
    # Masks to select black/red bits of input byte
    mask = ptr16(bytes([ 0x55, 0x55, 0xaa, 0xaa ]))
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    outp = ptr8(out)
    
    # Do once per colour
    c:int = 0
    while c <= 1:
      
      # Send data command (black/red)
      self._send_command( cmd[c] )
      
      # Prepare for transmission
      self.DC(1)
      self.CS(0)
      
      # Step through each byte of the (red or black) output
      i:int = 0
      while i < olen:
        
        # Mask off the colour we don't want, then rshift by 0 or 1 to normalise
        b = ( mask[c] & fb[i] ) >> c
        
        # b: _8_7_6_5_4_3_2_1
        # out:       12345678
        
        # Assemble a byte with all the bits in the right place, from the input two bytes
        outp[0] = (b&16384)>>14 | (b&4096)>>11 | (b&1024)>>8 | (b&256)>>5 | (b&64)>>2 | (b&16)<<1 | (b&4)<<4 | (b&1)<<7
        
        # Send the byte
        spi_w( out )
        
        # Next output byte
        i += 1
      
      # End transmission
      self.CS(1)
      
      # Next colour
      c += 1
  
  # Send with portrait rotation 2
  @micropython.viper
  def _send_2(self):
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = ptr16(self.buf)
    spi_w = self.spi.write
    
    # Data length
    olen:int = int(self.width) * int(self.height) // 8
    
    # Output commands
    cmd = ptr8(bytes([ 0x10, 0x13 ]))
    
    # Masks to select black/red bits of input byte
    mask = ptr16(bytes([ 0x55, 0x55, 0xaa, 0xaa ]))
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    outp = ptr8(out)
    
    # Do once per colour
    c:int = 0
    while c <= 1:
      
      # Send data command (black/red)
      self._send_command( cmd[c] )
      
      # Prepare for transmission
      self.DC(1)
      self.CS(0)
      
      # Step through each byte of the (red or black) output
      i:int = olen-1
      while i >= 0:
        
        # Mask off the colour we don't want, then rshift by 0 or 1 to normalise
        b = ( mask[c] & fb[i] ) >> c
        
        # b: _1_2_3_4_5_6_7_8
        # out:       12345678
        
        # Assemble a byte with all the bits in the right place, from the input two bytes
        outp[0] = (b&16384)>>7 | (b&4096)>>6 | (b&1024)>>5 | (b&256)>>4 | (b&64)>>3 | (b&16)>>2 | (b&4)>>1 | (b&1)
        
        # Send the byte
        spi_w( out )
        
        # Next output byte
        i -= 1
      
      # End transmission
      self.CS(1)
      
      # Next colour
      c += 1
  
  # Send with landscape rotation 1
  @micropython.viper
  def _send_1(self):
    
    # Output commands
    cmd = ptr8(bytes([ 0x10, 0x13 ]))
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    outp = ptr8(out)
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = ptr8(self.buf)
    spi_w = self.spi.write
    
    # Input pixel dimensions
    iw = int(self.width)
    ih = int(self.height)
    
    # Input byte width
    ibw = iw >> 2 # Divide by 4
    
    # Do everything once per colour
    c:int = 0
    while c <= 1:
      
      # Send data command (black/red)
      self._send_command( cmd[c] )
      
      # Prepare for transmission
      self.DC(1)
      self.CS(0)
      
      '''
      Input is always in rows of bytes
      Each byte is 4 pixels (2 bits per pixel)
      1-byte columns of the input image will be 4 pixels wide
      These columns will correspond to rows of the output image
      '''
      
      # Go column by column over the source image
      # Rot=1; start in the bottom-left and go up the columns
      x:int = 0
      while x < iw:
        
        # Split x into the byte-column we're in (col) and the pixel within that (bit)
        #
        # Byte-column is x//4
        col = x >> 2
        #
        # Convert from pixel position to bit position
        # ( ( x % 4 ) *2 ) +c
        bit = ((x&3)<<1)|c
        
        # Go up the columns, 8 rows at a time
        y:int = ih - 1
        while y >= 0:
          outp[0] = (
            ((( fb[ (ibw*(y  )) + col ] & (1<<bit) ) >> bit )<<7) |
            ((( fb[ (ibw*(y-1)) + col ] & (1<<bit) ) >> bit )<<6) |
            ((( fb[ (ibw*(y-2)) + col ] & (1<<bit) ) >> bit )<<5) |
            ((( fb[ (ibw*(y-3)) + col ] & (1<<bit) ) >> bit )<<4) |
            ((( fb[ (ibw*(y-4)) + col ] & (1<<bit) ) >> bit )<<3) |
            ((( fb[ (ibw*(y-5)) + col ] & (1<<bit) ) >> bit )<<2) |
            ((( fb[ (ibw*(y-6)) + col ] & (1<<bit) ) >> bit )<<1) |
            ((( fb[ (ibw*(y-7)) + col ] & (1<<bit) ) >> bit )   )
          )
          spi_w( out )
          
          # Next output byte
          y -= 8
        
        # Next column
        x += 1
      
      # End transmission
      self.CS(1)
      
      # Next colour
      c += 1
  
  # Send with landscape rotation 3
  @micropython.viper
  def _send_3(self):
    
    # Output commands
    cmd = ptr8(bytes([ 0x10, 0x13 ]))
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    outp = ptr8(out)
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = ptr8(self.buf)
    spi_w = self.spi.write
    
    # Input pixel dimensions
    iw = int(self.width)
    ih = int(self.height)
    
    # Input byte width
    ibw = iw >> 2 # Divide by 4
    
    # Do everything once per colour
    c:int = 0
    while c <= 1:
      
      # Send data command (black/red)
      self._send_command( cmd[c] )
      
      # Prepare for transmission
      self.DC(1)
      self.CS(0)
      
      '''
      Input is always in rows of bytes
      Each byte is 4 pixels (2 bits per pixel)
      1-byte columns of the input image will be 4 pixels wide
      These columns will correspond to rows of the output image
      '''
      
      # Go column by column over the source image
      # Rot=3; start in the top-right and go down the columns
      x:int = iw - 1
      while x >= 0:
        
        # Split x into the byte-column we're in (col) and the pixel within that (bit)
        #
        # Byte-column is x//4
        col = x >> 2
        #
        # Convert from pixel position to bit position
        # ( ( x % 4 ) *2 ) +c
        bit = ((x&3)<<1) | c
        
        # Go down the columns, 8 rows at a time
        y:int = 0
        while y < ih:
          outp[0] = (
            ((( fb[ (ibw*(y  )) + col ] & (1<<bit) ) >> bit )<<7) |
            ((( fb[ (ibw*(y+1)) + col ] & (1<<bit) ) >> bit )<<6) |
            ((( fb[ (ibw*(y+2)) + col ] & (1<<bit) ) >> bit )<<5) |
            ((( fb[ (ibw*(y+3)) + col ] & (1<<bit) ) >> bit )<<4) |
            ((( fb[ (ibw*(y+4)) + col ] & (1<<bit) ) >> bit )<<3) |
            ((( fb[ (ibw*(y+5)) + col ] & (1<<bit) ) >> bit )<<2) |
            ((( fb[ (ibw*(y+6)) + col ] & (1<<bit) ) >> bit )<<1) |
            ((( fb[ (ibw*(y+7)) + col ] & (1<<bit) ) >> bit )   )
          )
          spi_w( out )
          
          # Next output byte
          y += 8
        
        # Next column
        x -= 1
      
      # End transmission
      self.CS(1)
      
      # Next colour
      c += 1
