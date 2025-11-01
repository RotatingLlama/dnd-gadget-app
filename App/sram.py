# sram.py
# 
# For 23K256-I/SN SRAM chip
# https://www.mouser.co.uk/datasheet/2/268/23A256_23K256_256_Kbit_SPI_Bus_Low_Power_Serial_SR-3442970.pdf
# As found on Adafruit Feather Friend
#
# Modes:
# 0 Per byte
# 1 Per page (not implemented)
# 2 Sequential (not implemented)
#
# Hold:
# Enable or disable function of the Hold pin
#
# Jan 2025

# Reads/writes are always 8-bit instruction, 16-bit address, then data (however much, in whichever direction)
# SR is always 8-bit instruction, followed by 8-bit register

from struct import pack, unpack
from time import sleep_ms

class SRAM:
  
  def __init__(self,spi,cs):
    
    # SPI object and CS pin
    self.spi = spi
    self.cs = cs
    
    # Commands for SRAM chip
    self._READ = 3
    self._WRITE = 2
    self._RDSR = 5
    self._WRSR = 1
    
    # Set CS high (disable)
    self.cs(1)
    sleep_ms(1)
    
    # Status register
    self.sr = {
      'mode' : 0,
      'hold' : True
    }
    self._get_sr()
  
  # Write a byte
  def write_byte(self,address,byte):
    mosi = pack( '>BHB', self._WRITE, address, byte )
    self.cs(0)
    self.spi.write(mosi)
    self.cs(1)
  
  # Read a byte
  def read_byte(self,address):
    mosi = pack( '>BH', self._READ, address )
    self.cs(0)
    self.spi.write(mosi)
    miso = self.spi.read(1)
    self.cs(1)
    return miso
  
  def set_mode(self,mode):
    assert type(mode) is int
    assert mode >=0
    assert mode <=2
    self._set_sr( mode, self.sr['hold'] )
  
  def set_hold(self,hold):
    assert type(hold) is bool
    self._set_sr( self.sr['mode'], hold )
  
  # Write the status register
  def _set_sr(self,mode,hold):
    m = mode << 6
    h = (not hold)*1
    mosi = pack( '>BB', self._WRSR, m+h )
    self.cs(0)
    self.spi.write(mosi)
    self.cs(1)
    self.sr['mode'] = mode
    self.sr['hold'] = hold
    
  # Read the status register
  def _get_sr(self):
    self.cs(0)
    self.spi.write(bytes([self._RDSR]))
    sr = unpack( '>B', self.spi.read(1) )[0]
    self.cs(1)
    self.sr['mode'] = sr >> 6
    self.sr['hold'] = ( sr & 1 ) != 1
