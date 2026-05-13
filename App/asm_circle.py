# 03 May 2026

from array import array
from uctypes import addressof
import asyncio
from gadget_hw import HW
import time

# Ref ARMv7-M Architecture Reference Manual
_LSL = const( 0b00000 << 11 ) # LSL <Rd>, <Rm>, #<imm5> [ref p282] => data(2, _LSL | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )
_LSR = const( 0b00001 << 11 ) # LSR <Rd>, <Rm>, #<imm5> [ref p284] => data(2, _LSR | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )

_PARAM_WIDTH  = const(0x00)
_PARAM_HEIGHT = const(0x04)
_PARAM_CX     = const(0x08)
_PARAM_CY     = const(0x0C)
_PARAM_R      = const(0x10)
_PARAM_START  = const(0x14)
_PARAM_END    = const(0x18)
_PARAM_COLOUR = const(0x1C)
_PARAM_OUTPUT = const(0x20)

# circle( buf, params )
# buf = The raw buffer to draw to
# params = array (see example below)
#
@micropython.asm_thumb
def _asm_circle(r0,r1) -> int:
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
  #
  # Save the high registers
  mov( r0, r8 )
  mov( r1, r9 )
  mov( r2, r10 )
  mov( r3, r11 )
  mov( r4, r12 )
  push({r0,r1,r2,r3,r4}) # Can't push/pop the high registers directly TODO: OR CAN WE?
  #
  # Set up registers
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
  #
  # Put the high registers back
  pop({r0,r1,r2,r3,r4})
  mov( r8, r0 )
  mov( r9, r1 )
  mov( r10, r2 )
  mov( r11, r3 )
  mov( r12, r4 )
  #
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


