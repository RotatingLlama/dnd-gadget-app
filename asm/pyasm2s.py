# Scan a Micropython .py file for a (singular) inline assembly function
# Extract that function and save as a .s file, for actual assembly
#
# T. Lloyd
# 20 May 2026

# TODO:
# Deal with embedded constants
# - Detect const(), transform into .set
# - Treat text in args as immediate, if match const add #
# Multiple functions in one .py file is implemented, but not tested
# align() directive is implemented, but not tested
#
# Match function signature - WONTFIX, can't carry through .s

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
re_num = re.compile(r'^(0x[0-9a-f]+|[0-9]+)$')
re_brac = re.compile(r'(.*)\[(.*)\]')
re_pyfn = re.compile(r'def ([a-zA-Z0-9_]+) *\(') # If match, returns function name

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
def process_line( line:str ) -> str:
  
  # Extract comments
  cg = re_comment.match(line).groups()
  line = cg[0]
  comment = cg[1]
  if comment:
    comment = f'@{comment}'
  
  # Indent most lines
  out = ' '*OP_INDENT
  
  # Get the op and args
  op = None
  args = None
  oam = re_op_args.match(line)
  if oam:
    oag = oam.groups()
    op = oag[0]
    args = oag[1]
  #print(op,'::',args)
  
  # If there's no op here, deal with any comment and stop
  if not (op and args):
    return out + comment + '\n'
  
  # We now definitely have an op
  
  # Labels
  if op == 'label':
    if comment:
      return f'{args}: {comment}\n'
    else:
      return f'{args}:\n'
  
  # Alignment
  if op == 'align':
    out += f'.balign {args}'
    if comment:
      out += f' {comment}'
    out += '\n'
    return out
  
  # Data
  if op == 'data':
    ba = process_data(args)
    if ba is None:
      return '.err @ Invalid data object in MP file\n'
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
  
  a = ['','']
  
  # Do we have secondary brackets?
  ab = re_brac.match(args)
  if ab:
    abg = ab.groups()
    a[0] = abg[0].strip()
    a[1] = abg[1].strip()
  else:
    a[0] = args
  
  for i in range(2):
    aaa = a[i].split(',')
    for j in range(len(aaa)):
      aaa[j] = aaa[j].strip()
      #if aaa[j] == '':
      #  continue
      nm = re_num.match(aaa[j])
      if nm:
        aaa[j] = f'#{aaa[j]}'
    a[i] = ', '.join(aaa)
  #
  if a[1]:
    args = f'{a[0]}[ {a[1]} ]'
  else:
    args = a[0]
  
  if comment:
    out += f'{args:15s} {comment}\n'
  else:
    out += args + '\n'
  return out

# Turn a function name into an output filename
def fn2filename( pyfile:str, fn:str ) -> str:
  return f'{pyfile}-{fn}.s'

# Handles everything related to the output file(s)
class SFile:
  def __init__(self, filename:str ):
    self.path = filename
    self._fd = open( self.path, 'w' )
    
    self.write = self._fd.write
    
    # Write the boilerplate at the top of the .s file
    self.write('.section .text,"ax"\n')
    self.write('\n')
    self.write('main:\n')
  
  def close(self):
    self.write('\n.end\n')
    self._fd.close()
  
  def __del__(self):
    self._fd.close()

# Sanity
if len( sys.argv ) <= 1:
  err('No args')

# Input file
pyasm_file = Path(sys.argv[1])

# Sanity
if not pyasm_file.is_file():
  err('Not a file')

# Tracking variables used during the loop
in_asm_fn = 0
outer_indent = None
asm_indent = None
s_file = None

# Main loop
with open( pyasm_file, 'r' ) as py_fd:
  
  # Keep reading input lines until there are no more
  while True:
    ln = py_fd.readline()
    if len(ln) == 0:
      break
  
    # Detect the current indent level
    indent = 0
    for c in ln:
      if c == ' ':
        indent += 1
      else:
        break
      
    # We've found the start of an assembly function
    if in_asm_fn == 0:
      if ln[indent:].strip() == KEY:
        in_asm_fn = 1
        outer_indent = indent
        continue
    
    # Next line should be the function signature
    if in_asm_fn == 1:
      fnm = re_pyfn.match(ln[indent:])
      if not fnm:
        in_asm_fn = 0
        continue
      s_file = SFile( fn2filename( pyasm_file.name, fnm.group(1) ) )
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
        s_file.close()
        print(f'Saved file {s_file.path}')
        s_file = None
        continue
      
      # Convert the line and write it to the .s file
      s_file.write( process_line( ln[indent:].strip() ) )
