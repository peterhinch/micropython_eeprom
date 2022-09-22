# fs_test.py Extended filesystem test of SPIRAM devices
# Create multiple binary files of varying length and verify that they can be
# read back correctly. Rewrite files with new lengths then check that all files
# are OK.

import os
from machine import SPI, Pin
from spiram_test import get_spiram

directory = "/ram"
a = bytearray(range(256))
b = bytearray(256)
files = {}  # n:length
errors = 0


def fname(n):
    return "{}/{:05d}".format(directory, n + 1)  # Names start 00001


def fcreate(n):  # Create a binary file of random length
    length = int.from_bytes(os.urandom(2), "little") + 1  # 1-65536 bytes
    length &= 0x3FF  # 1-1023 for FRAM
    linit = length
    with open(fname(n), "wb") as f:
        while length:
            nw = min(length, 256)
            f.write(a[:nw])
            length -= nw
    files[n] = length
    return linit


def fcheck(n):
    length = files[n]
    with open(fname(n), "rb") as f:
        while length:
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
            print("File {:d} OK".format(n))
        else:
            print("Error in file", n)
            errors += 1
    print("Total errors:", errors)


def remove_all():
    for n in files:
        os.remove(fname(n))


def main():
    ram = get_spiram()
    os.VfsLfs2.mkfs(ram)  # Format littlefs
    try:
        os.mount(ram, "/ram")
    except OSError:  # Already mounted
        pass
    for n in range(128):
        length = fcreate(n)
        print("Created", n, length)
    print("Created files", files)
    check_all()
    for _ in range(100):
        for x in range(5):  # Rewrite 5 files with new lengths
            n = int.from_bytes(os.urandom(1), "little") & 0x7F
            length = fcreate(n)
            print("Rewrote", n, length)
        check_all()
    remove_all()


print("main() to run littlefs test. Erases any data on RAM.")
