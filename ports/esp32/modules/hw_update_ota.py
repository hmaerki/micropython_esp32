# -*- coding: utf-8 -*-

import gc
import uos
import utime
import machine
import hw_update_ota
import portable_firmware_constants

strMAC = ''.join(['%02X'%i for i in machine.unique_id()])

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

def __getSwVersion():
  try:
    with open(portable_firmware_constants.strFILENAME_VERSION, 'r') as fIn:
      return fIn.read().strip()
  except:
    return 'none'

strSwVersion = __getSwVersion()

def setRtcRamSSID(strWlanSsid, strWlanPw):
  import hw_rtc_mem
  d = hw_rtc_mem.objRtcMem.readRtcMemDict()
  d[portable_firmware_constants.strWLAN_SSID] = strWlanSsid
  d[portable_firmware_constants.strWLAN_PW] = strWlanPw
  hw_rtc_mem.objRtcMem.writeRtcMemDict(d)

def getRtcRamSSID():
  '''
    If the application stored a SSID and a PW in the RtcRam: Use these.
    Else use the hardcoded SSID and PW
  '''
  if bPowerOnBoot:
    # On power on, the RtcMem is invalid. Don event try to read it.
    return portable_firmware_constants.strWLAN_SSID, portable_firmware_constants.strWLAN_PW
  import hw_rtc_mem
  d = hw_rtc_mem.objRtcMem.readRtcMemDict()
  strWlanSsid = d.get(portable_firmware_constants.strWLAN_SSID, None)
  if strWlanSsid == None:
    # The application didn't store a Ssid
    return portable_firmware_constants.strWLAN_SSID, portable_firmware_constants.strWLAN_PW
  strWlanPw = d.get(portable_firmware_constants.strWLAN_PW, None)
  return strWlanSsid, strWlanPw

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

def isFilesystemEmpty():
  # Only 'boot.py' exists.
  return len(uos.listdir()) == 1

def isUpdateFinished():
  return portable_firmware_constants.strFILENAME_VERSION in uos.listdir()

def reboot(strReason):
  print(strReason)
  objGpio.setLed(bOn=False)
  # uos.sync() does not exist. Maybe a pause does the same. Maybe its event not used.
  feedWatchdog()
  utime.sleep_ms(1000)
  machine.reset()

def formatAndReboot():
  '''Destroy the filesystem so that it will be formatted during next boot'''
  gc.collect()
  objGpio.pwmLedReboot()
  # This will trigger a format of the filesystem and the creation of booty.py.
  # See: https://github.com/micropython/micropython/blob/master/ports/esp32/modules/inisetup.py
  import inisetup
  inisetup.setup()
  reboot('Reboot after format filesystem')

def update(strUrl):
  '''
    Returns True: If a new software was installed.
    Returns False: If there is no new software.
    On error: reboot
  '''
  import errno
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

  print('HTTP-Get ' + strUrl)
  try:
    feedWatchdog()
    r = urequests.get(strUrl)
    if r.status_code != 200:
      reboot('FAILED %d %s' % (r.status_code, r.reason))
      r.close()
  except OSError as e:
    reboot('FAILED %s' % e)

  tar = upip_utarfile.TarFile(fileobj=r.raw)
  for info in tar:
    if info.type != upip_utarfile.REGTYPE:
      continue
    print('  extracting ' + info.name)
    feedWatchdog()
    _makedirs(info.name)
    subf = tar.extractfile(info)
    upip.save_file(info.name, subf)
  r.close()

  print('Successful update!')
  return True

def connect(wlan, strSsid, strPassword):
  feedWatchdog()
  wlan.connect(strSsid, strPassword)
  for iPause in range(10):
    # Do not use self.delay_ms(): Light sleep will kill the wlan!
    feedWatchdog()
    utime.sleep_ms(1000)
    if wlan.isconnected():
      print('connected!')
      return True
  return False

def scanSsid(wlan, strSsid, iScanTime_ms=1500, iChannel=0):
  # wlan.scan(scan_time_ms, channel)
  # scan_time_ms > 0: Active scan
  # scan_time_ms < 0: Passive scan
  # channel: 0: All 11 channels
  feedWatchdog()
  listWlans = wlan.scan(iScanTime_ms, iChannel)
  # wlan.scan()
  # I (5108415) network: event 1
  # [
  # (b'rumenigge', b'Dn\xe5]$D', 1, -37, 3, False),
  # (b'waffenplatzstrasse26', b'\xa0\xf3\xc1KIP', 6, -77, 4, False),
  # (b'ubx-92907', b'\x08j\n.a\x00', 10, -92, 3, False)
  # ]
  for listWlan in listWlans:
    strSsid_ = listWlan[0].decode()
    if strSsid_ == strSsid:
      return True
  return False
    
def connectWlanReboot(bScanSsid=False):
  import network

  feedWatchdog()
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)

  strWlanSsid, strWlanPw = getRtcRamSSID()
  iChannel = portable_firmware_constants.iWLAN_Channel

  if bScanSsid:
    objGpio.pwmLedWlanScan()
    if not scanSsid(wlan, strWlanSsid, portable_firmware_constants.iWLAN_ScanTime_ms, iChannel):
      reboot('Scan failed for wlan "%s"' % strWlanSsid)

  print('Connecting to %s/%s' % (strWlanSsid, strWlanPw))
  objGpio.pwmLedWlanConnected()
  bConnected = connect(wlan, strWlanSsid, strWlanPw)
  if not bConnected:
    reboot('Could not connect to wlan "%s/%s" on channel %d' % (strWlanSsid, strWlanPw, iChannel))
  return wlan

def updateAndReboot(bScanSsid=False):
  wlan = connectWlanReboot(bScanSsid)

  strUrl = getDownloadUrl(wlan)
  bSoftwareUpdated = update(strUrl)
  feedWatchdog()
  wlan.active(False)

  if not bSoftwareUpdated:
    # This is somehow strange: There shouldn't be any software installed....s
    return

  reboot('SUCCESS: Successful update. Reboot')

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
    updateAndReboot()

  if not isUpdateFinished():
    print('Update was not finished. Format')
    activateWatchdog()
    formatAndReboot()

  objGpio.setLed(False)

def getSwVersionGit(wlan):
  '''
    returns verions: On success
    returns None: on failure
  '''
  import urequests
  strUrl = getVersionCheckUrl(wlan)
  print('HTTP-Get ' + strUrl)
  try:
    feedWatchdog()
    r = urequests.get(strUrl)
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
  
def checkForNewSwAndRebootRepl(bScanSsid=False):
  wlan = connectWlanReboot(bScanSsid)
  bNewSwVersion = checkIfNewSwVersion(wlan)
  feedWatchdog()
  wlan.active(False)
  if bNewSwVersion:
    formatAndReboot()
  objGpio.setLed(False)

class Command:
  def __init__(self, func):
    self.__func = func

  def __repr__(self):
    return self.__func()

  def __call__(self):
    return self.__repr__()
