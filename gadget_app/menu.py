# Menu library
# For OLED and LED Matrix displays
#
# T. Lloyd
# 15 Sep 2025

from gc import collect as gc_collect
import time

from .common import DeferredTask, HAL_PRIORITY_MENU

# Drives the needle to select from a number of equally-spaced positions across its arc
# hal: the HAL object
# n: The number of positions to select between
# btn: Function called when the button is pressed.  Is passed the current positional index
# back: Function called when the back switch pressed.  Is passed the current positional index
class NeedleMenu:
  
  def __init__(self,hal,n,btn,back):
    self.hal = hal
    #self.cr = hal.register( priority=HAL_PRIORITY_MENU, features=('input','needle'), input_target=self.input_target )
    self.i = 0
    self.max_i = n - 1
    self.f_btn = btn
    self.f_back = back
    
    # Low-level input handler
    self._ih = (
      lambda: self.f_back( self.i ),
      lambda: self.f_btn( self.i ),
      self.next,
      self.prev
    )
    
    self._update()
  
  def _update(self):
    self.hal.needle.position( self.i / self.max_i )
    
  def next(self):
    if self.i >= self.max_i:
      return
    self.i += 1
    self._update()
    
  def prev(self):
    if self.i <= 0:
      return
    self.i -= 1
    self._update()
  
  
  def input_target(self, i ):
    self._ih[i]()
  #def cw(self,x):
  #  self.next()
  ##
  #def ccw(self,x):
  #  self.prev()
  ##
  #def btn(self,x):
  #  self.f_btn( self.i )
  ##
  #def back(self,x):
  #  self.f_back( self.i )


''' Menu prototype:

MANDATORY METHODS:
==================
next_item() - Move cursor to next item in menu
            - Acts as entry point to menu
            - Attempts to call next_item method of next menu if end of memnu is reached
prev_item() - As above, but in opposite direction
reclaim()   - Called by an exiting child, returns focus to menu
exit()      - Do whatever tidying up is necessary and call self.parent.exit()
            - Cascades all the way up to RootMenu
cw()        - Gets called when the menu has focus and the knob is turned clockwise
ccw()       - Gets called when the menu has focus and the knob is turned counter-clockwise
btn()       - Gets called when the menu has focus and the OK button is pressed
back()      - Gets called when the menu has focus and the back button is pressed

MANDATORY PROPERTIES
====================
display_type - String, 'oled' or 'mtx' indicating which hardware this menu writes to
'''

class RootMenu:
  def __init__(self,hal,char,*args,**kwargs):
    #self.hal = hal
    self.char = char
    self.menus = []
    self.child = None
    
    # Low-level input handler
    self._ih = (
      self.back,
      self.btn,
      self.cw,
      self.ccw
    )
    
    self.init(*args,**kwargs)
  
  def init(self,cw=lambda:None,ccw=lambda:None,btn=lambda:None,back=lambda:None):
    # Default input actions
    self.f_cw = cw
    self.f_ccw = ccw
    self.f_btn = btn
    self.f_back = back
  
  # Reclaim focus (usually from an exiting child)
  def reclaim(self):
    self.child = None
    self.char.draw_mtx( show=True )
    gc_collect()
  
  def exit(self):
    self.reclaim()
  
  # Pass user inputs on to appropriate menu
  def cw(self):
    if self.child is None:
      self.f_cw()
    else:
      self.child.cw()
  #
  def ccw(self):
    if self.child is None:
      self.f_ccw()
    else:
      self.child.ccw()
  #
  def btn(self):
    if self.child is None:
      self.f_btn()
    else:
      self.child.btn()
  #
  def back(self):
    if self.child is None:
      self.f_back()
    else:
      self.child.back()
  #
  def input_target(self, i ):
    self._ih[i]()
  