# arc( buf, params )
# buf = The raw buffer to draw to
# params = array (see example below)
#
@micropython.asm_thumb
def _asm_arc(r0,r1) -> int:
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
  
  
  
  ### SUBROUTINE "CALC_OCTS" ###
  #
  # Pre-calculates which octants should be drawn / not drawn / checked
  # Input:  r7 = Params [NO CLOBBER]
  # Output: r2 = Draw
  #         r3 = Check
  label(CALC_OCTS)
  push({r0,r1,r4,r5,r6,r7,lr})
  #
  # Get start and end out of the params (it's all we need)
  ldr( r0, [r7,0x14] ) # Start => r0
  ldr( r1, [r7,0x18] ) # End => r1
  #
  # 0+++ xxxx xxxx xxxx xxxx xxxx xxxx xxxx
  # 0    : Always zero, to stop the N flag from tripping accidentally
  #  +++ : 3 bits to indicate the oct
  #      xxxx... : 28 bits of resolution within oct
  #
  # lsr( r4, r0, 29 )
  data(2, _LSR | 4 | ( 0 <<3 ) | ( 28 <<6 ) ) # Calculate the starting oct => r4
  # lsr( r5, r1, 29 )
  data(2, _LSR | 5 | ( 1 <<3 ) | ( 28 <<6 ) ) # Calculate the ending oct => r5
  #
  # Sort out the ending oct
  # lsl( r2, r1, 4 )
  data(2, _LSL | 2 | ( 1 <<3 ) | ( 4 <<6 ) ) # Testing if end (r1) is right on an oct boundary (all other bits zero)
  bne(_OCTS_ENDOK) # If the end octant's not right on a boundary, don't decrement it
  sub( r5, 1 ) # ending oct --
  bpl(_OCTS_ENDOK) # If r5 isn't negative now, don't set it to 7
  mov( r5, 7 ) # If ending oct was -1, set it to 7 instead
  label(_OCTS_ENDOK)
  #
  #
  # Are start and end oct the same?
  cmp( r4, r5 ) # startoct - endoct
  bne(_OCTS_START_END_DIFFER) # If start and end are in different octs, run the loop
  #
  # If we're here then start and end are in the same oct.
  #
  # lsl( r2, r0, 4 )
  data(2, _LSL | 2 | ( 0 <<3 ) | ( 4 <<6 ) ) # Shift the oct info off start
  bne(_OCTS_GOTTA_CHECK) # If there are bits left, start is not on a boundary.  Gotta check.
  # lsl( r2, r1, 4 )
  data(2, _LSL | 2 | ( 1 <<3 ) | ( 4 <<6 ) ) # Shift the oct info off end
  bne(_OCTS_GOTTA_CHECK) # If there are bits left, end is not on a boundary.  Gotta check.
  #
  # We're here because we don't have to check anything.  Zero out the Check byte => r3
  mov( r3, 0 )
  #
  # If start and end are in the same oct, and end is ZERO, then end is actually > start
  cmp( r1, 0 )
  beq(_OCTS_NOCHECK_DRAW_NOTHING)
  #
  # Which way round are they?
  cmp( r1, r0 ) # end - start
  bpl(_OCTS_NOCHECK_DRAW_NOTHING) # Branch if positive or zero (end is after start)
  #
  # This oct: No.  Other octs: Yes.
  mov( r6, 1 ) # 1 => r6
  lsl( r6, r4 ) # ( 1 << startoct ) => r6    000...00100000
  mov( r2, 0xff ) # 000...11111111 => r2     000...11111111
  bic( r2, r6 ) # r2 & !r6 => Draw => r2     000...11011111
  b(_OCTS_DONE)
  #
  # This oct: Yes.  Other octs: No
  label(_OCTS_NOCHECK_DRAW_NOTHING)
  mov( r2, 1 ) # 1 => r2                            000...00000001
  lsl( r2, r4 ) # ( 1 << startoct ) => Draw => r2   000...00100000
  b(_OCTS_DONE)
  #
  # We have to at least check the one oct where start and end are
  label(_OCTS_GOTTA_CHECK)
  #
  # Calculate the Check byte (just the one oct)
  mov( r3, 1 )
  lsl( r3, r4 ) # ( 1 << startoct ) => Check => r3
  #
  # If start and end are in the same oct, and end is ZERO, then end is actually > start
  cmp( r1, 0 )
  beq(_OCTS_CHECK_DRAW_NOTHING) # So we want to draw nothing
  #
  # Which way round are they?
  cmp( r1, r0 ) # end - start
  bpl(_OCTS_CHECK_DRAW_NOTHING) # Branch if positive or zero (end is after start)
  #
  # This oct: Everything -> End -> Start -> Everything
  #                               Use the Check byte: 000...00100000
  mov( r2, 0xff ) # 000...11111111 => r2              000...11111111
  bic( r2, r3 ) # r2 & !r3 => Draw => r2              000...11011111
  b(_OCTS_DONE)
  #
  # This oct: Nothing -> Start -> End -> Nothing
  label(_OCTS_CHECK_DRAW_NOTHING)
  mov( r2, 0 ) # Draw => r2
  b(_OCTS_DONE)
  #
  #
  # We have multiple octs to look at
  label(_OCTS_START_END_DIFFER)
  #
  # Initialise Draw and Check bytes to zero
  mov( r2, 0 ) # Draw => r2
  mov( r3, 0 ) # Check => r3
  #
  # The first iteration is always the ending oct, so do it here then go straight to loop-end
  #
  # Calculate the bitmask for the ending oct
  mov( r7, 1 )
  lsl( r7, r5 ) # 1 << octend => bitmask => r7
  #
  # lsl( r6, r1, 4 )
  data(2, _LSL | 6 | ( 1 <<3 ) | ( 4 <<6 ) ) # Test if end (r1) is right on an oct boundary (all other bits zero)
  bne(_OCTS_END_GOTTA_CHECK) # End is NOT right on an octant boundary?
  #
  # End is on a boundary.  Just draw.
  orr( r2, r7 ) # Update Draw byte with the bitmask
  mov( r6, r5 ) # ending oct => oct tracker => r6
  b(_OCTS_LOOPEND)
  #
  label(_OCTS_END_GOTTA_CHECK) # Can't just draw.  Gotta check
  orr( r3, r7 ) # Update the Check byte with the bitmask
  mov( r6, r5 ) # ending oct => oct tracker => r6
  b(_OCTS_LOOPEND)
  #
  label(_OCTS_LOOPSTART)
  #
  # Have we reached the starting oct?
  cmp( r6, r4 ) # oct - startoct
  bne(_OCTS_JUST_DRAW) # No, we're in between.  Just draw
  #
  # We are in the starting octant now
  #
  # lsl( r4, r0, 4 )
  data(2, _LSL | 4 | ( 0 <<3 ) | ( 4 <<6 ) ) # Test if start (r0) is right on an oct boundary (all other bits zero)
  bne(_OCTS_START_GOTTA_CHECK) # Start is NOT right on an octant boundary?
  #
  # Start is on a boundary.  Just draw.
  orr( r2, r7 ) # Update the Draw byte with the bitmask
  b(_OCTS_DONE) # We're done
  #
  label(_OCTS_START_GOTTA_CHECK)
  orr( r3, r7 ) # Update the Check byte with the bitmask
  b(_OCTS_DONE) # We're done
  #
  label(_OCTS_JUST_DRAW) # For in-between octs that aren't the start or the end
  orr( r2, r7 ) # Update the Draw byte with the bitmask
  #
  # The implicit comparison with zero here is the reason we decrement the oct tracker (r6), rather than increment
  # Would have to use an additional register for the comparison otherwise
  label(_OCTS_LOOPEND)
  sub( r6, 1 ) # decrement oct => r6
  bpl(_OCTS_OCTNOTNEG) # Do the thing below if r6 (oct) is negative
  mov( r6, 7 ) # 7 => oct => r6
  label(_OCTS_OCTNOTNEG)
  mov( r7, 1 )
  lsl( r7, r6 ) # 1 << oct => bitmask for what octant we're in => r7
  b(_OCTS_LOOPSTART)
  #
  label(_OCTS_DONE)
  pop({r0,r1,r4,r5,r6,r7,pc})

  
  
  ### SUBROUTINE "DRAW_OCTS" ###
  #
  # Octuple a pixel postion, write them to the fb
  # Input: r0 = colour
  #        r1 = X
  #        r2 = Y
  #        r5 = Draw byte [NO CLOBBER]
  #        r6 = Check byte [NO CLOBBER]
  #        r7 = Params [NO CLOBBER]
  #        r8 = Width of display [NO CLOBBER]
  #        r9 = Height of display [NO CLOBBER]
  #        r10 = CX [NO CLOBBER]
  #        r11 = CY [NO CLOBBER]
  #        r12 = Output buffer [NO CLOBBER]
  # Where X and Y are from the 3rd octant clockwise from TDC
  # i.e. 3 o'clock to 4:30
  label(DRAW_OCTS)
  push({r1,r2,r3,r4,r5,r6,lr})
  #
  mov( r3, r1 )  #  x => r3
  mov( r4, r2 )  #  y => r4
  #
  # Oct 0
  mov( r0, 0x01 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_0) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_0)
  #
  label(_PX_CHK_0)
  mov( r0, 0x01 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_1) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_0)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  add( r1, r1, r4 ) # x = cx + y
  sub( r2, r2, r3 ) # y = cy - x
  bl(PX)
  #
  # Oct 1
  label(_PX_1)
  mov( r0, 0x02 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_1) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_1)
  #
  label(_PX_CHK_1)
  mov( r0, 2 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_2) # No, skip
  #
  mov( r0, 0x02 ) # red
  #
  label(_PX_DRAW_1)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  add( r1, r1, r3 ) # x = cx + x
  sub( r2, r2, r4 ) # y = cy - y
  bl(PX)
  #
  # Oct 2
  label(_PX_2)
  mov( r0, 0x04 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_2) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_2)
  #
  label(_PX_CHK_2)
  mov( r0, 0x04 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_3) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_2)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  add( r1, r1, r3 ) # x = cx + x
  add( r2, r2, r4 ) # y = cy + y
  bl(PX)
  #
  # Oct 3
  label(_PX_3)
  mov( r0, 0x08 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_3) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_3)
  #
  label(_PX_CHK_3)
  mov( r0, 0x08 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_4) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_3)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  add( r1, r1, r4 ) # x = cx + y
  add( r2, r2, r3 ) # y = cy + x
  bl(PX)
  #
  # Oct 4
  label(_PX_4)
  mov( r0, 0x10 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_4) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_4)
  #
  label(_PX_CHK_4)
  mov( r0, 0x10 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_5) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_4)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  sub( r1, r1, r4 ) # x = cx - y ##
  add( r2, r2, r3 ) # y = cy + x ##
  bl(PX)
  #
  # Oct 5
  label(_PX_5)
  mov( r0, 0x20 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_5) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_5)
  #
  label(_PX_CHK_5)
  mov( r0, 0x20 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_6) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_5)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  sub( r1, r1, r3 ) # x = cx - x
  add( r2, r2, r4 ) # y = cy + y
  bl(PX)
  #
  # Oct 6
  label(_PX_6)
  mov( r0, 0x40 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_6) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_6)
  #
  label(_PX_CHK_6)
  mov( r0, 0x40 ) # oct
  and_( r0, r6 ) # Check?
  beq(_PX_7) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_6)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  sub( r1, r1, r3 ) # x = cx - x
  sub( r2, r2, r4 ) # y = cy - y
  bl(PX)
  #
  # Oct 7
  label(_PX_7)
  mov( r0, 0x80 ) # oct
  and_( r0, r5 ) # Draw?
  beq(_PX_CHK_7) # No, check
  #
  mov( r0, 1 ) # black
  b(_PX_DRAW_7)
  #
  label(_PX_CHK_7)
  mov( r0, 0x80 ) # oct
  and_( r0, r6 ) # Check?
  beq(_OCTS_END) # No, skip
  #
  mov( r0, 2 ) # red
  #
  label(_PX_DRAW_7)
  ldr( r1, [r7,_PARAM_CX] ) # cx => r1
  ldr( r2, [r7,_PARAM_CY] ) # cy => r2
  sub( r1, r1, r4 ) # x = cx - y
  sub( r2, r2, r3 ) # y = cy - x
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
  #
  #
  # Set up registers
  ldr( r5, [r7,_PARAM_WIDTH] ) # Display width => r5
  ldr( r6, [r7,_PARAM_HEIGHT] ) # Display height => r6
  mov( r8, r5 ) # Display width => r8
  mov( r9, r6 ) # Display height => r9
  ldr( r5, [r7,_PARAM_CX] ) # cx => r5
  ldr( r6, [r7,_PARAM_CY] ) # cy => r6
  #mov( r10, r5 ) # cx => r10
  #mov( r11, r6 ) # cy => r11
  ldr( r3, [r7,_PARAM_R] ) # radius => r3
  ldr( r0, [r7,_PARAM_COLOUR] ) # colour => r0
  #
  # Get the Draw and Check bytes
  push({r3})
  bl(CALC_OCTS)
  mov( r5, r2 ) # Draw byte => r5
  mov( r6, r3 ) # Check byte => r6
  pop({r3})
  #
  mov( r1, r3 ) # radius => x => r1 <<<
  mov( r2, 0 )   # 0 => y => r2 <<<
  # lsr( r3, r3, 4 )
  data(2, _LSR | 3 | ( 3 <<3 ) | ( 4 <<6 ) ) # r / 16 => t1 => r3 <<<<
  label(_CIRCLE_LOOP)
  cmp( r1, r2 )  # Compare x - y
  bmi(_CIRCLE_END)  # Branch if negative ( x < y )
  bl(DRAW_OCTS)     # Draw the pixel
  add( r2, 1 )      # y++
  add( r3, r3, r2 ) # t1 += y
  sub( r4, r3, r1 ) # t2 = t1 - x
  bmi(_CIRCLE_LOOP)    # Branch if negative ( t2 < 0 )
  mov( r3, r4 )     #  t1 = t2
  sub( r1, 1 )      #  x--
  b(_CIRCLE_LOOP)
  #
  label(_CIRCLE_END)
  #
  #
  pop({pc}) ################################
  
  
  ### ENTRY POINT ##########################
  #
  label(ENTRY)
  #
  # Save the inputs
  mov( r5, r0 ) # buf => r5
  mov( r7, r1 ) # params => r7
  #
  # Save the high registers
  mov( r0, r8 )
  mov( r1, r9 )
  mov( r2, r10 )
  mov( r3, r11 )
  mov( r4, r12 )
  push({r0,r1,r2,r3,r4}) # Can't push/pop the high registers directly TODO: OR CAN WE?
  #
  mov( r12, r5 ) # buf => r12
  
  # Run the circle-drawing algo
  # Needs r7 and r12 to be params and output buffer (respectively)
  # But this is handled at the very top of the function
  bl(CIRCLE)
  
  # Fill output array with lower registers
  # Have the shuffle around r7 to preserve it
  mov( r8, r7 ) # r7 => r8
  ldr( r7, [r7,_PARAM_OUTPUT] ) # Output array => r7
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
  #
  # Put the high registers back
  pop({r0,r1,r2,r3,r4})
  mov( r8, r0 )
  mov( r9, r1 )
  mov( r10, r2 )
  mov( r11, r3 )
  mov( r12, r4 )


