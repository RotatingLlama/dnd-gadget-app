# Scan a Micropython .py file for a (singular) inline assembly function
# Extract that function and save as a .s file, for actual assembly
#
# T. Lloyd
# 18 May 2026

# TODO:
# Match function signature
# assemble.py overwrites our input python file with its new one
# Alert when we encounter data() statements on the input
# Deal with embedded constants (somehow)
# Deal with multiple separate assembly functions in one file
# Investigate whether ".balign 2" would work in the .s file
# Suppport MP align() statement

import sys
from pathlib import Path
import re

# We see this, we've hit the thing we're interested in
KEY = '@micropython.asm_thumb'

OP_INDENT = 16
OP_PAD = 8
#ARG_INDENT = 20

# Define regular expressions to help with converting py-assembly into real assembly
re_label = re.compile(r'label\((.+)\)')
re_comment = re.compile(r'([^#]*)#?(.*)') # Always returns two strings, split by the first '#' (if any)
re_op_args = re.compile( r'(.+)\((.*)\)' ) # If match, always returns 2 strings.
re_num = re.compile(r'^(0x[0-9a-f]+|[0-9]+)$')
re_brac = re.compile(r'(.*)\[(.*)\]')

# Convenience function for when things go wrong
def err(msg:str):
  print(msg)
  sys.exit()

# Process a line
#have_label = False
def process_line( line:str ) -> str:
  #global have_label
  
  # Extract comments
  #comment = None
  cg = re_comment.match(line).groups()
  line = cg[0]
  comment = cg[1]
  if comment:
    comment = f'@{comment}\n'
  #  cmt = cmt.groups()
  #  line = cmt[0]
  #  if len(cmt) > 1:
  #    comment = cmt[1]
  
  # Treat labels differently
  lb = re_label.match(line)
  if lb:
    #label = lb.group(1) + ':'
    #have_label = True
    return f'{lb.group(1)}:{comment}'
    #label.ljust(OP_INDENT)
  
  # Indent compensation for labels
  '''
  if have_label:
    out = ''
  else:
    out = ' '*OP_INDENT
  have_label = False
  '''
  
  # Get the op and args
  op = None
  args = None
  oam = re_op_args.match(line)
  if oam:
    oag = oam.groups()
    op = oag[0]
    args = oag[1]
  
  # If there's no op here, deal with any comment and stop
  if not op:
    if comment:
      return comment.ljust(OP_INDENT)
    else:
      return '\n'
  
  # We now definitely have an op
  
  # Correct this Micropython-ism
  if op == 'and_':
    op = 'and'
  
  # Add the op to the line
  out = op.ljust(OP_PAD)
  
  # If there's no args here, deal with any comment and stop
  if not args:
    if comment:
      out += comment.ljust(OP_INDENT)
    else:
      out += '\n'
    return out
  
  # We now definitely have arg(s)
  
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
    args = f'{a[0]} [{a[1]}]'
  else:
    args = a[0]
    
  out += args.ljust(16)
  
  return f'{out}{comment}\n'

# Sanity
if len( sys.argv ) == 0:
  err('No args')

# Input file
pyasm_file = Path(sys.argv[1])

# Sanity
if not pyasm_file.is_file():
  err('Not a file')

# Useful bits of the input filename
dir = pyasm_file.parent
stem = pyasm_file.stem

# Output file
s_file = dir / f'{stem}.s'

# Tracking variables used during the loop
in_asm_fn = 0
outer_indent = None
asm_indent = None
#fn_name = None

# Main loop
with open( pyasm_file, 'r' ) as py_fd, open( s_file, 'w' ) as s_fd:
  
  # Write the boilerplate at the top of the .s file
  s_fd.write('.section .text,"ax"\n')
  s_fd.write(' '*OP_INDENT + '.balign 4\n')
  s_fd.write('\n')
  s_fd.write('main:\n')
  
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
      if ln[indent:indent+3] == 'def':
        in_asm_fn = 2
        # TODO: GET fn_name HDERE
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
        continue
      
      # Convert the line and write it to the .s file
      s_fd.write( process_line( ln[indent:].strip() ) )
  
  # Finish up the .s file
  s_fd.write('\n\n.end\n')
