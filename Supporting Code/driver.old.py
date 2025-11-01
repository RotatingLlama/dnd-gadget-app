# Old (non-viper) e-ink send functions
# Replaced with viper as of 21 Feb 2025

  # Send with landscape rotation
  # Slow (2.5s) without Viper.  Also doesn't support rot3.
  def _send_land(self):
    
    if self.rot == 3:
      raise NotImplementedError('Rotation #3 not implemented yet')
      return
    
    # Output commands
    cmd = bytes([ 0x10, 0x13 ])
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = self.fb.buf
    spi_w = self.spi.write
    
    # Input byte width, input height
    ibw = self.width // 4
    ih = self.height
    
    # Having these as elements of a bytearray makes things worse, for some reason
    col=0
    bit=0
    
    # Set these up ahead of time
    rx = range(self.width)
    r1 = range(ibw)
    r2 = range(4)
    ry = range( 0, ih, 8 )
    
    # Do everything once per colour
    for c in (0,1):
      
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
      
      '''
      # Go column by column over the source image
      for x in rx:
        
        # Split x into the byte-column we're in (col) and the pixel within that (bit)
        # col = x // 4
        col = x>>2
        
        # Convert bit from pixel position to bit position
        # bit = ( (x % 4 ) *2 ) +c
        bit = ((x&3)<<1)|c
        
        # Go up the columns, 8 rows at a time
        for y in ry:
          out[0] = (
            ((( fb[ (ibw*(ih-y-1)) + col ] & (1<<bit) ) >> bit )<<7) |
            ((( fb[ (ibw*(ih-y-2)) + col ] & (1<<bit) ) >> bit )<<6) |
            ((( fb[ (ibw*(ih-y-3)) + col ] & (1<<bit) ) >> bit )<<5) |
            ((( fb[ (ibw*(ih-y-4)) + col ] & (1<<bit) ) >> bit )<<4) |
            ((( fb[ (ibw*(ih-y-5)) + col ] & (1<<bit) ) >> bit )<<3) |
            ((( fb[ (ibw*(ih-y-6)) + col ] & (1<<bit) ) >> bit )<<2) |
            ((( fb[ (ibw*(ih-y-7)) + col ] & (1<<bit) ) >> bit )<<1) |
            ((( fb[ (ibw*(ih-y-8)) + col ] & (1<<bit) ) >> bit )   )
          )
          spi_w( out )
      '''
      
      # Input image, columns of 4 pixels, aka columns of bytes
      for col in r1:
        
        # Input image, columns of single pixels
        for incol in r2:
          
          # Select which bit from each byte we'll need
          #bit = (incol*2) +c
          bit = (incol<<1) | c
          
          # Input image, every 8th row is the start of an output byte
          for y in ry:
            
            # Select from framebuffer:
            # ( Input byte width * row of interest ) + column offset
            # AND with 2^bit
            # RSHIFT back down to zero or 1
            # LSHIFT to correct position within output byte
            # OR all 8 together
            out[0] = (
              ((( fb[ (ibw*(ih-y-1)) + col ] & (1<<bit) ) >> bit )<<7) |
              ((( fb[ (ibw*(ih-y-2)) + col ] & (1<<bit) ) >> bit )<<6) |
              ((( fb[ (ibw*(ih-y-3)) + col ] & (1<<bit) ) >> bit )<<5) |
              ((( fb[ (ibw*(ih-y-4)) + col ] & (1<<bit) ) >> bit )<<4) |
              ((( fb[ (ibw*(ih-y-5)) + col ] & (1<<bit) ) >> bit )<<3) |
              ((( fb[ (ibw*(ih-y-6)) + col ] & (1<<bit) ) >> bit )<<2) |
              ((( fb[ (ibw*(ih-y-7)) + col ] & (1<<bit) ) >> bit )<<1) |
              ((( fb[ (ibw*(ih-y-8)) + col ] & (1<<bit) ) >> bit )   )
            )
            spi_w( out )
      
      
      # End transmission
      self.CS(1)
    
    # Tidy up memory
    del cmd, out, fb, spi_w
    #del ibw, ih, c, col, incol, bit, row
    #del ibw, ih, c, col, x
    gc.collect()
  
  # Send with portrait rotation
  @micropython.native
  def _send_port(self):
    
    # How to locate a 2-bit pixel in the buffer for a given rotation
    '''
    buflen = len(self.fb.buf)
    locator = [
      #             ( self.fb.buf[ (i*2)  + (j//4) ] >> ((j%4)*2 ) ) & 3
      lambda i, j : ( self.fb.buf[ (i<<1) + (j>>2) ] >> ((j&3)<<1) ) & 3, # Zero rotation (portrait)
      lambda i, j : 0,
      lambda i, j : ( self.fb.buf[ buflen-(i<<1)-(j>>2)-1 ] >> ((3-(j&3))<<1) ) & 3, # 180,
      lambda i, j : 0,
    ][self.rot]
    '''
    
    # Output commands
    cmd = bytes([ 0x10, 0x13 ])
    
    # Temporary store for byte values.  Avoids repeated in-loop memory allocation.
    out = bytearray(1)
    
    # For speed, cache locally all global variables that we'll need in the loop
    fb = self.fb.buf
    spi_w = self.spi.write
    
    # Range object and byte decoders for loop
    if self.rot == 0:
      r = range( 0, self.kr_fb_size * 2, 2 )
      nybble = [
        lambda b : (b&64)>>6 | (b&16)>>3 | (b&4) | (b&1)<<3,     # black
        lambda b : (b&128)>>7 | (b&32)>>4 | (b&8)>>1 | (b&2)<<2, # red
      ]
      ob = lambda i, n : ( n( fb[i] ) << 4 ) | ( n( fb[i+1] ) ) # Output byte
    elif self.rot == 2:
      r = range( self.kr_fb_size*2-1, -1, -2 )
      nybble = [
        lambda b : (b&64)>>3 | (b&16)>>2 | (b&4)>>1 | (b&1),     # black
        lambda b : (b&128)>>4 | (b&32)>>3 | (b&8)>>2 | (b&2)>>1, # red
      ]
      ob = lambda i, n : ( n( fb[i] ) << 4 ) | ( n( fb[i-1] ) ) # Output byte
    else:
      raise NotImplementedError('Landscape modes not supported yet')
    
    # Do once per colour
    for c in (1,2):
      
      # Send data command (black/red)
      self._send_command( cmd[c-1] )
      
      # Prepare for transmission
      self.DC(1)
      self.CS(0)
      
      # Which nybble do we need?
      n = nybble[c-1]
      
      # Step through each byte of the (red or black) output
      for i in r:
        
        # Get two nybbles and compose them into one byte for monochrome output
        #print(
        out[0] = ob( i, n )
        #print(hex(out[0]))
        #print( nybble[1]( self.fb.buf[2*i] ) << 4 )
        #print( nybble[1]( self.fb.buf[(2*i)+1] ) )
        #return
        
        # Send the byte
        spi_w( out )
      
      # End transmission
      self.CS(1)
  