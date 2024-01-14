# eep_i2c.py MicroPython test program for Microchip I2C EEPROM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2024 Peter Hinch

import uos
import time
from machine import I2C, Pin
from eeprom_i2c import EEPROM, T24C512

# Return an EEPROM array. Adapt for platforms other than Pyboard or chips
# smaller than 64KiB.
def get_eep():
    if uos.uname().machine.split(" ")[0][:4] == "PYBD":
        Pin.board.EN_3V3.value(1)
        time.sleep(0.1)  # Allow decouplers to charge
    eep = EEPROM(I2C(2), T24C512)
    print("Instantiated EEPROM")
    return eep


# Dumb file copy utility to help with managing EEPROM contents at the REPL.
def cp(source, dest):
    if dest.endswith("/"):  # minimal way to allow
        dest = "".join((dest, source.split("/")[-1]))  # cp /sd/file /eeprom/
    try:
        with open(source, "rb") as infile:  # Caller should handle any OSError
            with open(dest, "wb") as outfile:  # e.g file not found
                while True:
                    buf = infile.read(100)
                    outfile.write(buf)
                    if len(buf) < 100:
                        break
    except OSError as e:
        if e.errno == 28:
            print("Insufficient space for copy.")
        else:
            raise


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


def test(eep=None):
    eep = eep if eep else get_eep()
    sa = 1000
    for v in range(256):
        eep[sa + v] = v
    for v in range(256):
        if eep[sa + v] != v:
            print("Fail at address {} data {} should be {}".format(sa + v, eep[sa + v], v))
            break
    else:
        print("Test of byte addressing passed")
    data = uos.urandom(30)
    sa = 2000
    eep[sa : sa + 30] = data
    if eep[sa : sa + 30] == data:
        print("Test of slice readback passed")

    block = 256
    res = _testblock(eep, block)
    if res is None:
        print("Test block boundary {} passed".format(block))
    else:
        print("Test block boundary {} fail".format(block))
        print(res)
    block = eep._c_bytes
    if eep._a_bytes > block:
        res = _testblock(eep, block)
        if res is None:
            print("Test chip boundary {} passed".format(block))
        else:
            print("Test chip boundary {} fail".format(block))
            print(res)
    else:
        print("Test chip boundary skipped: only one chip!")
    pe = eep.get_page_size() + 1  # One byte past page
    eep[pe] = 0xFF
    eep[:257] = b"\0" * 257
    print("Test page size: ", end="")
    if eep[pe]:
        print("FAIL")
    else:
        print("passed")


# ***** TEST OF FILESYSTEM MOUNT *****
def fstest(eep=None, format=False):
    eep = eep if eep else get_eep()
    try:
        uos.umount("/eeprom")
    except OSError:
        pass
    # ***** CODE FOR FATFS *****
    # if format:
    # os.VfsFat.mkfs(eep)
    # ***** CODE FOR LITTLEFS *****
    if format:
        uos.VfsLfs2.mkfs(eep)
    # General
    try:
        uos.mount(eep, "/eeprom")
    except OSError:
        raise OSError("Can't mount device: have you formatted it?")
    print('Contents of "/": {}'.format(uos.listdir("/")))
    print('Contents of "/eeprom": {}'.format(uos.listdir("/eeprom")))
    print(uos.statvfs("/eeprom"))


def cptest(eep=None):  # Assumes pre-existing filesystem of either type
    eep = eep if eep else get_eep()
    if "eeprom" in uos.listdir("/"):
        print("Device already mounted.")
    else:
        try:
            uos.mount(eep, "/eeprom")
        except OSError:
            print("Fail mounting device. Have you formatted it?")
            return
        print("Mounted device.")
    cp(__file__, "/eeprom/")
    # We may have the source file or a precompiled binary (*.mpy)
    cp(__file__.replace("eep", "eeprom"), "/eeprom/")
    print('Contents of "/eeprom": {}'.format(uos.listdir("/eeprom")))
    print(uos.statvfs("/eeprom"))


# ***** TEST OF HARDWARE *****
def full_test(eep=None, block_size=256):
    eep = eep if eep else get_eep()
    print(f"Testing with {block_size}byte blocks of random data...")
    block = 0
    for sa in range(0, len(eep), block_size):
        data = uos.urandom(block_size)
        eep[sa : sa + block_size] = data
        if eep[sa : sa + block_size] == data:
            print(f"Block {block} passed\r", end="")
        else:
            print(f"Block {block} readback failed.")
        block += 1
    print()

def help():
    st = """Available commands:
    help()  Print this text.
    test()  Basic fuctional test.
    full_test()  Read-write test of EEPROM chip(s).
    fstest()  Check or create a filesystem.
    cptest()  Check a filesystem by copying source files to it.

    Utilities:
    get_eep()  Initialise and return an EEPROM instance.
    cp()  Very crude file copy utility.
    """
    print(st)

help()
