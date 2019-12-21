# eeprom_spi.py MicroPython driver for Microchip 128KiB SPI EEPROM device,
# also STM 256KiB chip.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

import time
from micropython import const
from bdevice import BlockDevice

# Supported instruction set - common to both chips:
_READ = const(3)
_WRITE = const(2)
_WREN = const(6)  # Write enable
_RDSR = const(5)  # Read status register
# Microchip only:
_RDID = const(0xab)  # Read chip ID
_CE = const(0xc7)  # Chip erase
# STM only:
_RDID_STM = const(0x83)  # Read ID page
_WRID_STM = const(0x82)
_STM_ID = const(0x30)  # Arbitrary ID for STM chip
# Not implemented: Write disable and Write status register
# _WRDI = const(4)
# _WRSR = const(1)

# Logical EEPROM device comprising one or more physical chips sharing an SPI bus.
class EEPROM(BlockDevice):

    def __init__(self, spi, cspins, size=128, verbose=True, block_size=9):
        # args: virtual block size in bits, no. of chips, bytes in each chip
        if size not in (128, 256):
            raise ValueError('Valid sizes are 128 or 256')
        super().__init__(block_size, len(cspins), size * 1024)
        self._stm = size == 256
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        self._bufp = bytearray(5)  # instruction + 3 byte address + 1 byte value
        self._mvp = memoryview(self._bufp)  # cost-free slicing
        self.scan(verbose)

    # Read ID block ID[0]
    def _stm_rdid(self, n):
        cs = self._cspins[n]
        mvp = self._mvp
        mvp[:] = b'\0\0\0\0\0'
        mvp[0] = _RDID_STM
        cs(0)
        self._spi.write_readinto(mvp, mvp)
        cs(1)
        return mvp[4]

    # Write a fixed value to ID[0]
    def _stm_wrid(self, n):
        cs = self._ccs
        mvp = self._mvp
        mvp[0] = _WREN
        cs(0)
        self._spi.write(mvp[:1])  # Enable write
        cs(1)
        mvp[:] = b'\0\0\0\0\0'
        mvp[0] = _WRID_STM
        mvp[4] = _STM_ID
        cs(0)
        self._spi.write(mvp)
        cs(1)
        self._wait_rdy()

    # Check for valid hardware on each CS pin: use ID block
    def _stm_scan(self):
        for n, cs in enumerate(self._cspins):
            self._ccs = cs
            if self._stm_rdid(n) != _STM_ID:
                self._stm_wrid(n)
            if self._stm_rdid(n) != _STM_ID:
                raise RuntimeError('M95M02 chip not found at cs[{}].'.format(n))
        return n

    # Scan for Microchip devices: read manf ID
    def _mc_scan(self):
        mvp = self._mvp
        for n, cs in enumerate(self._cspins):
            mvp[:] = b'\0\0\0\0\0'
            mvp[0] = _RDID
            cs(0)
            self._spi.write_readinto(mvp, mvp)
            cs(1)
            if mvp[4] != 0x29:
                raise RuntimeError('25xx1024 chip not found at cs[{}].'.format(n))
        return n

    # Check for a valid hardware configuration
    def scan(self, verbose):
        n = self._stm_scan() if self._stm else self._mc_scan()
        if verbose:
            s = '{} chips detected. Total EEPROM size {}bytes.'
            print(s.format(n + 1, self._a_bytes))

    def erase(self):
        if self._stm:
            raise RuntimeError('Erase not available on STM chip')
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

    def _wait_rdy(self):  # After a write, wait for device to become ready
        mvp = self._mvp
        cs = self._ccs  # Chip is already current
        while True:
            mvp[0] = _RDSR
            cs(0)
            self._spi.write_readinto(mvp[:2], mvp[:2])
            cs(1)
            if not mvp[1]:  # We never set BP0 or BP1 so ready state is 0.
                break
            time.sleep_ms(1)

    # Given an address, set current chip select and address buffer.
    # Return the number of bytes that can be processed in the current page.
    def _getaddr(self, addr, nbytes):
        if addr >= self._a_bytes:
            raise RuntimeError("EEPROM Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._ccs = self._cspins[ca]  # Current chip select
        mvp = self._mvp
        mvp[1] = la >> 16
        mvp[2] = (la >> 8) & 0xff
        mvp[3] = la & 0xff
        pe = (addr & ~0xff) + 0x100  # byte 0 of next page
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
                self._spi.write(mvb[start: start + npage])
                cs(1)  # Trigger write start
                self._wait_rdy()  # Wait until done (6ms max)
            nbytes -= npage
            start += npage
            addr += npage
        return buf
