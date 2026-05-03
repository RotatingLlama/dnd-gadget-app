#import micropython
#from micropython import const
from array import array
#import math
#from uctypes import addressof
import machine

# RP2040 datasheet
# https://pip-assets.raspberrypi.com/categories/814-rp2040/documents/RP-008371-DS-1-rp2040-datasheet.pdf

# Memory Locations (absolute)
_ROM_VER = const(0x13)
_ROM_DATA_TABLE_PTR = const(0x16)
_HELPER_FN_PTR = const(0x18)

# Functions
_FTAN = const(0x44)

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
  data(2, 0x4780 | 2 <<3) # BLX(r2) # Helper function puts memory address into r0
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
  data(2, 0x4780 | 2 <<3) # BLX(r2) # Helper function puts memory address into r0
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
  data(2, 0x4780 | 2 <<3) # BLX(r2) # Run tan function
  str( r0, [ r4, 4 ] ) # Result => buf[1]

@micropython.asm_thumb
def data_test() -> int:
  mov( r1, pc )
  ldrh( r0, [r1,0x02] )
  b(AFTERDATA)
  data( 2, 0x1234 )
  label(AFTERDATA)

@micropython.asm_thumb
def pixeltest(r0):
  mov( r1, r0 ) # Copy address => r1
  mov( r2, 3 )  # Sub-byte mask => r2
  and_( r1, r2 ) # Apply sub-byte mask => r1
  mov(r3,2)
  mul( r1, r3 ) # Get leftshift amount => r1
  mov(r0,r1)

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

print(hex(pixeltest(13)))
#addr = data_test()
#for i in range(8):
#  print( hex(machine.mem16[ addr + (i*16) ] ))

# Print copyright notice
buf = array('L',[0]*2) # Unsigned ints
get_cr(buf)
print( get_mem_string( *buf ))

# Tan test
buf = array('f',[0]*2) # Floats
buf[0] = 1.57 # Input
tan_test(buf)
print(buf)

#pbuf = addressof(buf)

#print( ':',hex(test(buf)) )
#print(hex(test(buf)))


#print(chr(machine.mem8[buf[0]]))
#print([ hex(x) for x in buf ])

#print(get_mem_string(buf[0]))

#print('ROM version =',get_rom_ver())
#print('Magic =',chk_magic())