# Menu library
# For OLED and LED Matrix displays
#
# T. Lloyd
# 31 Jan 2026

from .common import DeferredTask

# ROOT MENUS
# Must at minimum have a destroy() method.
# This is called from the app, and should cause the root menu
# to tidy up its CRs etc and die cleanly.


# Drives the needle to select from a number of equally-spaced positions across its arc.
# Acts as a root menu, does not have a parent.
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
    if self.cr is not None:
      self.hal.unregister( self.cr )
      self.cr = None
  
  def _update(self):
    
    # If we only have one item, assume it's in the middle
    if self.max_i == 0:
      self.hal.needle.position( 0.5 )
    else:
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

# RootMenu
# Just handles inputs and dispatches callbacks for them.  Its CR gets overridden by the "real" menus.
# Additional methods besides destroy():
#  init() - Pass input callbacks as named args to replace the default (noop) callbacks
#  exit() - Terminator stub for cascading exit calls from children.  Does nothing.
# Properties:
#  menus - A list.  Not used by the library, but can be useful for external code.
class RootMenu:
  def __init__(self,hal,prio,*args,**kwargs):
    self.hal = hal
    
    # This list isn't used by anything in menu.py,
    # but provides a place to store refs to children so they don't get garbage collected
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
    if self._cr is not None:
      self.hal.unregister( self._cr )
      self._cr = None


class OledMenu:
  '''
    wrap:
    -1 = Exit on wrap
     0 = Do nothing on wrap
     1 = Full wrap
  '''
  
  def __init__(self,parent,hal,prio,wrap:int=0):
    
    # Catch essential params
    self.parent = parent # Only used for cascading exit() call
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
        if self.wrap > 0:
          self.s = 0
        elif self.wrap == 0:
          self.s = len(self.items) - 1
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
        if self.wrap > 0:
          self.s = len(self.items) - 1
        elif self.wrap == 0:
          self.s = 0
        else:
          self._leave()
          return
    
    # Register
    self._render()
  
  def exit(self):
    # Cascade before triggering CR deregistration, to prevent screen flickering through the cascade
    self.parent.exit()
    self._leave()
  
  def _leave(self):
    self.s = None
    self._unregister()

# Same as OledMenu but shows multiple entries and scrolls them
class ScrollingOledMenu(OledMenu):
  def _render(self):
    if self.wrap == 0:
      self._render_stop()
    else:
      self._render_wrap_exit()
  
  # Full wrap, or leaves blank space at ends
  def _render_wrap_exit(self):
    if self.s is not None:
      
      oled = self.hal.oled
      oled.fill(0)
      
      n = 3         # How many entries to show at once
      x = (n-1)//2  # The entry position to hilight
      yspacing = 12 # Pixel spacing between entries
      
      s = self.s-x
      for i in range( n ):
        
        # i = Position on screen
        # s = Position in items list
        
        # Make sure we wra, if neededp
        if self.wrap > 0:
          s %= len(self.items)
        
        # Ignore entry if out of bounds
        if s < 0:
          s += 1
          continue
        if s >= len(self.items):
          break
        
        # Generate the text
        t = self.items[ s ].get_title()
        oled.text( t, 3, i*yspacing, 1 )
        
        # Add the border if this is the selected entry
        if i == x:
          oled.rect( 0, (yspacing*x)-3, (len(t)*8)+6,14, 1 )
        
        # Next
        s += 1
      
      oled.show()
  
  # Can't scroll past ends, box moves, never blank space
  def _render_stop(self):
    if self.s is not None:
      
      lsi = len(self.items)
      oled = self.hal.oled
      oled.fill(0)
      
      n = 3         # How many entries to show at once
      x = (n-1)//2  # The entry position to hilight by default
      yspacing = 12 # Pixel spacing between entries
      
      # Figure out the first item to show
      s = self.s-x
      if s + n > lsi: # If we're going to run out of things to display:
        s = lsi - n     # Set the start based on only on the list length and display count
      if s < 0:       # If we have an invalid start point:
        s = 0           # Reset to safe value
      
      for i in range( n ):
        
        # i = Position on screen
        # s = Position in items list
        
        # Stop if entry is out of bounds
        if s >= lsi:
          break
        
        # Generate the text
        oled.text( self.items[ s ].get_title(), 4, i*yspacing, 1 )
        
        # Add the indicator if this is the selected entry
        if s == self.s:
          oled.vline( 0, (yspacing*i)+2, 4, 1 )
          oled.vline( 1, (yspacing*i)+3, 2, 1 )
        
        # Next
        s += 1
      
      oled.show()
  
