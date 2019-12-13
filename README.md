# MicroPython EEPROM drivers

EEPROM is a form of nonvolatile random access storage.

These drivers enable MicroPython to access Microchip EEPROM devices. There are
two variants, one for chips based on the I2C interface and a second for a 1MBit
SPI chip.

Unlike flash memory, EEPROMs may be written on a byte addressable basis. Their
endurance is specified as a million writes compared to the 10K typical of most
flash memory. In applications such as data logging the latter can be exceeded
relatively rapidly. For extreme endurance ferroelectric RAM has almost infinite
endurance but at higher cost per byte. See [this driver](https://github.com/peterhinch/micropython-fram).

Reading from EEPROM chips is fast. Writing is slower, typically around 5ms.
However where multiple bytes are written, that 5ms applies to a page of data so
the mean time per byte is quicker by a factor of the page size (128 or 256
bytes depending on the device).

The drivers support creating multi-chip arrays. In the case of I2C chips, up to
eight devices may share the bus. In the case of SPI expansion has no absolute
limit as each chip has its own chip select line.

Devices or arrays of devices may be mounted as a filesystem or may be treated
as an array of bytes.

For I2C devices see [I2C.md](./i2c/I2C.md). For SPI see [SPI.md](./spi/SPI.md).

# Choice of interface

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
