# pico-image converter
#
# 08 Feb 2026

# pallet is a list of tuples, mapping list indices to RGB values
# For example:
# pallet = [
#   (255,255,255), # 0 = White
#   (  0,  0,  0), # 1 = Black
#   (255,  0,  0), # 2 = Red
#   (255,  0,255), # 3 = Magenta
# ]
type Pallet = list[tuple[int,int,int]]

from PIL import Image
from struct import pack, unpack

# Our file format extension
EXT = '.pi'

# Standard image formats we recognise (incomplete list)
imageTypes = ( '.jpg', '.jpeg', '.gif', '.png' )


# Convert pi to PNG
def decode( path:str, pallet:Pallet ):
  '''Convert a Pico-Image to a PNG
  
  path:   The file path of the Pico-Image to convert
  pallet: A list of 3-tuples, mapping between the list indices and RGB values
  '''
  
  pal = _mkpal(pallet)
  
  # Load in the file
  fd = open( path, 'rb' )
  top = fd.read(2)
  
  # Get the version from the first byte
  version = top[0]
  
  # Check we know what we're doing
  if version > 1:
    raise NotImplementedError(f'File version ({version}) not supported')
  
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
  
  # Extract values from the head
  im_width = head[2]
  height = head[3]
  bpp = head[4]
  ppb = 8 // bpp
  data_width = im_width + (-im_width % ppb)
  
  # How long should the data section be?
  byte_len = data_width * height // ppb
  
  # Check for file read errors
  if len(ibuf) != byte_len:
    raise RuntimeError(f'Expected file length {byte_len}, but got {len(ibuf)}!')
  
  # Only support 1 or 2 bpp
  if bpp > 2:
    raise NotImplementedError('No support for BPP more than 2')
  
  # Unpack into one byte per pixel
  obuf = bytearray( data_width * height )
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
  img = Image.frombytes(
    mode='L',
    size=(data_width,height),
    data=obuf,
    decoder_name='raw'
  ).quantize(
    colors=(1<<bpp),
    palette=pal,
    dither=Image.Dither.NONE
    # type: ignore
  ).crop(
    (0,0,im_width,height)
  )
  
  # Save as PNG
  saveto = path + '.png'
  img.save( saveto )
  
  return saveto

# Encode a regular recognised image format as .pi
def encode( path:str, pallet:Pallet ):
  '''Convert a regular image to a Pico-Image
  
  path:   The file path of the image to convert
  pallet: A list of 3-tuples representing RGB values, where the list's indices will form the colour indices in the Pico-Image
  
  Palletises the given input image as closely as possible to the given RGB values.  Does not dither.
  '''
  
  if len(pallet) == 2:
    bpp = 1
  elif len(pallet) == 4:
    bpp = 2
  else:
    raise NotImplementedError('Invalid number of pallet colours (must be 2 or 4)')
  
  pal = _mkpal(pallet)
  
  # Load in the image to convert
  with Image.open(path) as original_img:
    original_img.load()
  
  # Get some stats
  original_width = original_img.width
  height = original_img.height
  ppb = 8 // bpp # Pixels per byte
  
  # First convert to RGB (or quantize complains)
  original_img = original_img.convert(mode='RGB').quantize( colors=len(pallet), palette=pal, dither=Image.Dither.NONE )
  
  # Show what it will look like
  original_img.show()
  
  # Ensure the width is padded out to a whole number of bytes
  encoded_width = original_width + (-original_width % ppb)
  #img = Image.new( mode='RGB', size=(encoded_width, height), color=paltuple[0] )
  img = Image.new( mode='P', size=(encoded_width, height), color=0 )
  img.paste( original_img, (0, 0) )
  
  # Get the reduced image as just bytes
  # Each pixel is a byte
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
  head = pack('>BBHHBB', v, ds, original_width, height, bpp, 0)
  obuf = bytearray( encoded_width * height // ppb )
  
  # Counts pixel position (one byte per pixel) within the input array
  p=0
  
  # Step through bytes of output buffer
  for i in range(len(obuf)):
    
    # Step through pixels within byte
    for j in range(ppb):
      
      # Bitshift pixel value to correct position in byte
      pixel = indexed[p] << (j*bpp)
      
      # Update the byte with the pixel
      obuf[i] = obuf[i] | pixel
      
      # Increment the pixel counter
      p += 1
  
  # Write out the file
  saveto = path + EXT
  with open( saveto, 'wb') as fd:
    fd.write(head)
    fd.write(obuf)
  
  return saveto

# Convert the pallette tuple into an PIL Image
def _mkpal( p:Pallet ):
  pal = Image.new( mode='P', size=( len(p), 1 ) )
  for i in range(len(p)):
    pal.putpixel( xy=(i,0), value=p[i] )
  return pal
