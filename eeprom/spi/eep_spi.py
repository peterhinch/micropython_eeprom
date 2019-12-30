# eep_spi.py MicroPython test program for Microchip SPI EEPROM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

import uos
from machine import SPI, Pin
from eeprom_spi import EEPROM
# Add extra pins if using multiple chips
cspins = (Pin(Pin.board.Y5, Pin.OUT, value=1), Pin(Pin.board.Y4, Pin.OUT, value=1))

# Return an EEPROM array. Adapt for platforms other than Pyboard.
def get_eep(stm):
    if uos.uname().machine.split(' ')[0][:4] == 'PYBD':
        Pin.board.EN_3V3.value(1)
    if stm:
        eep = EEPROM(SPI(2, baudrate=5_000_000), cspins, 256)
    else:
        eep = EEPROM(SPI(2, baudrate=20_000_000), cspins)
    print('Instantiated EEPROM')
    return eep

# Dumb file copy utility to help with managing EEPROM contents at the REPL.
def cp(source, dest):
    if dest.endswith('/'):  # minimal way to allow
        dest = ''.join((dest, source.split('/')[-1]))  # cp /sd/file /eeprom/
    with open(source, 'rb') as infile:  # Caller should handle any OSError
        with open(dest,'wb') as outfile:  # e.g file not found
            while True:
                buf = infile.read(100)
                outfile.write(buf)
                if len(buf) < 100:
                    break

# ***** TEST OF DRIVER *****
def _testblock(eep, bs):
    d0 = b'this >'
    d1 = b'<is the boundary'
    d2 = d0 + d1
    garbage = b'xxxxxxxxxxxxxxxxxxx'
    start = bs - len(d0)
    end = start + len(garbage)
    eep[start : end] = garbage
    res = eep[start : end]
    if res != garbage:
        return 'Block test fail 1:' + str(list(res))
    end = start + len(d0)
    eep[start : end] = d0
    end = start + len(garbage)
    res = eep[start : end]
    if res != b'this >xxxxxxxxxxxxx':
        return 'Block test fail 2:' + str(list(res))
    start = bs
    end = bs + len(d1)
    eep[start : end] = d1
    start = bs - len(d0)
    end = start + len(d2)
    res = eep[start : end]
    if res != d2:
        return 'Block test fail 3:' + str(list(res))

def test(stm=False):
    eep = get_eep(stm)
    sa = 1000
    for v in range(256):
        eep[sa + v] = v
    for v in range(256):
        if eep[sa + v] != v:
            print('Fail at address {} data {} should be {}'.format(sa + v, eep[sa + v], v))
            break
    else:
        print('Test of byte addressing passed')
    data = uos.urandom(30)
    sa = 2000
    eep[sa:sa + 30] = data
    if eep[sa:sa + 30] == data:
        print('Test of slice readback passed')

    block = 256
    res = _testblock(eep, block)
    if res is None:
        print('Test block boundary {} passed'.format(block))
    else:
        print('Test block boundary {} fail'.format(block))
        print(res)
    block = eep._c_bytes
    if eep._a_bytes > block:
        res = _testblock(eep, block)
        if res is None:
            print('Test chip boundary {} passed'.format(block))
        else:
            print('Test chip boundary {} fail'.format(block))
            print(res)
    else:
        print('Test chip boundary skipped: only one chip!')

# ***** TEST OF FILESYSTEM MOUNT *****
def fstest(format=False, stm=False):
    eep = get_eep(stm)
    try:
        uos.umount('/eeprom')
    except OSError:
        pass
    # ***** CODE FOR FATFS *****
    #if format:
        #os.VfsFat.mkfs(eep)
    # ***** CODE FOR LITTLEFS *****
    if format:
        uos.VfsLfs2.mkfs(eep)
    # General
    try:
        uos.mount(eep,'/eeprom')
    except OSError:
        raise OSError("Can't mount device: have you formatted it?")
    print('Contents of "/": {}'.format(uos.listdir('/')))
    print('Contents of "/eeprom": {}'.format(uos.listdir('/eeprom')))
    print(uos.statvfs('/eeprom'))

def cptest(stm=False):  # Assumes pre-existing filesystem of either type
    eep = get_eep(stm)
    if 'eeprom' in uos.listdir('/'):
        print('Device already mounted.')
    else:
        try:
            uos.mount(eep,'/eeprom')
        except OSError:
            print('Fail mounting device. Have you formatted it?')
            return
        print('Mounted device.')
    cp('eep_spi.py', '/eeprom/')
    cp('eeprom_spi.py', '/eeprom/')
    print('Contents of "/eeprom": {}'.format(uos.listdir('/eeprom')))
    print(uos.statvfs('/eeprom'))


# ***** TEST OF HARDWARE *****
def full_test(stm=False):
    eep = get_eep(stm)
    page = 0
    for sa in range(0, len(eep), 256):
        data = uos.urandom(256)
        eep[sa:sa + 256] = data
        got = eep[sa:sa + 256]
        if got == data:
            print('Page {} passed'.format(page))
        else:
            print('Page {} readback failed.'.format(page))
            break
        page += 1