def arc( buf, start:float, end:float ):
  
  if start == end:
    raise ValueError()
  
  MAX = 0x8000_0000
  istart = round( start * MAX ) % MAX
  iend = round( end * MAX ) % MAX
  
  # Preallocate an array to contain debugging output
  output = array('L', [0]*8 )
  
  params = array('L', (
    360, # [0x00] Width of display (pixels)
    240, # [0x04] Height of display (pixels)
    180, # [0x08] X of arc centre
    120, # [0x0C] Y of arc centre
    100, # [0x10] Radius of arc
    istart, # Start
    iend, # End
    1,   # [0x14] Colour of arc
    addressof(output) # [0x18] Output array pointer
  ))
  print(f'start: 0x{hex(istart)}  end: 0x{hex(iend)}')
  
  ret = _asm_arc( buf, params )
  
  # Draw, Check
  return ret & 0xff, ret >> 8

def circle(buf):
  
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
  #print(hex( _asm_circle( buf, params ) ))
  _asm_circle( buf, params )
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

def arc_grid(buf):
  
  MAX = 0x8000_0000
  
  # Preallocate an array to contain debugging output
  output = array('L', [0]*8 )
  
  params = array('L', (
    360, # [0x00] Width of display (pixels)
    240, # [0x04] Height of display (pixels)
    0, # [0x08] X of arc centre
    0, # [0x0C] Y of arc centre
    7, # [0x10] Radius of arc
    0, # Start
    0, # End
    1,   # [0x14] Colour of arc
    addressof(output) # [0x18] Output array pointer
  ))
  
  for start in range(16):
    for end in range(16):
      if start == end:
        continue
      params[2] = ( start * 15 ) + 7
      params[3] = ( end * 15 ) + 7
      params[5] = round( start/16 * MAX ) % MAX
      params[6] = round( end/16 * MAX ) % MAX
      _asm_arc( buf, params )

async def run():
  
  # Get the hw object and eink raw buffer
  hw = HW()
  buf = hw.eink.buf
  
  arc_grid(buf)
  
  #return
  
  # Send the buffer and update the eink
  await hw.eink.send()
  await hw.eink.wait_busy()
  await hw.eink.refresh()
  await asyncio.sleep(1)

# Have to do everything in a coroutine because the eink driver is fully async
asyncio.run( run() )
