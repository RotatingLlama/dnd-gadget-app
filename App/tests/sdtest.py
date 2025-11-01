# Test for sdcard block protocol
# Peter hinch 30th Jan 2016
import machine
import os
import sdcard

def getspi():
    spi = machine.SPI(0, sck=machine.Pin(18), mosi=machine.Pin(19), miso=machine.Pin(16), baudrate=400000, polarity=0, phase=0)
    spi.init()  # Ensure right baudrate
    return spi

def sdtest(spi):
    #spi = machine.SPI(0, sck=machine.Pin(18), mosi=machine.Pin(19), miso=machine.Pin(16), baudrate=400000, polarity=0, phase=0)
    #spi.init()  # Ensure right baudrate
    sd = sdcard.SDCard( spi=spi, cs=machine.Pin(2), baudrate=4000000)  # Compatible with PCB
    
    print( sd.ioctl(4,0) )
    print( sd.ioctl(5,0) )
    
    vfs = os.VfsFat(sd)
    os.mount(vfs, "/fc")
    print("Filesystem check")
    print(os.listdir("/fc"))
    
    return

    line = "abcdefghijklmnopqrstuvwxyz\n"
    lines = line * 200  # 5400 chars
    short = "1234567890\n"

    fn = "/fc/rats.txt"
    print()
    print("Multiple block read/write")
    with open(fn, "w") as f:
        n = f.write(lines)
        print(n, "bytes written")
        n = f.write(short)
        print(n, "bytes written")
        n = f.write(lines)
        print(n, "bytes written")

    with open(fn, "r") as f:
        result1 = f.read()
        print(len(result1), "bytes read")

    fn = "/fc/rats1.txt"
    print()
    print("Single block read/write")
    with open(fn, "w") as f:
        n = f.write(short)  # one block
        print(n, "bytes written")

    with open(fn, "r") as f:
        result2 = f.read()
        print(len(result2), "bytes read")

    os.umount("/fc")

    print()
    print("Verifying data read back")
    success = True
    if result1 == "".join((lines, short, lines)):
        print("Large file Pass")
    else:
        print("Large file Fail")
        success = False
    if result2 == short:
        print("Small file Pass")
    else:
        print("Small file Fail")
        success = False
    print()
    print("Tests", "passed" if success else "failed")

def discon_test(spi):
    import time
    
    sd = sdcard.SDCard( spi=spi, cs=machine.Pin(2), baudrate=4000000)
    
    print( sd.ioctl(4,0) )
    print( sd.ioctl(5,0) )
    
    #print(sd.cmd(0, 0, 0x95))
    
    vfs = os.VfsFat(sd)
    os.mount(vfs, "/fc")
    print("Filesystem check")
    print(os.listdir("/fc"))
    print(os.listdir("/fc/non-existanbt"))
    
    time.sleep(5)
    
    print('waking...')
    
    os.umount(vfs)
    print(os.listdir("/fc"))
    
    #print(sd.cmd(0, 0, 0x95))
    
    
    #print( sd.ioctl(4,0) )
    #print( sd.ioctl(5,0) )
    #print("Filesystem check")
    #print(os.listdir("/fc"))
    
    
spi = getspi()
discon_test(spi)
#sdtest(spi)