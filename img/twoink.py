# Functions for dealing with .2ink files
#
# T. Lloyd
# 11 Jul 2025

# Standard libs
from struct import unpack, pack
import micropython
from micropython import const

# Our libs
from . import fb as framebuf
from .utils import b2f

# Saves a GS2_HMSB framebuffer object to a .2ink file
def save_GS2_HMSB( fb, filename ):
  
  # Construct the head
  # Version = 1
  # Data will start at byte 8
  # width, height, bpp
  head = pack('>BBHHBB', 1, 8, fb.width, fb.height, fb.bpp, 0)
  
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
    return
  
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
  head = [ version, ds ]
  head.extend( unpack( '>HHB', fd.read( 6 ) ) )
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if head[2] == 0:
    raise RuntimeError('Attempted to load image with zero width!')
    return
  if head[3] == 0:
    raise RuntimeError('Attempted to load image with zero height!')
    return
  if head[2] % 8 != 0:
    raise RuntimeError('Image width must be multiple of 8')
    return
  if head[4] not in b2f:
    raise RuntimeError('Invalid number of bits per pixel!')
    return
  
  # Currently only support 2bpp
  if head[4] != 2:
    raise RuntimeError('Only 2 bits per pixel is supported')
    return
  
  # Make the FB
  buf = bytearray( head[2] * head[3] * head[4] // 8 )
  fb = framebuf.FB( buf, head[2], head[3], b2f[head[4]] )
  
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
  
  # Rearrange the pixel order to suit GS2_HMSB format
  #swap_pixel_order(buf)
  
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
    return
  
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
  head = [ version, ds ]
  head.extend( unpack( '>HHB', rest_of_head ) )
  
  # Tidy up
  del rest_of_head, version, ds, fd, top
  
  # Check for file read errors
  if img_len is None:
    raise RuntimeError('Error reading file')
    return
  if img_len != ( head[2] * head[3] * head[4] ) // 8:
    raise RuntimeError('File read error: unexpected length')
    return
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if head[2] == 0:
    raise RuntimeError('Attempted to load image with zero width!')
    return
  if head[3] == 0:
    raise RuntimeError('Attempted to load image with zero height!')
    return
  if head[2] % 8 != 0:
    raise RuntimeError('Image width must be multiple of 8')
    return
  if head[4] not in b2f:
    raise RuntimeError('Invalid number of bits per pixel!')
    return
  
  # Currently only support 2bpp
  if head[4] != 2:
    raise RuntimeError('Only 2 bits per pixel is supported')
    return
    
  # Were we given a big enough buffer?
  if len(buf) < img_len:
    raise RuntimeError('Provided buffer was too small!')
    return
  
  # Rearrange the pixel order to suit GS2_HMSB format
  #swap_pixel_order(buf)
  
  return framebuf.FB(
    buf,
    head[2], # width
    head[3], # height
    b2f[head[4]] # format
  )

# We can define these as const because we only accept bpp = 2
# bits per pixel
sbpp = const(2)
dbpp = const(2)
# Pixels per byte ( 8 // bpp )
sppb = const(4)
dppb = const(4)

# Blits image from file onto provided framebuffer
# Positions top-left corner of file image at x, y
# Transparency in file image is respected
# Allocates working buffer equal to file image width +1
# Fullscreen in 0.087s
@micropython.viper
def blit_onto( fb, x:int, y:int, filename ):
  
  # Destination info
  buf = ptr8(fb.buf)
  dest_width = int(fb.width)
  dest_height = int(fb.height)
  # dppb:int = 8 // int(fb.bpp) # Destination pixels per byte
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
  # sbpp:int = head[6]
  
  # Geometry validation
  # width and height values are guaranteed to be positive integers, because we've unpacked them as such
  if src_width == 0:
    raise RuntimeError('Attempted to load image with zero width!')
  if src_height == 0:
    raise RuntimeError('Attempted to load image with zero height!')
  if src_width % 8 != 0:
    raise RuntimeError('Image width must be multiple of 8')
  #if sbpp not in b2f: # This check doesn't work in Viper - but is redundant due to (working) sbpp != 2 check below
  #  raise RuntimeError('Invalid number of bits per pixel!')
  
  # Currently only support 2bpp
  # if sbpp != 2:
  if head[6] != 2:
    raise NotImplementedError('Only 2 bits per pixel is supported')
  
  # Source start/end positions (in case parts of it end up offscreen)
  # Since at least MP 1.23, expression `-x` modifies x in place
  # https://github.com/micropython/micropython/issues/14397
  src_startrow:int = int(max( 0, 0-y )) # Does the blitted image start offscreen?
  # src_endrow:int = int(min( src_height, dest_height - y )) # Does it end offscreen? # Not used
  # sppb:int = 8 // sbpp # Source pixels per byte
  src_bytewidth:int = src_width // sppb
  src_startbyte:int = int(max( 0, 0-x )) // sppb
  src_endbyte:int = int(min( src_width, dest_width - x )) // sppb
  src_eff_width:int = src_endbyte - src_startbyte
  
  dest_startrow:int = int(max( 0, y ))
  dest_endrow:int = int(min( dest_height, y+src_height ))
  
  # Where in the dest buffer do we start?
  dest_startbyte:int = int(max( 0, x )) // dppb
  
  # Where in dest buffer do we end?  Trick with negatives produces correct values for partial-byte offsets
  dest_endbyte:int = int(min( dest_bytewidth, -( -(x+src_width) // dppb ) ))
  
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
