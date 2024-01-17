# eep_spi.py MicroPython test program for Microchip SPI EEPROM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2024 Peter Hinch

import uos
import time
from machine import SPI, Pin, SoftSPI
from eeprom_spi import EEPROM

ESP8266 = uos.uname().sysname == "esp8266"
# Add extra pins if using multiple chips
if ESP8266:
    cspins = (Pin(5, Pin.OUT, value=1), Pin(14, Pin.OUT, value=1))
else:
    cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))

# Return an EEPROM array. Adapt for platforms other than Pyboard.
def get_eep(stm):
    if uos.uname().machine.split(" ")[0][:4] == "PYBD":
        Pin.board.EN_3V3.value(1)
        time.sleep(0.1)  # Allow decouplers to charge

    if stm:
        if ESP8266:
            spi = SoftSPI(baudrate=5_000_000, sck=Pin(4), miso=Pin(0), mosi=Pin(2))
        else:  # Pyboard. 1.22.1 hard SPI seems to have a read bug
            # spi = SPI(2, baudrate=5_000_000)
            spi = SoftSPI(baudrate=5_000_000, sck=Pin('Y6'), miso=Pin('Y7'), mosi=Pin('Y8'))
        eep = EEPROM(spi, cspins, 256)
    else:
        if ESP8266:
            spi = SoftSPI(baudrate=20_000_000, sck=Pin(4), miso=Pin(0), mosi=Pin(2))
        else:
            # spi = SPI(2, baudrate=20_000_000)
            spi = SoftSPI(baudrate=20_000_000, sck=Pin('Y6'), miso=Pin('Y7'), mosi=Pin('Y8'))
        eep = EEPROM(spi, cspins, 128)
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


def test(stm=False):
    eep = get_eep(stm)
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
    pe = eep.get_page_size()  # One byte past page
    eep[pe] = 0xFF
    eep[:257] = b"\0" * 257
    print("Test page size: ", end="")
    if eep[pe]:
        print("FAIL")
    else:
        print("passed")


# ***** TEST OF FILESYSTEM MOUNT *****
def fstest(format=False, stm=False):
    eep = get_eep(stm)
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


def cptest(stm=False):  # Assumes pre-existing filesystem of either type
    eep = get_eep(stm)
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
def full_test(stm=False):
    eep = get_eep(stm)
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
    test_str = """Available commands (see SPI.md):
    help()  Print this text.
    test(stm=False)  Basic hardware test.
    full_test(stm=False)  Thorough hardware test.
    fstest(format=False, stm=False)  Filesystem test (see doc).
    cptest(stm=False)  Copy files to filesystem (see doc).
stm: True is 256K chip, 5MHz bus. False is 128K chip, 20MHz bus.
"""
    print(test_str)


help()
