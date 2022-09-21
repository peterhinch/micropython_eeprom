# 1. MicroPython drivers for memory chips

These drivers support either byte level access or the littlefs filesystem.
Supported technologies are Flash, EEPROM, FRAM and SPIRAM.

Currently supported devices include technologies having superior performance
compared to flash. Resultant storage has much higher write endurance. In some
cases read and write access times may be shorter. EEPROM and FRAM chips have
much lower standby current than SD cards, benefiting micropower applications.

The drivers present a common API having the features listed below.

## 1.1 Features common to all drivers

The drivers have the following common features:
 1. Support for single or multiple chips on the same bus. Multiple chips are
 automatically configured as a single array.
 2. This can be accessed as an array of bytes, using Python slice syntax or via
 a `readwrite` method.
 3. Alternatively the array can be formatted and mounted as a filesystem using
 methods in the `uos` module. Any filesystem supported by the MicroPython build
 may be employed: FAT and littlefs have been tested. The latter is recommended.
 4. Drivers are portable: buses and pins should be instantiated using the
 `machine` module.
 5. Buses may be shared with other hardware. This assumes that the application
 pays due accord to differing electrical constraints such as baudrate.

## 1.2 Technologies

Currently supported technologies are SPIRAM (PSRAM), Flash, EEPROM, and FRAM
(ferroelectric RAM). The latter two are nonvolatile random access storage
devices with much higher endurance than flash memory. Flash has a typical
endurance of 10-100K writes per page. The figures for EEPROM and FRAM are 1-4M
and 10^12 writes respectively. In the case of the FAT filing system 1M page
writes probably corresponds to 1M filesystem writes because FAT repeatedly
updates the allocation tables in the low numbered sectors. Under `littlefs` I
would expect the endurance to be substantially better owing to its wear
levelling architecture; over-provisioning should enhance this.

SPIRAM has huge capacity and effectively infinite endurance. Unlike the other
technologies it is volatile: contents are lost after a power cycle.

## 1.3 Organisation of this repo

The directory structure is `technology/interface` where supported chips for a
given technology offer SPI and I2C interfaces; where only one interface exists
the `interface` subdirectory is omitted. The file `bdevice.py` is common to all
drivers and is in the root directory.

The link in the table below points to the docs relevant to the specific chip.
In that directory may be found test scripts which may need minor adaptation for
the host and interface in use. It is recommended to run these to verify the
hardware configuration.

## 1.4 Supported chips

