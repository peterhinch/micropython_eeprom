# flash_spi.py MicroPython driver for SPI NOR flash devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019-2020 Peter Hinch

import time
from micropython import const
from bdevice import FlashDevice

# Supported instruction set:
# 3 and 4 byte address commands
_READ = const(0)
_PP = const(1)
_SE = const(2)
_CMDS3BA = b'\x03\x02\x20'
_CMDS4BA = b'\x13\x12\x21'
# No address
_WREN = const(6)  # Write enable
_RDSR1 = const(5)  # Read status register 1
_RDID = const(0x9f)  # Read manufacturer ID
_CE = const(0xc7)  # Chip erase (takes minutes)

_SEC_SIZE = const(4096)  # Flash sector size 0x1000

# Logical Flash device comprising one or more physical chips sharing an SPI bus.
class FLASH(FlashDevice):

    def __init__(self, spi, cspins, size=None, verbose=True,
                 sec_size=_SEC_SIZE, block_size=9, cmdset=None):
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        self._bufp = bytearray(6)  # instruction + 4 byte address + 1 byte value
        self._mvp = memoryview(self._bufp)  # cost-free slicing
        self._page_size = 256  # Write uses 256 byte pages.
        # Defensive code: application should have done the following.
        # Pyboard D 3V3 output may just have been switched on.
        for cs in cspins:  # Deselect all chips
            cs(1)
        time.sleep_ms(1)  # Meet Tpu 300μs

        size = self.scan(verbose, size)  # KiB
        super().__init__(block_size, len(cspins), size * 1024, sec_size)

        # Select the correct command set
        if (cmdset is None and size <= 4096) or (cmdset == False):
            self._cmds = _CMDS3BA
            self._cmdlen = 4
        else:
            self._cmds = _CMDS4BA
            self._cmdlen = 5

        self.initialise()  # Initially cache sector 0

    # **** API SPECIAL METHODS ****
    # Scan: return chip size in KiB as read from ID.
    def scan(self, verbose, size):
        mvp = self._mvp
        for n, cs in enumerate(self._cspins):
            mvp[:] = b'\0\0\0\0\0\0'
            mvp[0] = _RDID
            cs(0)
            self._spi.write_readinto(mvp[:4], mvp[:4])
            cs(1)
            scansize = 1 << (mvp[3] - 10)
            if size is None:
                size = scansize  # Save size of 1st chip
            if size != scansize:  # Mismatch passed size or 1st chip.
                raise ValueError('Flash size mismatch: expected {}KiB, found {}KiB'.format(size, scansize))
        if verbose:
            s = '{} chips detected. Total flash size {}MiB.'
            n += 1
            print(s.format(n, (n * size) // 1024))
        return size

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
            mvp[0] = self._cmds[_PP]
            cs(0)
            self._spi.write(mvp[:self._cmdlen])  # Start write
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
            mvp[0] = self._cmds[_READ]
            cs(0)
            self._spi.write(mvp[:self._cmdlen])
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
        cmdlen = self._cmdlen
        mvp = self._mvp[:cmdlen]
        if cmdlen > 3:
            mvp[-4] = la >> 24
        mvp[-3] = la >> 16 & 0xff
        mvp[-2] = (la >> 8) & 0xff
        mvp[-1] = la & 0xff
        pe = (addr & -self._c_bytes) + self._c_bytes  # Byte 0 of next chip
        return min(nbytes, pe - la)

    # Erase sector. Address is start byte address of sector. Optimisation: skip
    # if sector is already erased.
    def _sector_erase(self, addr):
        if not self.is_empty(addr):
            self._getaddr(addr, 1)
            cs = self._ccs  # Current chip select from _getaddr
            mvp = self._mvp
            mvp[0] = _WREN
            cs(0)
            self._spi.write(mvp[:1])  # Enable write
            cs(1)
            mvp[0] = self._cmds[_SE]
            cs(0)
            self._spi.write(mvp[:self._cmdlen])  # Start erase
            cs(1)
            self._wait_rdy()  # Wait for erase to complete
