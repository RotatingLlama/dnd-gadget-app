import tkinter as tk
from tkinter.filedialog import askopenfilename 
from pathlib import Path
import libpi

# Our file format extension
EXT = '.pi'

# We don't want a full GUI, so keep the root window from appearing
tk.Tk().withdraw()

# Get the image file to convert
path = Path( askopenfilename() )

pal = (
  (255,255,255), # 0 = White
  (  0,  0,  0), # 1 = Black
  (255,  0,  0), # 2 = Red
  (255,  0,255), # 3 = Magenta
)

# What to do?
if path.suffix == EXT:
  out = libpi.decode( path, pal )
else:
  out = libpi.encode( path, pal )

if out is not None:
  print('Saved to:',out)
