# spiram.py Supports 8MiB SPI RAM
# Adafruit https://www.adafruit.com/product/4677

# These chips are almost identical. Command sets are identical.
# Product ID 1st byte, LS 4 bits is density 0x8 == 2MiB 0x9 == 4MiB

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2020 Peter Hinch

from micropython import const
from bdevice import BlockDevice

# Command set
_WRITE = const(2)
_READ = const(3)
_RSTEN = const(0x66)
_RESET = const(0x99)
_RDID = const(0x9f)


class SPIRAM(BlockDevice):
    def __init__(self, spi, cspins, size=8192, verbose=True, block_size=9):
        if size != 8192:
            print('SPIRAM size other than 8192KiB may not work.')
        super().__init__(block_size, len(cspins), size * 1024)
        self._spi = spi
        self._cspins = cspins
        self._ccs = None  # Chip select Pin object for current chip
        bufp = bytearray(6)  # instruction + 3 byte address + 2 byte value
        mvp = memoryview(bufp)  # cost-free slicing
        self._mvp = mvp
        # Check hardware
        for n, cs in enumerate(cspins):
            mvp[:] = b'\0\0\0\0\0\0'
            mvp[0] = _RDID
            cs(0)
            self._spi.write_readinto(mvp, mvp)
            cs(1)
            if mvp[4] != 0x0d or mvp[5] != 0x5d:
                print("Warning: expected manufacturer ID not found.")
            
        if verbose:
            s = 'Total SPIRAM size {} KiB in {} devices.'
            print(s.format(self._a_bytes//1024, n + 1))


    # Given an address, set current chip select and address buffer.
    # Return the number of bytes that can be processed in the current chip.
    def _getaddr(self, addr, nbytes):
        if addr >= self._a_bytes:
            raise RuntimeError("SPIRAM Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._ccs = self._cspins[ca]  # Current chip select
        mvp = self._mvp
        mvp[1] = la >> 16
        mvp[2] = (la >> 8) & 0xff
        mvp[3] = la & 0xff
        pe = (addr & -self._c_bytes) + self._c_bytes  # Byte 0 of next chip
        return min(nbytes, pe - la)

    # Interface to bdevice
    def readwrite(self, addr, buf, read):
        nbytes = len(buf)
        mvb = memoryview(buf)
        mvp = self._mvp
        start = 0  # Offset into buf.
        while nbytes > 0:
            nchip = self._getaddr(addr, nbytes)  # No of bytes that fit on current chip
            cs = self._ccs
            if read:
                mvp[0] = _READ
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.readinto(mvb[start : start + nchip])
                cs(1)
            else:
                mvp[0] = _WRITE
                cs(0)
                self._spi.write(mvp[:4])
                self._spi.write(mvb[start: start + nchip])
                cs(1)
            nbytes -= nchip
            start += nchip
            addr += nchip
        return buf

# Reset is unnecessary because it restores the default power-up state.
    #def _reset(self, cs, bufr = bytearray(1)):
        #cs(0)
        #bufr[0] = _RSTEN
        #self._spi.write(bufr)
        #cs(1)
        #cs(0)
        #bufr[0] = _RESET
        #self._spi.write(bufr)
        #cs(1)
