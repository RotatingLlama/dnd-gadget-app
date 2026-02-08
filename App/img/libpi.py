# Functions for dealing with .pi files (formerly 2ink)
#
# T. Lloyd
# 08 Feb 2026

# Standard libs
from struct import unpack, pack
import micropython
from micropython import const

# Our libs
from . import fb as framebuf
from .utils import b2f

# Saves a GS2_HMSB framebuffer object to a .pi file
def save_GS2_HMSB( fb, filename ):
  
  # Construct the head
  # Version = 1
  # Data will start at byte 8
  # width, height, bpp
  head = pack('>BBHHBB', 1, 8, fb.width, fb.height, fb.bpp, 0)
  
  # Sanity check on image width (whole number of bytes)
  ppb = 8 // fb.bpp # Pixels per byte
  if fb.width % ppb != 0:
    raise RuntimeError('Framebuffer has odd width (not whole bytes)')
  
  # Rearrange the pixel order to suit 2ink format
  #if GS2_HLSB:
  #  swap_pixel_order(fb.buf)
  
  # Write the file
  fd = open( filename, 'wb' )
  fd.write(head)
  fd.write(fb.buf)
  fd.close()
  
  # Put the buffer back how it was
  #if GS2_HLSB:
  #  swap_pixel_order(fb.buf)

