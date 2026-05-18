# Take a .s file, assemble it and then convert it into a MicroPython inline assembly function
#
# T. Lloyd
# 18 May 2026

# TODO:
# The output file name is the same as the input filename of pyasm2s.py, so this script's output clobbers the original input

import sys
import subprocess
from pathlib import Path

# Where to find, and how to call, the assembler executable
AS = r'C:\Program Files (x86)\Arm\GNU Toolchain mingw-w64-i686-arm-none-eabi\arm-none-eabi\bin\as.exe'
AS_FLAGS = ( '-mcpu=cortex-m0plus', '-k', '-mthumb', '-EL' ) # -o test.elf test.s

# Same, objcopy exe.  We need this to strip all the ELF stuff that GAS puts into its output
OBJCOPY = r'C:\Program Files (x86)\Arm\GNU Toolchain mingw-w64-i686-arm-none-eabi\arm-none-eabi\bin\objcopy.exe'
OPJCOPY_FLAGS = ( '-O', 'binary' ) # test.elf test.bin

# What we put at the head of our output file
PY_HEADER = '@micropython.asm_thumb\n'

# Convenience function for when things go wrong
def err(msg:str):
  print(msg)
  sys.exit()

# Sanity
if len( sys.argv ) == 0:
  err('No args')

# Input file
s_file = Path(sys.argv[1])

# Sanity
if not s_file.is_file():
  err('Not a file')

# Useful bits of the input filename
dir = s_file.parent
stem = s_file.stem

# Run the assembler exe
as_output = subprocess.run(( AS, *AS_FLAGS, '-o', f'{stem}.elf', s_file.name ))
if as_output.returncode != 0:
  err('assembler failed')

# Run the objcopy exe
objcopy_output = subprocess.run(( OBJCOPY, *OPJCOPY_FLAGS, f'{stem}.elf', f'{stem}.bin' ))
if objcopy_output.returncode != 0:
  err('objcopy failed')

# Main loop
with open( f'{stem}.bin', 'rb' ) as fd_bin, open( f'{stem}.py', 'w' ) as fd_py:
  
  # Write the top of the output .py file
  fd_py.write(PY_HEADER)
  fd_py.write(f'def _{stem}():\n')
  
   # Keep reading opcodes until there are no more
  while True:
    op = fd_bin.read(2)
    if len(op) == 0:
      break
    
    # Get the opcode
    op = int.from_bytes(op, byteorder='little',signed=False)
    
    # Format the opcode and wrap it in data() for MicroPython
    fd_py.write(f'  data(2,0x{op:04x})\n')
