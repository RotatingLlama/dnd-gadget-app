# Drawing functions
#
# T. Lloyd
# 23 Mar 2026

# Standard libraries
import micropython
from micropython import const
#from array import array
from math import sin, cos #, tan
from random import getrandbits, randint
#from gc import collect as gc_collect
#import time

# Our libraries
import img
from .common import CHAR_HEAD, CHAR_BG

# ASSETS
_IMG_LOGO_OLED= const('/assets/oledlogo.pi')
_IMG_CHOOSE_W = const('/assets/choose_w.2ink')
_IMG_CHOOSE_R = const('/assets/choose_r.2ink')
#_IMG_SKULL    = const('/assets/skull.pi')
#_IMG_LOWBATT  = const('/assets/low_batt.2ink')
_IMG_DEADBATT = const('/assets/deadbatt.2ink')
_IMG_NOSD     = const('/assets/nosd.pi')
_IMG_NOSD_SM  = const('/assets/nosd_24x16.pi')

# Universal constants
# MP-1.24.1 seems to round floats to 7 d.p.
# These values are consistent with each other and are collectively as accurate as possible within the constraints
_PI_2 = const(1.5707963)
_PI   = const(3.1415926)
_TAU  = const(6.2831852)
_DEG  = const(0.01745329) # pi/180

# EINK SIZE
_EINK_WIDTH  = const(360)
_EINK_HEIGHT = const(240)

# Character heads
_CHAR_HEAD_SIZE = const(64)
_MAX_CHAR_HEADS = const(6)

# Geometry for NeedleMenu
_X = const(184)
_Y = const(292)
#
_ACENTRE = const( 0 ) # Angle of midpoint of arc (relative to 12 o'clock)
_ATOTAL  = const( _DEG * 100 ) # Total angle made by arc
_ASTART  = const( _ACENTRE - (_ATOTAL/2) ) # Angle of start of arc
_AEND    = const( _ASTART + _ATOTAL ) # Angle of end of arc
_APX     = const( _DEG * 0.4 ) # Angle of one pixel thickness
#
_RI = const(157)
_ARC_THICKNESS = const(10)
_RO = const( _RI + _ARC_THICKNESS )
#
_ARC2_RI = const(171) # round(RI + _ARC_THICKNESS * 1.4)
_ARC2_THICKNESS = const(3)
_ARC2_RO = const( _ARC2_RI + _ARC2_THICKNESS)

# Rules (LUTs) for chaos_fill()
# Each is 64 elements long, defining a value for every possible combination of 6 bits
# [3] - try to swap the red for white?
cool_luts = (
  bytes([1, 0, 0, 0, 0, 2, 0, 0, 2, 1, 2, 1, 2, 1, 2, 2, 0, 1, 2, 2, 1, 1, 1, 0, 0, 2, 2, 0, 1, 0, 0, 1, 0, 1, 1, 2, 1, 0, 2, 1, 0, 0, 0, 2, 2, 0, 2, 1, 2, 1, 1, 0, 0, 2, 0, 0, 2, 2, 2, 2, 0, 0, 0, 2]),
  bytes([0, 2, 1, 2, 0, 1, 2, 0, 0, 2, 0, 2, 2, 0, 2, 1, 2, 2, 1, 1, 1, 1, 0, 1, 0, 1, 2, 0, 1, 2, 1, 2, 2, 2, 0, 0, 2, 1, 2, 2, 1, 0, 2, 0, 0, 1, 2, 2, 0, 2, 1, 2, 0, 1, 0, 0, 0, 1, 1, 1, 0, 2, 0, 2]),
  bytes([1, 0, 1, 0, 0, 1, 1, 2, 0, 0, 0, 1, 0, 2, 2, 2, 1, 0, 0, 2, 2, 0, 2, 0, 0, 2, 1, 0, 2, 2, 2, 2, 2, 0, 0, 2, 1, 1, 0, 1, 2, 0, 1, 2, 0, 0, 0, 0, 2, 1, 2, 1, 0, 2, 0, 2, 1, 2, 1, 1, 1, 1, 2, 0]),
  bytes([1, 0, 1, 2, 2, 2, 0, 0, 1, 0, 1, 2, 0, 2, 2, 1, 0, 0, 0, 1, 0, 2, 2, 0, 2, 1, 1, 1, 1, 0, 0, 2, 1, 2, 0, 2, 2, 0, 0, 0, 2, 1, 2, 2, 1, 2, 1, 1, 0, 0, 1, 1, 2, 2, 0, 0, 2, 1, 0, 2, 1, 1, 0, 2]),
  bytes([1, 0, 1, 2, 0, 0, 1, 1, 0, 2, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 2, 2, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 0, 1, 1, 1, 0, 0, 2, 1, 0, 2, 2, 2, 0, 0, 2, 1, 1, 1, 0, 1, 2, 1, 2, 2, 1, 0, 2, 1, 0]),
  bytes([2, 0, 0, 2, 2, 1, 2, 1, 0, 0, 0, 2, 2, 1, 2, 1, 0, 1, 0, 0, 1, 1, 2, 1, 1, 0, 1, 2, 2, 1, 0, 0, 1, 2, 1, 0, 2, 1, 2, 2, 1, 0, 2, 1, 0, 2, 2, 0, 0, 2, 2, 2, 0, 0, 2, 2, 2, 0, 2, 2, 0, 0, 1, 0]),
  bytes([0, 2, 0, 0, 2, 1, 0, 2, 2, 2, 0, 1, 1, 0, 0, 0, 2, 2, 1, 0, 1, 2, 1, 0, 0, 0, 1, 2, 0, 2, 2, 1, 2, 1, 0, 1, 2, 1, 0, 0, 1, 0, 1, 0, 2, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 2]),
)
# 0 - Busy interesting pattern, mostly red.  CONFIRMED
# 1 - tiger stripes, reddish.  CONFIRMED
# 2 - regions of red vert stripes, in chaos. Reddish.  CONFIRMED
# 3 - diagonal pattern, very red.  CONFIRMED
# 4 - red/black vert lines.  white text shows up better.  CONFIRMED
# 5 - barcodey with reddish int.  More black.
# 6 - vert lines and chaos.  very red.  CONFIRMED
# Mainly red (2) or mainly black (1)?
lut_colours = bytes([2,2,2,2,2,2,2])

