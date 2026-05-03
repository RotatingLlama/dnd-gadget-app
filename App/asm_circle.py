# 03 May 2026

from array import array
from uctypes import addressof
import asyncio
from gadget_hw import HW
import time

# Ref ARMv7-M Architecture Reference Manual
_LSL = const( 0b00000 << 11 ) # LSL <Rd>, <Rm>, #<imm5> [ref p282] => data(2, _LSL | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )
_LSR = const( 0b00001 << 11 ) # LSR <Rd>, <Rm>, #<imm5> [ref p284] => data(2, _LSR | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )

# circle( buf, params )
# buf = The raw buffer to draw to
# params = array (see example below)
#
@micropython.asm_thumb
def circle(r0,r1) -> int:
  mov(r12,r0) # buf => r12
  mov(r7,r1) # params => r7
  b(ENTRY)
  
  
  ### SUBROUTINE "PX" ###
  #
  # Write a pixel to the framebuffer
  # Input: r0 = colour
  #        r1 = X
  #        r2 = Y
  #        r7 = params [NO CLOBBER]
  #        r8 = Width of display [NO CLOBBER]
  #        r9 = Height of display [NO CLOBBER]
  #        r12 = Output buffer [NO CLOBBER]
  label(PX)
  push({r0,r1,r2,r3,r4,lr})
  #
  # Check Y is within bounds
  mov( r4, r9 ) # Display height (px) => r4
  cmp( r2, r4 )
  bge(_PX_END) # End if Y [r2] >= display height[r4]
  cmp( r2, 0 )
  bmi(_PX_END) # Branch if Y negative
  #
  # Check X is within upper bound
  mov( r4, r8 ) # Display width (px) => r4
  cmp( r1, r4 )
  bge(_PX_END) # End if X [r1] >= display width[r4]
  cmp( r1, 0 )
  bmi(_PX_END) # Branch if X is negative
  #
  # Calculate pixel number
  mul( r2, r4 ) # Y *= width
  add( r1, r1, r2 ) # Pixel number => r1
  #
  # Calculate bytes for pixel and mask
  mov( r3, 3 )  # Pixel mask => r3 <<<<<<
  mov( r2, r1 ) # Copy pixel number => r2
  and_( r2, r3 ) # Masked pixel number => pixel number within byte => r2
  # lsl( r2, r2, 1 )
  data(2, _LSL | 2 | ( 2 <<3 ) | ( 1 <<6 ) ) # Convert number of pixels to shift into number of bits ( r2 *= 2 ) => r2 <<<<<<
  lsl( r0, r2 ) # Shift colour to correct position => r0
  lsl( r3, r2 ) # Shift mask to correct position => r3
  #
  # Update the buffer
  mov(r4,2) # The number 2 => r4
  lsr( r1, r4 ) # Convert pixel number to address => r1
  mov( r2, r12 ) # Get the buffer address => r2
  add( r1, r1, r2 ) # Absolute byte address => r1 <<<<
  ldrb( r4, [r1,0] ) # Get the byte to modify => r4
  bic( r4, r3 ) # apply inverted mask to byte (r4 and not r3) => r4
  orr( r4, r0 ) # Apply the colour to the byte => r4
  strb( r4, [r1,0] ) # Put the updated byte back into the buffer
  #
  label(_PX_END)
  pop({r0,r1,r2,r3,r4,pc}) ################################
  
  
  ### SUBROUTINE "OCTS" ###
  #
  # Octuple a pixel postion, write them to the fb
  # Input: r0 = colour
  #        r1 = X
  #        r2 = Y
  #        r7 = Params [NO CLOBBER]
  #        r8 = Width of display [NO CLOBBER]
  #        r9 = Height of display [NO CLOBBER]
  #        r10 = CX [NO CLOBBER]
  #        r11 = CY [NO CLOBBER]
  #        r12 = Output buffer [NO CLOBBER]
  # Where X and Y are from the 3rd octant clockwise from TDC
  # i.e. 3 o'clock to 4:30
  label(OCTS)
  push({r1,r2,r3,r4,r5,r6,lr})
  #
  mov( r3, r1 )  #  x => r3
  mov( r4, r2 )  #  y => r4
  mov( r5, r10 ) # cx => r5
  mov( r6, r11 ) # cy => r6
  #
  # Q0
  add( r1, r5, r4 ) # x = cx + y
  sub( r2, r6, r3 ) # y = cy - x
  bl(PX)
  add( r1, r5, r3 ) # x = cx + x
  sub( r2, r6, r4 ) # y = cy - y
  bl(PX)
  #
  # Q1
  add( r1, r5, r3 ) # x = cx + x
  add( r2, r6, r4 ) # y = cy + y
  bl(PX)
  add( r1, r5, r4 ) # x = cx + y
  add( r2, r6, r3 ) # y = cy + x
  bl(PX)
  #
  # Q2
  sub( r1, r5, r4 ) # x = cx - y ##
  add( r2, r6, r3 ) # y = cy + x ##
  bl(PX)
  sub( r1, r5, r3 ) # x = cx - x
  add( r2, r6, r4 ) # y = cy + y
  bl(PX)
  #
  # Q3
  sub( r1, r5, r3 ) # x = cx - x
  sub( r2, r6, r4 ) # y = cy - y
  bl(PX)
  sub( r1, r5, r4 ) # x = cx - y
  sub( r2, r6, r3 ) # y = cy - x
  bl(PX)
  #
  label(_OCTS_END)
  pop({r1,r2,r3,r4,r5,r6,pc}) ####################
  
  
  ### SUBROUTINE "CIRCLE" ###
  # Input: r7 = Params [NO CLOBBER]
  #        r12 = Output buffer [NO CLOBBER]
  #
  # Draw a thin circle on the framebuffer
  label(CIRCLE)
  push({lr})
  mov( r0, r10 ) # Clobbering r10 causes crashing (don't know why)
  push({r0}) # Can't push/pop the high registers directly
  #
  ldr( r5, [r7,0x00] ) # Display width => r5
  ldr( r6, [r7,0x04] ) # Display height => r6
  mov( r8, r5 ) # Display width => r8
  mov( r9, r6 ) # Display height => r9
  ldr( r5, [r7,0x08] ) # cx => r5
  ldr( r6, [r7,0x0c] ) # cy => r6
  mov( r10, r5 ) # cx => r10
  mov( r11, r6 ) # cy => r11
  ldr( r3, [r7,0x10] ) # radius => r3
  ldr( r0, [r7,0x14] ) # colour => r0
  #
  mov( r1, r3 ) # radius => x => r1 <<<
  mov( r2, 0 )   # 0 => y => r2 <<<
  # lsr( r3, r3, 4 )
  data(2, _LSR | 3 | ( 3 <<3 ) | ( 4 <<6 ) ) # r / 16 => t1 => r3 <<<<
  label(_CIRCLE_LOOP)
  cmp( r1, r2 )  # Compare x - y
  bmi(_CIRCLE_END)  # Branch if negative ( x < y )
  bl(OCTS)          # Draw the pixel
  add( r2, 1 )      # y++
  add( r3, r3, r2 ) # t1 += y
  sub( r4, r3, r1 ) # t2 = t1 - x
  bmi(_CIRCLE_LOOP)    # Branch if negative ( t2 < 0 )
  mov( r3, r4 )     #  t1 = t2
  sub( r1, 1 )      #  x--
  b(_CIRCLE_LOOP)
  #
  label(_CIRCLE_END)
  pop({r0})
  mov( r10, r0 ) # Put r10 back
  pop({pc}) ################################
  
  
  ### ENTRY POINT ##########################
  #
  label(ENTRY)
  
  # Run the circle-drawing algo
  # Needs r7 and r12 to be params and output buffer (respectively)
  # But this is handled at the very top of the function
  bl(CIRCLE)
  
  # Fill output array with lower registers
  # Have the shuffle around r7 to preserve it
  mov( r8, r7 ) # r7 => r8
  ldr( r7, [r7,0x18] ) # Output array => r7
  str( r0, [r7,0x00] )
  str( r1, [r7,0x04] )
  str( r2, [r7,0x08] )
  str( r3, [r7,0x0C] )
  str( r4, [r7,0x10] )
  str( r5, [r7,0x14] )
  str( r6, [r7,0x18] )
  mov( r0, r7 ) # Output array => r0
  mov( r7, r8 ) # Original r7 => r7
  str( r7, [r0,0x1C] )
  

