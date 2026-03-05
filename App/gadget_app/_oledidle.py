# Idle status screen
#
# T. Lloyd
# 04 Jan 2026

import asyncio
from gc import mem_alloc as gcma, mem_free as gcmf
from micropython import const

from .common import HAL_PRIORITY_IDLE
from . import gfx

# Store this figure for future use
_MEM_TOTAL = gcma() + gcmf()

# Used for memory history graph on idle screen
memlog = bytearray(33) # 32-long ring buffer, plus pointer

class OledIdle:
  def __init__(self, gadget, refresh_ms=1000 ):
    self.g = gadget
    self.ms = refresh_ms
    self._trigger = asyncio.ThreadSafeFlag()
    self.cr = self.g.hal.register(
      priority=HAL_PRIORITY_IDLE,
      features=('oled',),
      callback=self._trigger.set,
      name='OledIdle'
    )
    self.tasks = asyncio.create_task(asyncio.gather(
      self._renderer(),
      self._runner(),
    ))
    gfx.render_boot_logo(self.g.hal.oled)
  
  # Trigger a render now.  Safe to call from non-async code.
  def render(self):
    if self.cr.ready:
      self._trigger.set()
  
  # Repeatedly triggers _renderer()
  async def _runner(self):
    ts = self._trigger.set
    while True:
      if self.cr.ready:
        ts()
      await asyncio.sleep_ms(self.ms)
  
  # Actually renders and updates the OLED.
  # Waits to be triggered.
  async def _renderer(self):

    # Localisation
    g = self.g
    hal = g.hal
    oled = hal.oled
    v = oled.vline
    h = oled.hline
    r = oled.rect
    p = oled.pixel
    t = oled.text
    
    # Battery monitor.  8 high, 44 wide.  Sticks to top-right corner
    def batt() -> int:
      
      # Top-right point
      x = 127
      y = 0
      #
      # Draw the battery outline             xxxxxxxxxxxx+
      v( x-1,  y,     6, 1 ) # Right wall    x          x
      v( x,    y+2,   3, 1 ) # Nub           x          xx
      h( x-1,  y,   -12, 1 ) # Top wall      x          xx
      v( x-12, y,     6, 1 ) # Left wall     x          xx
      h( x-1,  y+6, -12, 1 ) # Bottom wall   x          x
      #                                      xxxxxxxxxxxx
      
      pc = hal.batt_pc()
      if pc is None:
        # If we didn't get a percentage, we probably have VBUS
        txt = 'USB'
      else:
          
        # How full is the battery?
        bars = ( pc // 10 )
        
        # Draw the bars
        for i in range(bars):
          v( x-11+i, y+1, 5, 1 )
        
        # Percentage text
        txt = f'{pc}%'
      
      # Add the text next to the battery
      t( txt, x - 12 -( 8*len(txt) ), y, 1 )
      
      # Add the actual voltage, below the battery
      #t( f'{round(self.hal.hw.voltage_stable(),4)}v', x-47, y+8, 1 )
      
      # Pixel width used
      return 44
    
    # Memory info.  16 high
    def mem(x,y) -> int:
      
      ### MEMORY ###
      #
      # Uses space:
      #   0 <= x < 43
      #  16 <= y < 32
      #
      ### MEMORY HISTORY GRAPH ###
      #
      mlen = len(memlog) - 1
      mptr = memlog[mlen] # Pointer is last element of memlog
      
      # Record current mem usage (on a scale of 0-16) at mptr
      memlog[mptr] = ( gcma() << 4 ) // _MEM_TOTAL
      
      # Set up the graph
      v( x+33, y, 16, 1 ) # axis line
      
      # Start at the beginning
      mptr = ( mptr+1 ) % mlen
      
      # Loop through memlog
      for i in range(mlen):
        p( x+i, y+16-memlog[mptr], 1 )
        mptr = ( mptr+1 ) % mlen
      
      # Store the updated mptr
      memlog[mlen] = mptr
      
      # Mem usage text
      t( 'mem', x+35, y-2, 1 )
      t( f'{ ( gcma() * 100 ) // _MEM_TOTAL }%', x+35, y+9, 1 )
      
      # Pixel width used
      return 60
    
    # Eink busy indicator.  8 high
    def eink(x,y) -> int:
      t( 'e', x,y, 1 )
      return 8
    
    # SD problems.  16 high
    # Cache the graphic to prevent constant flash accesses and memory allocation
    nosdfb = gfx.get_sd_fb()
    def sd(x,y) -> int:
      
      # Hardware errors get priority
      e = hal.get_sd_status()
      
      # If there's no hardware error, see if there's a software error
      if e == 0:
        e = g._sd_err
      
      # If there's still no error, leave
      if e == 0:
        return 0
      
      # e should now contain the most relevant error code
      
      # Add the graphic
      oled.blit( nosdfb, x,y )
      
      # Display error code
      oled.text( 'SD', x+25, y )
      oled.text( f'E{e}', x+25, y+8 )
      
      # Pixel width used
      return 48
    
    # Save icon.  12 high
    def save(x,y) -> int:
      
      # Vertically centre the icon in a 16-high bar
      y += 2
      
      # Draw a 12x12 floppy disk icon
      v(x,    y+1,   10, 1 ) # Left wall
      h(x+1,  y+11,  10, 1 ) # Bottom
      v(x+11, y+10,  -9, 1 ) # Right wall
      p(x+10, y+1, 1 )       # Corner
      h(x+9,  y,     -9, 1 ) # Top
      r(x+2, y+7, 8,5, 1, False ) # Label
      r(x+3, y,   6,4, 1, False ) # Shield outline
      r(x+4, y+1, 2,2, 1, False ) # Shield fill
      
      # Pixel width used
      return 12
    
    while True:
      await self._trigger.wait()
      self._trigger.clear()

      oled.fill(0)
      top = []
      btm = []
    
      # Draw a startup logo (hides spurious sd errors)
      if g._show_splash:
        gfx.render_boot_logo(oled)
        continue
      
      # Draw the battery health, top-right
      batt()
      
      # Draw the memory info
      btm.append( mem )
      
      # Eink busy?  (direct from pin)
      if hal.eink.Busy.value() == 0:
      #if True:
        top.append( eink )
    
      # SD problems?
      if hal.get_sd_status() > 0 or g._sd_err > 0:
      #if True:
        btm.append( sd )
      
      ### BOOT ARG ###
      #t( str(g.boot_arg) ,0,8, 1)
      
      # Save icon
      #if True:
      if g.character is not None:
        if g.character.is_dirty():
          btm.append( save )
      
      # Render top
      x = 0
      for i in top:
        x += i( x, 0 ) + 1
      
      # Render bottom
      x = 0
      for i in btm:
        x += i( x, 16 ) + 1
      
      # Done
      oled.show()
