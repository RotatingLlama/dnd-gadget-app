# 10 May 2026

#import micropython
#from micropython import const
from array import array
#import math
#from uctypes import addressof
import machine

# RP2040 datasheet
# https://pip-assets.raspberrypi.com/categories/814-rp2040/documents/RP-008371-DS-1-rp2040-datasheet.pdf

# Ref ARMv7-M Architecture Reference Manual
_BLX = const( 0b010001111 << 7 )# BLX <Rm> [ref p214] => data(2, _BLX | ( Rm <<3 ) )
_LSL = const( 0b00000 << 11 ) # LSL <Rd>, <Rm>, #<imm5> [ref p282] => data(2, _LSL | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )
_LSR = const( 0b00001 << 11 ) # LSR <Rd>, <Rm>, #<imm5> [ref p284] => data(2, _LSR | Rd | ( Rm <<3 ) | ( imm5 <<6 ) )
_LDMIA = const( 0b1100_1 << 11 ) # LDMIA <Rn>!, reglist [ref p242] => data(2, _LDMIA | ( Rn <<8) | reglist ) # ldmia( Rn, {reglist} )

# p132
# 010001     # Special data instructions and branch and exchange
#       0100 # UNPREDICTABLE
#       0101 # Compare registers
#       011x # Compare registers
#         n        # MSB of Rn
#          mmmm    # Rm
#              nnn # Rn
#
# At least one of Rn, Rm must be a high register with this encoding
_CMP = const( 0b010001_01 << 8 ) # data(2, _CMP | ( Rn &7) | (( Rn &8)<<3) | ( Rm <<3) ) # cmp( Rn, Rm )

# Add high registers.  At least one must be high, see _CMP above
_ADD = const( 0b010001_00 << 8 ) # data(2, _ADD | ( Rd &7) | (( Rd &8)<<3) | ( Rm <<3) ) # add( Rd, Rm )

# Memory Locations (absolute)
_ROM_VER = const(0x13)
_ROM_DATA_TABLE_PTR = const(0x16)
_HELPER_FN_PTR = const(0x18)
_SIO_BASE = const(0xd0000000)

# Bootrom floating point library functions
_FMUL = const(0x08) # p138, 58 cycles
_FDIV = const(0x0c) # p138, 71 cycles
_FLOAT2INT = const(0x1c) # p138, 40 cycles
_INT2FLOAT = const(0x2c) # p139, 55 cycles
_FTAN = const(0x44) # p139, 653 cycles (!)
#
# SIO Integer Divider registers
_SIO_DIV_UDIVIDEND = const(0x060) # Divider unsigned dividend P/q
_SIO_DIV_UDIVISOR = const(0x064) # Divider unsigned divisor p/Q
_SIO_DIV_SDIVIDEND = const(0x068) # Divider signed dividend
_SIO_DIV_SDIVISOR = const(0x06c) # Divider signed divisor
_SIO_DIV_QUOTIENT = const(0x070) # Divider result quotient
_SIO_DIV_REMAINDER = const(0x074) # Divider result remainder
_SIO_DIV_CSR = const(0x078) # Control and status register for divider.

_MAX = const(0x8000_0000)
_TAU = const(6.283184)

# Check out 'blend mode' for linear interpolation - datasheet p37

# Check the magic bytes in the rp2040 ROM.
# Return bool indicating if there is magic
@micropython.asm_thumb
def chk_magic() -> bool:
  
  # Check magic
  # Output: r3 = 1 if there is magic
  #              Otherwise zero
  mov( r1, 0x00000010 ) # Location of the magic
  ldr( r1, [r1,0] ) # Get the magic -> r1
  lsl( r1, r1, 8 ) # Cut off the non-magical version byte
  lsr( r1, r1, 8 ) # Put the magic back where it was
  #
  mov( r0, 0x4d ) # Constructing our own magic -> r0
  mov( r2, 0x75 )
  lsl( r2, r2, 8 )
  orr( r0, r2 )
  mov( r2, 0x1 )
  lsl( r2, r2, 16 )
  orr( r0, r2 )
  #
  cmp( r0, r1 ) # Magical comparison
  beq(__MAGICK)
  mov( r0, 0 ) # No magic :(
  b(__MAGEND)
  label(__MAGICK)
  mov( r0, 1 ) # Yes maggick :)))
  label(__MAGEND)