These currently include Microchip and STM EEPROM chips and
[this Adafruit FRAM board](http://www.adafruit.com/product/1895). Note that the
largest EEPROM chip uses SPI: see [below](./README.md#2-choice-of-interface)
for a discussion of the merits and drawbacks of each interface.

Supported devices. Microchip manufacture each chip in different variants with
letters denoted by "xx" below. The variants cover parameters such as minimum
Vcc value and do not affect the API. There are two variants of the STM chip,
M95M02-DRMN6TP and M95M02-DWMN3TP/K. The latter has a wider temperature range.

In the table below the Interface column includes page size in bytes.  

| Manufacturer | Part      | Interface | Bytes   | Technology | Docs                          |
|:------------:|:---------:|:---------:|:-------:|:----------:|:-----------------------------:|
| Various      | Various   | SPI 4096  | <=32MiB |   Flash    | [FLASH.md](./flash/FLASH.md)  |
| STM          | M95M02-DR | SPI 256   | 256KiB  |   EEPROM   | [SPI.md](./eeprom/spi/SPI.md) |
| Microchip    | 25xx1024  | SPI 256   | 128KiB  |   EEPROM   | [SPI.md](./eeprom/spi/SPI.md) |
| Microchip    | 25xx512*  | SPI 256   |  64KiB  |   EEPROM   | [SPI.md](./eeprom/spi/SPI.md) |
| Microchip    | 24xx512   | I2C 128   |  64KiB  |   EEPROM   | [I2C.md](./eeprom/i2c/I2C.md) |
| Microchip    | 24xx256   | I2C 128   |  32KiB  |   EEPROM   | [I2C.md](./eeprom/i2c/I2C.md) |
| Microchip    | 24xx128   | I2C 128   |  16KiB  |   EEPROM   | [I2C.md](./eeprom/i2c/I2C.md) |
| Microchip    | 24xx64    | I2C 128   |   8KiB  |   EEPROM   | [I2C.md](./eeprom/i2c/I2C.md) |
| Microchip    | 24xx32    | I2C 32    |   4KiB  |   EEPROM   | [I2C.md](./eeprom/i2c/I2C.md) |
| Adafruit     | 4719      | SPI n/a   | 512KiB  |   FRAM     | [FRAM_SPI.md](./fram/FRAM_SPI.md) |
| Adafruit     | 4718      | SPI n/a   | 256KiB  |   FRAM     | [FRAM_SPI.md](./fram/FRAM_SPI.md) |
| Adafruit     | 1895      | I2C n/a   |  32KiB  |   FRAM     | [FRAM.md](./fram/FRAM.md)     |
| Adafruit     | 4677      | SPI n/a   |   8MiB  |   SPIRAM   | [SPIRAM.md](./spiram/SPIRAM.md) |

Parts marked * have been tested by users (see below).  
The SPIRAM chip is equivalent to Espressif ESP-PSRAM64H.

The flash driver now has the capability to support a variety of chips. The
following have been tested to date:

| Chip              | Size (MiB) |
|:-----------------:|:----------:|
| Cypress S25FL256L | 32         |
| Cypress S25FL128L | 16         |
| Cypress S25FL064L |  8         |
| Winbond W25Q32JV  |  4         |


It is likely that other chips with 4096 byte blocks will work but I am unlikely
to be able to support hardware I don't possess. Users should check datasheets
for compatibility.

### 1.4.1 Chips tested by users

If you have success with other chips please raise an issue and I will update
this doc. Please note the `cmd5` arg. It is essential to know whether a chip
uses 4 or 5 byte commands and to set this correctly otherise very confusing
behaviour results.

CAT24C256LI-G I2C EEPROM 32KiB tested by
[Julien Phalip](https://github.com/peterhinch/micropython_eeprom/issues/6#issuecomment-825801065).

Winbond W25Q128JV Flash 128MiB tested by
[mweber-bg](https://github.com/peterhinch/micropython_eeprom/issues/8#issuecomment-917603913).  
This requires setting `cmd5=False`.

Microchip 25LC512 SPI EEPROM 64KiB tested by
[ph1lj-6321](https://github.com/peterhinch/micropython_eeprom/issues/10).

## 1.5 Performance

FRAM and SPIRAM are truly byte-addressable: speed is limited only by the speed
of the I2C or SPI interface (SPI being much faster).

Reading from EEPROM chips is fast. Writing is slower, typically around 5ms.
However where multiple bytes are written, that 5ms applies to a page of data so
the mean time per byte is quicker by a factor of the page size (128 or 256
bytes depending on the device).

The drivers provide the benefit of page writing in a way which is transparent.
If you write a block of data to an arbitrary address, page writes will be used
to minimise total time.

In the case of flash, page writing is mandatory: a sector is written by first
erasing it, a process which is slow. This physical limitation means that the
driver must buffer an entire 4096 byte sector. This contrasts with FRAM and
EEPROM drivers where the buffering comprises a few bytes.

# 2. Choice of interface

The principal merit of I2C is to minimise pin count. It uses two pins
regardless of the number of chips connected. It requires pullup resistors on
those lines, although these may be provided on the target device. The
supported EEPROM devices limit expansion to a maximum of 8 chips on a bus.

SPI requires no pullups, but uses three pins plus one for each connected chip.
It is much faster than I2C, but in the case of EEPROMs the benefit is only
apparent on reads: write speed is limited by the EEPROM device. In principle
expansion is limited only by the number of available pins. (In practice
electrical limits may also apply).

The larger capacity chips generally use SPI.

# 3. Design details

A key aim of these drivers is support for littlefs. This requires the extended
block device protocol as described
[here](http://docs.micropython.org/en/latest/reference/filesystem.html) and
[in the uos doc](http://docs.micropython.org/en/latest/library/os.html).
This protocol describes a block structured API capable of handling offsets into
the block. It is therefore necessary for the device driver to deal with any
block structuring inherent in the hardware. The device driver must enable
access to varying amounts of data at arbitrary physical addresses.

These drivers achieve this by implementing a device-dependent `readwrite`
method which provides read and write access to arbitrary addresses, with data
volumes which can span page and chip boundaries. A benefit of this is that the
array of chips can be presented as a large byte array. This array is accessible
by Python slice notation: behaviour provided by the hardware-independent base
class.

A consequence of the above is that the page size in the ioctl does not have any
necessary connection with the memory hardware, so the drivers enable the value
to be specified as a constructor argument. Littlefs requires a minimum size of
128 bytes - 
[theoretically 104](https://github.com/ARMmbed/littlefs/blob/master/DESIGN.md).
The drivers only allow powers of 2: in principle 128 bytes could be used. The
default in MicroPython's littlefs implementation is 512 bytes and all testing
was done with this value. FAT requires 512 bytes minimum: FAT testing was done
with the same block size.

## 3.1 Developer Documentation

This [doc](./BASE_CLASSES.md) has information on the base classes for those
wishing to write drivers for other memory devices.

# 4. littlefs support

The test programs use littlefs and therefore require MicroPython V1.12 or
later. On platforms that don't support littlefs the options are either to adapt
the test programs for FAT (code is commented out) or to build firmware with
littlefs support. This can be done by passing `MICROPY_VFS_LFS2=1` to the
`make` command.
