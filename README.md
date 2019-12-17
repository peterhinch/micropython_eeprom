# 1. MicroPython drivers for nonvolatile memory

These drivers support nonvolatile memory chips.

Currently supported devices use technologies having superior performance
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
 may be employed.
 4. Drivers are portable: buses and pins should be instantiated using the
 `machine` module.
 5. Buses may be shared with other hardware. This assumes that the application
 pays due accord to differing electrical constraints such as baudrate.

## 1.2 Technologies

Currently supported technologies are EEPROM and FRAM (ferroelectric RAM). These
are nonvolatile random access storage devices with much higher endurance than
flash memory. Flash has a typical endurance of 10K writes per page. The figures
for EEPROM and FRAM are 1M and 10^12 writes respectively. In the case of the
FAT filing system 1M page writes probably corresponds to 1M filesystem writes
because FAT repeatedly updates the allocation tables in the low numbered
sectors. If `littlefs` is used I would expect the endurance to be substantially
better owing to its wear levelling architecture.

## 1.3 Supported chips

These currently include Microchip EEPROM chips and
[this Adafruit FRAM board](http://www.adafruit.com/product/1895). Note that the
largest EEPROM chip uses SPI: see [below](./README.md#2-choice-of-interface)
for a discussion of the merits and drawbacks of each interface.

Supported devices. Microchip manufacture each chip in different variants with
letters denoted by "xx" below. The variants cover parameters such as minimum
Vcc value and do not affect the API.

In the table below the Interface column includes page size in bytes.  
| Manufacturer | Part     | Interface | Bytes  |
|:------------:|:--------:|:---------:|:------:|
| Microchip    | 25xx1024 | SPI 256   | 128KiB |
| Microchip    | 24xx512  | I2C 128   |  64KiB |
| Microchip    | 24xx256  | I2C 128   |  32KiB |
| Microchip    | 24xx128  | I2C 128   |  16KiB |
| Microchip    | 24xx64   | I2C 128   |   8KiB |
| Adafruit     | 1895     | I2C n/a   |  32KiB |



| Manufacturer | Part     | Interface | Bytes  | Technology | Docs      |
|:------------:|:--------:|:---------:|:------:|:----------:|:---------:|
| Microchip    | 25xx1024 | SPI 256   | 128KiB |   EEPROM   | [SPI.md]  |
| Microchip    | 24xx512  | I2C 128   |  64KiB |   EEPROM   | [I2C.md]  |
| Microchip    | 24xx256  | I2C 128   |  32KiB |   EEPROM   | [I2C.md]  |
| Microchip    | 24xx128  | I2C 128   |  16KiB |   EEPROM   | [I2C.md]  |
| Microchip    | 24xx64   | I2C 128   |   8KiB |   EEPROM   | [I2C.md]  |
| Adafruit     | 1895     | I2C n/a   |  32KiB |   FRAM     | [FRAM.md] |

Documentation:  
[SPI.md](./spi/SPI.md)  
[I2C.md](./i2c/I2C.md)  
[FRAM.md](./fram/FRAM.md)  

## 1.4 Performance

FRAM is truly byte-addressable: its speed is limited only by the speed of the
I2C interface.

Reading from EEPROM chips is fast. Writing is slower, typically around 5ms.
However where multiple bytes are written, that 5ms applies to a page of data so
the mean time per byte is quicker by a factor of the page size (128 or 256
bytes depending on the device).

The drivers provide the benefit of page writing in a way which is transparent.
If you write a block of data to an arbitrary address, page writes will be used
to minimise total time.

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

In the case of the Microchip devices supported, the SPI chip is larger at
128KiB compared to a maximum of 64KiB in the I2C range.

# 3. Design details

The fact that the API enables accessing blocks of data at arbitrary addresses
implies that the handling of page addressing is done in the driver. This
contrasts with drivers intended only for filesystem access. These devolve the
detail of page addressing to the filesystem by specifying the correct page size
in the ioctl and (if necessary) implementing a block erase method.

The nature of the drivers in this repo implies that the block address in the
ioctl is arbitrary.
