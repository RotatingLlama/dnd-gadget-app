from gadget_hw import defs_rev1 as DEFS
from machine import Pin
from micropython import alloc_emergency_exception_buf
alloc_emergency_exception_buf(100) 

# Define the switch and the button
s = DEFS.SW1
b = DEFS.ROT_BTN

# Set them up as inputs
s.init( Pin.IN, Pin.PULL_UP )
b.init( Pin.IN, Pin.PULL_UP )

# Calculate a value based on which ones are pressed
# 0 : None pressed
# 1 : Switch pressed
# 2 : Button pressed
# 3 : Both pressed
action = s.value() | ( b.value() << 1 )

del s, b, DEFS

### EVENTUAL PLAN ###
# 0 : Launch app to character select
# 1 : Launch app to last character
# 2 : Do nothing?
# 3 : secret function?


# Nothing pressed: launch app
if action == 0:
  print('> RUNNING APP...')
  from gadget_app import Gadget
  g = Gadget()
  g.run()

# Switch pressed:  Do nothing

# Button pressed: Clear eink only
if action == 2:
  print('> CLEARING EINK...')
  from gadget_hw import HW
  hw = HW()
  hw.clear_eink()

# Both pressed: also nothing
if action == 3:
  pass
