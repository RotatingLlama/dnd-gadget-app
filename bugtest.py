import micropython

# Unamry minus modifies variables in place
# https://github.com/micropython/micropython/issues/14397

@micropython.viper
def bug(y:int):
  print(y)
  startrow = int(max( 0, -y ))
  print(y)

@micropython.viper
def vip_unaryminus() -> int:
  a = 5
  b = -a
  print(a,b)

@micropython.viper
def ok() -> int:
  a = 5
  b = 0-a
  print(a,b)


# Memoryview slicing causes hang
# https://github.com/micropython/micropython/issues/6523
from micropython import const

@micropython.viper
def memoryviewbug():
  
  ba = bytearray(16)
  mv = memoryview(ba)
  
  a = const(0)
  b = const(15)
  c:int = 0
  d:int = 15
  
  print('still ok here')
  #return
  
  # slc = mv[:15] # Crashes
  #slc = mv[a:b] # Also crashes
  slc = mv[c:d] # Also crashes
  
  print('never reached')

@micropython.viper
def memoryviewbug_ok():
  
  ba = bytearray(16)
  mv = memoryview(ba)
  
  slc = mv[const(0):const(-1)] 
  
  print('works')
