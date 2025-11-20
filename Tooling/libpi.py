# pico-image converter
#
# 12 Sep 2025

# TODO: Do this properly
# https://pillow.readthedocs.io/en/stable/handbook/writing-your-own-image-plugin.html#file-codecs-py

from PIL import Image #, ImagePalette
from struct import pack, unpack

# Our file format extension
EXT = '.pi'

# Standard image formats we recognise (incomplete list)
imageTypes = ( '.jpg', '.jpeg', '.gif', '.png' )

# Convert pi to PNG
def decode( path, paltuple ):
  
  pal = _mkpal(paltuple)
  
  # Load in the file
  fd = open( path, 'rb' )
  top = fd.read(2)
  
  # Get the version from the first byte
  version = top[0]
  
  # Check we know what we're doing
  assert version <= 1
  
  # Data start pointer
  ds = top[1]
  
  # Get the rest of the head
  rest_of_head = fd.read( ds - 2 )
  
  # Get the image data
  ibuf = fd.read()
  
  # Close the file
  fd.close()
  
  # Head format
  # 00 1b Version
  # 01 1b Data start pointer
  # 02 2b Width (pixels)
  # 04 2b Height (pixels)
  # 06 1b bits per pixel
  # 07 1b reserved
  
  # Make a nice object containing the head data
  head = [ version, ds ]
  head.extend( unpack( '>HHBB', rest_of_head ) )
  
  # Check for file read errors
  assert len(ibuf) == ( head[2] * head[3] * head[4] ) // 8
  
  # Only support 1 or 2 bpp
  bpp = head[4]
  assert bpp <= 2
  
  # Unpack into one byte per pixel
  obuf = bytearray( head[2] * head[3] )
  ppb = 8 // bpp
  mask = ( 1 << bpp ) -1
  for i in range(len(ibuf)):
    for j in range(ppb):
      obuf[ (i*ppb) + j ] = ( ibuf[i] >> (j*bpp) ) & mask
  '''
    obuf[ (i*8) +1 ] = ( ibuf[i] >> 1 ) & 1
    obuf[ (i*8) +2 ] = ( ibuf[i] >> 2 ) & 1
    obuf[ (i*8) +3 ] = ( ibuf[i] >> 3 ) & 1
    obuf[ (i*8) +4 ] = ( ibuf[i] >> 4 ) & 1
    obuf[ (i*8) +5 ] = ( ibuf[i] >> 5 ) & 1
    obuf[ (i*8) +6 ] = ( ibuf[i] >> 6 ) & 1
    obuf[ (i*8) +7 ] = ( ibuf[i] >> 7 ) & 1
  '''
  
  # Set up the PIL image
  img = Image.frombytes( 'L', head[2:4], obuf, 'raw').quantize( colors=(1<<bpp), palette=pal, dither=Image.Dither.NONE ) # type: ignore
  
  # Save as PNG
  saveto = path.with_suffix('.png')
  img.save( saveto )
  
  return saveto

# Encode a regular recognised image format as .pi
def encode( path, paltuple ):
  
  if len(paltuple) == 2:
    bpp = 1
  elif len(paltuple) == 4:
    bpp = 2
  else:
    raise NotImplementedError('Invalid number of pallette colours')
  
  pal = _mkpal(paltuple)
  
  # Load in the image to convert
  with Image.open(path) as img:
    img.load()
  
  # First convert to RGB (or the next stage complains)
  img = img.convert(mode='RGB').quantize( colors=len(paltuple), palette=pal, dither=Image.Dither.NONE )
  
  # Show what it will look like
  img.show()
  
  # Get some stats
  width = img.width
  height = img.height
  ppb = 8 // bpp # Pixels per byte
  
  # Get the reduced image as just bytes
  # Each pixel is a byte
  # 0 = white
  # 1 = black
  # 2 = red
  # 3 = magenta
  indexed = img.tobytes()
  
  # 00 1 Version
  # 01 1 Data start pointer
  # 02 2 Width (pixels)
  # 04 2 Height (pixels)
  # 06 1 bits per pixel
  # 07 1 reserved
  # 08 DATA
  v = 1   # Format version
  ds = 8  # Data starts at byte 8
  head = pack('>BBHHBB', v, ds, width, height, bpp, 0)
  obuf = bytearray( width * height // ppb )
  
  # Convert from Pillow indexing to our format
  LUT = (
    0, # input 0 = white
    1, # input 1 = black
    2, # input 2 = red
    3, # input 3 = transparent
  )
  
  # 00 = 0 = white
  # 01 = 1 = black
  # 10 = 2 = red
  # 11 = 3 = transparent
  
  # Counts pixel position (one byte per pixel) within the input array
  p=0
  
  # Step through bytes of output buffer
  for i in range(len(obuf)):
    
    # Step through pixels within byte
    for j in range(ppb):
      
      # Encode pixel colour format and bitshift to correct position in byte
      #pixel = LUT[ indexed[p] ] << ((3-j)*2)
      pixel = LUT[ indexed[p] ] << (j*bpp)
      
      # Update the byte with the pixel
      obuf[i] = obuf[i] | pixel
      
      # Increment the pixel counter
      p += 1
  
  # Write out the file
  saveto = path.with_suffix(EXT)
  with open( saveto, 'wb') as fd:
    fd.write(head)
    fd.write(obuf)
  
  return saveto

# Convert the pallette tuple into an PIL Image
def _mkpal( p ):
  pal = Image.new( mode='P', size=( len(p), 1 ) )
  for i in range(len(p)):
    pal.putpixel( xy=(i,0), value=p[i] )
  return pal
