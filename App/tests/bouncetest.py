from machine import Pin
from time import ticks_us, ticks_diff
import asyncio
from array import array

# Seeing maybe 25ms total bounce time on the switch

count = 0

#last = ticks_us()
ptr = 0
n=10
last = array('L',[0]*n)
i=0
diff=0
def ihf(pin):
  global ptr, last, count
  last[ptr] = ticks_us()
  print(str(pin)[:9], end='' )
  i = (ptr+1)%n
  while i != ptr:
    diff = ticks_diff( last[ptr], last[i] )//1000
    if diff < 0 or diff > 1000:
      diff=0
    print( ' {:3d}'.format( diff ), end='' )
    i = (i+1)%n
  ptr = (ptr+1)%n
  count +=1
  print(' :',count)

ac=0
def ihf_a(pin):
  global ac
  ac+=1
  print('_',ac)

bc=0
def ihf_b(pin):
  global bc
  bc+=1
  print('^',bc)

btn = Pin(5, Pin.IN, Pin.PULL_UP)
btn.irq( handler=ihf, trigger=Pin.IRQ_RISING)

sw = Pin(17, Pin.IN, Pin.PULL_UP)
sw.irq( handler=ihf, trigger=Pin.IRQ_RISING)

a = Pin(6, Pin.IN, Pin.PULL_UP)
a.irq( handler=ihf_a, trigger=Pin.IRQ_RISING)

b = Pin(7, Pin.IN, Pin.PULL_UP)
b.irq( handler=ihf_b, trigger=Pin.IRQ_RISING)


async def blink(led, period_ms):
    while True:
        led.on()
        await asyncio.sleep_ms(5)
        led.off()
        await asyncio.sleep_ms(period_ms)

async def wait():
  while True:
    await asyncio.sleep(1)
  
async def main(led1, led2):
    asyncio.create_task(blink(led1, 700))
    asyncio.create_task(blink(led2, 400))
    await asyncio.sleep_ms(10_000)

# Running on a generic board
asyncio.run( wait() )

# 18869 25140 25233 25352 