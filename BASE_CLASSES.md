# 1. Base classes for memory device drivers

This doc is primarily to aid those wishing to use these base classes to write
drivers for additional memory devices. It describes the two classes in
`bdevice.py` namely `BlockDevice` and the subclass `FlashDevice`. Both provide
hardware-independent abstractions of memory devices. The base class provides
the API. This has the following characteristics:
 1. Support for single or multiple chips on the same bus. Multiple chips are
 automatically configured as a single byte array.
 2. The byte array can be accessed using Python slice syntax.
 3. Alternatively the array can be formatted and mounted as a filesystem using
 methods in the `uos` module. Any filesystem supported by the MicroPython build
 may be employed: FAT and littlefs have been tested. The latter is recommended.

The `BlockDevice` class supports byte-addressable technologies such as EEPROM
and FRAM. Such devices can be written on a single byte basis. Where a chip also
offers multi-byte writes this optimisation can be handled in the user driver:
see the EEPROM drivers for examples of this.

`FlashDevice` subclasses `BlockDevice` to support devices which must buffer a
sector of data for writing. The API continues to support byte addressing: this
is achieved by modifying the buffer contents and writing it out when necessary.

# 2. The BlockDevice class

The class provides these characteristics:
 1. An API which represents multiple physical devices as a single byte array.
 The physical means of achieving this is provided in the hardware subclass.
 2. An implementation of the `AbstractBlockDev` protocol with extended
 interface as required by littlefs as documented
 [here](http://docs.micropython.org/en/latest/library/uos.html).
 3. An API based on Python slice notation for byte level access to the array.
 4. Support for the `len` operator.

## 2.1 Constructor

Constructor args - mandatory, positional, integer
 1. `nbits` Block size reported to the filesystem expressed as a number of
 bits: the block size is `2^nbits`. The usual value is 9 (512 bit block).
 2. `nchips` Number of chips in the array.
 3. `chip_size` Size of each chip in bytes.

## 2.2 Necessary subclass support

The subclass must provide a method `readwrite` taking the following args:
 1. `addr` Address relative to the start of the array.
 2. `buf` A buffer holding data to write or to contain data to be read.
 3. `read` Boolean: `True` to read, `False` to write.

The amount of data read or written is defined by the length of the buffer.

Return value: the buffer.

The method must handle the case where a buffer crosses chip boundaries. This
involves physical accesses to each chip and reading or writing partial buffer
contents. Addresses are converted by the method to chip-relative addresses.

## 2.3 The `AbstractBlockDev` protocol

This is provided by the following methods:
 1. `sync()` In the `BlockDevice` class this does nothing. It is defined in the
 `FlashDevice` class [section 3.3](./BASE_CLASSES.md#33-methods).
 2. `readblocks(blocknum, buf, offset=0)` Converts the block address and offset
 to an absolute address into the array and calls `readwrite`.
 3. `writeblocks(blocknum, buf, offset=0` Works as above.
 4. `ioctl` This supports the following operands:

 3. `sync` Calls the `.sync()` method.
 4. `sector count` Returns `chip_size` * `nchips` // `block_size`
 5. `block size`  Returns block size calculated as in section 2.1.
 6. `erase` Necessary for correct filesystem operation: returns 0.

The drivers make no use of the block size: it exists only for filesystems. The
`readwrite` method hides any physical device structure presenting an array of
bytes. The specified block size must match the intended filesystem. Littlefs
requires >=128 bytes, FATFS requires >=512 bytes. All testing was done with 512
byte blocks.

## 2.4 Byte level access

This is provided by `__getitem__` and `__setitem__`. The `addr` arg can be an
integer or a slice, enabling the following syntax examples:
```python
a = eep[1000]  # Read a single byte
eep[1000] = 42  # write a byte
eep[1000:1004] = b'\x11\x22\x33\x44'  # Write 4 consecutive bytes
b = eep[1000:1004]  # Read 4 consecutive bytes
```
The last example necessarily performs allocation in the form of a buffer for
the resultant data. Applications can perform allocation-free reading by calling
the `readwrite` method directly.

## 2.5 The len operator

This returns the array size in bytes.

# 3. The FlashDevice class

By subclassing `BlockDevice`, `FlashDevice` provides the same API for flash
devices. At a hardware level reading is byte addressable in a similar way to
EEPROM and FRAM devices. These chips do not support writing arbitrary data to
individual byte addresses. Writing is done by erasing a block, then rewriting
it with new contents. To provide logical byte level writing it is necessary to
read and buffer the block containing the byte, update the byte, erase the block
and write out the buffer.

In practice this would be slow and inefficient - erasure is a slow process and
results in wear. The `FlashDevice` class defers writing the buffer until it is
necessary to buffer a different block.

The class caches a single sector. In currently supported devices this is 4KiB
of RAM. This is adequate for littlefs, however under FATFS wear can be reduced
by cacheing more than one sector. These drivers are primarily intended for
littlefs with its wear levelling design.

## 3.1 Constructor

Constructor args - mandatory, positional, integer
 1. `nbits` Block size reported to the filesystem expressed as a number of
 bits: the block size is `2^nbits`. The usual value is 9 (512 bit block).
 2. `nchips` Number of chips in the array.
 3. `chip_size` Size of each chip in bytes.
 4. `sec_size` Physical sector size of the device in bytes.

## 3.2 Necessary subclass support

A subclass supporting a flash device must provide the following methods:
 1. `readwrite(addr, buf, read)` Args as defined in section 2.2. This calls the
 `.read` or `.write` methods of `FlashDevice` as required.
 2. `rdchip(addr, mvb)` Args `addr`: address into the array, `mvb` a
 `memoryview` into a buffer for read data. This reads from the chip into the
 `memoryview`.
 3. `flush(cache, addr)` Args `cache` a buffer holding one sector of data,
 `addr` address into the array of the start of a physical sector. Erase the
 sector and write out the data in `cache`.

The constructor must call `initialise()` after the hardware has been
initialised to ensure valid cache contents.

## 3.3 Methods

 1. `read(addr, mvb`) Args `addr` address into array, `mvb` a `memoryview` into
 a buffer. Fills the `memoryview` with data read. If some or all of the data is
 cached, the cached data is provided.
 2. `write(addr, mvb`) Args `addr` address into array, `mvb` a `memoryview`
 into a buffer. If the address range is cached, the cache contents are updated.
 More generally the currently cached data is written out using `flush`, a new
 sector is cached, and the contents updated. Depending on the size of the data
 buffer this may occur multiple times.
 3. `sync()` This flushes the current cache. An optimisation is provided by the
 `._dirty` flag. This ensures that the cache is only flushed if its contents
 have been modified since it was last written out.
 4. `is_empty(addr, ev=0xff)` Arg: `addr` start address of a sector. Reads the
 sector returning `True` if all bytes match `ev`. Enables a subclass to avoid
 erasing a sector which is already empty.
 5. `initialise()` Called by the subclass constructor to populate the cache
 with the contents of sector 0.

# 4. References

[uos docs](http://docs.micropython.org/en/latest/library/uos.html)
[Custom block devices](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices)
[Littlefs](https://github.com/ARMmbed/littlefs/blob/master/DESIGN.md)
