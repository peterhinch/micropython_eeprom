# eeprom_i2c.py MicroPython driver for Microchip I2C EEPROM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

import time
from micropython import const
from bdevice import BlockDevice

_ADDR = const(0x50)  # Base address of chip

T24C512 = const(65536)  # 64KiB 512Kbits
T24C256 = const(32768)  # 32KiB 256Kbits
T24C128 = const(16384)  # 16KiB 128Kbits
T24C64 = const(8192)  # 8KiB 64Kbits

# Logical EEPROM device consists of 1-8 physical chips. Chips must all be the
# same size, and must have contiguous addresses starting from 0x50.
class EEPROM(BlockDevice):

    def __init__(self, i2c, chip_size=T24C512, verbose=True, block_size=9):
        self._i2c = i2c
        if chip_size not in (T24C64, T24C128, T24C256, T24C512):
            raise RuntimeError('Invalid chip size', chip_size)
        nchips = self.scan(verbose, chip_size)  # No. of EEPROM chips
        super().__init__(block_size, nchips, chip_size)
        self._i2c_addr = 0  # I2C address of current chip
        self._buf1 = bytearray(1)
        self._addrbuf = bytearray(2)  # Memory offset into current chip

    # Check for a valid hardware configuration
    def scan(self, verbose, chip_size):
        devices = self._i2c.scan()  # All devices on I2C bus
        eeproms = [d for d in devices if _ADDR <= d < _ADDR + 8]  # EEPROM chips
        nchips = len(eeproms)
        if nchips == 0:
            raise RuntimeError('EEPROM not found.')
        if min(eeproms) != _ADDR or (max(eeproms) - _ADDR) >= nchips:
            raise RuntimeError('Non-contiguous chip addresses', eeproms)
        if verbose:
            s = '{} chips detected. Total EEPROM size {}bytes.'
            print(s.format(nchips, chip_size * nchips))
        return nchips

    def _wait_rdy(self):  # After a write, wait for device to become ready
        self._buf1[0] = 0
        while True:
            try:
                if self._i2c.writeto(self._i2c_addr, self._buf1):  # Poll ACK
                    break
            except OSError:
                pass
            finally:
                time.sleep_ms(1)

    # Given an address, set ._i2c_addr and ._addrbuf and return the number of
    # bytes that can be processed in the current page
    def _getaddr(self, addr, nbytes):  # Set up _addrbuf and _i2c_addr
        if addr >= self._a_bytes:
            raise RuntimeError("EEPROM Address is out of range")
        ca, la = divmod(addr, self._c_bytes)  # ca == chip no, la == offset into chip
        self._addrbuf[0] = (la >> 8) & 0xff
        self._addrbuf[1] = la & 0xff
        self._i2c_addr = _ADDR + ca
        pe = (addr & ~0x7f) + 0x80  # byte 0 of next page
        return min(nbytes, pe - la)

    # Read or write multiple bytes at an arbitrary address
    def readwrite(self, addr, buf, read):
        nbytes = len(buf)
        mvb = memoryview(buf)
        start = 0  # Offset into buf.
        while nbytes > 0:
            npage = self._getaddr(addr, nbytes)  # No. of bytes in current page
            assert npage > 0
            if read:
                self._i2c.writeto(self._i2c_addr, self._addrbuf)
                self._i2c.readfrom_into(self._i2c_addr, mvb[start : start + npage])
            else:
                self._i2c.writevto(self._i2c_addr, (self._addrbuf, buf[start: start + npage]))
                self._wait_rdy()
            nbytes -= npage
            start += npage
            addr += npage
        return buf
