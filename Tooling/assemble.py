# Take a .s file, assemble it and then convert it into a MicroPython inline assembly function
#
# T. Lloyd
# 29 May 2026
#
# USAGE:
# py assembly.py foo.s           -> Compiled .py to stdout
# py assemble.py foo.s -o bar.py -> Outputs bar.py
#
# If a .ident directive containing a Python function signature is placed near
# the top of the .s file, that function signature will be used in the output.
# Eg:
# .ident "my_func( r0, r1 ) -> int"

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

# Parse the input args. Return input and output file Paths
def parse_args( argv:list ) -> tuple[Path|None,Path|None]:
  
  # Only input file given, or input file and one other arg
  if len(argv) in (2,3):
    return ( Path(argv[1]), None )
  
  # Enough args to maybe be an output file too
  if len(argv) >= 4:
    if argv[2] == '-o':
      return ( Path(argv[1]), Path(argv[3]) )
  
  # Default
  return (None,None)

# Returns the contents of the first .ident directive found, or else None
def get_ident( s_file:str ) -> str|None:
  with open( s_file, 'r' ) as fd:
    while True:
      line = fd.readline()
      if not line:
        return None
      fsig = re_fsig.match(line)
      if fsig:
        return fsig.group(1)

# Main
def assemble( s_file:Path, out_file:Path|None ) -> None:
  
  # Sanity
  if not s_file.is_file():
    err('Not a file')
  
  # Get the function signature (if any)
  f_sig = get_ident(str( s_file ))
      
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
  
  if out_file:
    fd_py = open( out_file, 'w' )
    write = fd_py.write
  else:
    write = lambda x : print(x,end='')
  
  # Main loop
  with open( bin_file.name, 'rb' ) as fd_bin: # type: ignore
    
    # Write the top of the output .py file
    write(f'# Source file: {s_file.name}\n')
    write(PY_HEADER)
    if f_sig:
      write(f'def {f_sig}:\n')
    else:
      write(f'def _{s_file.stem}():\n')
    
    # Counter for how many opcodes we've packed
    i = 0
    
    # Keep reading opcodes until there are no more
    while True:
      op = fd_bin.read(2)
      if len(op) == 0:
        if i > 0:
          write(')\n')
        break
      
      # Get the opcode
      op = int.from_bytes( op, byteorder='little', signed=False )
      
      # Start of line
      if i == 0:
        write(f'  data(2')
        
      # Format the opcode to hex
      write(f',0x{op:04x}')
      i += 1
      
      # End of line
      if i == PACK:
        write(')\n')
        i = 0
  
  # Clean up temp files
  unlink(elf_file.name) # type: ignore
  unlink(bin_file.name) # type: ignore
  
  #
  if out_file:
    fd_py.close()
    print(f'Saved to {out_file}')

if __name__ == '__main__':
  
  # Get the filenames from the args
  input, output = parse_args( sys.argv )
  
  # Sanity
  if not input:
    err('No args')
  
  # Go
  assemble( input, output ) # pyright: ignore[reportArgumentType]
