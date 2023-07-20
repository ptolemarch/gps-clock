#! /bin/bash

# full cold restart  -- don't do this!
# $PMTK104*37

# disable easy mode, whatever that is
# actually turns out to be perhaps useful? From the datasheet:
# The EASY™ is embedded assist system for quick positioning, the GPS engine
# will calculate and predict automatically the single ephemeris (Max. up to 3
# days) when power on, and save the predict information into the memory, GPS
# engine will use these information for positioning if no enough information
# from satellites, so the function will be helpful for positioning and TTFF
# improvement under indoor or urban condition, the Backup power (VBACKUP) is
# necessary.
#echo -e -n '\$PMTK869,1,0*34\r\n'  >> /dev/ttyAMA0

# baud rate
echo -e -n '\$PMTK251,115200*1F\r\n'  >> /dev/ttyAMA0
sleep 0.5

# enable SBAS
echo -e -n '\$PMTK313,1*2E\r\n'  >> /dev/ttyAMA0
sleep 0.5

# DGPS via WAAS (satellite)
echo -e -n '\$PMTK301,2*2E\r\n'  >> /dev/ttyAMA0
sleep 0.5

# Active Interference Cancellation (AIC)
echo -e -n '\$PMTK286,1*23\r\n'  >> /dev/ttyAMA0
sleep 0.5

# turn on antenna reporting
echo -e -n '\$CDCMD,33,1*7C\r\n'  >> /dev/ttyAMA0
sleep 0.5

# hot restart  -- let's maybe not do this
#echo -e -n '\$PMTK101*32\r\n'  >> /dev/ttyAMA0
