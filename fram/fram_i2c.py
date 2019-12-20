# fram_i2c.py Driver for Adafruit 32K Ferroelectric RAM module (Fujitsu MB85RC256V)

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

from micropython import const
from bdevice import BlockDevice

_SIZE = const(32768)  # Chip size 32KiB
_ADDR = const(0x50)  # FRAM I2C address 0x50 to 0x57
_FRAM_SLAVE_ID = const(0xf8)  # FRAM device ID location
_MANF_ID = const(0x0a)
_PRODUCT_ID = const(0x510)


# A logical ferroelectric RAM made up of from 1 to 8 chips
class FRAM(BlockDevice):
    def __init__(self, i2c, verbose=True, block_size=9):
        self._i2c = i2c
        self._buf1 = bytearray(1)
        self._addrbuf = bytearray(2)  # Memory offset into current chip
        self._buf3 = bytearray(3)
        self._nchips = self.scan(verbose, _SIZE)
        super().__init__(block_size, self._nchips, _SIZE)
        self._i2c_addr = None  # i2c address of current chip

    def scan(self, verbose, chip_size):
        devices = self._i2c.scan()
        chips = [d for d in devices if d in range(_ADDR, _ADDR + 8)]
        nchips = len(chips)
        if nchips == 0:
            raise RuntimeError('FRAM not found.')
        if min(chips) != _ADDR or (max(chips) - _ADDR) >= nchips:
            raise RuntimeError('Non-contiguous chip addresses', chips)
        for chip in chips:
            if not self._available(chip):
                raise RuntimeError('FRAM at address 0x{:02x} reports an error'.format(chip))
        if verbose:
            s = '{} chips detected. Total FRAM size {}bytes.'
            print(s.format(nchips, chip_size * nchips))
        return nchips

    def _available(self, device_addr):
        res = self._buf3
        self._i2c.readfrom_mem_into(_FRAM_SLAVE_ID >> 1, device_addr << 1, res)
        manufacturerID = (res[0] << 4) + (res[1]  >> 4)
        productID = ((res[1] & 0x0F) << 8) + res[2]
        return manufacturerID == _MANF_ID and productID == _PRODUCT_ID

    # In the context of FRAM a page == a chip.
    # Args: an address and a no. of bytes. Set ._i2c_addr to correct chip.
    # Return the no. of bytes available to access on that chip.
    def _getaddr(self, addr, nbytes):  # Set up _addrbuf and i2c_addr
        if addr >= self._a_bytes:
            raise RuntimeError('FRAM Address is out of range')
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._addrbuf[0] = (la >> 8) & 0xff
        self._addrbuf[1] = la & 0xff
        self._i2c_addr = _ADDR + ca
        return min(nbytes, self._c_bytes - la)

    def readwrite(self, addr, buf, read):
        nbytes = len(buf)
        mvb = memoryview(buf)
        start = 0  # Offset into buf.
        while nbytes > 0:
            npage = self._getaddr(addr, nbytes)  # No of bytes that fit on current chip
            if read:
                self._i2c.writeto(self._i2c_addr, self._addrbuf)
                self._i2c.readfrom_into(self._i2c_addr, mvb[start : start + npage])  # Sequential read
            else:
                self._i2c.writevto(self._i2c_addr, (self._addrbuf, buf[start: start + npage]))
            nbytes -= npage
            start += npage
            addr += npage
        return buf
