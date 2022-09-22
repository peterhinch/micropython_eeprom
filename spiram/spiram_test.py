# spiram_ test.py MicroPython test program for Adafruit SPIRAM device
# Adafruit https://www.adafruit.com/product/4677


# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2021 Peter Hinch

import os
import time
from machine import SPI, Pin
from spiram import SPIRAM

cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))

# Return an RAM array. Adapt for platforms other than Pyboard.
def get_spiram():
    if os.uname().machine.split(" ")[0][:4] == "PYBD":
        Pin.board.EN_3V3.value(1)
        time.sleep(0.1)  # Allow decouplers to charge
    ram = SPIRAM(SPI(2, baudrate=25_000_000), cspins)
    print("Instantiated RAM")
    return ram


# Dumb file copy utility to help with managing FRAM contents at the REPL.
def cp(source, dest):
    if dest.endswith("/"):  # minimal way to allow
        dest = "".join((dest, source.split("/")[-1]))  # cp /sd/file /ram/
    with open(source, "rb") as infile:  # Caller should handle any OSError
        with open(dest, "wb") as outfile:  # e.g file not found
            while True:
                buf = infile.read(100)
                outfile.write(buf)
                if len(buf) < 100:
                    break


# ***** TEST OF DRIVER *****
def _testblock(eep, bs):
    d0 = b"this >"
    d1 = b"<is the boundary"
    d2 = d0 + d1
    garbage = b"xxxxxxxxxxxxxxxxxxx"
    start = bs - len(d0)
    end = start + len(garbage)
    eep[start:end] = garbage
    res = eep[start:end]
    if res != garbage:
        return "Block test fail 1:" + str(list(res))
    end = start + len(d0)
    eep[start:end] = d0
    end = start + len(garbage)
    res = eep[start:end]
    if res != b"this >xxxxxxxxxxxxx":
        return "Block test fail 2:" + str(list(res))
    start = bs
    end = bs + len(d1)
    eep[start:end] = d1
    start = bs - len(d0)
    end = start + len(d2)
    res = eep[start:end]
    if res != d2:
        return "Block test fail 3:" + str(list(res))


def test():
    ram = get_spiram()
    sa = 1000
    for v in range(256):
        ram[sa + v] = v
    for v in range(256):
        if ram[sa + v] != v:
            print(
                "Fail at address {} data {} should be {}".format(sa + v, ram[sa + v], v)
            )
            break
    else:
        print("Test of byte addressing passed")
    data = os.urandom(30)
    sa = 2000
    ram[sa : sa + 30] = data
    if ram[sa : sa + 30] == data:
        print("Test of slice readback passed")
    # On SPIRAM the only meaningful block test is on a chip boundary.
    block = ram._c_bytes
    if ram._a_bytes > block:
        res = _testblock(ram, block)
        if res is None:
            print("Test chip boundary {} passed".format(block))
        else:
            print("Test chip boundary {} fail".format(block))
            print(res)
    else:
        print("Test chip boundary skipped: only one chip!")


# ***** TEST OF FILESYSTEM MOUNT *****
def fstest():
    ram = get_spiram()
    os.VfsLfs2.mkfs(ram)  # Format littlefs
    try:
        os.mount(ram, "/ram")
    except OSError:  # Already mounted
        pass
    print('Contents of "/": {}'.format(os.listdir("/")))
    print('Contents of "/ram": {}'.format(os.listdir("/ram")))
    print(os.statvfs("/ram"))


def cptest():
    ram = get_spiram()
    if "ram" in os.listdir("/"):
        print("Device already mounted.")
    else:
        os.VfsLfs2.mkfs(ram)  # Format littlefs
        os.mount(ram, "/ram")
        print("Formatted and mounted device.")
    cp("/sd/spiram_test.py", "/ram/")
    cp("/sd/spiram.py", "/ram/")
    print('Contents of "/ram": {}'.format(os.listdir("/ram")))
    print(os.statvfs("/ram"))


# ***** TEST OF HARDWARE *****
def full_test():
    bsize = 2048
    ram = get_spiram()
    page = 0
    for sa in range(0, len(ram), bsize):
        data = os.urandom(bsize)
        ram[sa : sa + bsize] = data
        if ram[sa : sa + bsize] == data:
            print("Page {} passed".format(page))
        else:
            print("Page {} readback failed.".format(page))
        page += 1
