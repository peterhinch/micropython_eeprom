# littlefs_test.py Extended filesystem test of flash devices
# Create multiple binary files of varying length and verify that they can be
# read back correctly. Rewrite files with new lengths then check that all files
# are OK.

import uos
from machine import SPI, Pin
from flash_spi import FLASH
from flash_test import get_device

directory = '/fl_ext'
a = bytearray(range(256))
b = bytearray(256)
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

def main():
    eep = get_device()
    try:
        uos.mount(eep, directory)
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