# Get the ROM version
@micropython.asm_thumb
def get_rom_ver() -> int:
  mov( r0, _ROM_VER ) # Location of the rom version
  ldrb( r0, [r0,0] ) # The rom version (byte)

@micropython.asm_thumb
def get_cr(r0) -> int:
  
  b(ENTRY)
  
  # Retrieve the address of something in the ROM Data Table [ref rp2040 datasheet p132]
  #  Input: r1 = Lookup code
  # Output: r0 = Memory address
  label(ROM_DATA_TABLE)
  push({lr})
  mov( r0, _ROM_DATA_TABLE_PTR ) # Location of pointer to the lookup table.
  ldrh( r0, [r0,0] ) # Pointer to the lookup table (halfword)
  mov( r2, _HELPER_FN_PTR ) # Location of pointer to the helper function.
  ldrh( r2, [r2,0] ) # Pointer to the helper function (halfword)
  # blx( r2 )
  data(2, _BLX | ( 2 <<3 ) ) # Helper function puts memory address into r0
  pop({pc})
  
  # Copyright notice
  # Output: r0 = Start byte of copyright notice
  #         r1 = Length of notice
  label(GET_CR)
  push({lr})
  mov( r1, 0x43 ) # 'C'
  mov( r2, 0x52 ) # 'R'
  lsl( r2, r2, 8 )
  orr( r1, r2 )
  bl(ROM_DATA_TABLE)
  mov( r1, r0 ) # String address => r1
  label(_CR_LOOP) # while True {
  ldrb( r2, [r1, 0] ) # c = mem[r1]
  cmp( r2, 0 ) # if c == 0:
  beq(_CR_END) #   break;
  add( r1, 1 ) # else: r1 ++
  b(_CR_LOOP)  # }
  label(_CR_END)
  sub( r1, r1, r0 ) # Convert and address to length => r1
  pop({pc})
  
  # Main Routine
  label(ENTRY)
  mov( r4, r0 ) # Keep the buffer address in r4
  
  # Copyright notice
  bl(GET_CR)
  
  # Bottom 4 registers into buffer
  str( r0, [ r4, 0 ] )
  str( r1, [ r4, 4 ] )
  #str( r2, [ r4, 8 ] )
  #str( r3, [ r4, 12 ] )
  
@micropython.asm_thumb
def tan_test(r0) -> int:
  
  b(ENTRY)
  
  # Retrieve the address of something in the ROM Data Table [ref rp2040 datasheet p132]
  #  Input: r1 = Lookup code
  # Output: r0 = Memory address
  label(ROM_DATA_TABLE)
  push({lr})
  mov( r0, _ROM_DATA_TABLE_PTR ) # Location of pointer to the lookup table.
  ldrh( r0, [r0,0] ) # Pointer to the lookup table (halfword)
  mov( r2, _HELPER_FN_PTR ) # Location of pointer to the helper function.
  ldrh( r2, [r2,0] ) # Pointer to the helper function (halfword)
  # blx( r2 )
  data(2, _BLX | ( 2 <<3 ) ) # Helper function puts memory address into r0
  pop({pc})
  
  # Get the Float Table location
  # Output: r0 = Pointer to float table
  label(GET_FLOAT_TABLE)
  push({lr})
  mov( r1, 0x53 ) # 'S'
  mov( r2, 0x46 ) # 'F'
  lsl( r2, r2, 8 )
  orr( r1, r2 ) # Float table lookup code => r1
  bl(ROM_DATA_TABLE) # Start address of SF table => r0
  pop({pc})
  
  
  # Main Routine
  label(ENTRY)
  mov( r4, r0 ) # Keep the buffer address in r4
  
  # Get the float table
  bl(GET_FLOAT_TABLE)
  mov( r7, r0 ) # Float table => r7
  
  # Run tan function
  ldr( r0, [ r4, 0 ] ) # buf[0] => r0
  ldr( r2, [ r7, _FTAN ] ) # Get tan function => r2
  # blx( r2 )
  data(2, _BLX | ( 2 <<3 ) ) # Run tan function
  str( r0, [ r4, 4 ] ) # Result => buf[1]

