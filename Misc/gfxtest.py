# Gfx testbed
# 20 Apr 2026

from PIL import Image, ImageDraw
from math import tan

_PI_2 = (1.5707963)
_PI   = (3.1415926)
_TAU  = (6.2831852)
_DEG  = (0.01745329) # pi/180

im = Image.new("RGBA", (360, 240), (255, 255, 255))
d = ImageDraw.Draw(im)

colours = (
  (0,0,0), # 0 black
  (255,255,255), # 1 white
  (255,0,0), # 2 red
  (0,255,0), # 3 green
  (0,0,255), # 4 blue
  (255,255,0), # 5 yellow
  (255,0,255), # 6 magenta
  (0,255,255), # 7 turquoise
)

### PRIMITIVES ###

def pixel( x:int, y:int, c=0 ):
  d.point([x,y],fill=colours[c])

def hline(x:int,y:int,len:int,c:int=0):
  for _x in range(x,x+len):
    pixel(_x,y,c)

def vline(x:int,y:int,len:int,c:int=0):
  for _y in range(y,y+len):
    pixel(x,_y,c)


### ADVANCED SHAPES ###

def partial_ellipse(rx:int, ry:int, cx:int, cy:int, start:float, end:float ): 
    
  start = start % _TAU
  end = end % _TAU
  if start == end:
    raise ValueError('Start and End cannot be the same!')
  
  # Which halves do we start and end in?
  # 0 = right
  # 1 = left
  hstart = int( start // _PI )
  hend = int( end // _PI )
  # Deal with edge cases
  if end == 0: # 12 o'clock
    hend = 1   # We're actually ending at the very end of the left half
  elif end == _PI: # 6 o'clock
    hend = 0       # Ending at the end of the right half
  
  # Startline gradient
  if start == 0:
    mstart = -2*ry
  elif start == _PI:
    mstart = -2*ry
  else:
    mstart = tan(start+_PI_2) # Opposite / adjacent
  
  # Endline gradient
  if end == 0:
    mend = 2*ry
  elif end == _PI:
    mend = 2*ry
  else:
    mend = tan(end+_PI_2) # Opposite / adjacent
  
  # Start/end lines in green/red
  #for x in range(-rx,rx):
  #  pixel(x+cx,(x*mstart)+cy,3)
  #  pixel(x+cx,(x*mend)+cy,2)
  
  # Decide whether to plot a point, based on start and end (and hstart and hend and mstart and mend)
  def check_point( x, y ) -> bool:
    
    # Start and end in the same half?
    # Order of start -> end is flipped in second half after 180'
    # So everything that compares order has to be flipped too
    if hstart == hend:
      if ( start < end ) ^ hstart:
        return ( (x*mstart) < y < (x*mend) ) ^ hstart
      else:
        return ( (x*mstart) < y or y < (x*mend) ) ^ hstart
    
    # Which half are we in?
    if x >= 0: # Right half
      
      # Is start in this half?
      if hstart == 0:
        return (x*mstart) < y
      
      # Is end in this half?
      else: #if hend == 0: # We know hend==0 because hend != hstart
        return y < (x*mend)
      
    else: # Left half
      
      # Is start in this half?
      if hstart == 1:
        return y < (x*mstart)
      
      # Is end in this half?
      else: #if hend == 1: # We know hend==1 because hend != hstart
        return (x*mend) < y
  
  # Mirrors the points to all quadrants, checks them, then draws them
  def draw_ellipse_points( x, y, cx, cy ):
    if check_point(x,y):
      pixel( cx + x, cy + y )
    if check_point(-x,y):
      pixel( cx - x, cy + y )
    if check_point(x,-y):
      pixel( cx + x, cy - y )
    if check_point(-x,-y):
      pixel( cx - x, cy - y )
  
  # These values are used repeatedly.  Precalculate them
  ry_sq = ry*ry
  rx_sq = rx*rx
  two_rysq = 2 * ry_sq
  two_rxsq = 2 * rx_sq
  
  # Start at 12 o'clock
  x = 0; 
  y = ry
  
  # Initial decision parameter of flatter region
  param = ry_sq - (rx_sq * ry) + ( rx_sq / 4 )
  dx = two_rysq * x
  dy = two_rxsq * y

  # Flatter (upper) region
  while (dx < dy): 
      
      draw_ellipse_points( x, y, cx, cy )
      
      # Update the runnings values
      x += 1
      dx += two_rysq
      param += dx
      param += ry_sq
      
      # Are we outside the ellipse?
      if param >= 0:
          y -= 1
          dy -= two_rxsq
          param -= dy

  # Initial decision parameter of steeper region
  #param = ( ry_sq * ((x + 0.5) * (x + 0.5)) ) + (rx_sq * ((y - 1) * (y - 1))) - ( rx_sq * ry_sq )
  param = ( ry_sq * (x*x + x + 0.25) ) + (rx_sq * (y*y - 2*y + 1 ) ) - ( rx_sq * ry_sq )
  # Steeper (lower) region
  while y >= 0:
      
      draw_ellipse_points( x, y, cx, cy )
      
      # Update the runnings values
      y -= 1
      dy -= two_rxsq
      param -= dy
      param += rx_sq
      
      # Are we outside the ellipse?
      if param < 0:
          x += 1
          dx += two_rysq
          param += dx

def circle( cx:int, cy:int, r:int ):
  
  # Draw octants
  def octs(x,y,c=0):
    
    # Pixels arranged in clockwise order from TDC
    
    # Q0
    pixel( cx+y, cy-x, c=c )
    pixel( cx+x, cy-y, c=c )
    
    # Q1
    pixel( cx+x, cy+y, c=c )
    pixel( cx+y, cy+x, c=c )
    
    # Q2
    pixel( cx-y, cy+x, c=c )
    pixel( cx-x, cy+y, c=c )
    
    # Q3
    pixel( cx-x, cy-y, c=c )
    pixel( cx-y, cy-x, c=c )
  
  # https://en.wikipedia.org/wiki/Midpoint_circle_algorithm#Jesko's_method
  # Starts at 3 o'clock (r,0) and proceeds clockwise (+ve y-direction)
  t1 = r >> 4 # //16
  x = r
  y = 0
  while x >= y:
    octs( x, y )
    y += 1
    t1 += y
    t2 = t1 - x
    if t2 >= 0:
      t1 = t2
      x -= 1

def tcircle( cx:int, cy:int, ro:int, ri:int ):
  
  def octs(x,y,c=0):
    
    # Pixels arranged in clockwise order from TDC
    
    # Q0
    pixel( cx+y, cy-x, c=c )
    pixel( cx+x, cy-y, c=c )
    
    # Q1
    pixel( cx+x, cy+y, c=c )
    pixel( cx+y, cy+x, c=c )
    
    # Q2
    pixel( cx-y, cy+x, c=c )
    pixel( cx-x, cy+y, c=c )
    
    # Q3
    pixel( cx-x, cy-y, c=c )
    pixel( cx-y, cy-x, c=c )
  
  # https://en.wikipedia.org/wiki/Midpoint_circle_algorithm#Jesko's_method
  # Starts at 3 o'clock (r,0) and proceeds clockwise (+ve y-direction)
  t1i = ri >> 4 # //16
  t1o = ro >> 4
  xi = ri
  xo = ro
  y = 0
  
  # Draw the inner circle and most of the outer one
  while xi >= y:
    
    # Draw hline from xi to xo
    px = xi
    while px <= xo:
      octs( px, y )
      px += 1
    y += 1
    
    t1i += y
    t2i = t1i - xi
    if t2i >= 0:
      t1i = t2i
      xi -= 1
    
    t1o += y
    t2o = t1o - xo
    if t2o >= 0:
      t1o = t2o
      xo -= 1
  
  # Draw the rest of the outer circle
  while xo >= y:
    
    # Draw hline starting from xi to xo,
    # but now xi just increments by 1 every loop
    px = xi
    while px <= xo:
      octs( px, y )
      px += 1
    xi += 1
    
    y += 1
    t1o += y
    t2o = t1o - xo
    if t2o >= 0:
      t1o = t2o
      xo -= 1

def carc( cx:int, cy:int, ro:int, ri:int, start:float, end:float, oc:int=0, fc:int=-1 ):
  
  start = start % _TAU
  end = end % _TAU
  if start == end:
    raise ValueError('Start and End cannot be the same!')
  
  FILL = ( fc >= 0 )
  
  # Which halves do we start and end in?
  # 0 = right
  # 1 = left
  hstart = int( start // _PI )
  hend = int( end // _PI )
  # Deal with edge cases
  if end == 0: # 12 o'clock
    hend = 1   # We're actually ending at the very end of the left half
    end = _TAU
  elif end == _PI: # 6 o'clock
    hend = 0       # Ending at the end of the right half
  
  # Startline gradient and 'start vertical' flag
  if start == 0:
    sv = 1
  elif start == _PI:
    sv = 1
  else:
    mstart = tan(start+_PI_2) # Opposite / adjacent
    sv = 0
  
  # Endline gradient and 'end vertical' flag
  if end == 0:
    ev = 1
  elif end == _PI:
    ev = 1
  else:
    mend = tan(end+_PI_2) # Opposite / adjacent
    ev = 0
  
  def ckp( x, y ) -> bool:
    hx = int(x < 0) # Which half is x in?
    
    # Start and end in the same half?
    if hstart == hend:
      
      # If we're in the other half, we're either drawing everything or nothing
      if hstart != hx:
        return start > end
      
      # Order of start -> end is flipped in second half after 180'
      # So everything that compares order has to be flipped too
      if ( start < end ) ^ hstart:
        if sv:
          ok = 1
        else:
          ok = (x*mstart) < y
        if ev:
          ok &= 1
        else:
          ok &= y < (x*mend)
        ok ^= hstart
        return bool(ok)
      else:
        if sv:
          ok = 1^hstart
        else:
          ok = (x*mstart) < y
        if ev:
          ok = 1 # Anything OR'd with 1, equals 1
        else:
          ok |= y < (x*mend)
        ok ^= hstart
        return bool(ok)
      
    elif hx == hstart: # start/end in different halves AND x is in the starting half
      if sv:
        return True
      else:
        return ( y > x * mstart ) ^ hstart
    else: # start/end in different halves AND x is in the ending half
      if ev:
        return True#bool(1^hend)
      else:
        return ( y < x * mend ) ^ hend
  
  def octs(x,y,c=0):
    
    # Pixels arranged in clockwise order from TDC
    
    # Q0
    if ckp(y,-x):
      pixel( cx+y, cy-x, c=c )
    if ckp(x,-y):
      pixel( cx+x, cy-y, c=c )
    
    # Q1
    if ckp(x,y):
      pixel( cx+x, cy+y, c=c )
    if ckp(y,x):
      pixel( cx+y, cy+x, c=c )
    
    # Q2
    if ckp(-y,x):
      pixel( cx-y, cy+x, c=c )
    if ckp(-x,y):
      pixel( cx-x, cy+y, c=c )
    
    # Q3
    if ckp(-x,-y):
      pixel( cx-x, cy-y, c=c )
    if ckp(-y,-x):
      pixel( cx-y, cy-x, c=c )
  
  # https://en.wikipedia.org/wiki/Midpoint_circle_algorithm#Jesko's_method
  # Starts at 3 o'clock (r,0) and proceeds clockwise (+ve y-direction)
  t1i = ri >> 4 # //16
  t1o = ro >> 4
  xi = ri
  xo = ro
  y = 0
  
  # Draw the inner circle and most of the outer one
  while xi >= y:
    
    # Draw hline from xi to xo
    octs( xi, y, oc )
    if FILL:
      px = xi+1
      while px < xo:
        octs( px, y, fc )
        px += 1
    octs( xo, y, oc )
    
    y += 1
    
    t1i += y
    t2i = t1i - xi
    if t2i >= 0:
      t1i = t2i
      xi -= 1
    
    t1o += y
    t2o = t1o - xo
    if t2o >= 0:
      t1o = t2o
      xo -= 1
  
  # Draw the rest of the outer circle
  while xo >= y:
    
    # Draw hline starting from xi to xo,
    # but now xi just increments by 1 every loop
    if FILL:
      px = xi+1
      while px < xo:
        octs( px, y, fc )
        px += 1
    octs( xo, y, oc )
    xi += 1
    
    y += 1
    t1o += y
    t2o = t1o - xo
    if t2o >= 0:
      t1o = t2o
      xo -= 1

###################################

start = _TAU * 0.5
end = _TAU * 0.9

X = 180
Y = 120
R = 100
T = 10

#hline( X-R, Y, R*2, 7 )
#vline( X, Y-R, R*2, 7 )
#partial_ellipse( R, R, X, Y, start, end )
#circle( X, Y, R )
#tcircle( X, Y, R, R-10 )
#carc( X, Y, R, R-T, start, end )

# Test all combinations of quadrants
#positions = (0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9)
positions = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)
for i,a in enumerate(positions):
  for j,b in enumerate(positions):
    hline( 30*i, 30*j, 30, 5 )
    vline( 30*i, 30*j, 30, 5 )
    if a==b:
      continue
    #partial_ellipse( 14, 14, 15+(30*i), 15+(30*j), a*_TAU, b*_TAU )
    carc( 15+(30*i), 15+(30*j), 14, 10, a*_TAU, b*_TAU, oc=0, fc=0 )

#im.show()
im.resize( (720,480), Image.Resampling.NEAREST ).show()
