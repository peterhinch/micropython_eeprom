# 1. A MicroPython Flash memory driver

This driver supports the Cypress S25FL256L and S25FL128L chips, providing 64MiB
and 32MiB respectively. These have 100K cycles of write endurance (compared to
10K for Pyboard Flash memory). These were the largest capacity available with a
sector size small enough for microcontroller use.

Multiple chips may be used to construct a single logical nonvolatile memory
module. The driver allows the memory either to be mounted in the target
filesystem as a disk device or to be addressed as an array of bytes.

The driver has the following attributes:
 1. It supports multiple Flash chips to configure a single array.
 2. It is cross-platform.
 3. The SPI bus can be shared with other chips.
 4. It supports filesystem mounting.
 5. Alternatively it can support byte-level access using Python slice syntax.

Flash technology requires a sector buffer. Consequently this driver uses 4KiB
of RAM (compared to minuscule amounts for the FRAM and EEPROM drivers). This is
an inevitable price for the large capacity of flash chips.

FAT and littlefs filesystems are supported but the latter is preferred owing to
its resilience and wear levelling characteristics.

Arguably byte level access on such large devices has few use cases other than
for facilitating effective hardware tests and for diagnostics.

##### [Main readme](../README.md)

# 2. Connections

Any SPI interface may be used. The table below assumes a Pyboard running SPI(2)
as per the test program. To wire up a single flash chip, connect to a Pyboard
as below. Pin numbers an 8 pin SOIC or WSON package. Inputs marked `nc` may be
connected to 3V3 or left unconnected.

| Flash | Signal  |  PB | Signal |
|:-----:|:-------:|:---:|:------:|
| 1     |  CS/    | Y5  | SS/    |
| 2     |  SO     | Y7  | MISO   |
| 3     |  WP/    | nc  | -      |
| 4     |  Vss    | Gnd | Gnd    |
| 5     |  SI     | Y8  | MOSI   |
| 6     |  SCK    | Y6  | SCK    |
| 7     |  RESET/ | nc  | -      |
| 8     |  Vcc    | 3V3 | 3V3    |

For multiple chips a separate CS pin must be assigned to each chip: each one
being wired to a single chip's CS line. The test program assumes a second chip
with CS connected to Y4. Multiple chips should have 3V3, Gnd, SCL, MOSI and
MISO lines wired in parallel.

If you use a Pyboard D and power the chips from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
```
Other platforms may vary but the Cypress chips require a 3.3V supply.

## 2.1 SPI Bus

The devices support baudrates up to 50MHz. In practice MicroPython targets do
not support such high rates. The test programs specify 20MHz, but in practice
the Pyboard D delivers 15MHz. Testing was done at this rate. In testing a
"lashup" breadboard was unsatisfactory: a problem entirely fixed with a PCB.
Bus lines should be short and direct.

# 3. Files

 1. `flash_spi.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `flash_test.py` Test programs for above.
 4. `littlefs_test.py` Torture test for the littlefs filesystem on the flash
 array. Requires `flash_test.py` which it uses for hardware configuration.
 5. `wemos_flash.py` Test program running on a Wemos D1 Mini ESP8266 board.

Installation: copy files 1 and 2 (3 - 5 are optional) to the target filesystem.
The `flash_test` script assumes two S25FL256L chips connected to SPI(2) with
CS/ pins wired to Pyboard pins Y4 and Y5. The `get_device` function may be
adapted for other setups and is shared with `littlefs_test`.

For a quick check of hardware issue:
```python
import flash_test
flash_test.test()
```

# 4. The device driver

The driver supports mounting the Flash chips as a filesystem. Initially the
device will be unformatted so it is necessary to issue code along these lines
to format the device. Code assumes two devices and the (recommended) littlefs
filesystem:

```python
import os
from machine import SPI, Pin
from flash_spi import FLASH
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
flash = FLASH(SPI(2, baudrate=20_000_000), cspins)
# Format the filesystem
os.VfsLfs2.mkfs(flash)  # Omit this to mount an existing filesystem
os.mount(flash,'/fl_ext')
```
The above will reformat a drive with an existing filesystem erasing all files:
to mount an existing filesystem omit the commented line.

Note that, at the outset, you need to decide whether to use the array as a
mounted filesystem or as a byte array. Most use cases for flash will require a
filesystem, although byte level reads may be used to debug filesystem issues.

The SPI bus must be instantiated using the `machine` module.

## 4.1 The FLASH class

An `FLASH` instance represents a logical flash memory: this may consist of
multiple physical devices on a common SPI bus.

### 4.1.1 Constructor

