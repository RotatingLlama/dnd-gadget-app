# Take a .s file, assemble it and then convert it into a MicroPython inline assembly function
#
# T. Lloyd
# 24 May 2026

import sys
import subprocess
import tempfile
from os import unlink
import re
from pathlib import Path

# How many instructions to pack into each data() statement
PACK = 8

# Where to find, and how to call, the assembler executable
AS = r'C:\Program Files (x86)\Arm\GNU Toolchain mingw-w64-i686-arm-none-eabi\arm-none-eabi\bin\as.exe'
AS_FLAGS = ( '-mcpu=cortex-m0plus', '-k', '-mthumb', '-EL' ) # -o test.elf test.s

# Same, objcopy exe.  We need this to strip all the ELF stuff that GAS puts into its output
OBJCOPY = r'C:\Program Files (x86)\Arm\GNU Toolchain mingw-w64-i686-arm-none-eabi\arm-none-eabi\bin\objcopy.exe'
OPJCOPY_FLAGS = ( '-O', 'binary' ) # test.elf test.bin

# What we put at the head of our output file
PY_HEADER = '@micropython.asm_thumb\n'

# Regex for function signature
re_fsig = re.compile(r'.ident +"(.*)"')

# Convenience function for when things go wrong
def err(msg:str):
  print(msg)
  sys.exit()

def assemble( s_file:Path ) -> None:
  
  # Sanity
  if not s_file.is_file():
    err('Not a file')

  # Useful bits of the input filename
  dir = s_file.parent
  stem = s_file.stem

  # Get the function signature, if present
  with open( s_file, 'r' ) as fd:
    line = fd.readline()
    fsig = re_fsig.match(line)
    if fsig:
      f_sig = fsig.group(1)
    else:
      f_sig = None
      
  # Set up intermediate files
  elf_file = tempfile.NamedTemporaryFile( delete=False, delete_on_close=False )
  bin_file = tempfile.NamedTemporaryFile( delete=False, delete_on_close=False )
  elf_file.close()
  bin_file.close()

  # Run the assembler exe
  as_output = subprocess.run(( AS, *AS_FLAGS, '-o', elf_file.name, s_file.name ))
  if as_output.returncode != 0:
    err('assembler failed')

  # Run the objcopy exe
  objcopy_output = subprocess.run( ( OBJCOPY, *OPJCOPY_FLAGS, elf_file.name, bin_file.name ) )
  if objcopy_output.returncode != 0:
    err('objcopy failed')

  # Main loop
  out_file = f'{stem}.py'
  with open( bin_file.name, 'rb' ) as fd_bin, open( out_file, 'w' ) as fd_py:
    
    # Write the top of the output .py file
    fd_py.write(PY_HEADER)
    if f_sig:
      fd_py.write(f'def {f_sig}:\n')
    else:
      fd_py.write(f'def _{stem}():\n')
    
    # Counter for how many opcodes we've packed
    i = 0
    
    # Keep reading opcodes until there are no more
    while True:
      op = fd_bin.read(2)
      if len(op) == 0:
        if i > 0:
          fd_py.write(')\n')
        break
      
      # Get the opcode
      op = int.from_bytes( op, byteorder='little', signed=False )
      
      # Start of line
      if i == 0:
        fd_py.write(f'  data(2')
        
      # Format the opcode to hex
      fd_py.write(f',0x{op:04x}')
      i += 1
      
      # End of line
      if i == PACK:
        fd_py.write(')\n')
        i = 0
        

  # Clean up temp files
  unlink(elf_file.name)
  unlink(bin_file.name)

  print(f'Saved to {out_file}')

if __name__ == '__main__':
  
  # Sanity
  if len( sys.argv ) <= 1:
    err('No args')

  # Input file
  assemble( Path(sys.argv[1]) )