def tan( a:float ) -> float:
  buf = array('f',[a,0]) # Floats
  tan_test(buf)
  return buf[1]

# Obsolete, see data_test2() below for better method
@micropython.asm_thumb
def data_test() -> int:
  align(4)
  mov( r1, pc )
  b(AFTERDATA)
  data( 4, 0x12345678 )
  label(AFTERDATA)
  ldr( r0, [r1,0] )

@micropython.asm_thumb
def data_test2() -> int:
  align(4)
  data(4, 0xe0004800|( 0 <<8), 0x12345678 ) # Put 0x12345678 into r0
  # 0x4800 = LDR (literal) : Gets the data into a register [p248]
  # 0xe000 = B : Branch to PC + 0 [p205]

# Loads the address of the data array ( 0x12345678 , 0x1eadbeef, 0x789abcde ) into r0
@micropython.asm_thumb
def data_block() -> int:
  align(4)
  data(4,(0xe000a000|( 0 <<8)|(( 3  -1)<<17)), 0x12345678 , 0x1eadbeef, 0x789abcde ) # r0, 3, d0, d1, d2
  # Rd = Destination register for base address
  # n = array length: number of 32bit values defined
  # 0xa000 = ADR : Gets the address of the data into a register
  # 0xe000 = B : Unconditional branch to PC + imm11 [p205]

# Creates a small scratch pad in memory and puts the address into r0
@micropython.asm_thumb
def scratch32() -> int:
  align(4)
  data(4,(0xe000a000|( 0 <<8)|(( 4  -1)<<17)), 1,2,3,4 ) # r0, 3, d0, d1, d2, d3
  # Rd = Destination register for base address
  # n = array length: number of 32bit values in scratch space
  # 0xa000 = ADR : Gets the address of the data into a register
  # 0xe000 = B : Unconditional branch to PC + imm11 [p205]

# Test of storing data on the stack
# Should return r0 - r1
@micropython.asm_thumb
def stack_test(r0,r1):
  sub( sp, 8 )
  str( r0, [sp,-8] )
  str( r1, [sp,-4] )
  mov( r0, 0xff )   # dummy
  mov( r1, 0xaa )   # dummy
  add( r0, r0, r1 ) # dummy
  ldr( r0, [sp,-8] )
  ltr( r1, [sp,-4] )
  sub( r0, r0, r1 )
  add( sp, 8 )

@micropython.asm_thumb
def pixeltest(r0):
  mov( r1, r0 ) # Copy address => r1
  mov( r2, 3 )  # Sub-byte mask => r2
  and_( r1, r2 ) # Apply sub-byte mask => r1
  mov(r3,2)
  mul( r1, r3 ) # Get leftshift amount => r1
  mov(r0,r1)

@micropython.asm_thumb
def cmp_test(r0,r1) -> bool:
  mov( r9, r0 )
  mov( r11, r1 )
  data(2, _CMP | ( 9 &3) | (( 9 &8)<<4) | ( 11 <<3) ) # cmp( 9, 11 )
  bne(NOTEQUAL)
  mov( r0, 1 )
  b(END)
  label(NOTEQUAL)
  mov( r0, 0 )
  label(END)

@micropython.asm_thumb
def high_add(r0,r1) -> int:
  mov(r8,r1)
  data(2, _ADD | ( 0 &3) | (( 0 &8)<<4) | ( 8 <<3) ) # add( r0, r8 )

@micropython.asm_thumb
def _idiv( r0, r1 ) -> int:
  align(4)
  data(4, 0xe0004800|( 2 <<8), _SIO_BASE ) # Put _SIO_BASE into r2
  str( r0, [ r2, _SIO_DIV_SDIVIDEND ] )
  str( r1, [ r2, _SIO_DIV_SDIVISOR ] )
  nop() # 1
  nop() # 2
  nop() # 3
  nop() # 4
  nop() # 5
  nop() # 6
  nop() # 7
  nop() # 8
  #ldr( r1, [ r2, _SIO_DIV_REMAINDER ] )
  ldr( r0, [ r2, _SIO_DIV_QUOTIENT ] )
  