# Prototype menu item class.
# Provides methods:
#  _register()
#  _unregister()
#  enter()
#  exit()
#  _leave()
# Children must define methods:
#  _update()
#  render_title()
class _OledMenuItem:
  
  def __init__(self, parent, hal, prio, title, ih ):
    
    # Capture these
    self.parent = parent
    self.hal = hal
    self.prio = prio
    self.title = title
    self._ih = ih
    
    # Define this
    self._cr = None
  
  def _register(self):
    if self._cr is not None:
      return
    self._cr = self.hal.register(
      priority=self.prio,
      features=('input','oled',),
      input_target=lambda i:self._ih[i](),
      callback=self._update, # type: ignore -- Class is never used directly; children set this
      name=self.title,
    )
  
  def _unregister(self):
    if self._cr is not None:
      self.hal.unregister( self._cr )
      self._cr = None
  
  def enter(self):
    self._register()
  
  def get_title(self) -> str:
    return self.title
  
  def exit(self):
    # Cascade before triggering CR deregistration, to prevent screen flickering through the cascade
    self.parent.exit()
    self._leave()
  
  def _leave(self):
    self._unregister()

# For adjusting numeric values
# screen is 128/8 = 16 characters wide
class SimpleAdjuster(_OledMenuItem):
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
    self.accel = IncrementAccelerator( self.adj )
    ih = (
      self._leave, # back
      self.btn,
      lambda: self.accel.adj(1), # cw
      lambda: self.accel.adj(-1) # ccw
    )
    super().__init__(parent=parent, hal=hal, prio=prio, title=title, ih=ih)
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
    if ( not callable(set_abs) ) and ( not callable(set_rel) ):
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
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.get_title(), 12,12,1)
    oled.show()
  
  def get_title(self) -> str:
    return self.title + ': ' + str(self.get())
  
  def adj(self, i ):
    
    d = self.d + i
    
    # Clamp d to min and max d
    if self.dmin is not None:
      if d < self.dmin:
        d = self.dmin
    if self.dmax is not None:
      if d > self.dmax:
        d = self.dmax
    
    # Clamp d to the values that will produce abs min and abs max
    if self.min is not None:
      d = max( d, self.min - self.get() )
    if self.max is not None:
      d = min( d, self.max - self.get() )
    
    # Set
    self.d = d
    self._update()
  
  def btn(self):
    
    # Optionally do nothing if d=0 (az = allow zero)
    if self.d == 0 and not self.az:
      return
    
    # Make the change
    if self.set_abs is not None:
      self.set_abs( self.get() + self.d )
    if self.set_rel is not None:
      self.set_rel( self.d )
    
    # Done
    self.exit()
  
  def _leave(self): # Override default _leave()
    self.d = 0
    self.accel.reset()
    self.aadj(self.get())
    self.radj(0)
    self._unregister()