class OledMenu:
  
  def __init__(self,parent,hal,char,next_menu=None,prev_menu=None):
    self.parent = parent
    self.hal = hal
    self.char = char
    self.display_type = 'oled'
    self.items = []
    self.s = None
    self.child = None
    
    # Low-level input handler
    self._ih = (
      self.back,
      self.btn,
      self.cw,
      self.ccw
    )
    
    self.init( next_menu, prev_menu )
  
  def init(self,next_menu=None,prev_menu=None):
    self.next_menu = next_menu
    self.prev_menu = prev_menu
  
  def _register(self):
    self.parent.child = self
    self._cs = self.hal.register(
      priority=HAL_PRIORITY_MENU,
      features=('input','oled',),
      input_target=self.input_target,
      callback=lambda: self.items[ self.s ].render_title(),
    )
  
  def _unregister(self):
    self.hal.unregister( self._cs )
  
  def next_item(self):
    
    # Deal with the item pointer
    if self.s == None:
      self.s = 0
    else:
      self.s += 1
      if self.s >= len(self.items):
        self.s = None
        if self.next_menu is None:
          self.parent.reclaim()
        else:
          if self.next_menu.display_type != self.display_type:
            #self.hal.oled.release()
            self._unregister()
          self.next_menu.next_item()
        return
    
    # Register
    self._register()
    #self.hal.oled.lock = True
  
  def prev_item(self):
    
    # Deal with the item pointer
    if self.s == None:
      self.s = len(self.items)-1
    else:
      self.s -= 1
      if self.s < 0:
        self.s = None
        if self.prev_menu is None:
          self.parent.reclaim()
        else:
          if self.next_menu.display_type != self.display_type:
            #self.hal.oled.release()
            self._unregister()
          self.prev_menu.prev_item()
        return
    
    # Register
    self._register()
    #self.hal.oled.lock = True
  
  def exit(self):
    self.s = None
    self.child = None
    #self.hal.oled.release()
    self._unregister()
    self.parent.exit()
  
  def reclaim(self):
    self.child = None
    self.items[ self.s ].render_title()
    gc_collect()
  
  def cw(self):
    if self.child is not None:
      self.child.cw()
    else:
      self.next_item()
  
  def ccw(self):
    if self.child is not None:
      self.child.ccw()
    else:
      self.prev_item()
  
  def back(self):
    if self.child is not None:
      self.child.back()
    else:
      self.s = None
      #self.hal.oled.release()
      self._unregister()
      self.parent.reclaim()
  
  def btn(self):
    
    # Pass through if needed
    if self.child is not None:
      self.child.btn()
      return
    
    c = self.items[ self.s ]
    self.child = c
    c.enter()
    
  def input_target(self, i ):
    self._ih[i]()

# For adjusting numeric values
# screen is ~15 characters wide
class SimpleAdjuster:
  def __init__(self,
    parent,      # The menu that this adjuster is attached to
    hal,         # HAL object (for control of hardware)
    title,       # What to display on the menu
    get_cur,     # Function returning current value of adjustment parameter
    prompt=None, # Text to display while adjusting.  Default to same as title.
    set_abs=None,# Function to set the absolute value of the parameter
    set_rel=None,# Function to inc/dec the parameter by a relative amount
    adj_abs=None, # Function to call every time the knob is turned.  Is given the absolute value
    adj_rel=None, # Function to call every time the knob is turned.  Is given the relative inc/dec amount.
    min_d=None,  # Minimum allowable adjustment
    max_d=None,  # Maximum allowable adjustment
    min=0,       # Minimum allowable parameter
    max=None,    # Maximum allowable parameter
    allow_zero=False # Accept 'no adjustment'?  Default: no
  ):
    self.parent = parent
    self.hal = hal
    #self.hw = hal.hw
    self.title = title
    self.prompt = f'{title}:' if prompt is None else prompt
    self.get = get_cur
    self.set_abs = set_abs
    self.set_rel = set_rel
    self.d = 0
    self.dmin = min_d
    self.dmax = max_d
    self.min = min
    self.max = max
    self.az = allow_zero
    if adj_abs is None:
      self.aadj = lambda x: True
    else:
      self.aadj = adj_abs
    if adj_rel is None:
      self.radj = lambda x: True
    else:
      self.radj = adj_rel
    if set_abs is None and set_rel is None:
      raise RuntimeError('At least one of set_abs or set_rel must be callable')
  
  def _update(self):
    oled = self.hal.oled
    cur = self.get()
    d = self.d
    self.aadj(cur+d)
    self.radj(d)
    oled.fill(0)
    oled.text( self.prompt, 0,0,1)
    oled.text( f'{cur:4}', 90,0,1)
    oled.text( f'{abs(d):4}', 90,10,1)
    if d > 0:
      oled.text('+',82,10,1)
    elif d < 0:
      oled.text('-',82,10,1)
    oled.hline(50,20,90,32)
    oled.text( 'New:  ', 0, 20, 1 )
    oled.text( '% 4s' % (cur+d ) ,90,22,1)
    oled.show()
  
  def enter(self):
    self._update()
  
  def exit(self):
    self.parent.exit()
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title + ': ' + str(self.get()) ,12,12,1)
    oled.show()
  
  def cw(self):
    
    if self.dmax is not None:
      if self.d >= self.dmax:
        return
    
    if self.max is not None:
      if self.get() + self.d >= self.max:
        return
    
    self.d += 1
    self._update()
  
  def ccw(self):
    
    if self.dmin is not None:
      if self.d <= self.dmin:
        return
    
    if self.min is not None:
      if self.get() + self.d <= self.min:
        return
    
    self.d -= 1
    self._update()
  
  def btn(self):
    
    if self.d == 0 and not self.az:
      return
    
    if self.set_abs is not None:
      self.set_abs( self.get() + self.d )
    if self.set_rel is not None:
      self.set_rel( self.d )
    
    self.d = 0
    self.exit()
  
  def back(self):
    self.d = 0
    self.aadj(self.get())
    self.radj(0)
    self.parent.reclaim()

