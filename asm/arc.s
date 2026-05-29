@ arc.s
@
@ T. Lloyd
@ 29 May 2026

.ident "_asm_arc(r0,r1) -> int"
.section .text,"ax"
.global _start

# Keys into the params array
.set _PARAM_WIDTH, 0x00
.set _PARAM_HEIGHT, 0x04
.set _PARAM_CX, 0x08
.set _PARAM_CY, 0x0C
.set _PARAM_R, 0x10
.set _PARAM_START, 0x14
.set _PARAM_END, 0x18
.set _PARAM_COLOUR, 0x1C
.set _PARAM_OUTPUT, 0x20

_start:
  b       ENTRY
  
  
  @## SUBROUTINE "PX" ###
  @
  @ Write a pixel to the framebuffer
  @ Input: r0 = colour
  @        r1 = X
  @        r2 = Y
  @        r7 = params [NO CLOBBER]
  @        r12 = Output buffer [NO CLOBBER]
PX:
  push    {r0, r1, r2, r3, r4, lr}
  @
  @ Check Y is within bounds
  ldr     r4, [ r7, #_PARAM_HEIGHT ] @ Display height (px) => r4
  cmp     r2, r4          @ Y - display_height
  bge     PX_END         @ End if Y [r2] >= display height[r4]
  cmp     r2, #0
  bmi     PX_END         @ Branch if Y negative
  @
  @ Check X is within upper bound
  ldr     r4, [ r7, #_PARAM_WIDTH ] @ Display width (px) => r4
  cmp     r1, r4          @ X - display_height
  bge     PX_END         @ End if X [r1] >= display width[r4]
  cmp     r1, #0
  bmi     PX_END         @ Branch if X is negative
  @
  @ Calculate pixel number
  mul     r2, r4          @ Y *= width
  add     r1, r1, r2      @ Pixel number => r1
  @
  @ Calculate bytes for pixel and mask
  mov     r3, #3          @ Pixel mask => r3 <<<<<<
  mov     r2, r1          @ Copy pixel number => r2
  and     r2, r3          @ Masked pixel number => pixel number within byte => r2
  lsl     r2, r2, #1      @ Convert number of pixels to shift into number of bits ( r2 *= 2 ) => r2 <<<<<<
  lsl     r0, r2          @ Shift colour to correct position => r0
  lsl     r3, r2          @ Shift mask to correct position => r3
  @
  @ Update the buffer
  mov     r4, #2          @ The number 2 => r4
  lsr     r1, r4          @ Convert pixel number to address => r1
  mov     r2, r12         @ Get the buffer address => r2
  add     r1, r1, r2      @ Absolute byte address => r1 <<<<
  ldrb    r4, [ r1, #0 ]  @ Get the byte to modify => r4
  bic     r4, r3          @ apply inverted mask to byte (r4 and not r3) => r4
  orr     r4, r0          @ Apply the colour to the byte => r4
  strb    r4, [ r1, #0 ]  @ Put the updated byte back into the buffer
  @
PX_END:
  pop     {r0, r1, r2, r3, r4, pc} @###############################
  
  
  
  @## SUBROUTINE "CALC_OCTS" ###
  @
  @ Pre-calculates which octants should be drawn / not drawn / checked
  @ Input:  r7 = Params [NO CLOBBER]
  @ Output: r2 = Draw
  @         r3 = Check
CALC_OCTS:
  push    {r0, r1, r4, r5, r6, r7, lr}
  
  @ Get start and end out of the params (it's all we need)
  ldr     r0, [ r7, #0x14 ] @ Start => r0
  ldr     r1, [ r7, #0x18 ] @ End => r1
  @
  @ 0+++ xxxx xxxx xxxx xxxx xxxx xxxx xxxx
  @ 0    : Always zero, to stop the N flag from tripping accidentally
  @  +++ : 3 bits to indicate the oct
  @      xxxx... : 28 bits of resolution within oct
  @
  lsr     r4, r0, #28  @ Calculate the starting oct => r4
  lsr     r5, r1, #28  @ Calculate the ending oct => r5
  @
  @ Sort out the ending oct
  lsl     r2, r1, #4      @ Testing if end (r1) is right on an oct boundary (all other bits zero)
  bne     OCTS_ENDOK     @ If the end octant's not right on a boundary, don't decrement it
  sub     r5, #1          @ ending oct --
  bpl     OCTS_ENDOK     @ If r5 isn't negative now, don't set it to 7
  mov     r5, #7          @ If ending oct was -1, set it to 7 instead
OCTS_ENDOK:
  @
  @
  @ Are start and end oct the same?
  cmp     r4, r5          @ startoct - endoct
  bne     OCTS_START_END_DIFFER @ If start and end are in different octs, run the loop
  @
  @ If we're here then start and end are in the same oct.
  @
  lsl     r2, r0, #4  @ Shift the oct info off start
  bne     OCTS_GOTTA_CHECK @ If there are bits left, start is not on a boundary.  Gotta check.
  lsl     r2, r1, #4  @ Shift the oct info off end
  bne     OCTS_GOTTA_CHECK @ If there are bits left, end is not on a boundary.  Gotta check.
  @
  @ We're here because we don't have to check anything.  Zero out the Check byte => r3
  mov     r3, #0
  @
  @ If start and end are in the same oct, and end is ZERO, then end is actually > start
  cmp     r1, #0
  beq     OCTS_NOCHECK_DRAW_NOTHING
  @
  @ Which way round are they?
  cmp     r1, r0          @ end - start
  bpl     OCTS_NOCHECK_DRAW_NOTHING @ Branch if positive or zero (end is after start)
  @
  @ This oct: No.  Other octs: Yes.
  mov     r6, #1          @ 1 => r6
  lsl     r6, r4          @ ( 1 << startoct ) => r6    000...00100000
  mov     r2, #0xff       @ 000...11111111 => r2     000...11111111
  bic     r2, r6          @ r2 & !r6 => Draw => r2     000...11011111
  b       OCTS_DONE
  @
  @ This oct: Yes.  Other octs: No
OCTS_NOCHECK_DRAW_NOTHING:
  mov     r2, #1          @ 1 => r2                            000...00000001
  lsl     r2, r4          @ ( 1 << startoct ) => Draw => r2   000...00100000
  b       OCTS_DONE
  @
  @ We have to at least check the one oct where start and end are
OCTS_GOTTA_CHECK:
  @
  @ Calculate the Check byte (just the one oct)
  mov     r3, #1
  lsl     r3, r4          @ ( 1 << startoct ) => Check => r3
  @
  @ If start and end are in the same oct, and end is ZERO, then end is actually > start
  cmp     r1, #0
  beq     OCTS_CHECK_DRAW_NOTHING @ So we want to draw nothing
  @
  @ Which way round are they?
  cmp     r1, r0          @ end - start
  bpl     OCTS_CHECK_DRAW_NOTHING @ Branch if positive or zero (end is after start)
  @
  @ This oct: Everything -> End -> Start -> Everything
  @                                       Use the Check byte: 000...00100000
  mov     r2, #0xff       @ 000...11111111 => r2              000...11111111
  bic     r2, r3          @ r2 & !r3 => Draw => r2            000...11011111
  b       OCTS_DONE
  @
  @ This oct: Nothing -> Start -> End -> Nothing
OCTS_CHECK_DRAW_NOTHING:
  mov     r2, #0          @ Draw => r2
  b       OCTS_DONE
  @
  @
  @ We have multiple octs to look at
OCTS_START_END_DIFFER:
  @
  @ Initialise Draw and Check bytes to zero
  mov     r2, #0          @ Draw => r2
  mov     r3, #0          @ Check => r3
  @
  @ The first iteration is always the ending oct, so do it here then go straight to loop-end
  @
  @ Calculate the bitmask for the ending oct
  mov     r7, #1
  lsl     r7, r5          @ 1 << octend => bitmask => r7
  @
  lsl     r6, r1, #4  @ Test if end (r1) is right on an oct boundary (all other bits zero)
  bne     _OCTS_END_GOTTA_CHECK @ End is NOT right on an octant boundary?
  @
  @ End is on a boundary.  Just draw.
  orr     r2, r7          @ Update Draw byte with the bitmask
  mov     r6, r5          @ ending oct => oct tracker => r6
  b       OCTS_LOOPEND
  @
_OCTS_END_GOTTA_CHECK: @ Can't just draw.  Gotta check
  orr     r3, r7          @ Update the Check byte with the bitmask
  mov     r6, r5          @ ending oct => oct tracker => r6
  b       OCTS_LOOPEND
  @
OCTS_LOOPSTART:
  @
  @ Have we reached the starting oct?
  cmp     r6, r4          @ oct - startoct
  bne     OCTS_JUST_DRAW @ No, we're in between.  Just draw
  @
  @ We are in the starting octant now
  @
  lsl     r4, r0, #4  @ Test if start (r0) is right on an oct boundary (all other bits zero)
  bne     OCTS_START_GOTTA_CHECK @ Start is NOT right on an octant boundary?
  @
  @ Start is on a boundary.  Just draw.
  orr     r2, r7          @ Update the Draw byte with the bitmask
  b       OCTS_DONE      @ We're done
  @
OCTS_START_GOTTA_CHECK:
  orr     r3, r7          @ Update the Check byte with the bitmask
  b       OCTS_DONE      @ We're done
  @
OCTS_JUST_DRAW: @ For in-between octs that aren't the start or the end
  orr     r2, r7          @ Update the Draw byte with the bitmask
  @
  @ The implicit comparison with zero here is the reason we decrement the oct tracker (r6), rather than increment
  @ Would have to use an additional register for the comparison otherwise
OCTS_LOOPEND:
  sub     r6, #1          @ decrement oct => r6
  bpl     OCTS_OCTNOTNEG @ Do the thing below if r6 (oct) is negative
  mov     r6, #7          @ 7 => oct => r6
OCTS_OCTNOTNEG:
  mov     r7, #1
  lsl     r7, r6          @ 1 << oct => bitmask for what octant we're in => r7
  b       OCTS_LOOPSTART
  @
OCTS_DONE:
  pop     {r0, r1, r4, r5, r6, r7, pc} @################################
  
  
  @## SUBROUTINE "CHECK_PX" ###
  @
  @ Octuple a pixel postion, write them to the fb
  @ Input: r0 = oct
  @        r3 = X (absolute)
  @        r4 = Y (absolute)
CHECK_PX:
  @ what oct is the pixel in (get from DRAW_OCTS)
  @ what oct is start in
  @ what oct is end in
  @ are we checking for start, end or both
  @
  @ if both:
  @ if start is on boundary, check for end only
  @ if end is on bondary, check for start only
  @ is px between or outside start and end
  @ flip sense of the above depending on order of start/end
  @
  @ if start or end:
  @ calc y boundary
  @ cmp( y, y_bound)
  @ draw or not = start or end  x  above or below x which half
  
  @ TODO:
  @ A function to pre-calculate m_start and m_end
  @ A function to get y, given x, m
  @ Store which oct start is in (can be none)
  @ Store which oct end is in (can be none)
  @ Implement logic above
  
  
  @## SUBROUTINE "DRAW_OCTS" ###
  @
  @ Octuple a pixel postion, write them to the fb
  @ Input: r0 = colour
  @        r1 = X               [NO CLOBBER]
  @        r2 = Y               [NO CLOBBER]
  @        r5 = Draw byte       [NO CLOBBER]
  @        r6 = Check byte      [NO CLOBBER]
  @        r7 = Params          [NO CLOBBER]
  @        r12 = Output buffer  [NO CLOBBER]
  @ Where X and Y are from the 3rd octant clockwise from TDC
  @ i.e. 3 o'clock to 4:30
DRAW_OCTS:
  push    {r1, r2, r3, r4, r5, r6, lr}
  @
  mov     r3, r1       @  x => r3
  mov     r4, r2       @  y => r4
  @
1: @ Oct 0
  mov     r0, #0x01    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @ Check
  mov     r0, #0x01    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  add     r1, r1, r4      @ x = cx + y
  sub     r2, r2, r3      @ y = cy - x
  bl      PX
  @
1: @ Oct 1
  mov     r0, #0x02    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #2       @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #0x02    @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  add     r1, r1, r3      @ x = cx + x
  sub     r2, r2, r4      @ y = cy - y
  bl      PX
  @
1: @ Oct 2
  mov     r0, #0x04    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x04    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  add     r1, r1, r3      @ x = cx + x
  add     r2, r2, r4      @ y = cy + y
  bl      PX
  @
1: @ Oct 3
  mov     r0, #0x08    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x08    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  add     r1, r1, r4      @ x = cx + y
  add     r2, r2, r3      @ y = cy + x
  bl      PX
  @
1: @ Oct 4
  mov     r0, #0x10    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x10    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  sub     r1, r1, r4      @ x = cx - y ##
  add     r2, r2, r3      @ y = cy + x ##
  bl      PX
  @
1: @ Oct 5
  mov     r0, #0x20    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x20    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  sub     r1, r1, r3      @ x = cx - x
  add     r2, r2, r4      @ y = cy + y
  bl      PX
  @
1: @ Oct 6
  mov     r0, #0x40    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x40    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  sub     r1, r1, r3      @ x = cx - x
  sub     r2, r2, r4      @ y = cy - y
  bl      PX
  @
1: @ Oct 7
  mov     r0, #0x80    @ oct
  and     r0, r5       @ Draw?
  beq     2f           @ No, check
  @
  mov     r0, #1       @ black
  b       3f
  @
2: @Check
  mov     r0, #0x80    @ oct
  and     r0, r6       @ Check?
  beq     1f           @ No, skip
  @
  mov     r0, #2       @ red
  @
3: @ Draw
  ldr     r1, [ r7, #_PARAM_CX ] @ cx => r1
  ldr     r2, [ r7, #_PARAM_CY ] @ cy => r2
  sub     r1, r1, r4      @ x = cx - y
  sub     r2, r2, r3      @ y = cy - x
  bl      PX
  @
1: @ Octs end
  pop     {r1, r2, r3, r4, r5, r6, pc} @###################
  
  
  @## SUBROUTINE "CIRCLE" ###
  @ Input: r7 = Params [NO CLOBBER]
  @        r12 = Output buffer [NO CLOBBER]
  @
  @ Draw a thin circle on the framebuffer
CIRCLE:
  push    {lr}
  @
  @ Set up registers
  ldr     r1, [ r7, #_PARAM_R ] @ radius => starting x => r1
  ldr     r0, [ r7, #_PARAM_COLOUR ] @ colour => r0
  @
  @ Get the Draw and Check bytes
  bl      CALC_OCTS       @ Draw => r2, Check => r3
  mov     r5, r2          @ Draw byte => r5
  mov     r6, r3          @ Check byte => r6
  @
  mov     r2, #0          @ 0 => y => r2 <<<
  lsr     r3, r1, #4  @ r / 16 => t1 => r3 <<<<
_CIRCLE_LOOP:
  cmp     r1, r2          @ Compare x - y
  bmi     _CIRCLE_END     @ Branch if negative ( x < y )
  bl      DRAW_OCTS       @ Draw the pixel
  add     r2, #1          @ y++
  add     r3, r3, r2      @ t1 += y
  sub     r4, r3, r1      @ t2 = t1 - x
  bmi     _CIRCLE_LOOP    @ Branch if negative ( t2 < 0 )
  mov     r3, r4          @  t1 = t2
  sub     r1, #1          @  x--
  b       _CIRCLE_LOOP
  @
_CIRCLE_END:
  @
  @
  pop     {pc}            @###############################
  
  
  @## ENTRY POINT ##########################
  @
ENTRY:
  @
  @ Save the inputs
  mov     r5, r0          @ buf => r5
  mov     r7, r1          @ params => r7
  @
  @ Save the high registers
  mov     r0, r8
  mov     r1, r9
  mov     r2, r10
  mov     r3, r11
  mov     r4, r12
  push    {r0, r1, r2, r3, r4} @ Can't push/pop the high registers directly TODO: OR CAN WE?
  @
  mov     r12, r5         @ buf => r12
  
  @ Run the circle-drawing algo
  @ Needs r7 and r12 to be params and output buffer (respectively)
  @ But this is handled at the very top of the function
  bl      CIRCLE
  
  @ Fill output array with lower registers
  @ Have the shuffle around r7 to preserve it
  mov     r8, r7          @ r7 => r8
  ldr     r7, [ r7, #_PARAM_OUTPUT ] @ Output array => r7
  str     r0, [ r7, #0x00 ]
  str     r1, [ r7, #0x04 ]
  str     r2, [ r7, #0x08 ]
  str     r3, [ r7, #0x0C ]
  str     r4, [ r7, #0x10 ]
  str     r5, [ r7, #0x14 ]
  str     r6, [ r7, #0x18 ]
  mov     r0, r7          @ Output array => r0
  mov     r7, r8          @ Original r7 => r7
  str     r7, [ r0, #0x1C ]
  @
  @ Put the high registers back
  pop     {r0, r1, r2, r3, r4}
  mov     r8, r0
  mov     r9, r1
  mov     r10, r2
  mov     r11, r3
  mov     r12, r4

.end

@ _mstart = round( tan( (start/_MAX) * _TAU ) * (1<<22) )
@ 
@ _MAX = (1<<31)
@ r0 = start/_MAX
@ r0 = r0 * TAU
@ r0 = tan(r0)
@ r0 = r0 * (1<<22)
@ _mstart = int( r0 )