# Error phrases for render_sd_error()
_SD_ERRORS = {
  #   '123456789__123456789',123456789',
  1 : ' Card not\n present!',
  2 : 'Card     \nunready, \nor faulty',
  3 : 'Could not\nmount SD!',
  4 : ' No files\n on SD!  ',
}

# Takes a buffer (bytearray) to operate on
# Takes a lookup table (bytes) to map the 6 bits above a pxel to the 2 bits of that pixel
@micropython.viper
def chaos_fill( buf:ptr8, lut:ptr8 ):
  
  # bpp=2 is baked in
  
  #width = int( _EINK_WIDTH )
  #height = int( _EINK_HEIGHT )
  byte_width:int = _EINK_WIDTH // 4
  
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
  while row < _EINK_HEIGHT:
    
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

# Draws the character select screen to the given framebuffer
# Expects 360x240 2bpp framebuffer
# Needs chars list from Gadget._find_chars()
# Returns same list, truncated to only the chars displayed (subject to _MAX_CHAR_HEADS)
def draw_char_select( fb, chars ):
  
  # Fill with a cool background
  i = randint(0, len(cool_luts)-1)
  print(f'LUT {i} today')
  chaos_fill( fb.buf, cool_luts[i] )
  
  # Do we want red text or white text in our banner?
  if lut_colours[i] == 1:
    c = _IMG_CHOOSE_R
  else:
    c = _IMG_CHOOSE_W
  
  # Add the banner
  img.blit_onto( fb, 0,0, c, 3 )
  
  # Truncate list to max length
  chars = chars[:_MAX_CHAR_HEADS]
  
  # Angular distance between heads, and position of first head
  if len(chars) > 1:
    da = _ATOTAL / ( len(chars) - 1 )
    a = _ASTART
  else:
    da = 0
    a = _ACENTRE
  
  # Offset to centre of character head (instead of top left)
  hdos = _CHAR_HEAD_SIZE // 2
  
  # Truncate text names
  max_name_len = _CHAR_HEAD_SIZE // 8 # Assume 8px letter width
  
  for char in chars:
    
    # Is there a headshot?
    head = ( char.dir / CHAR_HEAD )
    headok = head.is_file()
    if headok:
      try:
        x = round( _X + _ARC2_RI*sin(a) -hdos )
        y = round( _Y - _ARC2_RI*cos(a) -hdos )
        img.blit_onto( fb, x, y, str(head) )
      except (RuntimeError, NotImplementedError) as e:
        headok = False
    
    # If no head (that we can use)
    if not headok:
      txt = char.stats['name'][:max_name_len]
      x = round( _X + _ARC2_RI*sin(a) - (len(txt)*4) )
      y = round( _Y - _ARC2_RI*cos(a) -4 )
      fb.rect(x-2, y-2, len(txt)*8 +4, 12, 2, False )
      fb.rect(x-1, y-1, len(txt)*8 +2, 10, 0, True )
      fb.text( txt, x,y, 1 )
      
    a += da
  
  # We might have displayed fewer chars than we were given, so return the list we actually used
  return chars

# Draws a 'dead battery' graphic to the framebuffer
def draw_dead_batt(fb):
  img.load_into( fb.buf, _IMG_DEADBATT )

def render_boot_logo(oled):
    fb = img.load( _IMG_LOGO_OLED )
    oled.blit(fb,0,0)
    oled.show()
    
# Render the SD error screen on the oled, with some text.
def render_sd_error( e:int, oled ):
  
  oled.fill(0)
  
  # No-SD graphic
  fb = img.load( _IMG_NOSD )
  oled.blit(fb,0,0)
  
  # Display message
  lines = _SD_ERRORS[e].split('\n')
  h = min( len(lines)*8, 32 )
  y = ( 32 - h ) // 2
  for line in lines:
    oled.text( line, 57,y )
    y += 8
  
  oled.show()

# Returns a framebiuffer with the small (24x16) nosd image in it, ready for blitting
def get_sd_fb():
  return img.load( _IMG_NOSD_SM )