# One adjustment affects two values
class DoubleAdjuster( SimpleAdjuster ):
  def __init__(self,parent,hal,title,preview,get_cur,set_new,a='A',b='B',adj_rel=None,min_d=0,max_d=None,min_a=None,min_b=None,max_a=None,max_b=None):
    self.parent = parent
    self.hal = hal
    self.title = title
    self.preview = preview
    self.get = get_cur
    self.set = set_new
    self.a = a
    self.b = b
    self.d = 0
    self.dmin = min_d
    self.dmax = max_d
    self.amin = min_a
    self.bmin = min_b
    self.amax = max_a
    self.bmax = max_b
    if adj_rel is None:
      self.radj = lambda x: None
    else:
      self.radj = adj_rel
    self.aadj = lambda x: True # Placeholder until we need to implement absolute adjustment in DoubleAdjuster
  
  def _update(self):
    self.radj(self.d)
    oled = self.hal.oled
    a1, b1 = self.get()
    d = self.d
    a2, b2 = self.preview( d )
    
    # Draw a very small right-pointing arrow
    def arrow(x,y):
      oled.hline( x,y, 5, 1 )
      oled.line( x+2, y-2, x+5, y, 1 )
      oled.line( x+2, y+2, x+5, y, 1 )
    
    # Setup
    oled.fill(0)
    oled.hline( 0,9, 128, 2 )
    
    # Title and amount
    sign=' '
    if d > 0:
      sign = '+'
    elif d < 0:
      sign = '-'
    oled.text( f'{self.title}: {sign}{abs(d):3}' , 0,0,1) # this one has correct spacing
    
    # Labels
    oled.text( self.a, 0,11, 1 )
    oled.text( self.b, 0,20, 1 )
    
    # Current values
    oled.text( f'{a1:4}', 57,11, 1 )
    oled.text( f'{b1:4}', 57,20, 1 )
    
    # Arrows
    arrow( 91, 15 )
    arrow( 91, 24 )
    
    # New values
    oled.text( f'{a2:4}', 97,11, 1 )
    oled.text( f'{b2:4}', 97,20, 1 )
    
    self.hal.oled.show()
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title, 12,12, 1)
    oled.show()
  
  # Checks an adjustment and returns if it'll be OK or not
  def _chk_adj(self, d ):
    
    #print(f'd:{d}; dmin:{self.dmin()}: dmax:{self.dmax()}')
    
    if self.dmin is not None:
      if d < self.dmin():
        return False
    
    if self.dmax is not None:
      if d > self.dmax():
        return False
    
    p = self.preview( d )
    #print(f'a:{p[0]}; amin:{self.amin}; amax:{self.amax}; b:{p[1]}; bmin:{self.bmin}; bmax:{self.bmax}')
    
    if self.amax is not None:
      if p[0] > self.amax():
        return False
    
    if self.bmax is not None:
      if p[1] > self.bmax():
        return False
    
    if self.amin is not None:
      if p[0] < self.amin():
        return False
    
    if self.bmin is not None:
      if p[1] < self.bmin():
        return False
    
    return True
  
  def cw(self):
    if self._chk_adj( self.d + 1 ):
      self.d += 1
      self._update()
  
  def ccw(self):
    if self._chk_adj( self.d - 1 ):
      self.d -= 1
      self._update()
  
  def btn(self):
    self.set( self.d )
    self.d = 0
    self.exit()

