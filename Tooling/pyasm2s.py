# Scan a Micropython .py file for a (singular) inline assembly function
# Extract that function and save as a .s file, for actual assembly
#
# T. Lloyd
# 29 May 2026

# TODO:
# align() directive is not tested
# Check for gaps in coverage of MP asm_thumb statements
# BUG: Blank comment line (just a #) turns into blank line (no corresponding @)

import sys
from pathlib import Path
import re

# We see this, we've hit the thing we're interested in
KEY = '@micropython.asm_thumb'

OP_INDENT = 2
OP_PAD = 8

# Define regular expressions to help with converting py-assembly into real assembly
re_comment = re.compile(r'([^#]*)#?(.*)') # Always returns two strings, split by the first '#' (if any)
re_op_args = re.compile( r'([^\(]+)\((.*)\)' ) # If match, always returns 2 strings.
re_num = re.compile(r'^(0x[a-fA-F0-9_]+|0b[01_]+|[0-9_]+)$')
re_brac = re.compile(r'(.*)\[(.*)\]')
re_pyfn = re.compile(r'def *(([a-zA-Z0-9_]+) *\((.*)\) *(-> *([a-z\,\[\]]+))?):') # If match, returns: signature, name, argstring, (ignore), return_type
re_const = re.compile(r'([_A-Z0-9]+) *= *const\( *(0x[a-fA-F0-9_]+|0b[01_\]+|[0-9_]+) *\)') # If match, returns constant name and value

# Convenience function for when things go wrong
def err(msg:str):
  print(msg)
  sys.exit()

# Process the MicroPython data() instruction into bytes
def process_data( arg:str ) -> bytearray|None:
  args = arg.split(',')
  try:
    size = int( args[0].strip() )
  except ValueError:
    return None
  ba = bytearray()
  for i in range( 1, len(args) ):
    try:
      a = int( args[i].strip(), 0 )
    except ValueError:
      return None
    for _ in range(size):
      ba.append( a & 0xff )
      a >>= 8
  return ba

# Process a line
def process_line( line:str, consts:dict[str,str]={} ) -> str:
  
  # Extract comments
  cg = re_comment.match(line).groups() # type: ignore
  line = cg[0]
  comment = cg[1]
  if comment:
    comment = f'@{comment}'
  
  # Indent most lines
  out = ' '*OP_INDENT
  
  # Get the op and args
  op = None
  argstring = None
  oam = re_op_args.match(line)
  if oam:
    oag = oam.groups()
    op = oag[0]
    argstring = oag[1]
  
  # If there's no op here, deal with any comment and stop
  if not (op and argstring):
    return out + comment + '\n'
  
  # We now definitely have an op
  
  # Labels
  if op == 'label':
    if comment:
      return f'{argstring}: {comment}\n'
    else:
      return f'{argstring}:\n'
  
  # Alignment
  if op == 'align':
    out += f'.balign {argstring}'
    if comment:
      out += f' {comment}'
    out += '\n'
    return out
  
  # Data
  if op == 'data':
    ba = process_data(argstring)
    if ba is None:
      return f'.err @ {line} {comment}\n'
    bytelist = []
    for b in ba:
      bytelist.append( f'0x{b:02x}' )
    out += '.byte'.ljust(OP_PAD)
    out += ', '.join(bytelist)
    if comment:
      out += f' {comment}'
    out += '\n'
    return out
    
  # Correct this Micropython-ism
  if op == 'and_':
    op = 'and'
  
  # If we're here, we have a regular op
  
  # Add the op to the line
  out += op.ljust(OP_PAD)
  
  argsets = ['','']
  
  # Do we have secondary brackets?
  brac = re_brac.match(argstring)
  if brac:
    argsets[0] = brac.group(1).strip()
    argsets[1] = brac.group(2).strip()
  else:
    argsets[0] = argstring
  
  for i in range(2):
    args = argsets[i].split(',')
    for j in range(len(args)):
      args[j] = args[j].strip()
      num = re_num.match(args[j])
      if num:
        args[j] = f'#{args[j]}'
        continue
      if args[j] in consts:
        args[j] = f'#{args[j]}'
    argsets[i] = ', '.join(args)
  #
  if argsets[1]:
    argstring = f'{argsets[0]}[ {argsets[1]} ]'
  else:
    argstring = argsets[0]
  
  if comment:
    out += f'{argstring:15s} {comment}\n'
  else:
    out += argstring + '\n'
  return out

# Turn a function name into an output filename
def fn2filename( pyfile:str, fn:str ) -> str:
  return f'{pyfile}-{fn}.s'

# Handles everything related to the output file(s)
class SFile:
  def __init__(self, filename:str, consts:dict[str,str], f_sig:str='' ):
    self.path = filename
    self._fd = open( self.path, 'w' )
    
    self.write = self._fd.write
    
    # Write the boilerplate at the top of the .s file
    if f_sig:
      self.write(f'.ident "{f_sig}"\n')
    self.write('.section .text,"ax"\n')
    self.write('.global _start\n')
    for c in consts:
      self.write(f'.set {c}, {consts[c]}\n')
    self.write('\n')
    self.write('_start:\n')
  
  def close(self):
    self.write('\n.end\n')
    self._fd.close()
    print(f'Saved file {self.path}')
  
  def __del__(self):
    self._fd.close()

def process_py_file( pyasm_file:Path ) -> None:

  # Sanity
  if not pyasm_file.is_file():
    err('Not a file')
  
  # Tracking variables used during the loop
  in_asm_fn = 0
  #outer_indent = None
  asm_indent = None
  s_file = None
  consts = {}

  # Main loop
  with open( pyasm_file, 'r' ) as py_fd:
    
    # Keep reading input lines until there are no more
    while True:
      ln = py_fd.readline()
      if len(ln) == 0:
        
        # If we're still in a asm function
        if in_asm_fn == 3:
          s_file.close() # type: ignore
        
        break
    
      # Detect the current indent level
      indent = 0
      for c in ln:
        if c == ' ':
          indent += 1
        else:
          break
      
      # We're not currently in an assembly function
      if in_asm_fn == 0:
        
        # But we've found the start of an assembly function
        if ln[indent:].strip() == KEY:
          in_asm_fn = 1
          outer_indent = indent
          continue
        
        # We've found a constant definition
        cr = re_const.match(ln[indent:])
        if cr:
          consts.update({ cr.group(1) : cr.group(2) })
          continue
      
      # Next line should be the function signature
      if in_asm_fn == 1:
        fnm = re_pyfn.match(ln[indent:]) # signature, name, argstring, (ignore), return_type
        if not fnm:
          in_asm_fn = 0
          continue
        s_file = SFile( filename=fn2filename( pyasm_file.name, fnm.group(2) ), consts=consts, f_sig=fnm.group(1) )
        in_asm_fn = 2
        continue
      
      # We're at the start of the asm
      if in_asm_fn == 2:
        asm_indent = indent
        in_asm_fn = 3
      
      # We're in the asm
      if in_asm_fn == 3:
        
        # If the indent has changed, we're no longer in the asm
        if indent != asm_indent:
          in_asm_fn = 0
          s_file.close() # type: ignore
          s_file = None
          continue
        
        # Convert the line and write it to the .s file
        s_file.write( process_line( ln[indent:].strip(), consts ) ) # type: ignore

if __name__ == '__main__':
  
  # Sanity
  if len( sys.argv ) <= 1:
    err('No args')
  
  process_py_file( Path(sys.argv[1]) )
