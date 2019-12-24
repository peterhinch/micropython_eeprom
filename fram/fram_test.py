# fram_test.py MicroPython test program for Adafruit FRAM devices.

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2019 Peter Hinch

import uos
from machine import I2C, Pin
from fram_i2c import FRAM

# Return an FRAM array. Adapt for platforms other than Pyboard.
def get_fram():
    if uos.uname().machine.split(' ')[0][:4] == 'PYBD':
        Pin.board.EN_3V3.value(1)
    fram = FRAM(I2C(2))
    print('Instantiated FRAM')
    return fram

# Dumb file copy utility to help with managing FRAM contents at the REPL.
def cp(source, dest):
    if dest.endswith('/'):  # minimal way to allow
        dest = ''.join((dest, source.split('/')[-1]))  # cp /sd/file /fram/
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

def test():
    fram = get_fram()
    sa = 1000
    for v in range(256):
        fram[sa + v] = v
    for v in range(256):
        if fram[sa + v] != v:
            print('Fail at address {} data {} should be {}'.format(sa + v, fram[sa + v], v))
            break
    else:
        print('Test of byte addressing passed')
    data = uos.urandom(30)
    sa = 2000
    fram[sa:sa + 30] = data
    if fram[sa:sa + 30] == data:
        print('Test of slice readback passed')
    # On FRAM the only meaningful block test is on a chip boundary.
    block = fram._c_bytes
    if fram._a_bytes > block:
        res = _testblock(fram, block)
        if res is None:
            print('Test chip boundary {} passed'.format(block))
        else:
            print('Test chip boundary {} fail'.format(block))
            print(res)
    else:
        print('Test chip boundary skipped: only one chip!')

# ***** TEST OF FILESYSTEM MOUNT *****
def fstest(format=False):
    fram = get_fram()
    if format:
        uos.VfsFat.mkfs(fram)
    vfs=uos.VfsFat(fram)
    try:
        uos.mount(vfs,'/fram')
    except OSError:  # Already mounted
        pass
    print('Contents of "/": {}'.format(uos.listdir('/')))
    print('Contents of "/fram": {}'.format(uos.listdir('/fram')))
    print(uos.statvfs('/fram'))

def cptest():
    fram = get_fram()
    if 'fram' in uos.listdir('/'):
        print('Device already mounted.')
    else:
        vfs=uos.VfsFat(fram)
        try:
            uos.mount(vfs,'/fram')
        except OSError:
            print('Fail mounting device. Have you formatted it?')
            return
        print('Mounted device.')
    cp('fram_test.py', '/fram/')
    cp('fram_i2c.py', '/fram/')
    print('Contents of "/fram": {}'.format(uos.listdir('/fram')))
    print(uos.statvfs('/fram'))

# ***** TEST OF HARDWARE *****
def full_test():
    fram = get_fram()
    page = 0
    for sa in range(0, len(fram), 256):
        data = uos.urandom(256)
        fram[sa:sa + 256] = data
        if fram[sa:sa + 256] == data:
            print('Page {} passed'.format(page))
        else:
            print('Page {} readback failed.'.format(page))
        page += 1
