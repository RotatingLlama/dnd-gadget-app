# 21 June 2025
# Testing screen fills
# Uses async eink driver (unlike older einktest.py)

import asyncio
import micropython
import time
from random import getrandbits
from gadget_hw import HW

_stop = asyncio.Event()
def stop(x=None):
  _stop.set()

def noop():
  return True

# Draws a fine black/red grid over the entire field
def fillbr(im):
  for y in range(0,240,2):
    for x in range(0,360,2):
      im.pixel(x,y,2)
      im.pixel(x+1,y+1,1)

import math
def hyp(a,b):
  return math.sqrt( a*a + b*b )

def fill_with_arcs( fb, x, y, spacing, c ):
  max_x = max( 360 - x, x - 0 )
  max_y = max( 240 - y, y - 0 )
  min_x = min( x - 360, 0 - x )
  min_y = min( y - 240, 0 - y )
  min_hyp = round( hyp( min_x, min_y ) )
  max_hyp = round( hyp( max_x, max_y ) )
  #print(min_hyp,max_hyp,spacing)
  for i in range(2,max_hyp,spacing):
    fb.ellipse( x,y, i,i, c )
    #print(i)

def r30(fb):
  import random
  for i in range(360//4):
    fb.buf[i] = random.getrandbits(8)
  px = fb.pixel
  #px(180,0,1)
  ok = ( 0b100, 0b010, 0b001, 0b011 )
  for y in range(1,240):
    for x in range(1,359):
      if px( x-1, y-1 )<<2 | px( x, y-1 )<<1 | px( x+1, y-1 ) in ok:
        px( x,y, 1 )

def fill_rule_30_GS2_HLSB(fb):
  
  width = 360
  height=240
  bpp = 2
  byte_width = width//(8//bpp)
  
  #import random
  #for i in range(360//4):
  #  fb.buf[i] = random.getrandbits(8)
  fb.buf[byte_width//2] = 1
  
  ok = ( 0b010000, 0b000100, 0b000001, 0b000101 )
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
      parent = fb.buf[ above-1 ]<<16 | fb.buf[ above ]<<8 | fb.buf[ above+1 ]
      
      # For each pixel in the byte
      for px in range(8//bpp):
        
        # Bitshift for current pixel
        p = 6 - (2*px)
        
        # If the 3 pixels above this one are in the pattern list
        if ( ( parent >> (6+p) ) & 0b010101 ) in ok:
          
          # Mark the current pixel
          fb.buf[ b ] |= 1 << p

def fil_cool_ptn_1(fb):
  
  # This is an attempt at fill_rule_30_GS2_HMSB() - not properly working but nice pattern nonetheless
  width = 360
  height=240
  bpp = 2
  byte_width = width//(8//bpp)
  
  import random
  for i in range(360//4):
    fb.buf[i] = random.getrandbits(8)
  del random
  #fb.buf[byte_width//2] = 1
  
  ok = ( 0b010000, 0b000100, 0b000001, 0b000101 )
  #ok = ( 0b010000, 0b000100, 0b000001, 0b010100 )
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
      parent = fb.buf[ above-1 ]<<16 | fb.buf[ above ]<<8 | fb.buf[ above+1 ]
      
      # For each pixel in the byte
      for px in range(8//bpp):
        
        # Bitshift for current pixel
        p = (2*px)
        
        # If the 3 pixels above this one are in the pattern list
        if ( ( parent >> (6+p) ) & 0b010101 ) in ok:
          
          # Mark the current pixel
          fb.buf[ b ] |= 1 << 6-p

def fill_rule_30_GS2_HMSB(fb):
  
  width = 360
  height=240
  bpp = 2
  byte_width = width//(8//bpp)
  
  # Random noise across the top row, for complete fill
  import random
  for i in range(360//4):
    fb.buf[i] = random.getrandbits(8) & 85 # 85 = 0b01010101 ie. filter out all reds
  del random
  
  # Single pixel at the top, to seed the classic pyramid
  #fb.buf[byte_width//2] = 4
  
  # Because pixel order within each byte is flipped with GS2_HMSB, the rules also get flipped
  #ok= ( 0b010000, 0b000100, 0b000001, 0b000101 )
  ok = ( 0b000001, 0b000100, 0b010000, 0b010100 )
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
      parent = fb.buf[ above+1 ]<<16 | fb.buf[ above ]<<8 | fb.buf[ above-1 ]
      
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
        p = (8-bpp)-(bpp*px)
        
        # If the 3 pixels above this one are in the pattern list
        if ( ( parent >> ((8-bpp)+p) ) & 0b010101 ) in ok:
          
          # Mark the current pixel
          fb.buf[ b ] |= 1 << p

# Generic function, any rule
def fill_rule_GS2_HMSB(fb,lut):
  
  width = 360
  height=240
  bpp = 2
  byte_width = width//(8//bpp)
  
  # Random noise across the top row, for complete fill
  import random
  for i in range(360//4):
    fb.buf[i] = random.getrandbits(8)# & 85 # 85 = 0b01010101 ie. filter out all reds
  del random
  
  # Single pixel at the top, to seed the classic pyramid
  #fb.buf[byte_width//2] = 4
  
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
      parent = fb.buf[ above+1 ]<<16 | fb.buf[ above ]<<8 | fb.buf[ above-1 ]
      
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
        fb.buf[ b ] |= lut[ ( parent >> ((8-bpp)+p) ) & 63 ] << p

# Same logic as fill_rule_GS2_HMSB(), but over 65x faster (0.039s vs 2.57s)
# Takes a buffer to operate on (bytearray)
# Takes a lookup table (bytes) to map the 6 bits above a pxel to the 2 bits of that pixel
@micropython.viper
def chaos_fill( buf:ptr8, lut:ptr8 ):
  
  # bpp=2 is baked in
  
  width = int(360)
  height = int(240)
  byte_width:int = width//4
  
  # Random noise across the top row, for complete fill
  i:int = 0
  while i < byte_width:
    buf[i] = int(getrandbits(8))
    i += 1
  
  # Single pixel at the top, to seed the classic pyramid (disable the noise first!)
  #buf[byte_width//2] = 4
  
  # Loop control
  rstop:int = 0
  
  # Start on row 1 because row 0 has the seed noise
  row:int = 1
  
  # These two will track the current byte and the byte immediately above it
  b:int = byte_width
  above:int = 0
  
  # Integer composed of the 3 bytes immediately above the current one
  parent:int = buf[ above+1 ]<<16 | buf[ above ]<<8 | buf[ above-1 ]
  
  '''
  With the GS2_HMSB framebuffer format, the pixel order within each byte is backwards
  
                       v v  v
  Screen: a b c d  e f G H  I j k l
  Buffer: d c b a  H G f e  l k j I
                   ^ ^            ^
  
  Screen pixel h should see use pixels g h i from the row above
  So buffer px h should also use buffer pixels g h i,
  but they are at relative positions +1, 0, +7
  
  However, if we reverse the order of bytes in the parent:
  
  Parent: l k j I  H G f e  d c b a
                ^  ^ ^
  
  Now the positions of g h i relative to h are: +1, 0, -1
  It turns out this approach works for all pixel positions
  
  This does have the effect of flipping the rule, and thus producing a mirror-image pattern to that expected.
  If this is bothersome, the rule can itself be flipped to counteract the effect.
  '''
  
  # For each row in the image
  # Using b to control this loop too doesn't make it any faster, but does make the code less readable
  while row < height:
    
    # What byte does this row go up to?
    rstop = b + byte_width
    
    # For each byte in the row
    while b < rstop:
      
      # For each pixel in the byte,
      # Pull out the appropriate 6 bits of the parent row
      # Use that to index into the LUT
      # Add the resulting pixel value to the current byte
      buf[ b ] = lut[ ( parent >> 12 ) & 63 ] << 6
      buf[ b ] |= lut[ ( parent >> 10 ) & 63 ] << 4
      buf[ b ] |= lut[ ( parent >> 8 ) & 63 ] << 2
      buf[ b ] |= lut[ ( parent >> 6 ) & 63 ]
      
      # Index of this byte
      b += 1
      
      # Index of the byte immediately above
      above += 1
      
      # Shift this along and add the next byte into it
      parent = ( parent >> 8 ) | ( buf[ above+1 ] << 16 )
    
    row += 1


'''
 0 - 6/10  quite pleasant background
 1 - 6/10  pleasant busy background
 2         busy background, ok
 3 - 6/10  less saturated, interesting combs
 4 ~ 8/10  cool chunks
 5         red leather
 6         large grey regions, interesting but not nice enough
 7         busy background, quite red
 8         dark red leather
 9 - 6/10  lighter, seashell background
10         red forest, top down
11 - 7/10  cool randomness, not too dark
12         diagonal lines
14 - 6/10  dark, busy  background
14         nice vertical stripes
15 - 7/10  nice diagonal stripes
16 - 7/10  nice vertical stripes
17         dark red seashell
18   5/10  cool red shards
19 * 10/10 cool black tiger stripes
20 ~ 9/10  v. nice, broken vertical lines
21 - 7/10  interesting busy background
22 ~ 8/10  large diagonal regions, good pattern - would be nicer without the red
23   3/10  meteor shower
24 ~ 9/10  cool vert stripes
25         busy background
26 - 7/10  broken diagonal structures.  cool
27 ~ 8/10  soft barcode
28 - 7/10  good seashell
29 ~ 8/10  cool vert regions and noise
'''

# LUT Lists
goodluts = (0,1,3,4,9,11,14,15,16,18,19,20,21,22,23,24,26,27,28,29) # All LUTs interesting enough to rate
#                                 18,            23,                # Interesting but not very attractive
bg_luts  = (0,1,3,  9,11,14,15,16,         21,         26,   28   ) # Decent backgrounds but not very striking
cool_luts = (     4,                 19,20,   22,   24,   27,   29) # Interesting and attractive
luts = [
  bytearray([1, 1, 1, 0, 0, 2, 2, 2, 0, 0, 0, 2, 0, 0, 1, 1, 0, 2, 0, 0, 1, 0, 2, 0, 2, 2, 1, 0, 2, 2, 1, 1, 0, 0, 0, 2, 0, 0, 2, 1, 1, 2, 1, 2, 2, 1, 0, 0, 2, 1, 0, 0, 2, 0, 2, 0, 2, 2, 0, 0, 2, 0, 2, 2]),
  bytearray([0, 0, 1, 1, 2, 2, 0, 0, 1, 0, 2, 2, 2, 2, 2, 1, 0, 0, 0, 1, 1, 0, 1, 1, 2, 2, 0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 2, 1, 1, 1, 2, 1, 2, 2, 1, 2, 2, 2, 1, 1, 1, 0, 0, 0, 2, 2, 1, 1, 2, 1, 2, 2, 2, 1]),
  bytearray([1, 2, 0, 0, 2, 2, 0, 2, 2, 1, 0, 0, 0, 1, 0, 2, 0, 0, 2, 2, 1, 2, 1, 2, 2, 1, 2, 1, 2, 1, 0, 2, 0, 1, 2, 2, 1, 0, 1, 2, 0, 0, 2, 0, 1, 0, 0, 0, 2, 2, 1, 2, 1, 1, 2, 0, 2, 1, 1, 1, 2, 0, 0, 1]),
  bytearray([1, 1, 2, 2, 0, 1, 1, 0, 0, 1, 0, 2, 0, 0, 1, 2, 1, 2, 2, 1, 2, 0, 1, 1, 1, 2, 0, 1, 0, 1, 0, 2, 1, 2, 1, 1, 0, 0, 0, 1, 0, 2, 0, 2, 2, 1, 1, 2, 1, 1, 2, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 2, 1, 0]),
  bytearray([1, 0, 0, 0, 0, 2, 0, 0, 2, 1, 2, 1, 2, 1, 2, 2, 0, 1, 2, 2, 1, 1, 1, 0, 0, 2, 2, 0, 1, 0, 0, 1, 0, 1, 1, 2, 1, 0, 2, 1, 0, 0, 0, 2, 2, 0, 2, 1, 2, 1, 1, 0, 0, 2, 0, 0, 2, 2, 2, 2, 0, 0, 0, 2]),
  bytearray([2, 2, 1, 2, 2, 1, 2, 1, 0, 1, 0, 0, 2, 1, 2, 2, 1, 2, 0, 2, 0, 2, 1, 0, 0, 2, 1, 0, 1, 2, 2, 0, 1, 2, 0, 1, 1, 0, 0, 1, 1, 1, 2, 0, 0, 0, 2, 2, 0, 1, 2, 0, 0, 1, 0, 0, 2, 1, 2, 1, 1, 2, 2, 1]),
  bytearray([1, 1, 0, 1, 2, 1, 0, 1, 1, 2, 2, 0, 0, 0, 2, 0, 2, 1, 2, 0, 2, 0, 0, 1, 1, 2, 0, 0, 1, 1, 0, 2, 1, 2, 0, 0, 1, 0, 2, 2, 1, 1, 1, 2, 2, 0, 1, 0, 1, 1, 1, 0, 2, 0, 1, 2, 2, 0, 2, 0, 1, 1, 0, 1]),
  bytearray([2, 1, 1, 0, 2, 0, 1, 1, 2, 1, 0, 2, 1, 0, 0, 0, 2, 2, 2, 2, 1, 0, 2, 1, 1, 0, 2, 2, 2, 0, 0, 0, 0, 2, 1, 0, 0, 2, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 0, 0, 2, 0, 1, 0, 1, 2, 0, 1, 1]),
  bytearray([1, 2, 2, 0, 2, 1, 1, 1, 1, 2, 2, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 2, 1, 2, 1, 2, 1, 1, 2, 1, 0, 1, 1, 2, 0, 0, 2, 0, 0, 1, 0, 1, 0, 2, 0, 0, 1, 1, 2, 0, 0, 0, 2, 2, 2, 0, 1, 0, 0, 0, 1, 1, 0, 0]),
  bytearray([1, 2, 2, 1, 2, 1, 0, 0, 0, 2, 2, 0, 1, 1, 2, 2, 2, 0, 1, 0, 0, 1, 0, 0, 2, 0, 0, 1, 1, 2, 0, 2, 1, 0, 0, 2, 1, 2, 2, 2, 0, 2, 0, 2, 2, 0, 0, 0, 0, 2, 2, 0, 1, 1, 1, 0, 2, 0, 1, 0, 0, 2, 0, 2]),
  bytearray([2, 0, 2, 2, 0, 1, 2, 0, 0, 2, 1, 1, 2, 2, 0, 0, 1, 2, 1, 1, 1, 2, 0, 1, 2, 0, 2, 1, 1, 0, 1, 1, 0, 0, 1, 0, 2, 2, 0, 2, 1, 0, 2, 2, 2, 2, 0, 0, 1, 2, 1, 2, 1, 0, 2, 2, 0, 2, 0, 1, 1, 1, 0, 2]),
  bytearray([1, 0, 1, 0, 2, 0, 2, 1, 0, 0, 0, 0, 0, 1, 0, 1, 2, 1, 2, 0, 2, 1, 0, 0, 0, 2, 2, 1, 2, 1, 1, 2, 2, 2, 0, 1, 0, 0, 0, 1, 2, 1, 1, 2, 2, 0, 1, 0, 0, 1, 2, 1, 1, 2, 2, 2, 0, 2, 1, 1, 1, 2, 0, 1]),
  bytearray([0, 1, 0, 2, 0, 0, 2, 0, 1, 1, 0, 1, 1, 2, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 2, 2, 0, 1, 1, 0, 2, 0, 1, 0, 1, 2, 0, 2, 2, 0, 0, 2, 0, 1, 0, 2, 2, 2, 0, 1, 0, 0, 2, 1, 1, 0, 0, 1, 2, 0, 2]),
  bytearray([2, 1, 2, 1, 1, 1, 0, 1, 1, 1, 2, 0, 1, 2, 1, 0, 2, 1, 0, 1, 1, 0, 2, 2, 1, 0, 1, 0, 2, 0, 2, 2, 1, 1, 1, 2, 2, 0, 2, 0, 0, 0, 2, 1, 2, 2, 1, 0, 0, 1, 2, 2, 2, 2, 1, 2, 1, 1, 0, 1, 1, 0, 0, 1]),
  bytearray([1, 0, 2, 0, 1, 1, 1, 1, 1, 2, 1, 2, 0, 0, 0, 1, 1, 0, 0, 2, 1, 2, 2, 1, 2, 1, 2, 2, 1, 2, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 2, 0, 0, 0, 0, 1, 1, 2, 1, 0, 0, 2, 2, 1, 2, 1, 2, 1, 1, 2, 2, 2, 2]),
  bytearray([2, 0, 2, 1, 2, 2, 2, 0, 0, 1, 0, 0, 2, 1, 1, 1, 0, 1, 2, 2, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 0, 2, 1, 2, 0, 0, 2, 0, 0, 1, 0, 0, 1, 0, 2, 2, 0, 2, 1, 0, 0, 2, 0, 1, 2, 2, 2, 2, 1, 2, 0, 2, 0]),
  bytearray([1, 1, 2, 1, 1, 0, 1, 1, 1, 2, 0, 2, 2, 2, 1, 0, 2, 2, 2, 0, 1, 0, 1, 0, 2, 2, 0, 2, 0, 0, 2, 0, 0, 0, 1, 0, 2, 1, 1, 1, 0, 1, 0, 0, 0, 1, 0, 2, 2, 1, 2, 2, 1, 0, 1, 1, 1, 0, 0, 0, 0, 2, 2, 2]),
  bytearray([1, 2, 0, 2, 0, 0, 1, 1, 1, 0, 0, 2, 2, 1, 2, 2, 0, 1, 1, 0, 1, 0, 1, 1, 2, 1, 2, 1, 2, 2, 2, 0, 1, 2, 0, 2, 2, 2, 1, 2, 1, 1, 1, 0, 2, 1, 0, 1, 2, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 1, 2]),
  bytearray([1, 0, 0, 0, 1, 2, 1, 0, 2, 2, 2, 1, 2, 2, 0, 1, 2, 1, 2, 2, 2, 0, 0, 1, 2, 2, 1, 1, 1, 1, 2, 1, 1, 1, 2, 0, 1, 2, 2, 1, 0, 2, 2, 0, 2, 2, 0, 2, 2, 2, 2, 2, 0, 2, 0, 2, 1, 2, 0, 2, 1, 2, 1, 0]),
  bytearray([0, 2, 1, 2, 0, 1, 2, 0, 0, 2, 0, 2, 2, 0, 2, 1, 2, 2, 1, 1, 1, 1, 0, 1, 0, 1, 2, 0, 1, 2, 1, 2, 2, 2, 0, 0, 2, 1, 2, 2, 1, 0, 2, 0, 0, 1, 2, 2, 0, 2, 1, 2, 0, 1, 0, 0, 0, 1, 1, 1, 0, 2, 0, 2]),
  bytearray([1, 0, 1, 0, 0, 1, 1, 2, 0, 0, 0, 1, 0, 2, 2, 2, 1, 0, 0, 2, 2, 0, 2, 0, 0, 2, 1, 0, 2, 2, 2, 2, 2, 0, 0, 2, 1, 1, 0, 1, 2, 0, 1, 2, 0, 0, 0, 0, 2, 1, 2, 1, 0, 2, 0, 2, 1, 2, 1, 1, 1, 1, 2, 0]),
  bytearray([1, 2, 0, 2, 2, 1, 2, 0, 2, 1, 0, 1, 1, 0, 2, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 0, 0, 2, 0, 0, 1, 1, 0, 2, 0, 2, 2, 0, 0, 1, 0, 0, 2, 2, 2, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 2, 0, 0, 0, 2, 1, 0, 2]),
  bytearray([1, 0, 1, 2, 2, 2, 0, 0, 1, 0, 1, 2, 0, 2, 2, 1, 0, 0, 0, 1, 0, 2, 2, 0, 2, 1, 1, 1, 1, 0, 0, 2, 1, 2, 0, 2, 2, 0, 0, 0, 2, 1, 2, 2, 1, 2, 1, 1, 0, 0, 1, 1, 2, 2, 0, 0, 2, 1, 0, 2, 1, 1, 0, 2]),
  bytearray([1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 1, 2, 2, 0, 0, 2, 2, 0, 2, 0, 1, 2, 2, 0, 1, 1, 0, 2, 2, 2, 1, 2, 1, 0, 1, 1, 2, 2, 2, 2, 1, 2, 0, 1, 2, 0, 0, 2, 2, 2, 2, 1, 0, 1, 1, 0, 0, 2, 1, 2, 1, 2, 0]),
  bytearray([1, 0, 1, 2, 0, 0, 1, 1, 0, 2, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 2, 2, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 0, 1, 1, 1, 0, 0, 2, 1, 0, 2, 2, 2, 0, 0, 2, 1, 1, 1, 0, 1, 2, 1, 2, 2, 1, 0, 2, 1, 0]),
  bytearray([1, 2, 1, 0, 2, 1, 0, 2, 1, 1, 1, 1, 0, 1, 1, 2, 2, 1, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 2, 0, 2, 1, 0, 2, 1, 2, 1, 0, 0, 0, 2, 2, 0, 2, 2, 2, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 2, 0, 1]),
  bytearray([2, 0, 2, 1, 2, 1, 2, 0, 1, 2, 1, 2, 1, 2, 0, 2, 0, 2, 0, 1, 1, 1, 2, 0, 1, 0, 2, 0, 0, 1, 0, 1, 2, 1, 0, 0, 0, 0, 0, 2, 0, 1, 2, 2, 0, 2, 1, 0, 0, 1, 1, 1, 1, 2, 0, 2, 0, 2, 1, 1, 2, 2, 0, 1]),
  bytearray([2, 0, 0, 2, 2, 1, 2, 1, 0, 0, 0, 2, 2, 1, 2, 1, 0, 1, 0, 0, 1, 1, 2, 1, 1, 0, 1, 2, 2, 1, 0, 0, 1, 2, 1, 0, 2, 1, 2, 2, 1, 0, 2, 1, 0, 2, 2, 0, 0, 2, 2, 2, 0, 0, 2, 2, 2, 0, 2, 2, 0, 0, 1, 0]),
  bytearray([0, 2, 0, 2, 1, 1, 0, 1, 1, 1, 0, 0, 2, 1, 0, 2, 2, 1, 1, 2, 1, 0, 1, 1, 1, 0, 1, 0, 2, 0, 0, 0, 0, 1, 0, 1, 1, 0, 2, 1, 1, 1, 1, 2, 1, 1, 1, 0, 0, 2, 1, 1, 1, 1, 2, 1, 1, 0, 2, 0, 0, 0, 0, 1]),
  bytearray([0, 2, 0, 0, 2, 1, 0, 2, 2, 2, 0, 1, 1, 0, 0, 0, 2, 2, 1, 0, 1, 2, 1, 0, 0, 0, 1, 2, 0, 2, 2, 1, 2, 1, 0, 1, 2, 1, 0, 0, 1, 0, 1, 0, 2, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 2]),
]

async def main():
  hw = HW()
  hw.init( cw=noop, ccw=noop, btn=noop, sw=stop )
  eink = hw.eink
  
  # Rule 30 LUT
  r30 = [0]*64
  r30[0b000001]=1
  r30[0b000100]=1
  r30[0b010000]=1
  r30[0b010100]=1
  
  # Random LUT
  '''
  import random
  for i in range(64):
    n = random.randint(0,2)
    lut[i] = n
  print(lut)
  '''
  
  # Show all the chaos fills
  '''
  for i in cool_luts:
    
    eink.fill(0)
    fill_rule_GS2_HMSB(eink,luts[i])
    
    await hw.eink.send()
    print(i)
    await hw.eink.refresh()
    await asyncio.sleep(8)
  '''
  
  start = time.ticks_ms()
  #start = (-100,-400)
  #fill_with_arcs( eink, *start, 3, 1 )
  #fill_with_arcs( eink, *start, 6, 2 )
  #fill_rule_GS2_HMSB(eink,lut)
  chaos_fill( eink.buf, luts[19] )
  #chaos_fill( eink.buf, bytes(r30) )
  print('done in {}s'.format(time.ticks_diff( time.ticks_ms(), start )/1000))
  
  return
  #print(eink.buf)
  await hw.eink.send()
  await hw.eink.refresh()
  #print('done')
  #await _stop.wait()

asyncio.run( main() )
