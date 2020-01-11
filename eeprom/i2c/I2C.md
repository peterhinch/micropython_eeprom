# 1. A MicroPython I2C EEPROM driver

This driver supports chips from the 64KiB 25xx512 series and related chips with
smaller capacities.

From one to eight chips may be used to construct a nonvolatile memory module
with sizes upto 512KiB. The driver allows the memory either to be mounted in
the target filesystem as a disk device or to be addressed as an array of bytes.
Where multiple chips are used, all must be the same size.

The work was inspired by [this driver](https://github.com/dda/MicroPython.git).
This was written some five years ago. The driver in this repo employs some of
the subsequent improvements to MicroPython to achieve these advantages:
 1. It supports multiple EEPROM chips to configure a single array.
 2. Writes are up to 1000x faster by using ACK polling and page writes.
 3. Page access improves the speed of multi-byte reads.
 4. It is cross-platform.
 5. The I2C bus can be shared with other chips.
 6. It supports filesystem mounting.
 7. Alternatively it can support byte-level access using Python slice syntax.
 8. RAM allocations are reduced.

##### [Main readme](../../README.md)

# 2. Connections

Any I2C interface may be used. The table below assumes a Pyboard running I2C(2)
as per the test program. To wire up a single EEPROM chip, connect to a Pyboard
or ESP8266 as below. Any ESP8266 pins may be used, those listed below are as
used in the test program.

EEPROM Pin numbers assume a PDIP package (8 pin plastic dual-in-line).

| EEPROM |  PB | ESP8266 |
|:------:|:---:|:-------:|
| 1 A0   | Gnd |  Gnd    |
| 2 A1   | Gnd |  Gnd    |
| 3 A2   | Gnd |  Gnd    |
| 4 Vss  | Gnd |  Gnd    |
| 5 Sda  | Y10 |  12 D6  |
| 6 Scl  | Y9  |  13 D7  |
| 7 WPA1 | Gnd |  Gnd    |
| 8 Vcc  | 3V3 |  3V3    |

For multiple chips the address lines A0, A1 and A2 of each chip need to be
wired to 3V3 in such a way as to give each device a unique address. These must
start at zero and be contiguous:

| Chip no. | A2  | A1  | A0  |
|:--------:|:---:|:---:|:---:|
|    0     | Gnd | Gnd | Gnd |
|    1     | Gnd | Gnd | 3V3 |
|    2     | Gnd | 3V3 | Gnd |
|    3     | Gnd | 3V3 | 3V3 |
|    4     | 3V3 | Gnd | Gnd |
|    5     | 3V3 | Gnd | 3V3 |
|    6     | 3V3 | 3V3 | Gnd |
|    7     | 3V3 | 3V3 | 3V3 |

Multiple chips should have 3V3, Gnd, SCL and SDA lines wired in parallel.

The I2C interface requires pullups, typically 3.3KΩ to 3.3V although any value
up to 10KΩ will suffice. The Pyboard 1.x has these on board. The Pyboard D has
them only on I2C(1). Even if boards have pullups, additional externalresistors
will do no harm.

If you use a Pyboard D and power the EEPROMs from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
```
Other platforms may vary.

# 3. Files

 1. `eeprom_i2c.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `eep_i2c.py` Pyboard test programs for above.
 4. `wemos_i2c_eeprom.py` Test program using a Wemos D1 mini ESP8266 board.

Installation: copy files 1 and 2 (optionally 3 and/or 4) to the target
filesystem.

# 4. The device driver

The driver supports mounting the EEPROM chips as a filesystem. Initially the
device will be unformatted so it is necessary to issue code along these lines
to format the device. Code assumes one or more 64KiB devices and also assumes
the littlefs filesystem:

```python
import os
from machine import I2C
from eeprom_i2c import EEPROM, T24C512
eep = EEPROM(I2C(2), T24C512)
# Format the filesystem
os.VfsLfs2.mkfs(eep)  # Omit this to mount an existing filesystem
os.mount(eep,'/eeprom')
```
The above will reformat a drive with an existing filesystem: to mount an
existing filesystem simply omit the commented line.

Note that, at the outset, you need to decide whether to use the array as a
mounted filesystem or as a byte array. The filesystem is relatively small but
has high integrity owing to the hardware longevity. Typical use-cases involve
files which are frequently updated. These include files used for storing Python
objects serialised using Pickle/ujson or files holding a btree database.

The I2C bus must be instantiated using the `machine` module.

## 4.1 The EEPROM class

An `EEPROM` instance represents a logical EEPROM: this may consist of multiple
physical devices on a common I2C bus.

### 4.1.1 Constructor

This scans the I2C bus - if one or more correctly addressed chips are detected
an EEPROM array is instantiated. A `RuntimeError` will be raised if no device
is detected or if device address lines are not wired as described in
[Connections](./README.md#2-connections).

Arguments:  
 1. `i2c` Mandatory. An initialised master mode I2C bus created by `machine`.
 2. `chip_size=T24C512` The chip size in bits. The module provides constants
 `T24C64`, `T24C128`, `T24C256`, `T24C512` for the supported chip sizes.
 3. `verbose=True` If `True`, the constructor issues information on the EEPROM
 devices it has detected.
 4. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Larger arrays are faster, especially when writing: the driver uses the chip's
hardware page access where possible. Writing a page (128 bytes) takes the same
time (~5ms) as writing a single byte.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import I2C
from eeprom_i2c import EEPROM, T24C512
eep = EEPROM(I2C(2), T24C512)
eep[2000] = 42
print(eep[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import I2C
from eeprom_i2c import EEPROM, T24C512
eep = EEPROM(I2C(2), T24C512)
eep[2000:2002] = bytearray((42, 43))
print(eep[2000:2002])  # Returns a bytearray
```
Three argument slices are not supported: a third arg (other than 1) will cause
an exception. One argument slices (`eep[:5]` or `eep[13100:]`) and negative
args are supported. See [section 4.2](./I2C.md#42-byte-addressing-usage-example)
for a typical application.

#### 4.1.2.2 readwrite

This is a byte-level alternative to slice notation. It has the potential
advantage when reading of using a pre-allocated buffer. Arguments:  
 1. `addr` Starting byte address  
 2. `buf` A `bytearray` or `bytes` instance containing data to write. In the
 read case it must be a (mutable) `bytearray` to hold data read.  
 3. `read` If `True`, perform a read otherwise write. The size of the buffer
 determines the quantity of data read or written. A `RuntimeError` will be
 thrown if the read or write extends beyond the end of the physical space.

### 4.1.3 Other methods

#### The len operator

The size of the EEPROM array in bytes may be retrieved by issuing `len(eep)`
where `eep` is the `EEPROM` instance.

#### scan

Scans the I2C bus and returns the number of EEPROM devices detected.

Other than for debugging there is no need to call `scan()`: the constructor
will throw a `RuntimeError` if it fails to communicate with and correctly
identify the chip.

### 4.1.4 Methods providing the block protocol

These are provided by the base class. For the protocol definition see
[the pyb documentation](http://docs.micropython.org/en/latest/library/uos.html#uos.AbstractBlockDev)
also [here](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices).

`readblocks()`  
`writeblocks()`  
`ioctl()`

## 4.2 Byte addressing usage example

A sample application: saving a configuration dict (which might be large and
complicated):
```python
import ujson
from machine import I2C
from eeprom_i2c import EEPROM, T24C512
eep = EEPROM(I2C(2), T24C512)
d = {1:'one', 2:'two'}  # Some kind of large object
wdata = ujson.dumps(d).encode('utf8')
sl = '{:10d}'.format(len(wdata)).encode('utf8')
eep[0 : len(sl)] = sl  # Save data length in locations 0-9
start = 10  # Data goes in 10:
end = start + len(wdata)
eep[start : end] = wdata
```
After a power cycle the data may be read back. Instantiate `eep` as above, then
issue:
```python
slen = int(eep[:10].decode().strip())  # retrieve object size
start = 10
end = start + slen
d = ujson.loads(eep[start : end])
```
It is much more efficient in space and performance to store data in binary form
but in many cases code simplicity matters, especially where the data structure
is subject to change. An alternative to JSON is the pickle module. It is also
possible to use JSON/pickle to store objects in a filesystem.

# 5. Test program eep_i2c.py

This assumes a Pyboard 1.x or Pyboard D with EEPROM(s) wired as above. It
provides the following.

## 5.1 test()

This performs a basic test of single and multi-byte access to chip 0. The test
reports how many chips can be accessed. Existing array data will be lost. This
primarily tests the driver: as a hardware test it is not exhaustive.

## 5.2 full_test()

This is a hardware test. Tests the entire array. Fills each 128 byte page with
random data, reads it back, and checks the outcome. Existing array data will be
lost.

## 5.3 fstest(format=False)

If `True` is passed, formats the EEPROM array as a littlefs filesystem and
mounts the device on `/eeprom`. If no arg is passed it mounts the array and
lists the contents. It also prints the outcome of `uos.statvfs` on the array.

## 5.4 cptest()

Tests copying the source files to the filesystem. The test will fail if the
filesystem was not formatted. Lists the contents of the mountpoint and prints
the outcome of `uos.statvfs`.

## 5.5 File copy

A rudimentary `cp(source, dest)` function is provided as a generic file copy
routine for setup and debugging purposes at the REPL. The first argument is the
full pathname to the source file. The second may be a full path to the
destination file or a directory specifier which must have a trailing '/'. If an
OSError is thrown (e.g. by the source file not existing or the EEPROM becoming
full) it is up to the caller to handle it. For example (assuming the EEPROM is
mounted on /eeprom):

```python
cp('/flash/main.py','/eeprom/')
```

See `upysh` in [micropython-lib](https://github.com/micropython/micropython-lib.git)
for other filesystem tools for use at the REPL.
