# Augments MicroPython's native framebuffer module
# T. Lloyd
# 16 Jun 2025
#
# Improves existing methods:
# - hline
# - vline
#
# TODO:
# - Loosen requirement for width and height to both be divisible by eight?
# - Implement fonts?
#
# Version 1.2-pre
# date goes here
# - Moved drawThickArc() out to gfx.py
# - Changed all assert statements to exceptions

from framebuf import FrameBuffer #, GS2_HMSB, GS4_HMSB, GS8, MONO_HLSB, MONO_HMSB, MONO_VLSB, MVLSB, RGB565
from .utils import f2b
  
class FB(FrameBuffer):
  
  def __init__(self, buf, width, height, fmt, stride=None):
    
    # Input validation
    if type(width) is not int:
      raise TypeError('width must be integer')
    if type(height) is not int:
      raise TypeError('height must be integer')
    #
    if width <= 0:
      raise ValueError('width must be positive')
    if width % 8 != 0:
      raise ValueError('width must be multiple of 8')
    if height <= 0:
      raise ValueError('height must be positive')
    if height % 8 != 0:
      raise ValueError('height must be multiple of 8')
    
    if stride is None:
      stride = width
    
    # Record these
    self.buf = buf
    self.width = width
    self.height = height
    self.format = fmt
    self.bpp = f2b[fmt]
    
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
  
  #
  #def text(self, txt, x, y, c=1, font=''):
  #  
  #  # No font given: mirror the builtin function
  #  if font=='':
  #    super().text(txt,x,y,c)
  #    return
    
    