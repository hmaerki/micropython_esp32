# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)


import machine
import hw_utils

# Register some useful commands
# setRtcRamSSID = hw_update_ota.setRtcRamSSID
# checkForNewSwAndReboot = hw_utils.Command(hw_update_ota.checkForNewSwAndRebootRepl)
# updateAndReboot = hw_utils.Command(hw_update_ota.updateAndReboot)
formatAndReboot = hw_utils.Command(hw_utils.formatAndReboot)
deleteVERSION_TXTandReboot = hw_utils.Command(hw_utils.deleteVERSION_TXTandReboot)
reboot = hw_utils.Command(machine.reset)
print_mem_usage = hw_utils.Command(hw_utils.print_mem_usage)

# The following line will not return if a update is available
hw_utils.bootCheckUpdate()

hw_utils.print_mem_usage()
print('end of boot.py')
