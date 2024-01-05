# 1. A MicroPython SPIRAM driver

A driver to enable MicroPython targets to access the SPIRAM (PSRAM) board from
Adafruit, namely [the 8MiB board](https://www.adafruit.com/product/4677). The
SPIRAM chip is equivalent to Espressif ESP-PSRAM64H. SPIRAM offers infinite
endurance and fast access but is volatile: its contents are lost on power down.

An arbitrary number of boards may be used to construct a memory array whose
size is a multiple of 8MiB. The driver allows the memory either to be mounted
in the host filesystem as a disk device or to be addressed as an array of
bytes.

##### [Main readme](../README.md)

# 2. Connections

Any SPI interface may be used. The table below assumes a Pyboard running SPI(2)
as per the test program. To wire up a single RAM chip, connect to a Pyboard as
below (n/c indicates no connection):

| Pin | Signal |  PB | Signal |
|:---:|:------:|:---:|:------:|
|  1  |  CE/   | Y5  | SS/    |
|  2  |  SO    | Y7  | MISO   |
|  3  |  SIO2  | n/c |        |
|  4  |  Vss   | Gnd | Gnd    |
|  5  |  SI    | Y8  | MOSI   |
|  6  |  SCLK  | Y6  | Sck    |
|  7  |  SIO3  | n/c |        |
|  8  |  Vcc   | 3V3 | 3V3    |

For multiple boards a separate CS pin must be assigned to each one: each pin
must be wired to a single board's CS line. Multiple boards should have Vin, Gnd,
SCK, MOSI and MISO lines wired in parallel.

If you use a Pyboard D and power the devices from the 3V3 output you will need
to enable the voltage rail by issuing:
```python
machine.Pin.board.EN_3V3.value(1)
time.sleep(0.1)  # Allow decouplers to charge
```
Other platforms may vary.

# 3. Files

 1. `spiram.py` Device driver.
 2. `bdevice.py` (In root directory) Base class for the device driver.
 3. `spiram_test.py` Test programs for above. Assumes two 8MiB boards with CS
 connected to pins Y4 and Y5 respectively. Adapt for other configurations.
 4. `fs_test.py` A torture test for littlefs.

Installation: copy files 1 and 2 to the target filesystem. `spiram_test.py`
has a function `test()` which provides quick verification of hardware, but
`cspins` and `get_spiram` at the start of the file may need adaptation to your
hardware.

# 4. The device driver

The driver supports mounting the SPIRAM chips as a filesystem. After power up
the device will be unformatted so it is necessary to issue code along these
lines to format the device. Code assumes one or more devices and also assumes
the littlefs filesystem:

```python
import os
from machine import SPI, Pin
from spiram import SPIRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
ram = SPIRAM(SPI(2, baudrate=25_000_000), cspins)
# Format the filesystem
os.VfsLfs2.mkfs(ram)  # Omit this to mount an existing filesystem
os.mount(ram,"/ram")
```
The above will reformat a drive with an existing filesystem: to mount an
existing filesystem simply omit the commented line.

Note that, at the outset, you need to decide whether to use the array as a
mounted filesystem or as a byte array. Typical use-cases involve temporary
files. These include files used for storing Python objects serialised using
pickle/ujson or files holding a btree database.

The SPI bus must be instantiated using the `machine` module. In the mode used
by the driver the chips are specified to a baudrate of 33MHz. I tested on a
Pyboard D, specifying 25MHz - this produced an actual baudrate of 18MHz.

## 4.1 The SPIRAM class

An `SPIRAM` instance represents a logical RAM: this may consist of multiple
physical devices on a common SPI bus.

### 4.1.1 Constructor

This checks each CS line for an attached board of the correct type and of the
specified size. A `RuntimeError` will occur in case of error, e.g. bad ID, no
device detected or size not matching that specified to the constructor. If all
is OK an SPIRAM instance is created.

Arguments:  
 1. `spi` Mandatory. An initialised SPIbus created by `machine`.
 2. `cspins` A list or tuple of `Pin` instances. Each `Pin` must be initialised
 as an output (`Pin.OUT`) and with `value=1` and be created by `machine`.
 3. `size=8192` Chip size in KiB.
 4. `verbose=True` If `True`, the constructor issues information on the SPIRAM
 devices it has detected.
 5. `block_size=9` The block size reported to the filesystem. The size in bytes
 is `2**block_size` so is 512 bytes by default.

### 4.1.2 Methods providing byte level access

It is possible to read and write individual bytes or arrays of arbitrary size.
Arrays will be somewhat faster owing to more efficient bus utilisation. Note
that, after power up, initial contents of RAM chips should be assumed to be
random.

#### 4.1.2.1 `__getitem__` and `__setitem__`

These provides single byte or multi-byte access using slice notation. Example
of single byte access:

```python
from machine import SPI, Pin
from spiram import SPIRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
ram = SPIRAM(SPI(2), cspins)
ram[2000] = 42
print(ram[2000])  # Return an integer
```
It is also possible to use slice notation to read or write multiple bytes. If
writing, the size of the slice must match the length of the buffer:
```python
from machine import SPI, Pin
from spiram import SPIRAM
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1),)
ram = SPIRAM(SPI(2), cspins)
ram[2000:2003] = "ABC"
print(ram[2000:2003])  # Returns a bytearray
```
Three argument slices are not supported: a third arg (other than 1) will cause
an exception. One argument slices (`ram[:5]` or `ram[32760:]`) and negative
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

The size of the RAM array in bytes may be retrieved by issuing `len(ram)`
where `ram` is the `SPIRAM` instance.

### 4.1.4 Methods providing the block protocol

These are provided by the base class. For the protocol definition see
[the pyb documentation](http://docs.micropython.org/en/latest/library/uos.html#uos.AbstractBlockDev)
also [here](http://docs.micropython.org/en/latest/reference/filesystem.html#custom-block-devices).

These methods exist purely to support the block protocol. They are undocumented:
their use in application code is not recommended.

`readblocks()`  
`writeblocks()`  
`ioctl()`

# 5. Test program spiram_test.py

This assumes a Pyboard 1.x or Pyboard D with SPIRAM(s) wired as above. It
provides the following.

## 5.1 test()

This performs a basic test of single and multi-byte access to chip 0. The test
reports how many chips can be accessed. Existing array data will be lost. This
primarily tests the driver: as a hardware test it is not exhaustive.

## 5.2 full_test()

This is a hardware test. Tests the entire array. Fills a 2048 byte block with
random data, reads it back, and checks the outcome before moving to the next
block. Existing data will be lost. This will detect serious hardware errors but
is not a comprehensive RAM chip test.

## 5.3 fstest()

Formats the RAM array as a littlefs filesystem and mounts the device on `/ram`.
Lists the contents (which will be empty) and prints the outcome of `os.statvfs`
on the array.

## 5.4 cptest()

Very simple filesystem test. If a filesystem is already mounted on `/ram`,
prints a message; otherwise formats the array with littlefs and mounts it.
Copies the source files to the filesystem, lists the contents of the mountpoint
and prints the outcome of `os.statvfs`.

## 5.5 File copy

A rudimentary `cp(source, dest)` function is provided as a generic file copy
routine for setup and debugging purposes at the REPL. The first argument is the
full pathname to the source file. The second may be a full path to the
destination file or a directory specifier which must have a trailing '/'. If an
OSError is thrown (e.g. by the source file not existing or the RAM becoming
full) it is up to the caller to handle it. For example (assuming the RAM is
mounted on /ram):

```python
cp('/flash/main.py','/ram/')
```

See the official `upysh` in
[micropython-lib](https://github.com/micropython/micropython-lib/tree/master/micropython/upysh)
for more fully developed filesystem tools for use at the REPL.

# 6. Test program fs_test.py

This is a torture test for littlefs. It creates many binary files of varying
length and verifies that they can be read back correctly. It rewrites files
with new lengths and checks that all files are OK. Run time is many minutes
depending on platform.
