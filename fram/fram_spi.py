# fram_spi.py Supports Fujitsu 256KiB and 512KiB FRAM devices
# M85RS2MT Adafruit https://www.adafruit.com/product/4718
# M85RS4MT Adafruit https://www.adafruit.com/product/4719

# These chips are almost identical. Command sets are identical.
# Product ID 1st byte, LS 4 bits is density 0x8 == 2MiB 0x9 == 4MiB

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2020 Peter Hinch

from micropython import const
from bdevice import BlockDevice
# import time  # for sleep command

# Command set
_WREN = const(6)
_WRDI = const(4)
_RDSR = const(5)  # Read status reg
_WRSR = const(1)
_READ = const(3)
_WRITE = const(2)
_RDID = const(0x9f)
# _FSTRD = const(0x0b)  No obvious difference to _READ
_SLEEP = const(0xb9)


class FRAM(BlockDevice):
    def __init__(self, spi, cspins, size=512, verbose=True, block_size=9):
        if size not in (256, 512):
            raise ValueError('FRAM size must be 256 or 512')
        super().__init__(block_size, len(cspins), size * 1024)
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        self._bufp = bytearray(5)  # instruction + 3 byte address + 1 byte value
        mvp = memoryview(self._bufp)  # cost-free slicing
        self._mvp = mvp
        # Check hardware
        density = 8 if size == 256 else 9
        for n, cs in enumerate(cspins):
            mvp[:] = b'\0\0\0\0\0'
            mvp[0] = _RDID
            cs(0)
            self._spi.write_readinto(mvp, mvp)
            cs(1)
            # Ignore bits labelled "proprietary"
            if mvp[1] != 4 or mvp[2] != 0x7f:
                s = 'FRAM not found at cspins[{}].'
                raise RuntimeError(s.format(n))
            if  (mvp[3] & 0x1f) != density:
                s = 'FRAM at cspins[{}] is incorrect size.'
                raise RuntimeError(s.format(n))
        if verbose:
            s = 'Total FRAM size {} bytes in {} devices.'
            print(s.format(self._a_bytes, n + 1))
        # Set up status register on each chip
        for cs in cspins:
            self._wrctrl(cs, True)
            mvp[0] = _WRSR
            mvp[1] = 0  # No block protect or SR protect
            cs(0)
            self._spi.write(mvp[:2])
            cs(1)
            self._wrctrl(cs, False)  # Disable write to array

        for n, cs in enumerate(self._cspins):
            mvp[0] = _RDSR
            cs(0)
            self._spi.write_readinto(mvp[:2], mvp[:2])
            cs(1)
            if mvp[1]:
                s = 'FRAM has bad status at cspins[{}].'
                raise RuntimeError(s.format(n))

    def _wrctrl(self, cs, en):  # Enable/Disable device write
        mvp = self._mvp
        mvp[0] = _WREN if en else _WRDI
        cs(0)
        self._spi.write(mvp[:1])
        cs(1)

    #def sleep(self, on):
        #mvp = self._mvp
        #mvp[0] = _SLEEP
        #for cs in self._cspins:
            #cs(0)
            #if on:
                #self._spi.write(mvp[:1])
            #else:
                #time.sleep_us(500)
            #cs(1)

    # Given an address, set current chip select and address buffer.
    # Return the number of bytes that can be processed in the current chip.
    def _getaddr(self, addr, nbytes):
        if addr >= self._a_bytes:
            raise RuntimeError("FRAM Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._ccs = self._cspins[ca]  # Current chip select
        mvp = self._mvp
        mvp[1] = la >> 16
        mvp[2] = (la >> 8) & 0xff
        mvp[3] = la & 0xff
        pe = (addr & ~0xff) + 0x100  # byte 0 of next chip
        return min(nbytes, pe - la)

    # Interface to bdevice
    def readwrite(self, addr, buf, read):
        nbytes = len(buf)
        mvb = memoryview(buf)
        mvp = self._mvp
        start = 0  # Offset into buf.
        while nbytes > 0:
            npage = self._getaddr(addr, nbytes)  # No of bytes that fit on current chip
            cs = self._ccs
            if read:
                mvp[0] = _READ
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.readinto(mvb[start : start + npage])
                cs(1)
            else:
                self._wrctrl(cs, True)
                mvp[0] = _WRITE
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.write(mvb[start: start + npage])
                cs(1)
                self._wrctrl(cs, False)
            nbytes -= npage
            start += npage
            addr += npage
        return buf