This tests each chip in the list of chip select pins - if a chip is detected on
each chip select line a flash array is instantiated. A `RuntimeError` will be
raised if a device is not detected on a CS line. The test has no effect on
the array contents.

Arguments:  
 1. `spi` Mandatory. An initialised SPI bus created by `machine`.
 2. `cspins` A list or tuple of `Pin` instances. Each `Pin` must be initialised
 as an output (`Pin.OUT`) and with `value=1` and be created by `machine`.
 3. `size=16384` Chip size in KiB. Set to 32768 for the S25FL256L chip.
 4. `verbose=True` If `True`, the constructor issues information on the flash
 devices it has detected.
 5. `sec_size=4096` Chip sector size.
 6. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Because of the very large size of the supported devices this mode is most
likely to be of use for debugging. When writing in this mode it is necessary to
be aware of the characteristics of flash devices. The memory is structured in
blocks of 4096 bytes. To write a byte a block has to be read into RAM and the
byte changed. The block on chip is erased then the new data written out. This
process is slow (~300ms). In practice writing is deferred until it is necessary
to access a different block: it is therefore faster to write data to
consecutive addresses. Writing individual bytes to random addresses would be
slow and cause undue wear because of the repeated need to erase and write
sectors.

The examples below assume two devices, one with `CS` connected to Pyboard pin
Y4 and the other with `CS` connected to Y5.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import SPI, Pin
from flash_spi import FLASH
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
flash = FLASH(SPI(2, baudrate=20_000_000), cspins)
flash[2000] = 42
print(flash[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import SPI, Pin
from flash_spi import FLASH
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))
flash = FLASH(SPI(2, baudrate=20_000_000), cspins)
flash[2000:2002] = bytearray((42, 43))
print(flash[2000:2002])  # Returns a bytearray
```
Three argument slices are not supported: a third arg (other than 1) will cause
an exception. One argument slices (`flash[:5]` or `flash[13100:]`) and negative
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

#### sync

This causes the cached sector to be written to the device. In normal filesystem
use this need not be called. If byte-level writes have been performed it should
be called prior to power down.

#### The len operator

The size of the flash array in bytes may be retrieved by issuing `len(flash)`
where `flash` is the `FLASH` instance.

#### scan

Activate each chip select in turn checking for a valid device and returns the
number of flash devices detected. A `RuntimeError` will be raised if any CS
pin does not correspond to a valid chip.

Other than for debugging there is no need to call `scan()`: the constructor
will throw a `RuntimeError` if it fails to communicate with and correctly
identify each chip.

#### erase

Erases the entire array. Beware: this takes many minutes.

### 4.1.4 Methods providing the block protocol

These are provided by the base class. For the protocol definition see
[the pyb documentation](http://docs.micropython.org/en/latest/library/uos.html#uos.AbstractBlockDev)
also [here](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices).

`readblocks()`  
`writeblocks()`  
`ioctl()`

# 5. Test program flash_spi.py

This assumes a Pyboard 1.x or Pyboard D with two chips wired to SPI(2) as
above with chip selects connected to pins `Y4` and `Y5`. It provides the
following.

## 5.1 test()

This performs a basic test of single and multi-byte access to chip 0. The test
reports how many chips can be accessed. Existing array data will be lost. This
primarily tests the driver: as a hardware test it is not exhaustive. It does
provide a quick verification that all chips can be accessed.

## 5.2 full_test(count=10)

This is a hardware test. Tests the entire array. Creates an array of 256 bytes
of random data and writes it to a random address. After synchronising the cache
with the hardware, reads it back, and checks the outcome. Existing array data
will be lost. The arg determines the number of passes.

## 5.3 fstest(format=False)

If `True` is passed, formats the flash array as a littlefs filesystem deleting
existing contents. In both cases of the arg it mounts the device on `/fl_ext`
lists the contents of the mountpoint. It also prints the outcome of
`uos.statvfs` on the mountpoint.

## 5.4 cptest()

Tests copying the source files to the filesystem. The test will fail if the
filesystem was not formatted. Lists the contents of the mountpoint and prints
the outcome of `uos.statvfs`.

## 5.5 File copy

A rudimentary `cp(source, dest)` function is provided as a generic file copy
routine for setup and debugging purposes at the REPL. The first argument is the
full pathname to the source file. The second may be a full path to the
destination file or a directory specifier which must have a trailing '/'. If an
OSError is thrown (e.g. by the source file not existing or the flash becoming
full) it is up to the caller to handle it. For example (assuming the flash is
mounted on /fl_ext):

```python
cp('/flash/main.py','/fl_ext/')
```

See `upysh` in [micropython-lib](https://github.com/micropython/micropython-lib.git)
for other filesystem tools for use at the REPL.