# For confirming single actions
class FunctionConfirmer:
  def __init__(self,parent,hal,title,confirmation,con_func):
    self.parent = parent
    self.hal = hal
    #self.hw = hal.hw
    self.title = title
    self.c_text = confirmation
    self.c_func = con_func
  
  # Displays the UI
  def enter(self):
    oled = self.hal.oled
    
    oled.fill(0)
    
    oled.text( 'CONFIRM?', 0,0, 1 )
    oled.hline( 0,9, 127, 1 )
    oled.text( self.c_text, 0,11, 1)
    
    # Do a cross
    oled.line( 0,24, 7,31, 1)
    oled.line( 0,31, 7,24, 1)
    
    # Do a circle
    oled.ellipse( 123,27, 4,4, 1 )
    
    oled.show()
  
  def exit(self):
    self.parent.exit()
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title, 12,12,1)
    oled.show()
  
  def cw(self):
    pass
  
  def ccw(self):
    pass
  
  def btn(self):
    self.c_func()
    self.exit()
  
  def back(self):
    self.parent.reclaim()


# Common code for both menus on the matrix
class MatrixMenu:
  
  def __init__(self,parent,hal,char,startrow,indices,next_menu=None,prev_menu=None,timeout=2500):
    self.parent = parent
    self.hal = hal
    #self.hw = hal.hw
    self.char = char
    self.display_type = 'mtx'
    self.first_row = startrow
    self.last_row = startrow + len(indices) -1
    self.indices = indices
    self.r = None
    self.to = DeferredTask( timeout=timeout, callback=self.exit )
    self.init( next_menu, prev_menu )
  
  def init(self,next_menu=None,prev_menu=None):
    self.next_menu = next_menu
    self.prev_menu = prev_menu
  
  def next_item(self):
    
    # Deal with the row pointer
    if self.r is None:
      self.r = self.first_row
    else:
      self.r += 1
      if self.r > self.last_row:
        self.r = None
        self.to.untouch()
        if self.next_menu is None:
          self.parent.reclaim()
        else:
          if self.next_menu.display_type != self.display_type:
            self.char.draw_mtx()
          self.next_menu.next_item()
        return
    
    # Update the timeout
    self.to.touch()
    
    # Register
    self.parent.child = self
    
    # Update the matrix
    self._update_mtx()
  
  def prev_item(self):
    
    # Deal with the row pointer
    if self.r is None:
      self.r = self.last_row
    else:
      self.r -= 1
      if self.r < self.first_row:
        self.r = None
        self.to.untouch()
        if self.prev_menu is None:
          self.parent.reclaim()
        else:
          if self.prev_menu.display_type != self.display_type:
            self.char.draw_mtx()
          self.prev_menu.prev_item()
        return
    
    # Update the timeout
    self.to.touch()
    
    # Register
    self.parent.child = self
    
    # Update the matrix
    self._update_mtx()
  
  # Redraws the matrix with the seector pip
  def _update_mtx(self):
    self.char.draw_mtx( show=False )
    mtx = self.hal.mtx
    mtx.bitmap[ self.r ] = mtx.bitmap[ self.r ] | 3
    mtx.update()
  
  def exit(self):
    self.r = None
    self.to.untouch()
    self.parent.exit()
  
  def ccw(self):
    self.next_item()
    
  def cw(self):
    self.prev_item()
  

# OK/back button for charges menu
class ChargeMenu( MatrixMenu ):
  
  def btn(self):
    i = self.indices[ self.r - self.first_row ]
    c = self.char.stats['charges'][i]
    if c['curr'] > 0:
      self.parent.char.set_charge( i, c['curr']-1, show=False )
      self._update_mtx()
    self.to.touch()
  
  def back(self):
    i = self.indices[ self.r - self.first_row ]
    c = self.char.stats['charges'][i]
    if c['curr'] < c['max']:
      self.parent.char.set_charge( i, c['curr']+1, show=False )
      self._update_mtx()
    self.to.touch()

# OK/back button for spells menu
class SpellMenu( MatrixMenu ):
  
  def btn(self):
    i = self.indices[ self.r - self.first_row ]
    c = self.char.stats['spells'][i]
    if c[0] > 0:
      self.parent.char.set_spell( i, c[0]-1, show=False )
      self._update_mtx()
    self.to.touch()
  
  def back(self):
    i = self.indices[ self.r - self.first_row ]
    c = self.char.stats['spells'][i]
    if c[0] < c[1]:
      self.parent.char.set_spell( i, c[0]+1, show=False )
      self._update_mtx()
    self.to.touch()
