from gadget_hw import defs_rev1 as DEFS
from machine import Pin, ADC
from micropython import alloc_emergency_exception_buf
alloc_emergency_exception_buf(100) 

# Define the switch and the button
s = DEFS.SW1
b = DEFS.ROT_BTN

# Determine whether we're on battery or USB
# ADC under-reports voltage immediately after poweron by a factor of ~0.64
# Divide its value by 4236.6 to get ballpark voltage value
# On a warm start, the above calculation will give a gross overestimate
#boot_vsys = ADC(DEFS.VSYS).read_u16()
on_usb = ( ADC(DEFS.VSYS).read_u16() > 0x4a80 ) # 19072 # Sets USB threshold just over 4.5v (2.9v for warm starts)

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

def run_app():
  print('> RUNNING APP...')
  from gadget_app import Gadget
  g = Gadget()
  g.run()

def clear_eink():
  print('> CLEARING EINK...')
  from gadget_hw import HW
  hw = HW()
  hw.clear_eink()

def noop():
  print('> Doing nothing.')

print('Plugged in:',on_usb)
print('     Input:', ['None','Switch','Button','Switch+Btn'][action] )

# Are we connected to a PC?
if on_usb:
  
  # Nothing pressed: do nothing
  if action == 0:
    noop()
  
  # Only start if the back button is pressed
  if action == 1:
    run_app()
  
  # Button pressed: Clear eink only
  if action == 2:
    clear_eink()
  
  # Both pressed: also nothing
  if action == 3:
    noop()
  
else: # Battery power
  
  # No controls being pressed
  # Probably been turned on for play.  Start app.
  if action == 0:
    run_app()
  
  if action == 1: # Back button
    noop()
  
  # Button pressed: Clear eink only
  if action == 2:
    clear_eink()
  
  # Both pressed: also nothing
  if action == 3:
    noop()
