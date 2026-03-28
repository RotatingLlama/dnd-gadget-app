# Drawing functions for character.py
#
# T. Lloyd
# 28 Mar 2026

# Standard libraries
from micropython import const
from array import array
from math import sin, cos, tan
from gc import collect as gc_collect
from framebuf import FrameBuffer, MONO_HLSB, GS2_HMSB

# Our libraries
import img
from .common import CHAR_HEAD, CHAR_BG

# ASSETS
_IMG_SKULL    = const('/assets/skull.pi')
_IMG_LOWBATT  = const('/assets/low_batt.2ink')


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
_APX     = const( _DEG * 0.4 ) # Angle of one pixel thickness
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
#_TICK_ANGLE   = const( _DEG * 3 )
_TICK_TEXT_PT = const( 8 ) # Pixels past end of tick for text point

# Geometry for titles
_HEAD_MIDPOINT_Y = const( _EINK_HEIGHT - (_CHAR_HEAD_SIZE//2) )
_TIT_MIDPOINT_Y  = const( 216 )
#TIT_Y = const(20)
#T1_C = const(1)
#T2_dY = const(14)
#T2_C = const(2)

# Geometry for charges labels
_CHG_X  = const(1)
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


# Indexes into the Character.data object
_NAME = const(0)
_TITLE = const(1)
#_XP = const(2)
#_CURRENCY = const(3)
_HP = const(4)
#_HD = const(5)
_SPELLS = const(6)
_CHARGES = const(7)
_DEATH = const(8)
#
#_CURRENCY_COPPER = const(0)
#_CURRENCY_SILVER = const(1)
#_CURRENCY_ELECTRUM = const(2)
#_CURRENCY_GOLD = const(3)
#_CURRENCY_PLATINUM = const(4)
#
_HP_CURR = const(0)
_HP_MAX = const(1)
_HP_TEMP = const(2)
_HP_ORIGTEMP = const(3)
#
#_HD_CURR = const(0)
#_HD_MAX = const(1)
#
_SPELLS_CURR = const(0)
#_SPELLS_MAX = const(1)
#
#_CHARGES_CURR = const(0)
#_CHARGES_MAX = const(1)
#_CHARGES_RESET = const(2)
_CHARGES_NAME = const(3)
#
_DEATH_STATUS = const(0)
#_DEATH_OK = const(1)
#_DEATH_NG = const(2)

# Codes for Character.data objects
#_CHARGE_RESET_SR = const(0x01)
#_CHARGE_RESET_LR = const(0x02)
#_CHARGE_RESET_DAWN = const(0x04)
#
_DEATH_STATUS_OK = const(0)
_DEATH_STATUS_SV = const(1)
#_DEATH_STATUS_DD = const(2)


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
  
  # Geometry
  g = array('h',(
    round( p0[0] ),
    round( p0[1] ),
    round( p1[0] ),
    round( p1[1] ),
    round( p2[0] ),
    round( p2[1] ),
    round( p0[0] + t[0] ),
    round( p0[1] + t[1] ),
  ))
  
  # Draw a filled poly in the correct colour
  fb.poly( 0,0, g, c, True )
  
  # Draw an outline poly in white
  fb.poly( 0,0, g, 0, False )
  
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
  fb.label(
    txt,
    pt[0] - round( len(txt)*8 /2 ),
    pt[1] - 4, # 8/2
    c
  )

# Draws the play screen to the given framebuffer
# Expects 360x240 2bpp framebuffer
# Needs the Character object
# lowbatt Boolean will replace character head with a low battery graphic
def draw_play_screen( fb, char, lowbatt=False ):
  
  # Localisation
  data = char.data
  hp = data[_HP]
  head = char.dir / CHAR_HEAD
  
  # Character-specific background
  bg = char.dir / CHAR_BG
  if bg.is_file():
    try:
      img.load_into( fb.buf, str(bg) )
    except (RuntimeError, NotImplementedError) as e:
      fb.fill(0)
  else:
    fb.fill(0)
  
  ### CHARACTER HEAD ###
  if lowbatt:
    chs2 = _CHAR_HEAD_SIZE//2
    img.blit_onto( fb, _X-chs2, _HEAD_MIDPOINT_Y-chs2, _IMG_LOWBATT )
  else:
    headok = head.is_file()
    if headok:
      try:
        chs2 = _CHAR_HEAD_SIZE//2
        img.blit_onto( fb, _X-chs2, _HEAD_MIDPOINT_Y-chs2, str( head ) )
      except (RuntimeError, NotImplementedError) as e:
        headok = False
    if not headok:
      fb.rect( _X-1, _TIT_MIDPOINT_Y-1, 3, 3, 2, True ) # dot
      chs2 = 2
  
  ######## TITLES ########
  
  #f = eink.Font('/assets/Gallaecia_variable.2f')
  #f.write_to( fb, 'BONK', *XY, (1,) )
  #f = eink.Font('/assets/Vermin.2f')
  #f.write_to( fb, 'L3 Artificer', XY[0], XY[1]+14, (2,) )
  fb.label( data[_NAME], _X - (chs2+(len(data[_NAME]) * 8)+5), _TIT_MIDPOINT_Y-4, 1 )
  if len( data[_TITLE] ) > 0:
    fb.label( data[_TITLE], _X + chs2 + 5, _TIT_MIDPOINT_Y-4, 1 )
  
  ######## SPELLS BAR ########
  
  nsp = len(data[_SPELLS][_SPELLS_CURR])
  if nsp > 0 and data[_DEATH][_DEATH_STATUS] == _DEATH_STATUS_OK:
    height = round( _SPL_DY * nsp ) + _SPL_OS
    fb.rect( 0, _SPL_Y-height-1, _SPL_X+_SPL_W+2, height+2, 0, True )
    fb.hline( _SPL_X, _SPL_Y, _SPL_W, _SPL_C )
    fb.vline( _SPL_X+_SPL_W, _SPL_Y, -height-1, _SPL_C )
    fb.hline( _SPL_X, _SPL_Y-height, _SPL_W, _SPL_C )
    del height
  del nsp
  
  ######## CHARGES ########
  if data[_DEATH][_DEATH_STATUS] == _DEATH_STATUS_OK:
    for i,chg in enumerate( data[_CHARGES] ):
      fb.label( chg[_CHARGES_NAME], _CHG_X, _CHG_Y+round( _CHG_DY * i ), _CHG_C )
    del i,chg
  elif data[_DEATH][_DEATH_STATUS] == _DEATH_STATUS_SV:
    fb.label( 'SUCCESS', _CHG_X, _CHG_Y, 1 )
    fb.label( 'FAILURE', _CHG_X, _CHG_Y+round( _CHG_DY ), 2 )
  
  ######## HP BAR ########
  
  # Make way for the ginormous function
  gc_collect()
  
  # Skull pullback (how far to extend the arc back to meet the skull)
  spb = _APX * 3
  
  if hp[_HP_TEMP] > 0: # If we have temp HP
    
    # How many HP will our arc(s) represent?
    # Either max HP, or current + temp : whichever is more
    max_range = char.max_displayable_hp()
    
    # Ratios
    r_half = ( hp[_HP_CURR] / 2 ) / max_range
    r_curr = hp[_HP_CURR] / max_range
    r_max  = hp[_HP_MAX] / max_range
    r_tmax = hp[_HP_ORIGTEMP] / max_range
    
    # Angular positions
    a_half = _ASTART + ( _ATOTAL * r_half )
    a_curr = _ASTART + ( _ATOTAL * r_curr )
    a_max  = _ASTART + ( _ATOTAL * r_max )
    a_tmax = a_curr + ( _ATOTAL * r_tmax )
    
    # Draw white background arc
    drawThickArc( fb, _X, _Y, _RO+1, _RI-1, _ASTART-spb-_APX, a_max+_APX, 0 )
    
    # Draw solid arc up to max HP
    drawThickArc( fb, _X, _Y, _RO, _RI, _ASTART-spb, a_max, 1 )
    
    # White out the main arc between current and max HP
    if hp[0] < hp[1]:
      drawThickArc( fb, _X, _Y, _RO-1, _RI+1, a_curr, a_max-_APX, 0 )
    
    # Draw white background for second (red) arc depicting temp HP
    drawThickArc( fb, _X, _Y, _ARC2_RO+1, _ARC2_RI-1, a_curr-_APX, a_tmax+_APX, 0 )
    
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
    
    # Finally draw the temp HP arc itself
    drawThickArc( fb, _X, _Y, _ARC2_RO, _ARC2_RI, a_curr, a_tmax, 2 )
  
  else: # No temp HP, normal bar
    
    # Angular positions
    a_q1 = _ASTART + ( _ATOTAL * 0.25 )
    a_q2 = _ASTART + ( _ATOTAL * 0.5 )
    a_q3 = _ASTART + ( _ATOTAL * 0.75 )
    a_q4 = _AEND
    
    # Draw solid arc up to max HP
    drawThickArc( fb, _X, _Y, _RO+1, _RI-1, _ASTART-spb-_APX, a_q4+_APX, 0 )
    drawThickArc( fb, _X, _Y, _RO, _RI, _ASTART-spb, a_q4, 1 )
    
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
