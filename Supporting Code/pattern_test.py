# For rapidly iterating through chaos backgrounds for the eink
#
# 20 Jun 2025

from PIL import Image

def fill_rule_GS2_HMSB(buf,lut):
  
  width = 360
  height=240
  bpp = 2
  byte_width = width//(8//bpp)
  
  # Random noise across the top row, for complete fill
  import random
  for i in range(360//4):
    buf[i] = random.getrandbits(8)# & 85 # 85 = 0b01010101 ie. filter out all reds
  #del random
  
  # Single pixel at the top, to seed the classic pyramid
  #buf[byte_width//2] = 4
  
  parent = 0
  
  # For each row in the image
  for row in range(1,height):
    
    # Index of the first byte of this row
    rb0 = row*byte_width
    
    # For each byte in the row
    for rb in range(byte_width):
      
      # Index of this byte
      b = rb0 + rb
      
      # Index of the byte immediately above
      above = b - byte_width
      
      # Integer composed of the 3 bytes immediately above
      parent = buf[ above+1 ]<<16 | buf[ above ]<<8 | buf[ above-1 ]
      
      # Buffer: d c b a  h g f e  l k j i
      # Screen: a b c d  e f g h  i j k l
      #
      # screen e should see screen d e f
      # so buffer h sees buffer a h g
      #
      # screen x should see screen x-1, x, x+1
      # so buffer (3-x) should see buffer (3- x-1), (3- x), (3- x+1)
      #           (3-x)                   (2-x)     (3-x)   (4-x)
      #           -x                      (-1-x)    (-x)    (1-x)
      #           x                       (x+1)     (x)     (x-1)
      # 
      # This will work if the order of the bytes in parent is flipped
      
      # For each pixel in the byte
      for px in range(8//bpp):
        
        # Bitshift for current pixel
        #   6 - ( 2 * px )
        p = (8-bpp)-(bpp*px)
        
        # if ( ( parent >> ((8-bpp)+p) ) & 0b010101 ) in ok:
        # Mark the current pixel
        buf[ b ] |= lut[ ( parent >> ((8-bpp)+p) ) & 63 ] << p

#

width = 360
height=240
bpp = 2
byte_width = width//(8//bpp)

buf_size = byte_width * height
buf = bytearray( buf_size )

# Set up blank LUT
lut = [0]*64

# Rule 30
'''
lut[0b000001]=1
lut[0b000100]=1
lut[0b010000]=1
lut[0b010100]=1
'''

# Random LUT
import random
for i in range(64):
  n = random.randint(0,2)
  lut[i] = n
print(lut)

# Go
fill_rule_GS2_HMSB(buf,lut)


bigbuf = bytearray(width*height)
for i in range(buf_size):
  b = buf[i]
  bb = i*4
  bigbuf[bb] = b & 3
  bigbuf[bb+1] = (b>>2) & 3
  bigbuf[bb+2] = (b>>4) & 3
  bigbuf[bb+3] = (b>>6) & 3


# Construct the colour pallette
pal = Image.new( mode='P', size=(4,1) )
pal.putpixel( xy=(0,0), value=(255,255,255) ) # 0 = white
pal.putpixel( xy=(1,0), value=(0,0,0) )       # 1 = black
pal.putpixel( xy=(2,0), value=(255,0,0) )     # 2 = red
pal.putpixel( xy=(3,0), value=(255,0,255) )   # 3 = transparent

#img = Image.frombytes( 'L', head[2:4], ibuf, 'raw').quantize( colors=3, palette=pal )

im = Image.frombytes( mode='L', size=(360,240), data=bigbuf, decoder_name='raw' ).quantize( colors=3, palette=pal )
im.show()