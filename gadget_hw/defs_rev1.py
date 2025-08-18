from micropython import const
from machine import Pin

# Pin assignments for hardware rev 1
# UART_TX = Pin(0) # These are handled in boot.py
# UART_RX = Pin(1) # No need to declare them again here
CS_SD1  = Pin(2)
SD1_DET = Pin(3)
NEEDLE  = Pin(4)
ROT_B   = Pin(5)
ROT_BTN = Pin(6)
ROT_A   = Pin(7)
SW1     = Pin(8)
EINK_DC = Pin(9)
CS_EINK = Pin(10)
CS_SRAM = Pin(11)
CS_SD2  = Pin(12)
CS_MTX  = Pin(13)
I2C_SDA = Pin(14)
I2C_SCL = Pin(15)
MISO    = Pin(16)
# pin 17 is PLUGGED in rev 1a
SPI_CLK = Pin(18)
MOSI    = Pin(19)
# pin 20 is CHARGING in rev 1a
EINK_BUSY = Pin(21)
EINK_RST = Pin(22)
# pin 26 is Vchg in rev 1a
VSYS =     Pin(29)

# Comms instance IDs for Rev 1
# This is a function of the pin allocations, ref datasheet
I2C_ID = const(1)
SPI_ID = const(0)
UART_ID = const(0)

# Bus speeds
I2C_FREQ = const( 100000) # 100 kHz
SPI_FREQ = const(4000000) # 4 MHz
