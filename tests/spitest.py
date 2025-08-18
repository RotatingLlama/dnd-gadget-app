from machine import SPI, Pin
from sram import SRAM

spi = SPI(0, sck=Pin(2), mosi=Pin(3), miso=Pin(4), baudrate=400000, polarity=0, phase=0) # 400 kHz
SRCS = Pin(19,mode=Pin.OUT,value=1)
ECS = Pin(20,mode=Pin.OUT,value=1)
DC = Pin(21,mode=Pin.OUT,value=1)

sram = SRAM(spi,SRCS)
sram.set_mode(0)

#sram.write_byte(13,255)
print( sram.read_byte(13) )
