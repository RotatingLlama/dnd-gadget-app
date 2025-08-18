# Common functions
#
# 22 Jun 2025

import micropython
from framebuf import GS2_HMSB, GS4_HMSB, GS8, MONO_HLSB, MONO_HMSB, MONO_VLSB, MVLSB, RGB565

# Format to BPP mapping
f2b = {
  MONO_VLSB : 1,
  MONO_HLSB : 1,
  MONO_HMSB : 1,
  GS2_HMSB :  2,
  GS4_HMSB :  4,
  GS8 :       8
}

# BPP to format mapping
b2f = {
  1: MONO_HMSB,
  2: GS2_HMSB,
  4: GS4_HMSB,
  8: GS8
}

# 1bpp version
@micropython.viper
def swap_pixel_order_1(buf):
  b = ptr8(buf)
  lb = int(len(buf))
  i:int = 0
  while i < lb:
    # Rearrange all the bits
    # 12345678
    # 87654321
    b[i] = ( 
      (b[i]&128)>>7 | (b[i]&64)>>5 | (b[i]&32)>>3 | (b[i]&16)>>1
      | (b[i]&8)<<1 | (b[i]&4)<<3 | (b[i]&2)<<5 | (b[i]&1)<<7
    )
    i += 1

# 2bpp version
@micropython.viper
def swap_pixel_order_2(buf):
  b = ptr8(buf)
  lb = int(len(buf))
  i:int = 0
  while i < lb:
    # Rearrange all the bits
    # 12345678
    # 78563412
    b[i] = ((b[i]&192)>>6) | ((b[i]&48)>>2) | ((b[i]&12)<<2) | ((b[i]&3)<<6)
    i += 1
