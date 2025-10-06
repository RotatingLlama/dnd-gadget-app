# Drawing functions
#
# T. Lloyd
# 06 Oct 2025

# Standard libraries
import micropython
from micropython import const
from array import array
from math import sin, cos, tan
from random import getrandbits, randint
from gc import collect as gc_collect
#import time
from framebuf import FrameBuffer, MONO_HLSB, GS2_HMSB

# Our libraries
import img
from .common import CHAR_HEAD, CHAR_BG

# ASSETS
_IMG_CHOOSE_W = const('/assets/choose_w.2ink')
_IMG_CHOOSE_R = const('/assets/choose_r.2ink')
_IMG_SKULL    = const('/assets/skull.2ink')
_IMG_LOWBATT  = const('/assets/low_batt.2ink')
_IMG_DEADBATT = const('/assets/deadbatt.2ink')
_IMG_NOSD     = const('/assets/nosd.pi')

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

# Geometry for HP bar
_X = const(184)
_Y = const(292)
#
_ACENTRE = const( 0 ) # Angle of midpoint of arc (relative to 12 o'clock)
_ATOTAL  = const( _DEG * 100 ) # Total angle made by arc
_ASTART  = const( _ACENTRE - (_ATOTAL/2) ) # Angle of start of arc
_AEND    = const( _ASTART + _ATOTAL ) # Angle of end of arc
#
_RI = const(157)
_ARC_THICKNESS = const(10)
_RO = const( _RI + _ARC_THICKNESS )
#
_ARC2_RI = const(171) # round(RI + _ARC_THICKNESS * 1.4)
_ARC2_THICKNESS = const(3)
_ARC2_RO = const( _ARC2_RI + _ARC2_THICKNESS)

# HP bar ticks geometry
_TICK_RI      = const( _RI + _ARC_THICKNESS * 1.4 )
_TICK_LENGTH  = const( _ARC_THICKNESS * 1.1 )
_TICK_THICK   = const( _ARC_THICKNESS * 0.5 )
_TICK_ANGLE   = const( _DEG * 3 )
_TICK_TEXT_PT = const( 8 ) # Pixels past end of tick for text point

