# 1. A MicroPython SPI FRAM driver

A driver to enable the Pyboard to access Ferroelectric RAM (FRAM) boards from
Adafruit, namely [the 256KiB board](https://www.adafruit.com/product/4718) and
[the 512KiB board](https://www.adafruit.com/product/4719). FRAM is a technology
offering nonvolatile memory with extremely long endurance and fast access,
avoiding the
limitations of Flash memory. Its endurance is specified as 10**13 writes,
contrasted with 10,000 which is the quoted endurance of the Pyboard's onboard
Flash memory. In data logging applications the latter can be exceeded relatively
rapidly. Flash writes can be slow because of the need for a sector erase: this
is not a fast process. FRAM is byte addressable and is not subject to this
limitation. Compared to a Micro SD card fitted to the Pyboard it offers lower
power consumption and longer endurance, albeit at a smaller capacity.

An arbitrary number of boards may be used to construct a nonvolatile memory
array with size from 256KiB upwards. The driver allows the memory either to be
mounted in the Pyboard filesystem as a disk device or to be addressed as an
array of bytes.

For users interested in the technology [this](https://www.mouser.com/pdfDOCS/cypress-fram-whitepaper.pdf)
is worth reading. Clue: the FRAM cell contains no iron.

##### [Main readme](../README.md)

# 2. Connections

Any SPI interface may be used. The table below assumes a Pyboard running SPI(2)
as per the test program. To wire up a single FRAM BOARD, connect to a Pyboard
as below (n/c indicates no connection):

| FRAM Signal |  PB | Signal |
|:-----------:|:---:|:------:|
|       Vin   | 3V3 | 3V3    |
|       3V3   | n/c | n/c    |
|       Gnd   | Gnd | Gnd    |
|       SCK   | Y6  | SCK    |
|       MISO  | Y7  | MISO   |
|       MOSI  | Y8  | MOSI   |
|       CS    | Y5  | SS/    |
|       WP/   | n/c | n/c    |
|       HOLD/ | n/c | n/c    |

For multiple boards a separate CS pin must be assigned to each one: each pin
must be wired to a single board's CS line. Multiple boards should have Vin, Gnd,
SCK, MOSI and MISO lines wired in parallel.

If you use a Pyboard D and power the devicess from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
time.sleep(0.1)  # Allow decouplers to charge
```
Other platforms may vary.

At the time of writing schematics for the Adafruit boards were unavailable but
measurement indicated that CS, WP/ and HOLD/ are pulled up with 10KΩ. It is
therefore safe to leave WP/ and HOLD/ unconnected, and CS will behave properly
at power-up.

# 3. Files

 1. `fram_spi.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `fram_spi_test.py` Test programs for above. Assumes two 512KiB boards with
 CS connected to pins Y4 and Y5 respectively. Adapt for other configurations.
 4. `fram_fs_test.py` A torture test for littlefs.

Installation: copy files 1 and 2 to the target filesystem. `fram_spi_test.py`
has a function `test()` which provides quick verification of hardware, but
`cspins` and `get_fram` at the start of the file may need adaptation to your
hardware.

# 4. The device driver

The driver supports mounting the FRAM chips as a filesystem. Initially the
device will be unformatted so it is necessary to issue code along these lines
to format the device. Code assumes one or more devices and also assumes the
littlefs filesystem:

```python
import os
from machine import SPI, Pin
from fram_spi import FRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
fram = FRAM(SPI(2, baudrate=25_000_000), cspins)
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

The SPI bus must be instantiated using the `machine` module. The chips are
specified to a baudrate of 40MHz. I tested on a Pyboard D, specifying 25MHz -
this produced an actual baudrate of 18MHz.

## 4.1 The FRAM class

An `FRAM` instance represents a logical FRAM: this may consist of multiple
physical devices on a common SPI bus.

### 4.1.1 Constructor

This checks each CS line for an attached board of the correct type and of the
specified size. A `RuntimeError` will occur in case of error, e.g. bad ID, no
device detected or size not matching that specified to the constructor. If all
is OK an FRAM instance is created.

Arguments:  
 1. `spi` Mandatory. An initialised SPIbus created by `machine`.
 2. `cspins` A list or tuple of `Pin` instances. Each `Pin` must be initialised
 as an output (`Pin.OUT`) and with `value=1` and be created by `machine`.
 3. `size=512` Chip size in KiB.
 4. `verbose=True` If `True`, the constructor issues information on the FRAM
 devices it has detected.
 5. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Arrays will be somewhat faster owing to more efficient bus utilisation.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import SPI, Pin
from fram_spi import FRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
fram = FRAM(SPI(2), cspins)
fram[2000] = 42
print(fram[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import SPI, Pin
from fram_spi import FRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
fram = FRAM(SPI(2), cspins)
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

### 4.1.4 Methods providing the block protocol

These are provided by the base class. For the protocol definition see
[the pyb documentation](http://docs.micropython.org/en/latest/library/uos.html#uos.AbstractBlockDev)
also [here](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices).

`readblocks()`  
`writeblocks()`  
`ioctl()`

# 5. Test program fram_spi_test.py

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

# 6. Low power operation

In the absence of an SPI clock signal the chip is specified to draw 50μA max.
This can be reduced to 8μA max by issuing a sleep command. Code to support this
is provided in `fram_spi.py` but is commented out; it is a somewhat specialised
requirement.

# 7. References

[256KiB Adafruit board](http://www.adafruit.com/product/4718)
[512KiB Adafruit board](http://www.adafruit.com/product/4719)
[256KiB Chip datasheet](https://cdn-shop.adafruit.com/product-files/4718/4718_MB85RS2MTA.pdf)
[512KiB Chip datasheet](https://cdn-shop.adafruit.com/product-files/4719/4719_MB85RS4MT.pdf)
[Technology](https://www.mouser.com/pdfDOCS/cypress-fram-whitepaper.pdf)