# One adjustment affects two values
class DoubleAdjuster( SimpleAdjuster ):
  def __init__(self,parent,hal,prio,title,preview,get_cur,set_new,a='A',b='B',adj_rel=None,min_d=lambda:0,max_d=None,min_a=None,min_b=None,max_a=None,max_b=None):
    self.accel = IncrementAccelerator( self.adj )
    ih = (
      self._leave, # back
      self.btn,
      lambda: self.accel.adj(1), # cw
      lambda: self.accel.adj(-1), # ccw
    )
    super(SimpleAdjuster,self).__init__(parent=parent, hal=hal, prio=prio, title=title, ih=ih)
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
  
  # Restore the default _OledMenuItem behaviour - don't use the SimpleAdjuster version
  def get_title(self):
    return self.title
  
  # Adjust self.d, by increment i (if permissible)
  def adj(self, i ):
    
    # Get the closest permissible d, based on the requested increment
    d = self._chk_adj( self.d + i )
    
    # If it changes anything, make the update
    if d != self.d:
      self.d = d
      self._update()
  
  # Checks an adjustment and returns that adjustment if ok, or the closest permissible if not
  def _chk_adj(self, d:int ) -> int:
    
    # Clamp d to min and max d
    if self.dmin is not None:
      if d < self.dmin():
        d = self.dmin()
    if self.dmax is not None:
      if d > self.dmax():
        d = self.dmax()
    
    # Get a preview of what a and b would do if we set this d
    p = self.preview( d )
    
    # If any of these checks fail, just return d=0 because we don't know the mapping
    
    if self.amax is not None:
      if p[0] > self.amax():
        d = 0
    
    if self.bmax is not None:
      if p[1] > self.bmax():
        d = 0
    
    if self.amin is not None:
      if p[0] < self.amin():
        d = 0
    
    if self.bmin is not None:
      if p[1] < self.bmin():
        d = 0
    
    return d
  
  def btn(self):
    self.set( self.d )
    self.exit()

# For confirming single actions
class FunctionConfirmer(_OledMenuItem):
  def __init__(self,parent,hal,prio,title,confirmation,con_func):
    ih = (
      self._leave, # back
      self.btn,
      lambda:None, # cw
      lambda:None # ccw
    )
    super().__init__(parent=parent, hal=hal, prio=prio, title=title, ih=ih)
    self.c_text = confirmation
    self.c_func = con_func
  
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
  
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title, 12,12,1)
    oled.show()
  
  def btn(self):
    self.c_func()
    self.exit()

# A menu item to launch a submenu.
# Lightweight wrapper to translate from _OledMenuItem instance to new OledMenu instance
class SubMenu(_OledMenuItem):
  def __init__(self,parent,hal,prio,title,wrap=0):
    
    super().__init__(parent=parent, hal=hal, prio=prio, title=title, ih=(lambda:None,)*4 )
    
    # Submenu's parent is our parent
    # Submenu's priority is our priority
    # We never render anything ourselves
    # We never hold a CR
    
    self.menu = ScrollingOledMenu(
      parent=parent,
      hal=hal,
      prio=prio,
      wrap=wrap
    )
  
  # Override the default, (prevent CR from registering), immediately enter submenu
  def enter(self):
    self.menu.next_item()
  
  # Called by the parent menu
  def render_title(self):
    oled = self.hal.oled
    oled.fill(0)
    oled.text( self.title, 12,12,1)
    oled.show()
  
  # Would be called by our inherited CR code, if we hadn't overridden it
  # Still must exist
  def _update(self):
    pass
  def _leave(self):
    pass
  

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
        self.exit()
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
        self.exit()
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


class IncrementAccelerator:
  def __init__(self, cb ):
    self.cb = cb
    
    self._incs = (1,10,100,1000)
    self._thresh = 40
    self._lmax = len(self._incs) - 1
    
    self.reset()
  
  def reset(self):
    self.direction = 0
    self.runlength = 0
    self.currlevel = 0
  
  # Takes -1 or +1 for the direction of adjustment.
  # Calls self.cb() with the amount of increment to move
  def adj(self,s):
    
    # Efficient sign() function
    # sign = lambda x: x and (-1 if x < 0 else 1)
    
    # If we have just changed direction (or just started)
    if s != self.direction:
      
      # Decrease the current level
      if self.currlevel > 0:
        self.currlevel -= 1
      
      self.direction = s
      self.runlength = 1
      
    else: # Another one in the same direction
      
      # Is it time to accelerate?
      if self.runlength >= self._thresh:
        
        # Increase the current level
        if self.currlevel < self._lmax:
          self.currlevel += 1
        
        self.runlength = 1
        
      else: # Not time yet
        
        self.runlength += 1
    
    # Call the handler
    self.cb( self._incs[ self.currlevel ] * s )