# Geometry for titles
_HEAD_MIDPOINT_Y = const( _EINK_HEIGHT - (_CHAR_HEAD_SIZE//2) )
_TIT_MIDPOINT_Y  = const( 216 )
#TIT_Y = const(20)
#T1_C = const(1)
#T2_dY = const(14)
#T2_C = const(2)

# Geometry for charges labels
_CHG_X  = const(3)
_CHG_Y  = const(0)
_CHG_DY = const(19.7)
_CHG_C  = const(1)

# Geometry for spell slot indicator
_SPL_X  = const(0)
_SPL_W  = const(5)
_SPL_Y  = const( _EINK_HEIGHT - 1 )
_SPL_DY = const(12)
_SPL_OS = const(-8)
_SPL_C  = const(1)

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

# TODO:
# Support drawing directly to main framebuffer (no scratch)
#
def drawThickArc( fb, x, y, ro, ri, start, end, c=1, scratch=None ):
  
  # Input validation
  if type(x) is not int:
    raise TypeError('x must be of type int')
  if type(y) is not int:
    raise TypeError('y must be of type int')
  if type(ro) is not int:
    raise TypeError('ro must be of type int')
  if type(ri) is not int:
    raise TypeError('ri must be of type int')
  if type(c) is not int:
    raise TypeError('c must be of type int')
  #
  if c < 0 or c > 2:
    raise ValueError('c must be between 0 and 2')
  
  # Permit (and correct) negative start/end
  start = start % _TAU
  end = end % _TAU
  if start == end:
    raise ValueError('Start and End cannot be the same!')
  
  # Determine which quadrants we want
  # Counting clockwise from TDC
  #
  # Start and end quadrants
  qstart = int( start // _PI_2 )
  qend = int( end // _PI_2 )
  
  # Deal with edge cases
  if end % _PI_2 == 0:
    qend -= 1
  if qend == -1:
    qend = 3
  
  # Go round the clock to find all quadrants
  # Top-right is 0
  q = qstart
  quads=[9,9,9,9,9] # Pre-allocate the list with dummy data to prevent memory overallocation (65536 bytes)
  for i in range(5):
    quads[i] = q
    if q == qend:
      break
    q += 1
    if q >= 4:
      q=0
  quads = quads[:i+1] # Trim the list to the correct size
  
  # Arc diameter is always 2r+1
  # There is always a centre pixel, and h/v midlines.
  # The arc extends beyond these midlines by r pixels.
  
  # Figure out canvas size and centre point
  width = ro+1
  height = ro+1
  centre = (ro,ro)
  if quads == [0,1]: # Right half
    height += ro
    centre = (0,ro)
  elif quads == [2,3]: # Left half
    height += ro
  elif quads == [3,0]: # Top half
    width += ro
  elif quads == [1,2]: # Bottom half
    width += ro
    centre = (ro,0)
  elif quads == [0]: # Top right
    centre = (0,ro)
  elif quads == [1]: # Bottom right
    centre = (0,0)
  elif quads == [2]: # Bottom left
    centre = (ro,0)
  elif quads == [3]: # Top left
    pass
  else: # More than two quads
    width += ro
    height += ro
  
  # Round up to multiples of 8
  width += -width % 8
  height += -height % 8
  
  # Calculate required buffer size, in bytes
  num_pixels = width * height
  bufsize = num_pixels // 8
  
  # Set up the scratch buffer
  if scratch is not None:
    if len(scratch) < bufsize:
      raise IndexError('Provided scratch buffer is too small!')
    scratch = FrameBuffer( scratch, width, height, MONO_HLSB )
  else:
    scratch = FrameBuffer( bytearray(bufsize), width, height, MONO_HLSB )
  
  # Arc will be 1; background will be 0.
  # This will be corrected later, according to c arg
  
  # Draw the outer arc
  scratch.ellipse( *centre, ro, ro, 1, True )
  
  # Draw the inner arc
  scratch.ellipse( *centre, ri, ri, 0, True )
  
  # Start and end gradients
  #mend = tan( end )     # Distance from axis / length along axis
  
  # Draw the start cut-off ramp
  mstart = tan( start % _PI_2 ) # Gradient; Opposite / adjacent
  j=0 # Distance from centre
  if qstart == 0: # Top right; go up y-axis then across
    scratch.vline( centre[0], 0, ro, 0 )
    for i in range( centre[1], -1, -1 ):
      scratch.hline( centre[0]+1, i, round(j*mstart), 0 )
      j += 1
  elif qstart == 1: # Bottom right; go across x-axis then down
    scratch.hline( centre[0]+1, centre[1], ro, 0 )
    for i in range( centre[0], width ):
      scratch.vline( i, centre[1]+1, round(j*mstart), 0 )
      j += 1
  elif qstart == 2: # Bottom left; go down y-axis then back
    scratch.vline( centre[0], centre[1]+1, ro, 0 )
    for i in range( centre[1], height ):
      # FrameBuffer.hline doesn't accept negative lengths
      length = round(j*mstart)
      scratch.hline( centre[0]-length, i, length, 0 )
      j += 1
  elif qstart == 3: # Top left; go back along x-axis then up
    scratch.hline( 0, centre[1], ro, 0 )
    for i in range ( centre[0], -1, -1 ):
      length = round(j*mstart)
      scratch.vline( i, centre[1]-length, length, 0 )
      j += 1
  
  # Draw the end cut-off ramp
  mend = tan( -end % _PI_2 ) # Gradient; Opposite / adjacent
  j=0 # Distance from centre
  if qend == 0: # Top right; go across x-axis then up
    scratch.hline( centre[0]+1, centre[1], ro, 0 )
    for i in range( centre[0], width ):
      length = round(j*mend)
      scratch.vline( i, centre[1]-length, length, 0 )
      j += 1
  elif qend == 1: # Bottom right; go down y-axis then across
    scratch.vline( centre[0], centre[1]+1, ro, 0 )
    for i in range( centre[1], height ):
      scratch.hline( centre[0]+1, i, round(j*mend), 0 )
      j += 1
  elif qend == 2: # Top left; go back along x-axis then down
    scratch.hline( 0, centre[1], ro, 0 )
    for i in range ( centre[0], -1, -1 ):
      scratch.vline( i, centre[1]+1, round(j*mend), 0 )
      j += 1
  elif qend == 3: # Top left; go up y-axis then back
    scratch.vline( centre[0], 0, ro, 0 )
    for i in range( centre[1], -1, -1 ):
      length = round(j*mend)
      scratch.hline( centre[0]-length, i, length, 0 )
      j += 1
  
  # Blank out unused quadrants
  if 0 not in quads: # Blank top right
    scratch.rect( centre[0], centre[1]-ro, ro+1, ro, 0, True )
  if 1 not in quads: # Blank bottom right
    scratch.rect( centre[0], centre[1], ro+1, ro+1, 0, True )
  if 2 not in quads: # Blank bottom left
    scratch.rect( centre[0]-ro, centre[1], ro, ro+1, 0, True )
  if 3 not in quads: # Blank top left
    scratch.rect( centre[0]-ro, centre[1]-ro, ro, ro, 0, True )
  
  # Define the pallet
  # Zeroes become 3, which we will use to mean transparent
  # Ones become the chosen colour
  pal = FrameBuffer( bytearray(1), 2, 1, GS2_HMSB )
  pal.pixel(0,0,3) # 0
  pal.pixel(1,0,c) # 1
  
  # Apply the scratch buffer (with the arc) to the main fb
  fb.blit( scratch, x-centre[0], y-centre[1], 3, pal )

# Creates rectangular ticks on the arc
# Angle = where on the arc
# c = Tick colour
# direction: -1=CCW, 0=Centred, 1=CW
# Returns tuple with midpoint of top of tick
def tick(fb, angle,c=1,direction=0):
  
  # Avoid calculating these multiple times
  sin_a = sin(angle)
  cos_a = cos(angle)
  
  # Define baseline
  p0 = (
    _X +(_TICK_RI)*sin_a,
    _Y -(_TICK_RI)*cos_a
  )
  p1 = (
    p0[0] +_TICK_LENGTH*sin_a,
    p0[1] -_TICK_LENGTH*cos_a,
  )
  
  # Text point
  tltp = _TICK_LENGTH + _TICK_TEXT_PT
  tp = (
    round( p0[0] +tltp*sin_a ),
    round( p0[1] -tltp*cos_a ),
  )
  del tltp
  
  # For a centred tick, adjsut some things
  if direction == 0:
    # Half the thickness
    t = (
      0.5 * _TICK_THICK * cos_a,
      0.5 * _TICK_THICK * sin_a,
    )
    # Offset point 0 half a thickness ccw
    p0 = (
      p0[0] - t[0],
      p0[1] - t[1],
    )
    # Offset point 1 half a thickness ccw
    p1 = (
      p1[0] - t[0],
      p1[1] - t[1],
    )
    # Set direction to CW
    direction = 1
  
  # Thickness offset
  t = (
    direction*_TICK_THICK*cos_a,
    direction*_TICK_THICK*sin_a,
  )
  
  p2 = (
    p1[0] + t[0],
    p1[1] + t[1],
  )
  
  # Draw
  fb.poly(0,0,array('h',(
    round( p0[0] ),
    round( p0[1] ),
    round( p1[0] ),
    round( p1[1] ),
    round( p2[0] ),
    round( p2[1] ),
    round( p0[0] + t[0] ),
    round( p0[1] + t[1] ),
  )),c,True)
  
  # Return the midpoint of the top of the tick
  #return (
  #  round( (p1[0]+p2[0])/2 ),
  #  round( (p1[1]+p2[1])/2 ),
  #)
  return tp

# Adds a label, centred in x and y on a point
def tick_txt(fb, txt, pt, c ):
  
  # This function assumes all characters are 8x8
  
  # Draw the text so that the centre of it ends up on the point
  fb.text(
    txt,
    pt[0] - round( len(txt)*8 /2 ),
    pt[1] - 4, # 8/2
    c
  )

# Gets the max displayable HP value
def needle_max_range(hp):
  return max( hp[1], hp[0] + hp[3] )
  
# Draws the play screen to the given framebuffer
# Expects 360x240 2bpp framebuffer
# Needs stats dict from Character
def draw_play_screen( fb, char, lowbatt=False ):
  
  # Localisation
  stats = char.stats
  hp = stats['hp']
  head = char.dir / CHAR_HEAD
  
  # Character-specific background
  bg = char.dir / CHAR_BG
  if bg.is_file():
    img.load_into( fb.buf, str(bg) )
  else:
    fb.fill(0)
  
  ### CHARACTER HEAD ###
  if lowbatt:
    chs2 = _CHAR_HEAD_SIZE//2
    img.blit_onto( fb, _X-chs2, _HEAD_MIDPOINT_Y-chs2, _IMG_LOWBATT )
  else:
    if head.is_file():
      chs2 = _CHAR_HEAD_SIZE//2
      img.blit_onto( fb, _X-chs2, _HEAD_MIDPOINT_Y-chs2, str( head ) )
    else:
      fb.rect( _X-1, _HEAD_MIDPOINT_Y-1, 3, 3, 2, True ) # dot
      chs2 = 2
  
  ######## TITLES ########
  
  #f = eink.Font('/assets/Gallaecia_variable.2f')
  #f.write_to( fb, 'BONK', *XY, (1,) )
  fb.text( stats['title'], _X + chs2 + 5, _TIT_MIDPOINT_Y-4, 1 )
  #f = eink.Font('/assets/Vermin.2f')
  #f.write_to( fb, 'L3 Artificer', XY[0], XY[1]+14, (2,) )
  text_len_px = len(stats['subtitle']) * 8
  fb.text( stats['subtitle'], _X - (chs2+text_len_px+5), _TIT_MIDPOINT_Y-4, 1 )
  
  ######## SPELLS BAR ########
  
  height = round( _SPL_DY * len(stats['spells']) ) + _SPL_OS
  fb.hline( _SPL_X, _SPL_Y, _SPL_W, _SPL_C )
  fb.vline( _SPL_X+_SPL_W, _SPL_Y, -height-1, _SPL_C )
  fb.hline( _SPL_X, _SPL_Y-height, _SPL_W, _SPL_C )
  del height
  
  ######## CHARGES ########
  
  for i,chg in enumerate( stats['charges'] ):
    fb.text( chg['name'], _CHG_X, _CHG_Y+round( _CHG_DY * i ), _CHG_C )
  del i,chg

  ######## HP BAR ########
  
  # Make way for the ginormous function
  gc_collect()
  
  if hp[2] > 0: # If we have temp HP
    
    # How many HP will our arc(s) represent?
    # Either max HP, or current + temp : whichever is more
    max_range = needle_max_range(hp)
    
    # Ratios
    r_half = ( hp[0] / 2 ) / max_range
    r_curr = hp[0] / max_range
    r_max  = hp[1] / max_range
    r_tmax = hp[3] / max_range
    
    # Angular positions
    a_half = _ASTART + ( _ATOTAL * r_half )
    a_curr = _ASTART + ( _ATOTAL * r_curr )
    a_max  = _ASTART + ( _ATOTAL * r_max )
    a_tmax = a_curr + ( _ATOTAL * r_tmax )
    
    # Draw solid arc up to max HP
    drawThickArc( fb, _X, _Y, _RO, _RI, _ASTART, a_max, 1 )
    
    # White out the main arc between current and max HP
    if hp[0] < hp[1]:
      drawThickArc( fb, _X, _Y, _RO-1, _RI+1, a_curr, a_max-0.01, 0 )
    
    # Draw second arc depicting temp HP
    drawThickArc( fb, _X, _Y, _ARC2_RO, _ARC2_RI, a_curr, a_tmax, 2 )
    
    # Tick at half HP, if there's room
    #print(f'a_curr - _ASTART:{a_curr - _ASTART}')
    if ( a_curr - _ASTART ) > 0.4:
      pt = tick( fb, (a_half), 1, 0 )
      tick_txt( fb, str(round( hp[0] / 2 )), pt, 1 )
    
    # Tick at current HP
    pt = tick( fb, (a_curr), 2, 1 )
    tick_txt( fb, str( hp[0] ), pt, 2 )
    
    # Tmax
    pt = tick( fb, (a_tmax), 2, -1 )
    tick_txt( fb, str( hp[0] + hp[3] ), pt, 2 )
  
  else: # No temp HP, normal bar
    
    # Angular positions
    a_q1 = _ASTART + ( _ATOTAL * 0.25 )
    a_q2 = _ASTART + ( _ATOTAL * 0.5 )
    a_q3 = _ASTART + ( _ATOTAL * 0.75 )
    a_q4 = _ASTART + _ATOTAL
    
    # Draw solid arc up to max HP
    # Pull back the start slightly, to meet up with the skull
    drawThickArc( fb, _X, _Y, _RO, _RI, _ASTART-_DEG, a_q4, 1 )
    
    # Ticks
    #tick( _ASTART, 1, 1)
    #
    pt = tick( fb, a_q1, 1, 0 )
    tick_txt( fb, str(round( hp[1] / 4 )), pt, 1 )
    #
    pt = tick( fb, a_q2, 1, 0 )
    tick_txt( fb, str(round( hp[1] / 2 )), pt, 1 )
    #
    pt = tick( fb, a_q3, 1, 0 )
    tick_txt( fb, str(round( hp[1] * 0.75 )), pt, 1 )
    #
    pt = tick( fb, a_q4, 1, -1 )
    tick_txt( fb, str( hp[1] ), pt, 1 )
    
  
  # Add the skull
  skull = img.load( _IMG_SKULL )
  start = (
    round( _X +_RI*sin(_ASTART) ),
    round( _Y -_RI*cos(_ASTART) ),
  )
  fb.blit( skull, start[0]-16, start[1]-6, 3 )
  
  # Start tick (skull instead)
  #tick(_ASTART,2,1)
  
  # Needle calibration
  #fb.vline(_X-1,120,120,1)
  #fb.vline(_X+1,120,120,1)
  
  #img.save( fb, 'playscreen.2ink')

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
  
  # Angular distance between heads
  da = _ATOTAL / ( len(chars) - 1 )
  
  # Offset to centre of character head (instead of top left)
  hdos = _CHAR_HEAD_SIZE // 2
  
  # Truncate text names
  max_name_len = _CHAR_HEAD_SIZE // 8 # Assume 8px letter width
  
  a = _ASTART
  for char in chars:
    if char['head'] is not None:
      x = round( _X + _ARC2_RI*sin(a) -hdos )
      y = round( _Y - _ARC2_RI*cos(a) -hdos )
      img.blit_onto( fb, x, y, char['head'] )
    else:
      txt = char['dir'].name[:max_name_len]
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
