# -*- coding: utf-8 -*-

import gc
import uos
import utime
import hw_urequests
import machine
import portable_firmware_constants

strMAC = ''.join(['%02X'%i for i in machine.unique_id()])

#
# Watchdog
#
objWdt = None

feedWatchdog = lambda: None

'''True if power on. False if reboot by software or watchdog.'''
bPowerOnBoot = machine.PWRON_RESET == machine.reset_cause()

'''True if Watchdog-Reset. False if reboot by software or power on.'''
bWatchdogBoot = machine.WDT_RESET == machine.reset_cause()

def activateWatchdog():
  global objWdt
  if objWdt != None:
    return
  objWdt = machine.WDT(0)
  global feedWatchdog
  feedWatchdog = objWdt.feed
  print('Watchdog: ACTIVE')

#
# SW Version
#
def readFile(strFilename, default):
  try:
    with open(strFilename, 'r') as fIn:
      return fIn.read()
  except:
    return default

def __getSwVersion():
  return readFile(portable_firmware_constants.strFILENAME_VERSION, default='none').strip()

strSwVersion = __getSwVersion()

#
# LED and Button
#
iFreqOn_hz = 1000

class Gpio:
  def __init__(self):
    self.pin_button = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
    self.pin_led = machine.Pin(22, machine.Pin.OUT)
    # LED off
    self.pwm = machine.PWM(self.pin_led, freq=iFreqOn_hz, duty=0)
    self.__iFreq = None
    self.__iDuty = None

  def pwmLed(self, iFreq_hz=10, iDuty_1023=512):
    if self.__iFreq != iFreq_hz:
      self.__iFreq = iFreq_hz
      self.pwm.freq(iFreq_hz)

    if self.__iDuty != iDuty_1023:
      self.__iDuty = iDuty_1023
      self.pwm.duty(iDuty_1023)

  'Scan: slow blink, sharp'
  def pwmLedReboot(self):
    self.pwmLed(portable_firmware_constants.iLedReboot_pwm_hz,
                portable_firmware_constants.iLedReboot_duty_1023)

  'Scan: blink, dark'
  def pwmLedWlanScan(self):
    self.pwmLed(portable_firmware_constants.iLedWlanScan_pwm_hz,
                portable_firmware_constants.iLedWlanScan_duty_1023)

  'Connected: blink, bright'
  def pwmLedWlanConnected(self):
    self.pwmLed(portable_firmware_constants.iLedWlanConnected_pwm_hz,
                portable_firmware_constants.iLedWlanConnected_duty_1023)

  def setLed(self, bOn=True):
    if bOn:
      self.pwmLed(iFreqOn_hz, 1023)
      return
    self.pwmLed(iFreqOn_hz, 0)

  def isButtonPressed(self):
    '''Returns True if the Button is pressed.'''
    return self.pin_button.value() == 0

objGpio = Gpio()


#
# Utils
#
def reboot(strReason):
  print(strReason)
  objGpio.setLed(bOn=False)
  # uos.sync() does not exist. Maybe a pause does the same. Maybe its event not used.
  feedWatchdog()
  utime.sleep_ms(1000)
  machine.reset()

def isFilesystemEmpty():
  # Only 'boot.py' exists.
  return len(uos.listdir()) == 1

def isUpdateFinished():
  return portable_firmware_constants.strFILENAME_VERSION in uos.listdir()

def deleteVERSION_TXTandReboot():
  '''Delete VERSION.TXT so that the filesystem will be formatted during next boot'''
  uos.remove(portable_firmware_constants.strFILENAME_VERSION)
  reboot('Reboot after deleting VERSION.TXT')

def formatAndReboot():
  '''Destroy the filesystem so that it will be formatted during next boot'''
  gc.collect()
  objGpio.pwmLedReboot()
  # This will trigger a format of the filesystem and the creation of booty.py.
  # See: https://github.com/micropython/micropython/blob/master/ports/esp32/modules/inisetup.py
  import inisetup
  inisetup.setup()
  reboot('Reboot after format filesystem')

def bootCheckUpdate():
  '''
    This method is called from 'boot.py' always after boot.

    May reboot several times to format the filesystem and do the update.
  '''
  objGpio.setLed(False)

  if objGpio.isButtonPressed() and bPowerOnBoot:
    print('Button presed. Format')
    activateWatchdog()
    formatAndReboot()

  if isFilesystemEmpty():
    print('Filesystem is empty: Update')
    activateWatchdog()
    # Don't import at the beginning: It would occupy memory...
    import hw_update_ota
    hw_update_ota.updateAndReboot()

  if not isUpdateFinished():
    print('Update was not finished. Format')
    activateWatchdog()
    formatAndReboot()

  objGpio.setLed(False)

#
# Verify SW-Version on Host
#
def getServer(wlan):
  listIfconfig = wlan.ifconfig()
  strGateway = listIfconfig[2]
  if strGateway == portable_firmware_constants.strGATEWAY_PI:
    return portable_firmware_constants.strSERVER_PI
  return portable_firmware_constants.strSERVER_DEFAULT

def getDownloadUrl(wlan):
  return __getUrl(wlan, portable_firmware_constants.strHTTP_PATH_SOFTWAREUPDATE)

def getVersionCheckUrl(wlan):
  return __getUrl(wlan, portable_firmware_constants.strHTTP_PATH_VERSIONCHECK)

def __getUrl(wlan, strFunction):
  return '%s%s?%s=%s&%s=%s' % (getServer(wlan), strFunction, portable_firmware_constants.strHTTP_ARG_MAC, strMAC, portable_firmware_constants.strHTTP_ARG_VERSION, strSwVersion)

def getSwVersionGit(wlan):
  '''
    returns verions: On success
    returns None: on failure
  '''
  strUrl = getVersionCheckUrl(wlan)
  print('HTTP-Get ' + strUrl)
  try:
    feedWatchdog()
    r = hw_urequests.get(strUrl)
    if r.status_code != 200:
      print('FAILED %d %s' % (r.status_code, r.reason))
      r.close()
      return None
    strSwVersionGit = r.text
    r.close()
    return strSwVersionGit
  except OSError as e:
    print('FAILED %s' % e)
  return None

def checkIfNewSwVersion(wlan):
  '''
    returns True: The version changed
    returns False: Same version or error
  '''
  strSwVersionGit = getSwVersionGit(wlan)
  if strSwVersionGit != None:
    print('Software version node: %s' % strSwVersion)
    print('Software version git:  %s' % strSwVersionGit)
    if strSwVersionGit != strSwVersion:
      print('Software version CHANGED')
      return True
    print('Software version EQUAL')
  return False

#
# Memory usage
#
def print_mem_usage(msg=''):
  gc.collect()
  f=gc.mem_free()
  a=gc.mem_alloc()
  print('mem_usage {}+{}={} {}'.format(f, a, f+a, msg))


#
# Repl-Command
#
class Command:
  def __init__(self, func):
    self.__func = func

  def __repr__(self):
    return self.__func()

  def __call__(self):
    return self.__repr__()

