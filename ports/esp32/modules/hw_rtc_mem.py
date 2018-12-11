# -*- coding: utf-8 -*-

'''
The RTC has memory which survives warm reboots.

These functions allow to write a string in this memory.

See:
https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf
Page 25
0x3FF8_0000 8kBytes RTC FAST Memory  (doesn't survive reboot)
0x5000_0000 8kBytes RTC SLOW Memory  (survives reboot)

https://github.com/micropython/micropython/pull/4046


Tesing:
import hw_rtc_mem
hw_rtc_mem.writeRtcMemDict({'a': 'Hallo', 5: 4711})

import machine
machine.reset()

import hw_rtc_mem
hw_rtc_mem.readRtcMemDict()

ASSERT; The dictionary above must be displayed!

'''

import machine
import uctypes

MAGIC = 0x3F2A8C1D
ADDR = 0x50000000
OFFSET_STRING_BYTES = 4
OFFSET_MAGIC_BYTES = 8
ENCODING = 'utf-8'

class RtcMem:
  def writeRtcMem(self, s):
    '''
      Writes a string into the slow memory.
    '''
    b = bytes(s, ENCODING)
    l = len(s)
    l_aligned4 = l + 4 - l%4
    machine.mem32[ADDR+0] = l
    machine.mem32[ADDR+l_aligned4+OFFSET_MAGIC_BYTES] = MAGIC
    mem = uctypes.bytearray_at(ADDR+OFFSET_STRING_BYTES, l)
    mem[:l] = b

  def readRtcMem(self, default=''):
    '''
      Reads a string into the slow memory.
    '''
    l = machine.mem32[ADDR+0]
    if (l<=0) or (l>0x2000-OFFSET_MAGIC_BYTES):
      print('RTC-Mem UNITIALIZED (wrong size).')
      return default
    l_aligned4 = l + 4 - l%4
    if machine.mem32[ADDR+l_aligned4+OFFSET_MAGIC_BYTES] != MAGIC:
      print('RTC-Mem UNITIALIZED (magic number dismatch)')
      return default
    mem = uctypes.bytearray_at(ADDR+OFFSET_STRING_BYTES, l)
    return bytes(mem).decode(ENCODING)

  def writeRtcMemDict(self, d):
    self.writeRtcMem(str(d))

  def readRtcMemDict(self):
    s = self.readRtcMem(default='{}')
    d = eval(s)
    return d

objRtcMem = RtcMem()