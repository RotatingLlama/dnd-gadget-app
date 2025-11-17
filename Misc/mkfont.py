# e-ink font converter
#
# 24 Feb 2025

import tkinter as tk
from tkinter.filedialog import askopenfilename
from tkinter import messagebox
from pathlib import Path
from PIL import Image
from struct import pack#, unpack
from sys import exit

# Our file format extension
EXT = '.2f'

# Standard image formats we recognise (incomplete list)
imageTypes = ( '.jpg', '.jpeg', '.gif', '.png' )

# Construct the 2-colour pallette
pal1 = Image.new( mode='P', size=(2,1) )
pal1.putpixel( xy=(0,0), value=(255,0,255) )   # 0 = transparent
pal1.putpixel( xy=(1,0), value=(0,0,0) )       # 1 = black

# Construct the 4-colour pallette
pal2 = Image.new( mode='P', size=(4,1) )
pal2.putpixel( xy=(0,0), value=(255,0,255) )   # 0 = transparent
pal2.putpixel( xy=(1,0), value=(0,0,0) )       # 1 = black
pal2.putpixel( xy=(2,0), value=(255,0,0) )     # 2 = red
pal2.putpixel( xy=(3,0), value=(255,255,255) ) # 3 = white

def encode(path):
  
  # Params
  # TODO: figure out a way to get these from user, don't hardcode
  #
  bpp = 1
  glyph_height = 13
  glyph_width = 10
  glyph_height_above_baseline = 12
  num_glyphs = 37
  #
  # Where in the image each glyph is
  # Table must start at ASCII 32, but can be any length (up to ASCII 255)
  glyph_index = [
  # 32, 33, ...
  #    !  "  #  $  %  &  '
    0, 0, 0, 0, 0, 0, 0, 0,
  # (  )  *  +  ,  -  .  /
    0, 0, 0, 0, 0, 0, 0, 0,
  #  0  1  2  3  4  5  6  7
    27,28,29,30,31,32,33,34,
  # 8  9  :  ;  <  =  >  ?
    35,36,0, 0, 0, 0, 0, 0,
  # @  A  B  C  D  E  F  G
    0, 1, 2, 3, 4, 5, 6, 7,
  # HIJKLMNO
    8, 9,10,11,12,13,14,15,
  # PQRSTUVW
    16,17,18,19,20,21,22,23,
  #  X  Y  Z  [  \  ]  ^  _
    24,25,26, 0, 0, 0, 0, 0,
  # `  a  b  c  d  e  f  g
    0, 1, 2, 3, 4, 5, 6, 7,
  # hijklmno
    8, 9,10,11,12,13,14,15,
  # pqrstuvw
    16,17,18,19,20,21,22,23,
  #  x  y  z  {  |  }  ~  127
    24,25,26
  ]
  #
  # Table should follow glyph index order
  #variable_width_table = None
  variable_width_table = [
    0,    
    12, 12, 11, 12, 11, 9, 11, 12,
    6, 9, 12, 10, 13, 12, 12, 11,
    13, 13, 8, 10, 12, 13, 13, 11,
    10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10
  ]
  #
  # End of params
  
  # Load in the image to convert
  with Image.open(path) as img:
    img.load()
  
  # Input validation
  assert glyph_height*num_glyphs == img.height
  if variable_width_table is not None:
    assert len(variable_width_table) == num_glyphs
  
  # Figure out some pallette stuff
  assert bpp in (1,2)
  if bpp == 1:
    pal = pal1
    transparent_rgb = 'rgb(255,0,255)'
    #transparent_index = 0
  else:
    pal = pal2
    transparent_rgb = 'rgb(255,0,255)'
    #transparent_index = 3
  
  # If the image isn't a multiple of 8 pixels wide, pad it with transparency
  to_add = -img.width % 8
  if to_add > 0:
    new_width = img.width + to_add
    new_img = Image.new( mode='RGB', size=( new_width, img.height ), color=transparent_rgb )
    new_img.paste( img, (0,0) )
    img = new_img
    del to_add, new_img
  
  # Get dims
  width = img.width
  #width_bytes = width//8
  height = img.height
    
  # Convert to indexed
  img = img.convert(mode='RGB').quantize( colors=2**bpp, palette=pal, dither=Image.Dither.FLOYDSTEINBERG )
  
  # Get some stats
  width = img.width
  height = img.height
  #byte_width = width // 8
  
  # Get the image as just bytes
  # Each pixel is a byte
  img_bytes = img.tobytes()
  
  # Setup the output image buffer
  output_bits = height * width * bpp
  output_len = output_bits // 8
  output = bytearray(output_len)
  #pixels_per_byte = 8//bpp
  
  # Counts pixel position (one byte per pixel) within the input array
  p=0
  
  # Generate the output image
  for i in range(output_len):
    
    # Step through pixels within byte
    for j in range( 0, 8, bpp ):
      
      # Encode pixel colour format and bitshift to correct position in byte
      pixel = img_bytes[p] << ((8-bpp)-j)
      
      # Update the byte with the pixel
      output[i] = output[i] | pixel
      
      # Increment the pixel counter
      p += 1
  
  # We are version 1
  version = 1
  
  # Where will the image data be?
  index_length = len(glyph_index)
  ptr_img = 0x10 + index_length
  
  # Figure out the variable widths table pointer
  # Table goes after image data
  if variable_width_table is None:
    ptr_variable_width = 0
  else:
    ptr_variable_width = ptr_img + output_len
  
  '''
  0x00 1   Format version (must be 1)
  0x01 1   Image width, in pixels
  0x02 1   Glyph height, in pixels
  0x03 1   Number of glyphs
  0x04 1   Bits per pixel
  0x05 1   Glyph width (ignored if variable width table is given)
  0x06 1   Baseline height
  0x07 1   Index length
  0x08 2   Pointer to start of image data
  0x0A 2   Pointer to optional table of individual glyph widths.  If zero, assume monospace
  0C   4   Reserved
  10   x   Glyph Index Table
  '''
  # Construct the head (bytes 0x00 to 0x0F)
  head = pack( '>8B2H4x',
    version,
    width,
    glyph_height,
    num_glyphs,
    bpp,
    glyph_width,
    glyph_height_above_baseline,
    index_length,
    ptr_img,
    ptr_variable_width,
  )

  # Write out the file
  with open( path.with_suffix(EXT), 'wb') as fd:
    fd.write(head)
    fd.write(bytes(glyph_index))
    fd.write(output)
    if variable_width_table is not None:
      fd.write(bytes(variable_width_table))

def decode(path):
  messagebox.showerror('Not Implemented','Font decode is not supported yet')
  raise NotImplementedError('No decode functionality yet')

# If this file has been run directly
if __name__ == "__main__":
  
  # We don't want a full GUI, so keep the root window from appearing
  tk.Tk().withdraw()
  
  # Get the image file to convert
  path = Path( askopenfilename() )
  
  if not path.name:
    print('Cancelled')
    exit()
    
  # What to do?
  if path.suffix == EXT:
    decode(path)
  else:
    encode(path)
