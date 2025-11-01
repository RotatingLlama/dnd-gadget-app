# e-ink image converter
#
# 03 Feb 2025 : Original file
# 05 Apr 2025 : Reversed pixel order within byte (GS2_HMSB format; matches 99% of other software)

# TODO: Do this properly
# https://pillow.readthedocs.io/en/stable/handbook/writing-your-own-image-plugin.html#file-codecs-py

import tkinter as tk
from tkinter.filedialog import askopenfilename 
from pathlib import Path
from PIL import Image #, ImagePalette
from struct import pack, unpack

# Our file format extension
EXT = '.2ink'

# Standard image formats we recognise (incomplete list)
imageTypes = ( '.jpg', '.jpeg', '.gif', '.png' )

# Construct the colour pallette
pal = Image.new( mode='P', size=(4,1) )
pal.putpixel( xy=(0,0), value=(255,255,255) ) # 0 = white
pal.putpixel( xy=(1,0), value=(0,0,0) )       # 1 = black
pal.putpixel( xy=(2,0), value=(255,0,0) )     # 2 = red
pal.putpixel( xy=(3,0), value=(255,0,255) )   # 3 = transparent

# Convert 2ink to PNG
def decode(path):
  
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
  buf = fd.read()
  
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
  assert len(buf) == ( head[2] * head[3] * head[4] ) // 8
  
  # Only support 2bpp
  assert head[4] == 2
  
  # Unpack into one byte per pixel
  ibuf = bytearray( head[2] * head[3] )
  '''
  for i in range(len(buf)):
    ibuf[ (i*4) ] = ( buf[i] >> 6 ) & 3
    ibuf[ (i*4) +1 ] = ( buf[i] >> 4 ) & 3
    ibuf[ (i*4) +2 ] = ( buf[i] >> 2 ) & 3
    ibuf[ (i*4) +3 ] = buf[i] & 3
  '''
  for i in range(len(buf)):
    ibuf[ (i*4) ] = buf[i] & 3
    ibuf[ (i*4) +1 ] = ( buf[i] >> 2 ) & 3
    ibuf[ (i*4) +2 ] = ( buf[i] >> 4 ) & 3
    ibuf[ (i*4) +3 ] = ( buf[i] >> 6 ) & 3
  
  # Set up the PIL image
  img = Image.frombytes( 'L', head[2:4], ibuf, 'raw').quantize( colors=3, palette=pal )
  
  # Save as PNG
  saveto = path.with_suffix('.png')
  img.save( saveto )
  
  return saveto

# Encode a regular recognised image format as .2ink
def encode(path):
  
  # Load in the image to convert
  with Image.open(path) as img:
    img.load()
  
  # First convert to RGB (or the next stage complains)
  img = img.convert(mode='RGB').quantize( colors=4, palette=pal, dither=Image.Dither.FLOYDSTEINBERG )
  
  # Show what it will look like
  img.show()
  
  # Get some stats
  width = img.width
  height = img.height
  byte_width = width // 8
  
  # Get the reduced image as just bytes
  # Each pixel is a byte
  # 0 = white
  # 1 = black
  # 2 = red
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
  bpp = 2 # 2 bits per pixel
  head = pack('>BBHHBB', v, ds, width, height, bpp, 0)
  buf = bytearray( byte_width * height * bpp )
  
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
  for i in range(len(buf)):
    
    # Step through pixels within byte
    for j in range(4):
      
      # Encode pixel colour format and bitshift to correct position in byte
      #pixel = LUT[ indexed[p] ] << ((3-j)*2)
      pixel = LUT[ indexed[p] ] << (j*2)
      
      # Update the byte with the pixel
      buf[i] = buf[i] | pixel
      
      # Increment the pixel counter
      p += 1
  
  # Write out the file
  saveto = path.with_suffix(EXT)
  with open( saveto, 'wb') as fd:
    fd.write(head)
    fd.write(buf)
  
  return saveto

# If this file has been run directly
if __name__ == "__main__":
  
  # We don't want a full GUI, so keep the root window from appearing
  tk.Tk().withdraw()
  
  # Get the image file to convert
  path = Path( askopenfilename() )

  # What to do?
  if path.suffix == EXT:
    out = decode(path)
  else:
    out = encode(path)
  
  if out is not None:
    print('Saved to:',out)
