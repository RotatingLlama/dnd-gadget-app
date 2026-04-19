"""
MicroPython max7219 cascadable 8x8 LED matrix driver
https://github.com/RotatingLlama/micropython-max7219

MIT License
Copyright (c) 2017 Mike Causer
Copyright (c) 2025 Tom Lloyd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from micropython import const
import framebuf

_NOOP = const(0)
_DIGIT0 = const(1)
_DECODEMODE = const(9)
_INTENSITY = const(10)
_SCANLIMIT = const(11)
_SHUTDOWN = const(12)
_DISPLAYTEST = const(15)

class Matrix8x8(framebuf.FrameBuffer):
    def __init__(self, spi, cs):
        """
        Driver for cascading MAX7219 8x8 LED matrices.
        Modified to work with TTRPG Gadget board rev 1
        TL Apr 2025

        >>> import max7219
        >>> from machine import Pin, SPI
        >>> spi = SPI(1)
        >>> display = max7219.Matrix8x8(spi, Pin('X5'), 4)
        >>> display.text('1234',0,0,1)
        >>> display.show()

        """
        self.spi = spi
        self.cs = cs
        self.cs.init(cs.OUT, True)
        self.buffer = bytearray(16) # hardcoded num=2
        self.num = 2 # hardcoded num=2
        super().__init__(
            self.buffer,
            8,  # hardcoded 8x16 portrait fb
            16,
            framebuf.MONO_HMSB
        )
        self.init()

    def _write(self, command, data):
        self.cs(0)
        for m in range(self.num):
            self.spi.write(bytes([command, data]))
        self.cs(1)

    def init(self):
        for command, data in (
            (_SHUTDOWN, 0),
            (_DISPLAYTEST, 0),
            (_SCANLIMIT, 7),
            (_DECODEMODE, 0),
            (_SHUTDOWN, 1),
        ):
            self._write(command, data)

    def brightness(self, value):
        if not 0 <= value <= 15:
            raise ValueError("Brightness out of range")
        self._write(_INTENSITY, value)
    
    def power(self, p):
        if p not in (0,1):
            raise ValueError("power() needs 0 or 1")
        self._write(_SHUTDOWN, p)
    
    # This version of show() rewritten to correct for incorrect orientation of large mtx in board rev 1
    # Sends the fb, displays immediately.  This display doesn't use a refresh command
    def show(self):
      
      fb = self.buffer
      outp = bytearray(4)
      
      # Rows are "digits" in 7219 lingo
      # Send byte for lge mtx first, then byte for sml mtx
      # Then do next line
      # etc.
      for orow in range(8):
        self.cs(0)
        
        # Tell the 7219s which row we're sending
        outp[0] = _DIGIT0 + orow
        outp[2] = _DIGIT0 + orow
        
        # Calculate the output byte for the (rotated) large matrix
        r = 7-orow
        outp[1] = (
          ((( fb[ 0 ] & (1<<r) ) >> r )   ) |
          ((( fb[ 1 ] & (1<<r) ) >> r )<<1) |
          ((( fb[ 2 ] & (1<<r) ) >> r )<<2) |
          ((( fb[ 3 ] & (1<<r) ) >> r )<<3) |
          ((( fb[ 4 ] & (1<<r) ) >> r )<<4) |
          ((( fb[ 5 ] & (1<<r) ) >> r )<<5) |
          ((( fb[ 6 ] & (1<<r) ) >> r )<<6) |
          ((( fb[ 7 ] & (1<<r) ) >> r )<<7)
        )
        
        # Output byte for the small matrix
        outp[3] = fb[ 8 + orow ]
        
        # Send the command
        self.spi.write(outp)
        
        self.cs(1)

# Takes an iterable of integers
# Returns an ascii depiction of the binary versions of the integers
def bin2ascii(b):
  r=''
  for row in b:
    t = bin(row)[2:].replace('0',' ').replace('1','X')
    r += "".join((" "*(8 - len(t)), t, '\n'))
  return r