# Load from file into new FrameBuffer object
# Creates a new buffer for this purpose
def load( filename ):
  
  # Load in the file
  fd = open( filename, 'rb' )
  top = fd.read(2)
  
  # Get the version from the first byte
  version = top[0]
  
  # Check we know what we're doing
  if version > 1:
    raise RuntimeError('Unrecognised file format')
  
  # Data start pointer
  ds = top[1]
  
  # Head format
  # 00 1b Version
  # 01 1b Data start pointer
  # 02 2b Width (pixels)
  # 04 2b Height (pixels)
  # 06 1b bits per pixel
  
  # Make a nice object containing the head data
  # Version 1 means there are 6 bytes left in the head
  head = [0]*5
  head[0:2] = list(top)
  head[2:] = unpack( '>HHB', fd.read( 6 ) )
  
  iwidth = head[2]
  height = head[3]
  
  # Pixels per byte
  ppb = 8 // head[4]
  
  # If the declared image width doesn't fit a whole number of bytes, assume it's been padded (with zeroes)
  pad = -iwidth % ppb
  dwidth = iwidth + pad
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if iwidth == 0:
    raise RuntimeError('Attempted to load image with zero width!')
  if height == 0:
    raise RuntimeError('Attempted to load image with zero height!')
  if head[4] not in b2f:
    raise RuntimeError('Invalid number of bits per pixel!')
  
  # Currently only support 1 or 2 bpp
  if head[4] > 2:
    raise RuntimeError('Only 1 or 2 bits per pixel is supported')
  
  # Make the FB
  buf = bytearray( dwidth * height // ppb )
  fb = framebuf.FB( buf, dwidth, height, b2f[head[4]] )
  
  # Get the image data
  img_len = fd.readinto( buf )
  
  # Close the file
  fd.close()
  
  # Tidy up
  del version, ds, fd, top
  
  # Check for file read errors
  if img_len is None:
    raise RuntimeError('Error reading file')
    return
  if img_len != len(buf):
    raise RuntimeError('File read error: unexpected length')
    return
  
  # Do we have to blank out some padding?
  if pad:
    fb.rect( iwidth, 0, pad, height, 3 ) # Fill the pad area with transparency
  
  return fb

# Loads from file into provided buffer (bytearray)
# Overwrites the provided buffer up to the length of the file image
# Does not allocate any working buffer
def load_into( buf, filename ):
  
  # Load in the file
  fd = open( filename, 'rb' )
  top = fd.read(2)
  
  # Get the version from the first byte
  version = top[0]
  
  # Check we know what we're doing
  if version > 1:
    raise RuntimeError('Unrecognised file format')
  
  # Data start pointer
  ds = top[1]
  
  # Get the rest of the head
  rest_of_head = fd.read( ds - 2 )
  
  # Get the image data
  img_len = fd.readinto( buf )
  
  # Close the file
  fd.close()
  
  # Head format
  # 00 1b Version
  # 01 1b Data start pointer
  # 02 2b Width (pixels)
  # 04 2b Height (pixels)
  # 06 1b bits per pixel
  
  # Make a nice object containing the head data
  head = [0]*5
  head[0:2] = list(top)
  head[2:5] = unpack( '>HHB', rest_of_head )
  
  iwidth = head[2]
  height = head[3]
  
  # Pixels per byte
  ppb = 8 // head[4]
  
  # If the declared image width doesn't fit a whole number of bytes, assume it's been padded (with zeroes)
  pad = -iwidth % ppb
  dwidth = iwidth + pad
  
  # Tidy up
  del rest_of_head, version, ds, fd, top
  
  # Check for file read errors
  if img_len is None:
    raise RuntimeError('Error reading file')
  if img_len != ( dwidth * height // ppb ):
    raise RuntimeError('File read error: unexpected length')
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if iwidth == 0:
    raise RuntimeError('Attempted to load image with zero width!')
  if height == 0:
    raise RuntimeError('Attempted to load image with zero height!')
  if head[4] not in b2f:
    raise RuntimeError('Invalid number of bits per pixel!')
  
  # Currently only support 1 or 2 bpp
  if head[4] > 2:
    raise RuntimeError('Only 1 or 2 bits per pixel is supported')
    
  # Were we given a big enough buffer?
  if len(buf) < img_len:
    raise RuntimeError('Provided buffer was too small!')
  
  # Rearrange the pixel order to suit GS2_HMSB format
  #swap_pixel_order(buf)
  
  # For 2bpp, replace transparency with white (otherwise it shows up as red)
  if head[4] == 2:
    _replace_colour_2bpp( buf, 3, 0 )
  
  # Construct the framebuffer object
  fb = framebuf.FB(
    buf,
    dwidth, # width
    height, # height
    b2f[head[4]] # format
  )
  
  # Do we have to blank out some padding?
  if pad:
    fb.rect( iwidth, 0, pad, height, 3 ) # Fill the pad area with transparency
  
  return fb
  

# Takes a raw buffer, and optionally a pair of integer colours
# Finds all instances of old colour and replaces it with new colour
# By default, replaces 3 (transparent) with 0 (white)
@micropython.viper
def _replace_colour_2bpp( buf, old:int=3, new:int=0 ):
  bf = ptr8(buf)
  c1 = ptr8(bytes(( old<<6, old<<4, old<<2, old, )))
  c2 = ptr8(bytes(( new<<6, new<<4, new<<2, new, )))
  b = ptr8(bytearray(2))
  
  i = int(0)
  z = int(len(buf))
  while i < z:
    
    # Reset
    b[0] = 0x00 # Blit
    b[1] = 0xff # Mask
    
    # Detect c1 in all 4 positions.  If found:
    # Set blit b[0] to c2 in that position
    # Set mask b[1] to 0s in that position
    if ( bf[i] & 0xc0 ) == c1[0]:
      b[0] |= c2[0]
      b[1] &= 0x3f # 00 11 11 11
    if ( bf[i] & 0x30 ) == c1[1]:
      b[0] |= c2[1]
      b[1] &= 0xcf # 11 00 11 00
    if ( bf[i] & 0x0c ) == c1[2]:
      b[0] |= c2[2]
      b[1] &= 0xf3 # 11 11 00 11
    if ( bf[i] & 0x03 ) == c1[3]:
      b[0] |= c2[3]
      b[1] &= 0xfc # 11 11 11 00
    
    # AND the byte with the mask; masked areas are now all 0s
    bf[i] &= b[1]
    
    # OR the byte with the blit
    bf[i] |= b[0]
    
    i += 1

def blit_onto( fb, x:int, y:int, filename, t=3 ):
  if fb.bpp != 2:
    raise NotImplementedError('Only 2bpp framebuffers are supported for blit_onto()')
  _blit_2bpp_onto_2bpp( fb, x, y, filename )
  #_blit_onto_any( fb, x, y, filename, t )

# We can define these as const because we only accept bpp = 2
# bits per pixel
#sbpp = const(2)
#dbpp = const(2)
# Pixels per byte ( 8 // bpp )
#sppb = const(4)
#dppb = const(4)

# Blits image from file onto provided framebuffer
# Positions top-left corner of file image at x, y
# Transparency in file image is respected
# Allocates working buffer equal to file image width +1
# Fullscreen in 0.087s
@micropython.viper
def _blit_2bpp_onto_2bpp( fb, x:int, y:int, filename ):
  
  # Destination info
  buf = ptr8(fb.buf)
  dest_width = int(fb.width)
  dest_height = int(fb.height)
  #dbpp:int = int(fb.bpp) # Destination bits per pixel (not used)
  dppb:int = 8 // int(fb.bpp) # Destination pixels per byte
  dest_bytewidth:int = dest_width // dppb
  
  # Open the source file
  fd = open( filename, 'rb' )
  
  # First 7 bytes should be the header
  head = ptr8(fd.read(7))
  
  # Version check - we only support v1
  if head[0] > 1:
    raise NotImplementedError('Unrecognised file format/version')
  
  # Head format
  # 00 1b Version
  # 01 1b Data start pointer
  # 02 2b Width (pixels)
  # 04 2b Height (pixels)
  # 06 1b bits per pixel
  
  # Have to construct multi-byte integers manually because Viper doesn't understand endianness
  ds:int = head[1]
  isrc_width:int = head[2]<<8 | head[3]
  src_height:int = head[4]<<8 | head[5]
  sbpp:int = head[6]
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if isrc_width == 0:
    raise RuntimeError('Attempted to load image with zero width!')
  if src_height == 0:
    raise RuntimeError('Attempted to load image with zero height!')
  #if src_width % 8 != 0:
  #  raise RuntimeError('Image width must be multiple of 8')
  #if sbpp not in b2f: # This check doesn't work in Viper - but is redundant due to (working) sbpp != 2 check below
  #  raise RuntimeError('Invalid number of bits per pixel!')
  
  # Currently only support 2bpp
  if sbpp != 2:
  #if head[6] != 2:
    raise NotImplementedError('Only 2 bits per pixel is supported')
  
  # Source start/end positions (in case parts of it end up offscreen)
  # Since at least MP 1.23, expression `-x` modifies x in place
  # https://github.com/micropython/micropython/issues/14397
  src_startrow:int = int(max( 0, 0-y )) # Does the blitted image start offscreen?
  # src_endrow:int = int(min( src_height, dest_height - y )) # Does it end offscreen? # Not used
  sppb:int = 8 // sbpp # Source pixels per byte
  
  # If the declared image width doesn't fit a whole number of bytes, assume it's been padded (with zeroes)
  src_pad:int = (0-isrc_width) % sppb
  src_width:int = isrc_width + src_pad
  print('isrc_width ',isrc_width)
  print('pad ',src_pad)
  print('src_width ',src_width)
  
  src_bytewidth:int = src_width // sppb
  src_startbyte:int = int(max( 0, 0-x )) // sppb
  src_endbyte:int = -( -int(min( isrc_width, dest_width - x )) // sppb )
  src_eff_width:int = src_endbyte - src_startbyte
  print('src_eff_width ',src_eff_width)
  
  dest_startrow:int = int(max( 0, y ))
  dest_endrow:int = int(min( dest_height, y+src_height ))
  
  # Where in the dest buffer do we start?
  dest_startbyte:int = int(max( 0, x )) // dppb
  
  # Where in dest buffer do we end?  Trick with negatives produces correct values for partial-byte offsets
  dest_endbyte:int = int(min( dest_bytewidth, -( -(x+isrc_width) // dppb ) ))
  
  # Within the start byte, which pixel do we start on?
  dest_pixeloffset:int = x % dppb
  
  # Individual pixel bit offsets
  po = ptr8(bytearray(4))
  po[0] = ( sppb - dest_pixeloffset ) * sbpp
  po[1] = ( sppb + 1 - dest_pixeloffset ) * sbpp
  po[2] = ( sppb + 2 - dest_pixeloffset ) * sbpp
  po[3] = ( sppb + 3 - dest_pixeloffset ) * sbpp
  
  # How many whole bytes in the dest buffer are after the blitted image?
  dest_bytesafter:int = dest_bytewidth - dest_endbyte
  
  # Effective byte width of image on dest buffer
  dest_eff_width:int = dest_endbyte - dest_startbyte
  
  # MP-1.24.1 Slices of memoryviews in Viper are bugged - workaround is index via const()
  # https://github.com/micropython/micropython/issues/6523
  
  # Container for the input image data (one line at a time)
  # Extra byte because affected bytes of dest image can be source bytes + 1 in case of byte non-alignment
  bline = bytearray( src_eff_width + 1 )       # Line buffer, one byte wider than the source image
  line = memoryview(bline)[const(0):const(-1)] # Memoryview of the buffer, sans extra byte
  p_bline = ptr8(bline)                        # Pointer to full buffer
  p_bline[src_eff_width] = 0xff                # Fill the extra byte with transparency
  
  # Construct the padding
  pad:int = 255 >> (src_pad*sbpp)
  pad = ~pad
  
  # Containers for in-loop byte data
  b = ptr8(bytearray(3))
  src:int = 0xffff
  
  # File pointer
  fp:int = ds + ( src_startrow * src_bytewidth ) + src_startbyte
  
  # Loop control
  row:int = dest_startrow
  i:int
  
  # Output (destination) byte index
  obi:int = ( row * dest_bytewidth ) + dest_startbyte
  
  # Step through each (needed) row of the output buffer
  while row < dest_endrow:
    
    # Get the line from the input file
    fd.seek( fp )
    if int(fd.readinto( line )) < src_eff_width:
      raise RuntimeError('Image file was shorter than expected!')
    
    # Apply the padding to the current line
    # TODO: This will always blank out a padding's-width of the last displayed byte
    # ...whether that's the last byte of the source line, or not
    # eg. if the source image is cut off by the rh edge of the dest fb
    p_bline[src_eff_width-1] |= pad
    
    # Step through each (needed) byte in the current row of the output buffer
    i = 0
    while i < dest_eff_width:
      
      # Reset this container
      b[1] = 0 # Mask
      b[2] = 0 # Values
      
      # Shift the last byte along and add the new one
      src = ( p_bline[i] << 8 ) | ( src >> 8 )
      
      # Pixel 0
      b[0] = ( src >> po[0] ) & 3
      if b[0] == 3: # If pixel is transparent
        b[1] |= 3 # Put ones in the mask byte (keep the existing value)
      else:
        b[2] |= b[0] # Put the pixel value in the data byte
      
      # Pixel 1
      b[0] = ( src >> po[1] ) & 3
      if b[0] == 3:
        b[1] |= 12 # 3 << 2
      else:
        b[2] |= b[0] << 2
      
      # Pixel 2
      b[0] = ( src >> po[2] ) & 3
      if b[0] == 3:
        b[1] |= 48 # 3 << 4
      else:
        b[2] |= b[0] << 4
      
      # Pixel 3
      b[0] = ( src >> po[3]) & 3
      if b[0] == 3:
        b[1] |= 192 # 3 << 6
      else:
        b[2] |= b[0] << 6
      
      # Update the destination buffer
      buf[ obi ] &= b[1] # Apply the mask (zero out everywhere we'll write)
      buf[ obi ] |= b[2] # Apply the data
      
      # Increment the output byte index counter
      obi += 1
      
      # Increment the input byte index counter
      i += 1
    
    # Next row
    row += 1
    
    # Update the file pointer
    fp += src_bytewidth
    
    # Skip the output byte index along by however many bytes we skip at the start of the line
    obi += dest_bytesafter + dest_startbyte
  
  # Done, finish up
  fd.close()

# NOT CURRENTLY USED
#
# Blits image from file onto provided framebuffer
# Positions top-left corner of file image at x, y
# Transparency in file image is respected
# Allocates working buffer equal to file image width +1
# Assumes sane, sequential framebuffers like GS2_HMSB - does NOT work with eg. MONO_VLSB
"""
@micropython.viper
def _blit_onto_any( fb, x:int, y:int, filename, t:int=-1 ):
  
  # Destination info
  buf = ptr8(fb.buf)
  dest_width = int(fb.width)
  dest_height = int(fb.height)
  dbpp:int = int(fb.bpp) # Destination bits per pixel
  dppb:int = 8 // dbpp # Destination pixels per byte
  dest_bytewidth:int = dest_width // dppb
  
  # Open the source file
  fd = open( filename, 'rb' )
  
  # First 7 bytes should be the header
  head = ptr8(fd.read(7))
  
  # Version check - we only support v1
  if head[0] > 1:
    raise NotImplementedError('Unrecognised file format/version')
  
  # Head format
  # 00 1b Version
  # 01 1b Data start pointer
  # 02 2b Width (pixels)
  # 04 2b Height (pixels)
  # 06 1b bits per pixel
  
  # Have to construct multi-byte integers manually because Viper doesn't understand endianness
  ds:int = head[1]
  src_width:int = head[2]<<8 | head[3]
  src_height:int = head[4]<<8 | head[5]
  sbpp:int = head[6]
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if src_width == 0:
    raise RuntimeError('Attempted to load image with zero width!')
  if src_height == 0:
    raise RuntimeError('Attempted to load image with zero height!')
  if src_width % 8 != 0:
    raise RuntimeError('Image width must be multiple of 8')
  if int(b2f.get(sbpp, -1 )) == -1:
    raise RuntimeError('Invalid number of bits per pixel!')
  if sbpp > 2:
    raise NotImplementedError('Bits per pixel > 2 are not supported')
  if dbpp > 2:
    raise NotImplementedError('Framebuffers with bits per pixel > 2 are not supported')
  if t < -1 or t >= (1<<sbpp):
    raise ValueError('Invalid transparency value')
  #if sbpp != dbpp:
  #  raise RuntimeError('Source/destination BPP mismatch!')
  
  # Source start/end positions (in case parts of it end up offscreen)
  # Since at least MP 1.23, expression `-x` modifies x in place
  # https://github.com/micropython/micropython/issues/14397
  src_startrow:int = int(max( 0, 0-y )) # Does the blitted image start offscreen?
  # src_endrow:int = int(min( src_height, dest_height - y )) # Does it end offscreen? # Not used
  sppb:int = 8 // sbpp # Source pixels per byte
  src_bytewidth:int = src_width // sppb
  src_startbyte:int = int(max( 0, 0-x )) // sppb
  src_endbyte:int = int(min( src_width, dest_width - x )) // sppb
  src_eff_width:int = src_endbyte - src_startbyte
  
  dest_startrow:int = int(max( 0, y ))
  dest_endrow:int = int(min( dest_height, y+src_height ))
  
  # Where in the dest buffer do we start?
  dest_startbyte:int = int(max( 0, x )) // dppb
  
  # Where in dest buffer do we end?
  # Trick with negatives produces correct values for partial-byte offsets
  dest_endbyte:int = int(min( dest_bytewidth, -( -(x+src_width) // dppb ) ))
  
  # Within the start byte, which pixel do we start on?
  dest_pixeloffset:int = x % dppb
  
  # Individual pixel bit offsets
  # ie. the number of bits to shift src by to align it with dest
  i:int = 0
  po = ptr8(bytearray(sppb))
  while i < sppb:
    po[i] = ( sppb + i - dest_pixeloffset ) * sbpp
    i += 1
  '''
  po[0] = ( sppb - dest_pixeloffset ) * sbpp
  po[1] = ( sppb + 1 - dest_pixeloffset ) * sbpp
  po[2] = ( sppb + 2 - dest_pixeloffset ) * sbpp
  po[3] = ( sppb + 3 - dest_pixeloffset ) * sbpp
  '''
  
  # How many whole bytes in the dest buffer are after the blitted image?
  dest_bytesafter:int = dest_bytewidth - dest_endbyte
  
  # Effective byte width of image on dest buffer
  dest_eff_width:int = dest_endbyte - dest_startbyte
  
  # MP-1.24.1 Slices of memoryviews in Viper are bugged - workaround is index via const()
  # https://github.com/micropython/micropython/issues/6523
  
  # Container for the input image data (one line at a time)
  # Extra byte because affected bytes of dest image can be source bytes + 1 in case of byte non-alignment
  bline = bytearray( src_eff_width + 1 )       # Line buffer, one byte wider than the source image
  line = memoryview(bline)[const(0):const(-1)] # Memoryview of the buffer, sans extra byte
  p_bline = ptr8(bline)                        # Pointer to full buffer
  p_bline[src_eff_width] = ( t | t<<2 | t<<4 | t<<6 ) # Fill the extra byte with transparency
  
  # Containers for in-loop byte data
  b = ptr8(bytearray(3))
  src:int = 0xffff
  
  # File pointer
  fp:int = ds + ( src_startrow * src_bytewidth ) + src_startbyte
  
  # Loop control
  row:int = dest_startrow
  i:int
  
  # Output (destination) byte index
  obi:int = ( row * dest_bytewidth ) + dest_startbyte
  
  # Which unrolled loop do we use?
  if dppb == 4 and sppb == 4:
    lt = 1 # 4 pixels per byte in source and dest
  elif dppb == 8:
    if sppb == 4:
      lt = 2 # 8 pixels per byte in dest, 4 in source
    elif sppb == 8:
      lt = 3 # 8 pixels per byte in source and dest
    else:
      raise NotImplementedError('Unsupported number of bits per pixel for source image:',sbpp)
  else:
    raise NotImplementedError('Unsupported number of bits per pixel for target framebuffer',dbpp)
  
  # Step through each (needed) row of the output buffer
  while row < dest_endrow:
    
    # Get the line from the input file
    fd.seek( fp )
    if int(fd.readinto( line )) < src_eff_width:
      raise RuntimeError('Image file was shorter than expected!')
    
    # Step through each (needed) byte in the current row of the output buffer
    i = 0
    if lt == 1: # 4 pixels per byte in source and dest # Works
      while i < dest_eff_width:
        
        # Reset this container
        b[1] = 0 # Mask
        b[2] = 0 # Values
        
        # Shift the last byte along and add the new one
        src = ( p_bline[i] << 8 ) | ( src >> 8 )
        
        # Pixel 0
        b[0] = ( src >> po[0] ) & 3
        if b[0] == t: # If pixel is transparent
          b[1] |= 3 # Put ones in the mask byte (keep the existing value)
        else:
          b[2] |= b[0] # Put the pixel value in the data byte
        
        # Pixel 1
        b[0] = ( src >> po[1] ) & 3
        if b[0] == t:
          b[1] |= 12 # 3 << 2
        else:
          b[2] |= b[0] << 2
        
        # Pixel 2
        b[0] = ( src >> po[2] ) & 3
        if b[0] == t:
          b[1] |= 48 # 3 << 4
        else:
          b[2] |= b[0] << 4
        
        # Pixel 3
        b[0] = ( src >> po[3]) & 3
        if b[0] == t:
          b[1] |= 192 # 3 << 6
        else:
          b[2] |= b[0] << 6
        
        # Update the destination buffer
        buf[ obi ] &= b[1] # Apply the mask (zero out everywhere we'll write)
        buf[ obi ] |= b[2] # Apply the data
        
        # Increment the output byte index counter
        obi += 1
        
        # Increment the input byte index counter
        i += 1
    
    elif lt == 2: # 8 pixels per byte in dest, 4 in source # TODO: test
      while i < dest_eff_width:
        
        # Reset this container
        # b[0] = per-pixel working area
        b[1] = 0 # Mask
        b[2] = 0 # Values
        
        # Shift the last byte along and add the new one
        src = ( p_bline[i*2] << 8 ) | ( src >> 8 )
        
        # Pixel 0
        b[0] = ( src >> po[0] ) & 3
        if b[0] == t: # If pixel is transparent
          b[1] |= 1 # Put a one in the mask byte (keep the existing value)
        else:
          b[0] &= 1
          b[2] |= b[0] # Put the pixel value in the data byte
        
        # Pixel 1
        b[0] = ( src >> po[1] ) & 3
        if b[0] == t:
          b[1] |= 2 # 1 << 1
        else:
          b[0] &= 1
          b[2] |= b[0] << 1
        
        # Pixel 2
        b[0] = ( src >> po[2] ) & 3
        if b[0] == t:
          b[1] |= 4 # 1 << 2
        else:
          b[0] &= 1
          b[2] |= b[0] << 2
        
        # Pixel 3
        b[0] = ( src >> po[3]) & 3
        if b[0] == t:
          b[1] |= 8 # 1 << 3
        else:
          b[0] &= 1
          b[2] |= b[0] << 3
        
        # Shift the last byte along and add the new one
        src = ( p_bline[ (i*2) +1 ] << 8 ) | ( src >> 8 )
        
        # Pixel 4
        b[0] = ( src >> po[0] ) & 3
        if b[0] == t:
          b[1] |= 16 # 1 << 4
        else:
          b[0] &= 1
          b[2] |= b[0] << 4
        
        # Pixel 5
        b[0] = ( src >> po[1] ) & 3
        if b[0] == t:
          b[1] |= 32 # 1 << 5
        else:
          b[0] &= 1
          b[2] |= b[0] << 5
        
        # Pixel 6
        b[0] = ( src >> po[2] ) & 3
        if b[0] == t:
          b[1] |= 64 # 1 << 6
        else:
          b[0] &= 1
          b[2] |= b[0] << 6
        
        # Pixel 7
        b[0] = ( src >> po[3]) & 3
        if b[0] == t:
          b[1] |= 128 # 1 << 7
        else:
          b[0] &= 1
          b[2] |= b[0] << 7
        
        # Update the destination buffer
        buf[ obi ] &= b[1] # Apply the mask (zero out everywhere we'll write)
        buf[ obi ] |= b[2] # Apply the data
        
        # Increment the output byte index counter
        obi += 1
        
        # Increment the input byte index counter
        i += 1
    
    elif lt == 3: # 8 pixels per byte in source and dest # TODO: test
      while i < dest_eff_width:
        
        # Reset this container
        # b[0] = per-pixel working area
        b[1] = 0 # Mask
        b[2] = 0 # Values
        
        # Shift the last byte along and add the new one
        src = ( p_bline[i] << 8 ) | ( src >> 8 )
        
        # Pixel 0
        b[0] = ( src >> po[0] ) & 1
        if b[0] == t: # If pixel is transparent
          b[1] |= 1 # Put a one in the mask byte (keep the existing value)
        else:
          b[2] |= b[0] # Put the pixel value in the data byte
        
        # Pixel 1
        b[0] = ( src >> po[1] ) & 1
        if b[0] == t:
          b[1] |= 2 # 1 << 1
        else:
          b[2] |= b[0] << 1
        
        # Pixel 2
        b[0] = ( src >> po[2] ) & 1
        if b[0] == t:
          b[1] |= 4 # 1 << 2
        else:
          b[2] |= b[0] << 2
        
        # Pixel 3
        b[0] = ( src >> po[3]) & 1
        if b[0] == t:
          b[1] |= 8 # 1 << 3
        else:
          b[2] |= b[0] << 3
        
        # Pixel 4
        b[0] = ( src >> po[4]) & 1
        if b[0] == t:
          b[1] |= 16 # 1 << 4
        else:
          b[2] |= b[0] << 4
        
        # Pixel 5
        b[0] = ( src >> po[5]) & 1
        if b[0] == t:
          b[1] |= 32 # 1 << 5
        else:
          b[2] |= b[0] << 5
        
        # Pixel 6
        b[0] = ( src >> po[6]) & 1
        if b[0] == t:
          b[1] |= 64 # 1 << 6
        else:
          b[2] |= b[0] << 6
        
        # Pixel 7
        b[0] = ( src >> po[7]) & 1
        if b[0] == t:
          b[1] |= 128 # 1 << 7
        else:
          b[2] |= b[0] << 7
          
        # Update the destination buffer
        buf[ obi ] &= b[1] # Apply the mask (zero out everywhere we'll write)
        buf[ obi ] |= b[2] # Apply the data
        
        # Increment the output byte index counter
        obi += 1
        
        # Increment the input byte index counter
        i += 1
    
    # Next row
    row += 1
    
    # Update the file pointer
    fp += src_bytewidth
    
    # Skip the output byte index along by however many bytes we skip at the start of the line
    obi += dest_bytesafter + dest_startbyte
  
  # Done, finish up
  fd.close()
"""
