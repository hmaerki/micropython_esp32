# -*- coding: utf-8 -*-

import uos
import utime
import network
import hw_utils
import hw_urequests
import portable_firmware_constants

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
  if hw_utils.bPowerOnBoot:
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


def update(strUrl):
  '''
    Returns True: If a new software was installed.
    Returns False: If there is no new software.
    On error: reboot
  '''
  import errno
  import upip
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
    hw_utils.feedWatchdog()
    r = hw_urequests.get(strUrl)
    if r.status_code != 200:
      hw_utils.reboot('FAILED %d %s' % (r.status_code, r.reason))
      r.close()
  except OSError as e:
    hw_utils.reboot('FAILED %s' % e)

  tar = upip_utarfile.TarFile(fileobj=r.raw)
  for info in tar:
    if info.type != upip_utarfile.REGTYPE:
      continue
    print('  extracting ' + info.name)
    hw_utils.feedWatchdog()
    _makedirs(info.name)
    subf = tar.extractfile(info)
    upip.save_file(info.name, subf)
  r.close()

  print('Successful update!')
  return True

def connect(wlan, strSsid, strPassword):
  hw_utils.feedWatchdog()
  wlan.connect(strSsid, strPassword)
  for _ in range(10):
    # Do not use self.delay_ms(): Light sleep will kill the wlan!
    hw_utils.feedWatchdog()
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
  hw_utils.feedWatchdog()
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
  hw_utils.feedWatchdog()
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)

  strWlanSsid, strWlanPw = getRtcRamSSID()
  iChannel = portable_firmware_constants.iWLAN_Channel

  if bScanSsid:
    hw_utils.objGpio.pwmLedWlanScan()
    if not scanSsid(wlan, strWlanSsid, portable_firmware_constants.iWLAN_ScanTime_ms, iChannel):
      hw_utils.reboot('Scan failed for wlan "%s"' % strWlanSsid)

  print('Connecting to %s/%s' % (strWlanSsid, strWlanPw))
  hw_utils.objGpio.pwmLedWlanConnected()
  bConnected = connect(wlan, strWlanSsid, strWlanPw)
  if not bConnected:
    hw_utils.reboot('Could not connect to wlan "%s/%s" on channel %d' % (strWlanSsid, strWlanPw, iChannel))
  return wlan

def updateAndReboot(bScanSsid=False):
  wlan = connectWlanReboot(bScanSsid)

  strUrl = hw_utils.getDownloadUrl(wlan)
  bSoftwareUpdated = update(strUrl)
  hw_utils.feedWatchdog()
  wlan.active(False)

  if not bSoftwareUpdated:
    # This is somehow strange: There shouldn't be any software installed....s
    return

  hw_utils.reboot('SUCCESS: Successful update. Reboot')
  
def checkForNewSwAndRebootRepl(bScanSsid=False):
  wlan = connectWlanReboot(bScanSsid)
  bNewSwVersion = hw_utils.checkIfNewSwVersion(wlan)
  hw_utils.feedWatchdog()
  wlan.active(False)
  if bNewSwVersion:
    hw_utils.formatAndReboot()
  hw_utils.objGpio.setLed(False)
