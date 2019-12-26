# flash_spi.py MicroPython driver for Cypress S25FL128L 16MiB and S25FL256L 32MiB
# flash devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

import time
from micropython import const
from bdevice import FlashDevice

# Supported instruction set:
# 4 byte address commands
_READ = const(0x13)
_PP = const(0x12)  # Page program
_SE = const(0x21)  # Sector erase
# No address
_WREN = const(6)  # Write enable
_RDSR1 = const(5)  # Read status register 1
_RDSR2 = const(7)  # Read status register 2
_RDID = const(0x9f)  # Read manufacturer ID
_CE = const(0xc7)  # Chip erase (takes minutes)

_SEC_SIZE = const(4096)  # Flash sector size 0x1000

# Logical Flash device comprising one or more physical chips sharing an SPI bus.
class FLASH(FlashDevice):

    def __init__(self, spi, cspins, size=16384, verbose=True, sec_size=_SEC_SIZE, block_size=9):
        # args: virtual block size in bits, no. of chips, bytes in each chip
        if size not in (16384, 32768):
            raise ValueError('Valid sizes: 16384 or 32768KiB')
        super().__init__(block_size, len(cspins), size * 1024, sec_size)
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        self._bufp = bytearray(6)  # instruction + 4 byte address + 1 byte value
        self._mvp = memoryview(self._bufp)  # cost-free slicing
        self._page_size = 256  # Write uses 256 byte pages.
        self.scan(verbose)
        self.initialise()  # Initially cache sector 0

    # **** API SPECIAL METHODS ****
    # Scan: read manf ID
    def scan(self, verbose):
        mvp = self._mvp
        for n, cs in enumerate(self._cspins):
            mvp[:] = b'\0\0\0\0\0\0'
            mvp[0] = _RDID
            cs(0)
            self._spi.write_readinto(mvp[:4], mvp[:4])
            cs(1)
            if mvp[1] != 1 or mvp[2] != 0x60 or not (mvp[3] == 0x18 or mvp[3] == 0x19):
                raise RuntimeError('Flash not found at cs[{}].'.format(n))
        if verbose:
            s = '{} chips detected. Total flash size {}MiB.'
            print(s.format(n + 1, self._a_bytes // (1024 * 1024)))
        return n

    # Chip erase. Can take minutes.
    def erase(self):
        mvp = self._mvp
        for cs in self._cspins:  # For each chip
            mvp[0] = _WREN
            cs(0)
            self._spi.write(mvp[:1])  # Enable write
            cs(1)
            mvp[0] = _CE
            cs(0)
            self._spi.write(mvp[:1])  # Start erase
            cs(1)
            self._wait_rdy()  # Wait for erase to complete

    # **** INTERFACE FOR BASE CLASS ****
    # Write cache to a sector starting at byte address addr
    def flush(self, cache, addr):  # cache is memoryview into buffer
        self._sector_erase(addr)
        mvp = self._mvp
        nbytes = self.sec_size
        ps = self._page_size
        start = 0  # Current offset into cache buffer
        while nbytes > 0:
            # write one page at a time
            self._getaddr(addr, 1)
            cs = self._ccs  # Current chip select from _getaddr
            mvp[0] = _WREN
            cs(0)
            self._spi.write(mvp[:1])  # Enable write
            cs(1)
            mvp[0] = _PP
            cs(0)
            self._spi.write(mvp[:5])  # Start write
            self._spi.write(cache[start : start + ps])
            cs(1)
            self._wait_rdy()  # Wait for write to complete
            nbytes -= ps
            start += ps
            addr += ps

    # Read from chip into a memoryview. Address range guaranteed not to be cached.
    def rdchip(self, addr, mvb):
        nbytes = len(mvb)
        mvp = self._mvp
        start = 0  # Offset into buf.
        while nbytes > 0:
            npage = self._getaddr(addr, nbytes)  # No. of bytes in current chip
            cs = self._ccs
            mvp[0] = _READ
            cs(0)
            self._spi.write(mvp[:5])
            self._spi.readinto(mvb[start : start + npage])
            cs(1)
            nbytes -= npage
            start += npage
            addr += npage

    # Read or write multiple bytes at an arbitrary address.
    # **** Also part of API ****
    def readwrite(self, addr, buf, read):
        mvb = memoryview(buf)
        self.read(addr, mvb) if read else self.write(addr, mvb)
        return buf

    # **** INTERNAL METHODS ****
    def _wait_rdy(self):  # After a write, wait for device to become ready
        mvp = self._mvp
        cs = self._ccs  # Chip is already current
        while True:  # TODO read status register 2, raise OSError on nonzero.
            mvp[0] = _RDSR1
            cs(0)
            self._spi.write_readinto(mvp[:2], mvp[:2])
            cs(1)
            if not (mvp[1] & 1):
                break
            time.sleep_ms(1)

    # Given an address, set current chip select and address buffer.
    # Return the number of bytes that can be processed in the current chip.
    def _getaddr(self, addr, nbytes):
        if addr >= self._a_bytes:
            raise RuntimeError("Flash Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._ccs = self._cspins[ca]  # Current chip select
        mvp = self._mvp
        mvp[1] = la >> 24
        mvp[2] = la >> 16 & 0xff
        mvp[3] = (la >> 8) & 0xff
        mvp[4] = la & 0xff
        pe = (addr & -self._c_bytes) + self._c_bytes  # Byte 0 of next chip
        return min(nbytes, pe - la)

    # Erase sector. Address is start byte address of sector.
    def _sector_erase(self, addr):
        if not self.is_empty(addr):
            self._getaddr(addr, 1)
            cs = self._ccs  # Current chip select from _getaddr
            mvp = self._mvp
            mvp[0] = _WREN
            cs(0)
            self._spi.write(mvp[:1])  # Enable write
            cs(1)
            mvp[0] = _SE
            cs(0)
            self._spi.write(mvp[:5])  # Start erase
            cs(1)
            self._wait_rdy()  # Wait for erase to complete
