# wemos_flash.py Test flash chips with ESP8266 host

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2020 Peter Hinch

import uos
from machine import SPI, Pin
from flash_spi import FLASH

cspins = (Pin(5, Pin.OUT, value=1), Pin(14, Pin.OUT, value=1))

spi=SPI(-1, baudrate=20_000_000, sck=Pin(4), miso=Pin(0), mosi=Pin(2))

def get_flash():
    flash = FLASH(spi, cspins)
    print('Instantiated Flash')
    return flash

directory = '/fl_ext'
a = bytearray(range(256))  # Data to write
b = bytearray(256)  # Data to read back
files = {}  # n:length
errors = 0

def fname(n):
    return '{}/{:05d}'.format(directory, n + 1)  # Names start 00001

def fcreate(n):  # Create a binary file of random length
    length = int.from_bytes(uos.urandom(2), 'little') + 1  # 1-65536 bytes
    linit = length
    with open(fname(n), 'wb') as f:
        while(length):
            nw = min(length, 256)
            f.write(a[:nw])
            length -= nw
    files[n] = length
    return linit

def fcheck(n):
    length = files[n]
    with open(fname(n), 'rb') as f:
        while(length):
            nr = f.readinto(b)
            if not nr:
                return False
            if a[:nr] != b[:nr]:
                return False
            length -= nr
    return True

def check_all():
    global errors
    for n in files:
        if fcheck(n):
            print('File {:d} OK'.format(n))
        else:
            print('Error in file', n)
            errors += 1
    print('Total errors:', errors)


def remove_all():
    for n in files:
        uos.remove(fname(n))

def flash_test(format=False):
    eep = get_flash()
    if format:
        uos.VfsLfs2.mkfs(eep)
    try:
        uos.mount(eep,'/fl_ext')
    except OSError:  # Already mounted
        pass
    for n in range(128):
        length = fcreate(n)
        print('Created', n, length)
    print('Created files', files)
    check_all()
    for _ in range(100):
        for x in range(5):  # Rewrite 5 files with new lengths
            n = int.from_bytes(uos.urandom(1), 'little') & 0x7f
            length = fcreate(n)
            print('Rewrote', n, length)
        check_all()
    remove_all()

msg='''Run wemos_flash.flash_test(True) to format new array, otherwise
wemos_flash.flash_test()
Runs prolonged test of filesystem.'''
print(msg)
