# Menu library
# For OLED and LED Matrix displays
#
# T. Lloyd
# 20 Sep 2025

from .common import DeferredTask

# Drives the needle to select from a number of equally-spaced positions across its arc
# hal: the HAL object
# prio: The hal CR prioity
# n: The number of positions to select between
# btn: Function called when the button is pressed.  Is passed the current positional index
# back: Function called when the back switch pressed.  Is passed the current positional index
class NeedleMenu:
  
  def __init__(self,hal,prio,n,btn,back):
    self.hal = hal
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
    
    # Register our CR for life
    self.cr = self.hal.register(
      priority=prio,
      features=('needle','input',),
      input_target=lambda i: self._ih[i](),
      callback=self._update,
      name=type(self).__name__
    )
  
  def __del__(self):
    self.destroy()
  
  def destroy(self):
    self.hal.unregister( self.cr )
  
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


class RootMenu:
  def __init__(self,hal,prio,*args,**kwargs):
    self.hal = hal
    self.menus = []
    
    self._cr = self.hal.register(
      priority=prio,
      features=('input',),
      input_target=lambda i:self._ih[i](),
      name=type(self).__name__
    )
    
    self.init(*args,**kwargs)
  
  def __del__(self):
    self.destroy()
  
  def init(self,cw=lambda:None,ccw=lambda:None,btn=lambda:None,back=lambda:None):
    # Low-level input handler
    self._ih = (
      back,
      btn,
      cw,
      ccw,
    )
  
  # Terminator stub for 'exit to root' cascading call
  def exit(self):
    pass
  
  # When the root menu actually needs to go away
  def destroy(self):
    self.hal.unregister( self._cr )


class OledMenu:
  
  def __init__(self,parent,hal,prio,wrap:bool=True):
    
    # Catch essential params
    self.parent = parent
    self.hal = hal
    self.prio = prio
    self.wrap = wrap
    
    # Internal stuff
    self.items = []
    self.s = None
    self._cr = None
    
    # Low-level input handler
    self._ih = (
      self._leave, # back
      lambda: self.items[ self.s ].enter(), # btn
      self.next_item, # cw
      self.prev_item, # ccw
    )
    
  def _register(self):
    if self._cr is not None:
      return
    self._cr = self.hal.register(
      priority=self.prio,
      features=('input','oled',),
      input_target=lambda i: self._ih[i](),
      callback=self._render,
      name=type(self).__name__
    )
  
  def _unregister(self):
    if self._cr is not None:
      self.hal.unregister( self._cr )
      self._cr = None
  
  # Show whichever item title we're currently on
  def _render(self):
    if self.s is not None:
      self.items[ self.s ].render_title()
  
  def next_item(self):
    
    # If we are being activated (from the start)
    if self.s == None:
      self.s = 0
      self._register()
    
    # If we are already active
    else:
      self.s += 1
      
      # If we are falling off the end
      if self.s >= len(self.items):
        if self.wrap:
          self.s = 0
        else:
          self._leave()
          return
    
    # Display the new title
    self._render()
  
  def prev_item(self):
    
    # If we are being activated (from the end)
    if self.s == None:
      self.s = len(self.items)-1
      self._register()
    
    # If we are already active
    else:
      self.s -= 1
      
      # If we are falling off the end
      if self.s < 0:
        if self.wrap:
          self.s = len(self.items)-1
        else:
          self._leave()
          return
    
    # Register
    self._render()
  
  def exit(self):
    self._leave()
    self.parent.exit()
  
  def _leave(self):
    self.s = None
    self._unregister()