async def run():
  
  # Get the hw object and eink raw buffer
  hw = HW()
  buf = hw.eink.buf
  
  # Preallocate an array to contain debugging output
  output = array('L', [0]*8 )
  
  # Parameters
  params = array('L', (
    360, # [0x00] Width of display (pixels)
    240, # [0x04] Height of display (pixels)
    184, # [0x08] X of circle centre xc=180
    292, # [0x0C] Y of circle centre yc=120
    167, # [0x10] Radius of circle r=100
    2,   # [0x14] Colour of circle
    addressof(output) # [0x18] Output array pointer
  ))
  
  # Set up timer
  t1 = 0
  t2 = 0
  tus = time.ticks_us
  
  # Optimised assembly function
  t1 = tus()
  #print(hex( circle( buf, params ) ))
  circle( buf, params )
  t2 = tus()
  print(f'asm function completed in {time.ticks_diff(t2,t1)} us')
  print(output)
  # Typically takes about 340 us for a hp arc
  # params = ( 360, 240, 184, 292, 167, c, op )
  
  '''
  # Micropython builtin for comparison
  hee = hw.eink.ellipse
  mpp = ( params[2], params[3], params[4], params[4], params[5] )
  t1 = tus()
  hee( *mpp )
  t2 = tus()
  print(f'MP function completed in {time.ticks_diff(t2,t1)} us')
  # Average = 790 us => Optimised function is ~2.3x faster
  '''
  
  return
  
  # Send the buffer and update the eink
  await hw.eink.send()
  await hw.eink.wait_busy()
  await hw.eink.refresh()
  await asyncio.sleep(1)

# Have to do everything in a coroutine because the eink driver is fully async
asyncio.run( run() )
