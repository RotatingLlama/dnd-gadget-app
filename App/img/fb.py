# Augments MicroPython's native framebuffer module
# T. Lloyd
# 09 Feb 2026
#
# Improves existing methods:
# - hline
# - vline
#
# TODO:
# - Implement fonts?

from framebuf import FrameBuffer #, GS2_HMSB, GS4_HMSB, GS8, MONO_HLSB, MONO_HMSB, MONO_VLSB, MVLSB, RGB565
from .utils import f2b
  
class FB(FrameBuffer):
  
  def __init__(self, buf, width, height, fmt, stride=None):
    
    # Input validation
    if type(width) is not int:
      raise TypeError('width must be integer')
    if type(height) is not int:
      raise TypeError('height must be integer')
    if width <= 0:
      raise ValueError('width must be positive')
    if height <= 0:
      raise ValueError('height must be positive')
    
    if stride is None:
      stride = width
    
    # Record these
    self.buf = buf
    self.width = width
    self.height = height
    self.format = fmt
    self.bpp = f2b[fmt]      # Bits per pixel
    self.ppb = 8 // self.bpp # Pixels per byte
    
    #
    if width % self.ppb != 0:
      raise ValueError('width must be a whole number of bytes')
    
    super().__init__(buf, width, height, fmt, stride)
  
  # Draw a horizontal line
  def hline(self, x, y, len, c):
    # Permit negative length (native version silently fails as of MP-1.24.1)
    if len < 0:
      len = -len
      x -= len-1
    super().hline(x,y,len,c)
  
  # Draw a vertical line
  def vline(self, x, y, len, c):
    # Permit negative length (native version silently fails as of MP-1.24.1)
    if len < 0:
      len = -len
      y -= len-1
    super().vline(x,y,len,c)
  
  # Draws text, on a solid background (for contrast, etc.)
  def label(self, s, x, y, c=1, b=0 ):
    '''
      s : The text to display
      x,y : Upper-left corner of text.  Text will be in same pixel position as text() method.
      c : Colour of text, optional, defaults to 1
      b : Colour of background, optional, defaults to 0
    '''
    
    w = len(s) * 8
    h = 8
    
    self.rect( x-2, y-1, w+4, h+2, b, True )
    self.hline( x-1, y-2, w+2, c=b )
    self.hline( x-1, y+h+1, w+2, c=b )
    self.text( s, x,y, c )
    
  #
  #def text(self, txt, x, y, c=1, font=''):
  #  
  #  # No font given: mirror the builtin function
  #  if font=='':
  #    super().text(txt,x,y,c)
  #    return
    
    