# bdevice.py Hardware-agnostic base classes.
# BlockDevice Base class for general block devices e.g. EEPROM, FRAM.
# FlashDevice Base class for generic Flash memory (subclass of BlockDevice).
# Documentation in BASE_CLASSES.md

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

from micropython import const


class BlockDevice:

    def __init__(self, nbits, nchips, chip_size):
        self._c_bytes = chip_size  # Size of chip in bytes
        self._a_bytes = chip_size * nchips  # Size of array
        self._nbits = nbits  # Block size in bits
        self._block_size = 2**nbits
        self._rwbuf = bytearray(1)

    def __len__(self):
        return self._a_bytes

    def __setitem__(self, addr, value):
        if isinstance(addr, slice):
            return self._wslice(addr, value)
        self._rwbuf[0] = value
        self.readwrite(addr, self._rwbuf, False)

    def __getitem__(self, addr):
        if isinstance(addr, slice):
            return self._rslice(addr)
        return self.readwrite(addr, self._rwbuf, True)[0]

    # Handle special cases of a slice. Always return a pair of positive indices.
    def _do_slice(self, addr):
        if not (addr.step is None or addr.step == 1):
            raise NotImplementedError('only slices with step=1 (aka None) are supported')
        start = addr.start if addr.start is not None else 0
        stop = addr.stop if addr.stop is not None else self._a_bytes
        start = start if start >= 0 else self._a_bytes + start
        stop = stop if stop >= 0 else self._a_bytes + stop
        return start, stop

    def _wslice(self, addr, value):
        start, stop = self._do_slice(addr)
        try:
            if len(value) == (stop - start):
                res = self.readwrite(start, value, False)
            else:
                raise RuntimeError('Slice must have same length as data')
        except TypeError:
            raise RuntimeError('Can only assign bytes/bytearray to a slice')
        return res

    def _rslice(self, addr):
        start, stop = self._do_slice(addr)
        buf = bytearray(stop - start)
        return self.readwrite(start, buf, True)

    # IOCTL protocol.
    def sync(self):  # Nothing to do for unbuffered devices. Subclass overrides.
        return

    def readblocks(self, blocknum, buf, offset=0):
        self.readwrite(offset + (blocknum << self._nbits), buf, True)

    def writeblocks(self, blocknum, buf, offset=0):
        self.readwrite(offset + (blocknum << self._nbits), buf, False)

    def ioctl(self, op, arg):  # ioctl calls: see extmod/vfs.h
        if op == 3:  # SYNCHRONISE
            self.sync()
            return
        if op == 4:  # BP_IOCTL_SEC_COUNT
            return self._a_bytes >> self._nbits
        if op == 5:  # BP_IOCTL_SEC_SIZE
            return self._block_size
        if op == 6:  # ERASE
            return 0

# Hardware agnostic base class for flash memory.

_RDBUFSIZE = const(32)  # Size of read buffer for erasure test


class FlashDevice(BlockDevice):

    def __init__(self, nbits, nchips, chip_size, sec_size):
        super().__init__(nbits, nchips, chip_size)
        self.sec_size = sec_size
        self._cache_mask = sec_size - 1  # For 4K sector size: 0xfff
        self._fmask = self._cache_mask ^ 0x3fffffff  # 4K -> 0x3ffff000
        self._buf = bytearray(_RDBUFSIZE)
        self._mvbuf = memoryview(self._buf)
        self._cache = bytearray(sec_size)  # Cache always contains one sector
        self._mvd = memoryview(self._cache)
        self._acache = 0  # Address in chip of byte 0 of current cached sector.
        # A newly cached sector, or one which has been flushed, will be clean,
        # so .sync() will do nothing. If cache is modified, dirty will be set.
        self._dirty = False

    def read(self, addr, mvb):
        nbytes = len(mvb)
        next_sec = self._acache + self.sec_size  # Start of next sector
        if addr >= next_sec or addr + nbytes <= self._acache:
            self.rdchip(addr, mvb)  # No data is cached: just read from device
        else:
            # Some of address range is cached
            boff = 0  # Offset into buf
            if addr < self._acache:  # Read data prior to cache from chip
                nr = self._acache - addr
                self.rdchip(addr, mvb[:nr])
                addr = self._acache  # Start of cached data
                nbytes -= nr
                boff += nr
            # addr now >= self._acache: read from cache.
            sa = addr - self._acache  # Offset into cache
            nr = min(nbytes, self._acache + self.sec_size - addr)  # No of bytes to read from cache
            mvb[boff : boff + nr] = self._mvd[sa : sa + nr]
            if nbytes - nr:  # Get any remaining data from chip
                self.rdchip(addr + nr, mvb[boff + nr : ])
        return mvb

    def sync(self):
        if self._dirty:
            self.flush(self._mvd, self._acache)  # Write out old data
        self._dirty = False
        return 0

# Performance enhancement: if cache intersects address range, update it first.
# Currently in this case it would be written twice. This may be rare.
    def write(self, addr, mvb):
        nbytes = len(mvb)
        acache = self._acache
        boff = 0  # Offset into buf.
        while nbytes:
            if (addr & self._fmask) != acache:
                self.sync()  # Erase sector and write out old data
                self._fill_cache(addr)  # Cache sector which includes addr
            offs = addr & self._cache_mask  # Offset into cache
            npage = min(nbytes, self.sec_size - offs)  # No. of bytes in current sector
            self._mvd[offs : offs + npage] = mvb[boff : boff + npage]
            self._dirty = True  # Cache contents do not match those of chip
            nbytes -= npage
            boff += npage
            addr += npage
        return mvb

    # Cache the sector which contains a given byte addresss. Save sector
    # start address.
    def _fill_cache(self, addr):
        addr &= self._fmask
        self.rdchip(addr, self._mvd)
        self._acache = addr
        self._dirty = False

    def initialise(self):
        self._fill_cache(0)

    # Return True if a sector is erased.
    def is_empty(self, addr, ev=0xff):
        mvb = self._mvbuf
        erased = True
        nbufs = self.sec_size // _RDBUFSIZE  # Read buffers per sector
        for _ in range(nbufs):
            self.rdchip(addr, mvb)
            if any(True for x in mvb if x != ev):
                erased = False
                break
            addr += _RDBUFSIZE
        return erased
