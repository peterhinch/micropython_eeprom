# 1. A MicroPython SPI EEPROM driver

This driver supports the Microchip 25xx1024 series of 128KiB SPI EEPROMs and
the STM M95M02-DR 256KiB device. These have 1M and 4M cycles of write endurance
respectively (compared to 10K for Pyboard Flash memory).

Multiple chips may be used to construct a single logical nonvolatile memory
module. The driver allows the memory either to be mounted in the target
filesystem as a disk device or to be addressed as an array of bytes.

The driver has the following attributes:
 1. It supports multiple EEPROM chips to configure a single array.
 2. For performance, writes use page writes where possible.
 3. Page access improves the speed of multi-byte reads.
 4. It is cross-platform.
 5. The SPI bus can be shared with other chips.
 6. It supports filesystem mounting.
 7. Alternatively it can support byte-level access using Python slice syntax.
 8. RAM allocations are minimised. Buffer sizes are tiny.

##### [Main readme](../../README.md)

## 1.1 This document

Code samples assume one or more Microchip devices. If using the STM chip the
SPI baudrate should be 5MHz and the chip size must be specified to the `EEPROM`
constructor, e.g.:
```python
eep = EEPROM(SPI(2, baudrate=5_000_000), cspins, 256)
```

# 2. Connections

Any SPI interface may be used. The table below assumes a Pyboard running SPI(2)
as per the test program. To wire up a single EEPROM chip, connect to a Pyboard
as below. Pin numbers assume a PDIP package (8 pin plastic dual-in-line) for
the Microchip device and 8 pin SOIC for the STM chip.

| EEPROM  | Signal |  PB | Signal |
|:-------:|:------:|:---:|:------:|
| 1       |  CS    | Y5  | SS/    |
| 2       |  SO    | Y7  | MISO   |
| 3       |  WP/   | 3V3 | 3V3    |
| 4       |  Vss   | Gnd | Gnd    |
| 5       |  SI    | Y8  | MOSI   |
| 6       |  SCK   | Y6  | SCK    |
| 7       |  HOLD/ | 3V3 | 3V3    |
| 8       |  Vcc   | 3V3 | 3V3    |

For multiple chips a separate CS pin must be assigned to each chip: each one
must be wired to a single chip's CS line. Multiple chips should have 3V3, Gnd,
SCL, MOSI and MISO lines wired in parallel.

If you use a Pyboard D and power the EEPROMs from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
```
Other platforms may vary.

## 2.1 SPI Bus

The Microchip devices support baudrates up to 20MHz. The STM chip has a maximum
of 5MHz. Both support the default SPI mode: simply specify the baudrate to the
constructor.

The SPI bus is fast: wiring should be short and direct.

# 3. Files

 1. `eeprom_spi.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `eep_spi.py` Test programs for above.

Installation: copy files 1 and 2 (optionally 3) to the target filesystem.

# 4. The device driver

The driver supports mounting the EEPROM chips as a filesystem. Initially the
device will be unformatted so it is necessary to issue code along these lines
to format the device. Code assumes two Microchip devices and also assumes the
littlefs filesystem:

```python
import os
from machine import SPI, Pin
from eeprom_spi import EEPROM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
eep = EEPROM(SPI(2, baudrate=20_000_000), cspins)
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

The SPI bus must be instantiated using the `machine` module.

## 4.1 The EEPROM class

An `EEPROM` instance represents a logical EEPROM: this may consist of multiple
physical devices on a common SPI bus.

### 4.1.1 Constructor

This test each chip in the list of chip select pins - if a chip is detected on
each chip select line an EEPROM array is instantiated. A `RuntimeError` will be
raised if a device is not detected on a CS line.

Arguments:  
 1. `spi` Mandatory. An initialised SPI bus created by `machine`.
 2. `cspins` A list or tuple of `Pin` instances. Each `Pin` must be initialised
 as an output (`Pin.OUT`) and with `value=1` and be created by `machine`.
 3. `size=128` Chip size in KiB. Set to 256 for the STM chip.
 4. `verbose=True` If `True`, the constructor issues information on the EEPROM
 devices it has detected.
 5. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

SPI baudrate: The 25LC1024 supports baudrates of upto 20MHz. If this value is
specified the platform will produce the highest available frequency not
exceeding this figure. Note that the STM chip has a maximum rate of 5MHz.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Larger arrays are faster, especially when writing: the driver uses the chip's
hardware page access where possible. Writing a page (256 bytes) takes the same
time as writing a single byte. This is 6ms max on the Microchip and 10ms max on
the STM.

The examples below assume two devices, one with `CS` connected to Pyboard pin
Y4 and the other with `CS` connected to Y5.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import SPI, Pin
from eeprom_spi import EEPROM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
eep = EEPROM(SPI(2, baudrate=20_000_000), cspins)
eep[2000] = 42
print(eep[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import SPI, Pin
from eeprom_spi import EEPROM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
eep = EEPROM(SPI(2, baudrate=20_000_000), cspins)
eep[2000:2002] = bytearray((42, 43))
print(eep[2000:2002])  # Returns a bytearray
```
Three argument slices are not supported: a third arg (other than 1) will cause
an exception. One argument slices (`eep[:5]` or `eep[13100:]`) and negative
args are supported. See [section 4.2](./SPI.md#42-byte-addressing-usage-example)
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

Activate each chip select in turn checking for a valid device and returns the
number of EEPROM devices detected. A `RuntimeError` will be raised if any CS
pin does not correspond to a valid chip.

Other than for debugging there is no need to call `scan()`: the constructor
will throw a `RuntimeError` if it fails to communicate with and correctly
identify the chip.

#### erase

Erases the entire array. Available only on the Microchip device.

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
from machine import SPI, Pin
from eeprom_spi import EEPROM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
eep = EEPROM(SPI(2, baudrate=20_000_000), cspins)
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

# 5. Test program eep_spi.py

This assumes a Pyboard 1.x or Pyboard D with two EEPROMs wired to SPI(2) as
above with chip selects connected to pins `Y4` and `Y5`. It provides the
following. In all cases the stm arg should be `True` if using the STM chips.

## 5.1 test(stm=False)

This performs a basic test of single and multi-byte access to chip 0. The test
reports how many chips can be accessed. Existing array data will be lost. This
primarily tests the driver: as a hardware test it is not exhaustive.

## 5.2 full_test(stm=False)

This is a hardware test. Tests the entire array. Fills each 256 byte page with
random data, reads it back, and checks the outcome. Existing array data will be
lost.

## 5.3 fstest(format=False, stm=False)

If `True` is passed, formats the EEPROM array as a littlefs filesystem and
mounts the device on `/eeprom`. If no arg is passed it mounts the array and
lists the contents. It also prints the outcome of `uos.statvfs` on the array.

## 5.4 cptest(stm=False)

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
