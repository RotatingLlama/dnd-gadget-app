'''
From micropython-lib [https://github.com/micropython/micropython-lib]

Copyright (c) 2013, 2014 micropython-lib contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

# MicroPython SSD1306 OLED driver, I2C and SPI interfaces

from micropython import const
from gc import collect as gc_collect
#from . import fb
from img import FrameBuffer, MONO_VLSB


# register definitions
_SET_CONTRAST     = const(0x81)
_SET_ENTIRE_ON    = const(0xA4)
_SET_NORM_INV     = const(0xA6)
_SET_DISP         = const(0xAE)
_SET_MEM_ADDR     = const(0x20)
_SET_COL_ADDR     = const(0x21)
_SET_PAGE_ADDR    = const(0x22)
_SET_DISP_START_LINE = const(0x40)
_SET_SEG_REMAP    = const(0xA0)
_SET_MUX_RATIO    = const(0xA8)
_SET_IREF_SELECT  = const(0xAD)
_SET_COM_OUT_DIR  = const(0xC0)
_SET_DISP_OFFSET  = const(0xD3)
_SET_COM_PIN_CFG  = const(0xDA)
_SET_DISP_CLK_DIV = const(0xD5)
_SET_PRECHARGE    = const(0xD9)
_SET_VCOM_DESEL   = const(0xDB)
_SET_CHARGE_PUMP  = const(0x8D)


# Subclassing FrameBuffer provides support for graphics primitives
# http://docs.micropython.org/en/latest/pyboard/library/framebuf.html
#class SSD1306(framebuf.FrameBuffer):
class SSD1306(FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        
        # Precaution before allocating buffer
        gc_collect()
        
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            _SET_DISP,  # display off
            # address setting
            _SET_MEM_ADDR,
            0x00,  # horizontal
            # resolution and layout
            _SET_DISP_START_LINE,  # start at line 0
            _SET_SEG_REMAP | 0x01,  # column addr 127 mapped to SEG0
            _SET_MUX_RATIO,
            self.height - 1,
            _SET_COM_OUT_DIR | 0x08,  # scan from COM[N] to COM0
            _SET_DISP_OFFSET,
            0x00,
            _SET_COM_PIN_CFG,
            0x02 if self.width > 2 * self.height else 0x12,
            # timing and driving scheme
            _SET_DISP_CLK_DIV,
            0x80,
            _SET_PRECHARGE,
            0x22 if self.external_vcc else 0xF1,
            _SET_VCOM_DESEL,
            0x30,  # 0.83*Vcc
            # display
            _SET_CONTRAST,
            #0xFF,  # maximum
            0x01,  # minimum
            _SET_ENTIRE_ON,  # output follows RAM contents
            _SET_NORM_INV,  # not inverted
            _SET_IREF_SELECT,
            0x30,  # enable internal IREF during display on
            # charge pump
            _SET_CHARGE_PUMP,
            0x10 if self.external_vcc else 0x14,
            _SET_DISP | 0x01,  # display on
        ):  # on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(_SET_DISP)

    def poweron(self):
        self.write_cmd(_SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(_SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(_SET_NORM_INV | (invert & 1))

    def rotate(self, rotate):
        self.write_cmd(_SET_COM_OUT_DIR | ((rotate & 1) << 3))
        self.write_cmd(_SET_SEG_REMAP | (rotate & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width != 128:
            # narrow displays use centred columns
            col_offset = (128 - self.width) // 2
            x0 += col_offset
            x1 += col_offset
        self.write_cmd(_SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(_SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b"\x40", None]  # Co=0, D/C#=1
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, external_vcc=False):
        self.rate = 10 * 1024 * 1024
        dc.init(dc.OUT, value=0)
        res.init(res.OUT, value=0)
        cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        import time

        self.res(1)
        time.sleep_ms(1)
        self.res(0)
        time.sleep_ms(10)
        self.res(1)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)
