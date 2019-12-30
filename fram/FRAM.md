# 1. A MicroPython FRAM driver

A driver to enable the Pyboard to access the Ferroelectric RAM (FRAM) board from
[Adafruit](http://www.adafruit.com/product/1895). FRAM is a technology offering
nonvolatile memory with extremely long endurance and fast access, avoiding the
limitations of Flash memory. Its endurance is specified as 10**12 writes,
contrasted with 10,000 which is the quoted endurance of the Pyboard's onboard
Flash memory. In data logging applications the latter can be exceeded relatively
rapidly. Flash writes can be slow because of the need for a sector erase: this
is not a fast process. FRAM is byte addressable and is not subject to this
limitation. The downside is limited capacity. Compared to a Micro SD card fitted
to the Pyboard it offers lower power consumption and longer endurance.

From one to eight boards may be used to construct a nonvolatile memory module
with size ranging from 32KiB to 256KiB. The driver allows the memory either to
be mounted in the Pyboard filesystem as a disk device or to be addressed as an
array of bytes.

For users interested in the technology [this](https://www.mouser.com/pdfDOCS/cypress-fram-whitepaper.pdf)
is worth reading. Clue: the FRAM cell contains no iron.

##### [Main readme](../README.md)

## 1.1 Changes compared to the old FRAM driver

API now matches other devices with support for slice syntax. Reduced RAM
allocation by virtue of `memorview` instances and pre-allocated buffers. Now
supports littlefs or FAT filesystems.

# 2. Connections

To wire up a single FRAM module, connect to the Pyboard as below (nc indicates
no connection).

| FRAM    |  L  |  R  |
|:-------:|:---:|:---:|
| Vcc     | 3V3 | 3V3 |
| Gnd     | GND | GND |
| WP      | nc  | nc  |
| SCL     | X9  | Y9  |
| SDA     | X10 | Y10 |
| A2      | nc  | nc  |
| A1      | nc  | nc  |
| A0      | nc  | nc  |

For multiple modules the address lines A0, A1 and A2 of each module need to be
wired to 3V3 in such a way as to give each device a unique address. These must
start at zero and be contiguous. Pins are internally pulled down, pins marked
`nc` may be left unconnected or linked to Gnd.
| Chip no. | A2  | A1  | A0  |
|:--------:|:---:|:---:|:---:|
|    0     | nc  | nc  | nc  |
|    1     | nc  | nc  | 3V3 |
|    2     | nc  | 3V3 | nc  |
|    3     | nc  | 3V3 | 3V3 |
|    4     | 3V3 | nc  | nc  |
|    5     | 3V3 | nc  | 3V3 |
|    6     | 3V3 | 3V3 | nc  |
|    7     | 3V3 | 3V3 | Gnd |

Multiple modules should have 3V3, Gnd, SCL and SDA lines wired in parallel.

The I2C interface requires pullups: these are provided on the Adafruit board.

If you use a Pyboard D and power the FRAMs from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
```
Other platforms may vary.

# 3. Files

 1. `fram_i2c.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `fram_test.py` Test programs for above.

Installation: copy files 1 and 2 (optionally 3) to the target filesystem.

# 4. The device driver

The driver supports mounting the FRAM chips as a filesystem. Initially the
device will be unformatted so it is necessary to issue code along these lines
to format the device. Code assumes one or more devices and also assumes the
littlefs filesystem:

```python
import os
from machine import I2C
from fram_i2c import FRAM
fram = FRAM(I2C(2))
# Format the filesystem
os.VfsLfs2.mkfs(fram)  # Omit this to mount an existing filesystem
os.mount(fram,'/fram')
```
The above will reformat a drive with an existing filesystem: to mount an
existing filesystem simply omit the commented line.

Note that, at the outset, you need to decide whether to use the array as a
mounted filesystem or as a byte array. The filesystem is relatively small but
has high integrity owing to the hardware longevity. Typical use-cases involve
files which are frequently updated. These include files used for storing Python
objects serialised using pickle/ujson or files holding a btree database.

The I2C bus must be instantiated using the `machine` module.

## 4.1 The FRAM class

An `FRAM` instance represents a logical FRAM: this may consist of multiple
physical devices on a common I2C bus.

### 4.1.1 Constructor

This scans the I2C bus and checks if one or more correctly addressed chips are
detected. Each chip is checked for correct ID data. A `RuntimeError` will occur
in case of error, e.g. bad ID, no device detected or device address lines not
wired as described in [Connections](./README.md#2-connections). If all is OK an
FRAM instance is created.

Arguments:  
 1. `i2c` Mandatory. An initialised master mode I2C bus created by `machine`.
 2. `verbose=True` If `True`, the constructor issues information on the FRAM
 devices it has detected.
 3. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Arrays will be somewhat faster owing to more efficient bus utilisation.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import I2C
from fram_i2c import FRAM
fram = FRAM(I2C(2))
fram[2000] = 42
print(fram[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import I2C
from fram_i2c import FRAM
fram = FRAM(I2C(2))
fram[2000:2002] = bytearray((42, 43))
print(fram[2000:2002])  # Returns a bytearray
```
Three argument slices are not supported: a third arg (other than 1) will cause
an exception. One argument slices (`fram[:5]` or `fram[32760:]`) and negative
args are supported.

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

#### The len() operator

The size of the FRAM array in bytes may be retrieved by issuing `len(fram)`
where `fram` is the `FRAM` instance.

#### scan

Scans the I2C bus and returns the number of FRAM devices detected.

Other than for debugging there is no need to call `scan()`: the constructor
will throw a `RuntimeError` if it fails to communicate with and correctly
identify the chip(s).

### 4.1.4 Methods providing the block protocol

These are provided by the base class. For the protocol definition see
[the pyb documentation](http://docs.micropython.org/en/latest/library/uos.html#uos.AbstractBlockDev)
also [here](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices).

`readblocks()`  
`writeblocks()`  
`ioctl()`

# 5. Test program fram_test.py

This assumes a Pyboard 1.x or Pyboard D with FRAM(s) wired as above. It
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

If `True` is passed, formats the FRAM array as a FAT filesystem and mounts
the device on `/fram`. If no arg is passed it mounts the array and lists the
contents. It also prints the outcome of `uos.statvfs` on the array.

## 5.4 cptest()

Tests copying the source files to the filesystem. The test will fail if the
filesystem was not formatted. Lists the contents of the mountpoint and prints
the outcome of `uos.statvfs`.

## 5.5 File copy

A rudimentary `cp(source, dest)` function is provided as a generic file copy
routine for setup and debugging purposes at the REPL. The first argument is the
full pathname to the source file. The second may be a full path to the
destination file or a directory specifier which must have a trailing '/'. If an
OSError is thrown (e.g. by the source file not existing or the FRAM becoming
full) it is up to the caller to handle it. For example (assuming the FRAM is
mounted on /fram):

```python
cp('/flash/main.py','/fram/')
```

See `upysh` in [micropython-lib](https://github.com/micropython/micropython-lib.git)
for other filesystem tools for use at the REPL.

# 6. References

[Adafruit board](http://www.adafruit.com/product/1895)
[Chip datasheet](https://cdn-learn.adafruit.com/assets/assets/000/043/904/original/MB85RC256V-DS501-00017-3v0-E.pdf?1500009796)
[Technology](https://www.mouser.com/pdfDOCS/cypress-fram-whitepaper.pdf)