# For circular arcs, having a start and end point.
# Start and end should not be equal.
# Calculates which octants of the circle should be checked before drawing,
# (because they contain the start and/or end), which can just be drawn without checking,
# and which should not be drawn at all
@micropython.asm_thumb
def octant_test(r0,r1):
  
  #  Input: r0 = Start (as uint32, where 2^31 = 0x8000_0000 = 2.pi)
  #         r1 = End (as uint32, where 2^31 = 0x8000_0000 = 2.pi)
  # Output: r0, r1 : Unchanged
  #         r2 = Draw
  #         r3 = Check
  #push(r0-r1,r4-r7)
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
  mov( r0, r2 ) # Draw byte => r0
  # lsl( r3, r3, 8 )
  data(2, _LSL | 3 | ( 3 <<3 ) | ( 8 <<6 ) ) # Check byte << 8
  orr( r0, r3 )
  #pop(r0-r1,r4-r7)
  #
  #OUTPUT: r0 start, r1 end, r2 draw, r3 check

# 
def octant( start:float, end:float ):
  
  start = round( start * _MAX ) % _MAX
  end = round( end * _MAX ) % _MAX
  print(f'start: 0x{hex(start)}  end: 0x{hex(end)}')
  
  if start == end:
    raise ValueError()
  
  data = octant_test( start, end )
  
  # Draw, Check
  return data & 0xff, data >> 8

def int_to_radians( angle:int ) -> float:
  return (angle/_MAX) * _TAU
def angle_to_gradient( radians:float ) -> float:
  return tan( radians )
def get_y_limit( x:int, angle:float ) -> int:
  m:float = angle_to_gradient(angle)
  _m:int = round( m * (1<<22) ) # 0x0040_0000
  _y = x * _m
  y = _y >> 22
  return y

# Pre-calculate start and end gradients
# Store which oct (if any) the start and end affect
# For each checked pixel:
# if start and end both affect this oct: do special things
# if start OR end :
#  calculate y-limit
#  gt or lt based on start/end and half
#  => draw or pass

def get_mem_str_len( addr:int ):
  
  MAXLEN = 1024
  
  # Figure out the length
  strlen = -1
  b = -1
  while b != 0:
    strlen += 1
    b = machine.mem8[addr+strlen]
    #print(f'0x{c:2x} {chr(c)}')
    if strlen > MAXLEN:
      break
  
  return strlen
  
# Pull a null-terminated string out of RAM, starting at addr
def get_mem_string( addr:int, strlen:int=0 ):
  
  if not strlen:
    strlen = get_mem_str_len(addr)
  
  # Build the string
  bstr = bytearray(strlen)
  for i in range(strlen):
    bstr[i] = machine.mem8[addr+i]
  
  return bstr

def test_all_octants():
  for start in range(16):
    for end in range(16):
      if start == end:
        continue
      print(f'start: {start}  end: {end}')
      draw, check = octant( start/16, end/16 )
      print(f'Draw: {draw:08b}   Check: {check:08b}')
      print()

# Generate massive output of 240 valid start/end octant pairings, to test the algo
#test_all_octants()

# Test of CMP between high registers
#print( cmp_test( 1234, 1234 ) )

# Test of add from high register
#print( high_add(12,300) )

#print(hex(pixeltest(13)))

# Test of retrieval of a 32-bit inline integer
#print(hex(data_test2()))

print(stack_test( 100, 20 ))

# Test of retrieval of the address of an inline array of 32-bit values or scratch space
#addr = data_block()
#addr = scratch32()
#for i in range(4):
#  print( hex(machine.mem32[ addr + (i*4) ] ))

# Print copyright notice
buf = array('L',[0]*2) # Unsigned ints
get_cr(buf)
print( get_mem_string( *buf ))

# Tan test
print( tan(1.57) )

# Integer division test
print( _idiv( 100, 3 ) )

#pbuf = addressof(buf)

#print( ':',hex(test(buf)) )
#print(hex(test(buf)))


#print(chr(machine.mem8[buf[0]]))
#print([ hex(x) for x in buf ])

#print(get_mem_string(buf[0]))

#print('ROM version =',get_rom_ver())
#print('Magic =',chk_magic())