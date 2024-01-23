# eeprom_spi.py MicroPython driver for EEPROM chips (see README.md for
# tested devices).

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2024 Peter Hinch

# Thanks are due to Abel Deuring for help in diagnosing and fixing a page size issue.

import time
from os import urandom
from micropython import const
from bdevice import EepromDevice

# Supported instruction set - common to both chips:
_READ = const(3)
_WRITE = const(2)
_WREN = const(6)  # Write enable
_RDSR = const(5)  # Read status register

# Logical EEPROM device comprising one or more physical chips sharing an SPI bus.
# args: SPI bus, tuple of CS Pin instances, chip size in KiB
# verbose: Test for chip presence and report
# block_size: Sector size for filesystems. See docs.
# erok: True if chip supports erase.
# page_size: None is auto detect. See docs.
class EEPROM(EepromDevice):
    def __init__(self, spi, cspins, size, verbose=True, block_size=9, page_size=None):
        if size not in (64, 128, 256):
            print(f"Warning: possible unsupported chip. Size: {size}KiB")
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        self._size = size * 1024  # Chip size in bytes
        self._bufp = bytearray(5)  # instruction + 3 byte address + 1 byte value
        self._mvp = memoryview(self._bufp)  # cost-free slicing
        if verbose:  # Test for presence of devices
            self.scan()
        # superclass figures out _page_size and _page_mask
        super().__init__(block_size, len(cspins), self._size, page_size, verbose)
        if verbose:
            print(f"Total EEPROM size {self._a_bytes:,} bytes.")

    # Low level device presence detect. Reads a location, then writes to it. If
    # a write value is passed, uses that, otherwise writes the one's complement
    # of the value read.
    def _devtest(self, cs, la, v=None):
        buf = bytearray(1)
        mvp = self._mvp
        # mvp[:] = b"\0" * 5  # test with addr 0
        mvp[1] = la >> 16
        mvp[2] = (la >> 8) & 0xFF
        mvp[3] = la & 0xFF
        mvp[0] = _READ
        cs(0)
        self._spi.write(mvp[:4])
        res = self._spi.read(1)
        cs(1)
        mvp[0] = _WREN
        cs(0)
        self._spi.write(mvp[:1])
        cs(1)
        mvp[0] = _WRITE
        cs(0)
        self._spi.write(mvp[:4])
        buf[0] = res[0] ^ 0xFF if v is None else v
        self._spi.write(buf)
        cs(1)  # Trigger write start
        self._ccs = cs
        self._wait_rdy()  # Wait until done (6ms max)
        return res[0]

    def scan(self):
        # Generate a random address to minimise wear
        la = int.from_bytes(urandom(3), "little") % self._size
        for n, cs in enumerate(self._cspins):
            old = self._devtest(cs, la)
            new = self._devtest(cs, la, old)
            if old != new ^ 0xFF:
                raise RuntimeError(f"Chip not found at cs[{n}]")
        print(f"{n + 1} chips detected.")
        return n

    def erase(self):
        mvp = self._mvp
        block = b"\0" * 256
        for n in range(0, self._a_bytes, 256):
            self[n : n + 256] = block

    def _wait_rdy(self):  # After a write, wait for device to become ready
        mvp = self._mvp
        cs = self._ccs  # Chip is already current
        tstart = time.ticks_ms()
        while True:
            mvp[0] = _RDSR
            cs(0)
            self._spi.write_readinto(mvp[:2], mvp[:2])
            cs(1)
            if not mvp[1]:  # We never set BP0 or BP1 so ready state is 0.
                break
            time.sleep_ms(1)
            if time.ticks_diff(time.ticks_ms(), tstart) > 1000:
                raise OSError("Device ready timeout.")

    # Given an address, set current chip select and address buffer.
    # Return the number of bytes that can be processed in the current page.
    def _getaddr(self, addr, nbytes):
        if addr >= self._a_bytes:
            raise RuntimeError("EEPROM Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._ccs = self._cspins[ca]  # Current chip select
        mvp = self._mvp
        mvp[1] = la >> 16
        mvp[2] = (la >> 8) & 0xFF
        mvp[3] = la & 0xFF
        pe = (la & self._page_mask) + self._page_size  # byte 0 of next page
        return min(nbytes, pe - la)

    # Read or write multiple bytes at an arbitrary address
    def readwrite(self, addr, buf, read):
        nbytes = len(buf)
        mvb = memoryview(buf)
        mvp = self._mvp
        start = 0  # Offset into buf.
        while nbytes > 0:
            npage = self._getaddr(addr, nbytes)  # No. of bytes in current page
            cs = self._ccs
            assert npage > 0
            if read:
                mvp[0] = _READ
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.readinto(mvb[start : start + npage])
                cs(1)
            else:
                mvp[0] = _WREN
                cs(0)
                self._spi.write(mvp[:1])
                cs(1)
                mvp[0] = _WRITE
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.write(mvb[start : start + npage])
                cs(1)  # Trigger write start
                self._wait_rdy()  # Wait until done (6ms max)
            nbytes -= npage
            start += npage
            addr += npage
        return buf