# For adjusting numeric values
# screen is 128/8 = 16 characters wide
class SimpleAdjuster:
  def __init__(self,
    parent,      # The menu that this adjuster is attached to
    hal,         # HAL object (for control of hardware)
    prio,        # The hal cr priority
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
    self.prio = prio
    self._ih = (
      self._leave, # back
      self.btn,
      self.cw,
      self.ccw
    )
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
    self._cr = None
  
  def _register(self):
    if self._cr is not None:
      return
    self._cr = self.hal.register(
      priority=self.prio,
      features=('input','oled',),
      input_target=lambda i:self._ih[i](),
      callback=self._update,
      name=self.title,
    )
  
  def _unregister(self):
    if self._cr is not None:
      self.hal.unregister( self._cr )
      self._cr = None
  
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
    self._register()
  
  def exit(self):
    self._leave()
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
  
  def _leave(self):
    self.d = 0
    self.aadj(self.get())
    self.radj(0)
    self._unregister()

# One adjustment affects two values
class DoubleAdjuster( SimpleAdjuster ):
  def __init__(self,parent,hal,prio,title,preview,get_cur,set_new,a='A',b='B',adj_rel=None,min_d=0,max_d=None,min_a=None,min_b=None,max_a=None,max_b=None):
    self.parent = parent
    self.hal = hal
    self.prio = prio
    self._ih = (
      self._leave, # back
      self.btn,
      self.cw,
      self.ccw
    )
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
    self._cr = None
  
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
  def __init__(self,parent,hal,prio,title,confirmation,con_func):
    self.parent = parent
    self.hal = hal
    self.prio = prio
    self._ih = (
      self._leave, # back
      self.btn,
      lambda:None, # cw
      lambda:None # ccw
    )
    self.title = title
    self.c_text = confirmation
    self.c_func = con_func
    self._cr = None
  
  def _register(self):
    if self._cr is not None:
      return
    self._cr = self.hal.register(
      priority=self.prio,
      features=('input','oled',),
      input_target=lambda i:self._ih[i](),
      callback=self._update,
      name=self.title,
    )
  
  def _unregister(self):
    if self._cr is not None:
      self.hal.unregister( self._cr )
      self._cr = None
  
  # Displays the UI
  def enter(self):
    self._register()
  
  def _update(self):
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
    self._leave()
    self.parent.exit()
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title, 12,12,1)
    oled.show()
  
  def btn(self):
    self.c_func()
    self.exit()
  
  def _leave(self):
    self._unregister()


# Manages the Matrix display
# hal: The hal object
# prio: The hal priority for our CRs
# active_rows: A list (or bytearray) of which matrix rows we should use
# inc: Function that will increment the value of a given row
# dec: Function that will decrement the value of a given row
# buffer: The raw buffer of the matrix (we draw to it)
# redraw_buffer: Function that will draw the default buffer
# send_buffer: Function that will cause the buffer to be displayed
# timeout: How long (ms) the adjuster pip should remain after the last user interaction
class MatrixMenu:
  
  def __init__(self,
    hal,
    prio:int,
    active_rows:bytearray,
    inc,
    dec,
    buffer:bytearray,
    redraw_buffer,
    send_buffer,
    timeout=2500,
  ):
    
    # Capture params
    self.hal = hal
    self.prio = prio
    self.active_rows = active_rows
    self.f_inc = inc
    self.f_dec = dec
    self.buffer = buffer
    self.f_redraw = redraw_buffer
    self.send_buffer = send_buffer
    
    # self.r is an index into self.active_rows
    # Scrolling up/down scrolls r over the list of active rows
    # To interact with a row, that row's number from the active_rows list is used
    
    # Internal values
    self.r = None
    self.to = DeferredTask( timeout=timeout, callback=self.exit )
    self._ih = (
      self.inc, # back
      self.dec, # btn
      self.prev_item, # cw
      self.next_item # ccw
    )
    self._cr = None
  
  def _register(self):
    if self._cr is not None:
      return
    self._cr = self.hal.register(
      priority=self.prio,
      features=('input','mtx'),
      input_target=lambda i:self._ih[i](),
      name=type(self).__name__
    )
  
  def _unregister(self):
    if self._cr is not None:
      self.hal.unregister(self._cr)
      self._cr = None
  
  def next_item(self):
    
    # If we are being activated (from the top)
    if self.r is None:
      self.r = 0
      self._register()
    
    # If we are already active
    else:
      
      self.r += 1
      
      # If we are being deactivated
      if self.r >= len(self.active_rows):
        self.r = None
        self.to.untouch()
        self._unregister()
        return
    
    # Update the timeout
    self.to.touch()
    
    # Update the matrix
    self._update_mtx()
  
  def prev_item(self):
    
    # If we are being activated (from the bottom)
    if self.r is None:
      self.r = len(self.active_rows) - 1
      self._register()
    
    # If we are already active
    else:
      
      self.r -= 1
      
      # If we are being deactivated
      if self.r < 0:
        self.r = None
        self.to.untouch()
        self._unregister()
        return
    
    # Update the timeout
    self.to.touch()
    
    # Update the matrix
    self._update_mtx()
  
  def inc(self):
    self.to.touch()
    self.f_inc( self.active_rows[self.r] )
    self._update_mtx()
  
  def dec(self):
    self.to.touch()
    self.f_dec( self.active_rows[self.r] )
    self._update_mtx()
  
  def _update_mtx(self):
    self.f_redraw()
    self.buffer[ self.active_rows[ self.r ] ] |= 3
    self.send_buffer()
  
  def exit(self):
    self.r = None
    self.to.untouch()
    self._unregister()
