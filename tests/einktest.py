import eink
#from drawfb import Image
import time
from sys import exit
import gc
import array, math

# E-ink driver and framebuffer
#epd = eink.Eink(240,360,rot=0) # Portrait
epd = eink.Eink(360,240,rot=1) # Landscape

print('mem free',gc.mem_free())

epd.init_panel()

# 4x4 grid of arcs with start and end points in different quadrants
def arcTest( im, ro, ri ):
  y = 0
  grid = (2*ro)+3
  for i in range(4):
    x=0
    end = 3.14159 * ((i*2)+1)/4 +0.1
    for j in range(4):
      im.drawRect(x,y,grid,grid,2)
      im.drawHLine(x,y+ro+1,grid,2)
      im.drawVLine(x+ro+1,y,grid,2)
      start = 3.14159 * ((j*2)+1)/4 -0.1
      im.drawThickArc( x+ro+1,  y+ro+1, ro, ri, start, end, 1 )
      x += grid
    y += grid

# Investigate small angles
def arcTest2( im, ro, ri ):
  grid = (2*ro)+3
  #inc = 0.017453 # approx 1 degree, in radians
  inc = 0.0087266 # approx 0.5 deg
  n=0
  y=0
  for i in range(2):
    x=0
    for j in range(2):
      im.drawRect(x,y,grid,grid,2)
      im.drawThickArc( x+ro+1, y+ro+1, ro, ri, inc*n, 3, 1 )
      n += 1
      x += grid
    y += grid

# Draws a fine black/red grid over the entire field
def fillbr(im):
  for y in range(0,im.h,2):
    for x in range(0,im.w,2):
      im.pixel(x,y,2)
      im.pixel(x+1,y+1,1)

# Draws a 1px black border around the perimeter
# Leaves a 1px white gap inside that
# Draws a 1px red border inside that
def borders(im):
  im.rect(0,0,im.w,im.h,1)
  im.rect(2,2,im.w-4,im.h-4,2)

# Character name etc
def drawTitle( im ):
  
  # Config
  XY = ( 100, 20 )
  
  f = eink.Font('/assets/Gallaecia_variable.2f')
  f.write_to( epd.fb, 'BONK', *XY, (1,) )
  f = eink.Font('/assets/Vermin.2f')
  f.write_to( epd.fb, 'L3 Artificer', XY[0], XY[1]+14, (2,) )
  
#gc.collect()
print('mem free',gc.mem_free())
print('Generating images... ',end='')
start = time.ticks_ms()

#eink.load_2ink_into( 'assets/autognome.2ink', epd.fb.buf )
#eink.load_2ink_into( 'assets/autognome_land.2ink', epd.fb.buf )
#eink.save_2ink( 'agtest1.2ink', epd.fb.buf, 240, 360 )

#fillbr(epd.fb)

#arcTest(img,28,0)
#arcTest2(img,58,10)


#drawTitle( epd.fb )
#drawHP( epd.fb, 59, 15 )
#drawLR( epd.fb )
#drawSpells( epd.fb, 8 )


#eink.save_2ink( 'display.2ink', epd.fb )
#exit()

# Test pattern for pixel ordering
# First two bytes in a specific order
# Naiive: k = 0101 0110 = 0x56 , r = 0011 0101 = 0x35
# Transparent = white: k = 0100 0010 = 0x42 , r = 0010 0001 = 0x21
#epd.fb.buf[0] = 0x1B # Test pattern: 00 01 10 11 = k0101 r0011
#epd.fb.buf[1] = 0x36 # Test pattern: 00 11 01 10 = k0110 r0101

# Test pattern for pixel ordering
# Diagonal black line from 0,0 for 16 pixels
# Followed by diagonal red line for 16 more pixels
#epd.fb.line(0,0,15,15,1)
#epd.fb.line(16,16,31,31,2)

#epd.fb.text('Top left',0,0)
#borders(epd.fb)

#epd.fb.hline(0,20,10,1)
#f = eink.Font('/assets/Bold.2f')
#f.write_to( epd.fb, 'Quick Brown Fox', 10, 10, (1,2,0))
#f.write_to( epd.fb, 'Quick Brown Fox', 10, 30, (2,0,0))
#f.write_to( epd.fb, 'Quick Brown Fox', 10, 40, (1,3,0))
#f = eink.Font('/assets/Gallaecia_variable.2f')
#f.write_to( epd.fb, 'Quick Brown Fox', 10, 25, (1,2,0))
#f.write_to( epd.fb, 'abcdef\nghijkl\nmnopqr\nstuvwx\nyz0123\n456789', 10, 55, (1,0,0))

print('done in {}s'.format(time.ticks_diff( time.ticks_ms(), start )/1000))

#print( hex(epd.fb.buf[0]), hex(epd.fb.buf[1]) )
#print( epd.fb.buf[:8] )

#exit()
print('Sending buffer... ',end='')
start = time.ticks_ms()
#epd.send()
epd.clear() # Fill with white
print('done in {}s'.format(time.ticks_diff( time.ticks_ms(), start )/1000))

#exit()
#epd.border(0)

print('Refreshing display... ', end='')
start = time.ticks_ms()
epd.refresh()
print('done in {}s'.format(time.ticks_diff( time.ticks_ms(), start )/1000))
gc.collect()

print('Deep sleep')
epd.sleep()

print('mem free',gc.mem_free())

