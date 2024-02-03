# eep_i2c.py MicroPython test program for Microchip I2C EEPROM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2024 Peter Hinch

import uos
import time
from machine import I2C, Pin, SoftI2C
from eeprom_i2c import EEPROM, T24C512

# Return an EEPROM array. Adapt for platforms other than Pyboard or chips
# smaller than 64KiB.
def get_eep():
    # Special code for Pyboard D: enable 3.3V output
    if uos.uname().machine.split(" ")[0][:4] == "PYBD":
        Pin.board.EN_3V3.value(1)
        time.sleep(0.1)  # Allow decouplers to charge

    if uos.uname().sysname == "esp8266":  # ESP8266 test fixture
        eep = EEPROM(SoftI2C(scl=Pin(13, Pin.OPEN_DRAIN), sda=Pin(12, Pin.OPEN_DRAIN)), T24C512)
    elif uos.uname().sysname == "esp32":  # ChronoDot on ESP32-S3
        eep = EEPROM(SoftI2C(scl=Pin(9, Pin.OPEN_DRAIN), sda=Pin(8, Pin.OPEN_DRAIN)), 256, addr=0x50)        
    else:  # Pyboard D test fixture
        eep = EEPROM(I2C(2), T24C512)
    print("Instantiated EEPROM")
    return eep


# Yield pseudorandom bytes (random module not available on all ports)
def psrand8(x=0x3FBA2):
    while True:
        x ^= (x & 0x1FFFF) << 13
        x ^= x >> 17
        x ^= (x & 0x1FFFFFF) << 5
        yield x & 0xFF


# Given a source of pseudorandom bytes yield pseudorandom 256 byte buffer.
def psrand256(rand, ba=bytearray(256)):
    while True:
        for z in range(256):
            ba[z] = next(rand)
        yield ba


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
    if bs >= len(eep):
        bs = len(eep) // 2
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
    address_range = 256
    if sa + address_range > len(eep):
        sa = (len(eep) - address_range) // 2
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
    if sa + len(data) > len(eep):
        sa = (len(eep) - len(data)) // 2
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
    write_length  = min(257, len(eep))
    eep[:write_length] = b"\0" * write_length
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
    try:
        cp(__file__, "/eeprom/")
        # We may have the source file or a precompiled binary (*.mpy)
        cp(__file__.replace("eep", "eeprom"), "/eeprom/")
        print('Contents of "/eeprom": {}'.format(uos.listdir("/eeprom")))
        print(uos.statvfs("/eeprom"))
    except NameError:
        print("Test cannot be performed by this MicroPython port. Consider using upysh.")


# ***** TEST OF HARDWARE *****
# Write pseudorandom data to entire array, then read back. Fairly rigorous test.
def full_test(eep=None):
    eep = eep if eep else get_eep()
    print("Testing with 256 byte blocks of random data...")
    r = psrand8()  # Instantiate random byte generator
    ps = psrand256(r)  # Random 256 byte blocks
    for sa in range(0, len(eep), 256):
        ea = sa + 256
        eep[sa:ea] = next(ps)
        print(f"Address {sa}..{ea} written\r", end="")
    print()
    r = psrand8()  # Instantiate new random byte generator with same seed
    ps = psrand256(r)  # Random 256 byte blocks
    for sa in range(0, len(eep), 256):
        ea = sa + 256
        if eep[sa:ea] == next(ps):
            print(f"Address {sa}..{ea} readback passed\r", end="")
        else:
            print(f"Address {sa}..{ea} readback failed.")
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
