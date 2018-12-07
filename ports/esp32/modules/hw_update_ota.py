# -*- coding: utf-8 -*-

import uos
import machine

FILENAME_UPDATE_FINISHED = 'update_finished'

listFiles = uos.listdir()

pin_button = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
pin_led = machine.Pin(22, machine.Pin.OUT)
pwm = None

def pwmLed(freq=10):
  global pwm
  pmw = machine.PWM(pin_led, freq=freq)

def setLed(bOn=True):
  global pwm
  if pwm != None:
    pwm.deinit()
  pin_led.value(bOn)

def isFilesystemEmpty():
  return len(listFiles) == 0

def reboot(strReason):
  print(strReason)
  setLed(bOn=False)
  machine.reset()

def isUpdateFinished():
  return FILENAME_UPDATE_FINISHED in listFiles

## States of the button

def isButtonPressed():
  '''Returns True if the Button is pressed.'''
  return pin_button.value() == 0

def isPowerOnBoot():
  '''Returns True if power on. False if reboot by software or watchdog.'''
  return machine.PWRON_RESET == machine.reset_cause()

def formatAndReboot():
  '''Destroy the filesystem so that it will be formatted during next boot'''
  pwmLed(freq=10)
  if True:
    # This will trigger code in 
    # https://github.com/micropython/micropython/blob/master/ports/esp32/modules/inisetup.py
    # which will format the filesystem and write 'boot.py'
    import flashbdev
    buf = bytearray(flashbdev.bdev.SEC_SIZE*(0xFF,))
    flashbdev.bdev.writeblocks(0, buf)
    reboot('Reboot to format filesystem')
  if False:
    # os.VfsFat.mkfs(flashbdev.bdev)
    pass
  if False:
    import inisetup
    # See: https://github.com/micropython/micropython/blob/master/ports/esp32/modules/inisetup.py
    inisetup.setup()

def updateAndReboot():
  pwmLed(freq=10)
  import errno
  import network
  import utime
  import upip
  import urequests
  import upip_utarfile

  # Forked from https://github.com/micropython/micropython/blob/master/tools/upip.py#L74
  # Expects *file* name
  def _makedirs(name, mode=0o777):
    ret = False
    s = ""
    comps = name.rstrip("/").split("/")[:-1]
    if len(comps) == 0:
      # There is not top-directory
      return True
    if comps[0] == "":
      s = "/"
    for c in comps:
      if s and s[-1] != "/":
        s += "/"
      s += c
      try:
        uos.mkdir(s)
        ret = True
      except OSError as e:
        if e.args[0] != errno.EEXIST and e.args[0] != errno.EISDIR:
          raise
        ret = False
    return ret

  def connect(wlan):
    wlan.connect('waffenplatzstrasse26', 'guguseli')
    for iPause in range(10):
      # Do not use self.delay_ms(): Light sleep will kill the wlan!
      utime.sleep_ms(1000)
      if wlan.isconnected():
        print('connected!')
        break
    else:
      reboot('Could not connect to wlan')

  def update():
    r = urequests.get('https://www.maerki.com/hans/tmp/node_heads-SLASH-master_1.tar')
    r.status_code
    r.reason

    tar = upip_utarfile.TarFile(fileobj=r.raw)
    for info in tar:
      if info.type != upip_utarfile.REGTYPE:
        continue
      print('  extracting ' + info.name)
      _makedirs(info.name)
      subf = tar.extractfile(info)
      upip.save_file(info.name, subf)
    r.close()

    with open(FILENAME_UPDATE_FINISHED, 'w') as f:
      pass

  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)
  # listWlans = wlan.scan(200, 6)
  connect(wlan)

  update()

  wlan.active(False)
  reboot('SUCCESS: Successful update. Reboot')

def formatOrUpdateAndReboot():
  '''
    May reboot several times to format the filesystem and do the update.
  '''
  pin_led.value(False)

  if isButtonPressed() and isPowerOnBoot():
    print('Button presed. Format')
    formatAndReboot()

  if not isUpdateFinished():
    print('Update was not finished. Format')
    formatAndReboot()

  if isFilesystemEmpty:
    print('Filesystem is empty: Update')
    updateAndReboot()
