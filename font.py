# Font support
#
# 25 Feb 2025

#from eink.utils import swap_pixel_order_1, swap_pixel_order_2
import framebuf
from struct import unpack

class Font:
  
  def __init__(self,f):
    
    with open(f,'rb') as fd:
      
      # Get the initial params
      head = unpack( '>8B2H', fd.read(12) )
      
      '''
      0x00 1   Format version (must be 1)
      0x01 1   Image width, in pixels
      0x02 1   Glyph height, in pixels
      0x03 1   Number of glyphs
      0x04 1   Bits per pixel
      0x05 1   Glyph width
      0x06 1   Baseline height
      0x07 1   Index length
      0x08 2   Pointer to start of image data
      0x0A 2   Pointer to optional table of individual glyph widths.  If zero, assume monospace
      0C   4   Reserved
      10   x   Glyph Index Table
      '''
      
      # Version number
      if head[0] != 1:
        raise NotImplementedError('Bad file version')
      
      # Capture params
      self.fbw = head[1] # Framebuffer width, px
      self.height = head[2]  # Glyph height, px
      self.ng = head[3]  # Number of glyphs
      self.bpp = head[4] # Bits per pixel
      self.gw = head[5]  # Glyph width, px
      self.blh = head[6] # Baseline height, px
      self.stride = head[1] * head[2] * head[4] // 8
      
      # Get the glyph index
      fd.seek( 0x10, 0 )
      self.index = fd.read( head[7] )
      assert len( self.index ) == head[7]
      
      # Variable width?
      if head[9] > 0: 
        fd.seek( head[9], 0 )
        self.vw = fd.read( head[3] )
        assert len( self.vw ) == head[3]
      else: # Constant width
        self.vw = None
    
      # Get the image
      ilen = self.stride * self.ng
      self.glyphs = bytearray( ilen )
      fd.seek( head[8], 0 )
      assert ilen == fd.readinto( self.glyphs )
      del ilen
    
    # Set up the pallette - needed for blitting
    # Pallet format must match destination format, but width is related to source by w=2**bpp
    # For 2-bit colour that's a width of 4px = one byte
    self.pal = bytearray(1)
    self.palfb = framebuf.FrameBuffer( self.pal, 1<<self.bpp, 1, framebuf.GS2_HMSB )
    
    # Set up bpp-specific stuff
    if self.bpp == 1:
      #swap_pixel_order_1(self.glyphs)
      self.f = framebuf.MONO_HMSB
    elif self.bpp == 2:
      #swap_pixel_order_2(self.glyphs)
      self.f = framebuf.GS2_HMSB
    else:
      raise NotImplementedError('bpp more than 2 is not supported')
    
    # Set up the framebuffer object
    self.fb = framebuf.FrameBuffer( self.glyphs, head[1], head[2]*head[3], self.f )
  
  # fb: The framebugf instance to write to
  # txt: The string to write
  # x, y: Starting position.  y is text baseline, not top-left
  # p: Optional pallet tuple: (main, fill, hilight)
  # cspacing: Character spacing, in px
  # lspacing: Line spacing, in px
  def write_to( self, fb, txt, x, y, p=None, cspacing=1, lspacing=1 ):
    
    # Default pallette
    if p is None:
      p = (1,2,0) # Black, red, white
    
    # Gather params
    g = self.glyphs
    h = self.height
    gw = self.gw
    vw = self.vw
    bpp = self.bpp
    fbw = self.fbw
    f = self.f
    index = self.index
    s = self.stride
    
    # Pallette validation
    # TODO: validate the contents of the pallet tuple?
    if bpp == 1:
      assert len(p) >= 1
      # Zeroes are filler: they won't get used, the code just needs 3 elements
      p = ( p[0], 0, 0 )
    elif bpp == 2:
      assert len(p) >= 3
    
    # Adjust top-left corner to be above the baseline
    y -= self.blh
    
    # w() : Glyph width
    if vw is None:
      # Constant width
      w = lambda ci : gw
    else:
      # Lookup table
      w = lambda ci : vw[ ci ]
    
    # Create the pallette
    # 3 is always at the zero position, for transparency
    self.pal[0] = 3 | (p[0]<<2) | (p[1]<<4) | (p[2]<<6)
    palfb = self.palfb
    
    # Set up temporary fb
    glyph = bytearray( s )
    glyph_fb = framebuf.FrameBuffer( glyph, fbw, h, f )
    
    # Step through the string
    cx = x
    for i in range(len(txt)):
      
      # Get the char
      char = ord(txt[i])
      
      # If this is a space (ascii 32)
      if char == 32:
        cx += gw
        continue
      
      # If this is a linefeed (ascii 10)
      if char == 10:
        cx = x
        y += h + lspacing
        continue
      
      # Our index starts at ascii 32
      char -= 32
      
      # Check we have this value in the index
      if char >= len(index):
        char = 0
      
      # Get the index position
      ci = index[char]
      
      # Extract the glyph from the full image
      glyph[:] = g[ s*ci : s*(ci+1) ]
      
      # Blit the glyph
      fb.blit( glyph_fb, cx, y, 3, palfb )
      
      # Increment current x
      cx += w( ci ) + cspacing
