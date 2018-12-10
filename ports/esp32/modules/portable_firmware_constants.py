# -*- coding: utf-8 -*-

#
# These constants are shared between the firmware
# and the application using this firmware.
# The original of this file is in the firmware.
# https://github.com/tempstabilizer2018group/micropython_esp32/blob/master/ports/esp32/modules/portable_firmware_constants.py
#
# The application may copy this file to be able to run on windows/linux
#

strHTTP_PATH_SOFTWAREUPDATE = '/softwareupdate'
strHTTP_PATH_VERSIONCHECK = '/versioncheck'
strHTTP_PATH_UPLOAD = '/upload'

strHTTP_ARG_MAC = 'mac'
strHTTP_ARG_VERSION = 'version'
strHTTP_ARG_FILENAME = 'filename'

strFILENAME_VERSION = 'VERSION.TXT'

strWLAN_SSID = 'TempStabilizer2018'
strWLAN_PW = None
