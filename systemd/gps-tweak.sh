#! /bin/bash

# full cold restart
# $PMTK104*37

# disable easy mode, whatever that is
echo -e -n '\$PMTK869,1,0*34\r\n'  >> /dev/ttyAMA0

# baud rate
echo -e -n '\$PMTK251,115200*1F\r\n'  >> /dev/ttyAMA0

# enable SBAS
echo -e -n '\$PMTK313,1*2E\r\n'  >> /dev/ttyAMA0

# DGPS via WAAS (satellite)
echo -e -n '\$PMTK301,2*2E\r\n'  >> /dev/ttyAMA0

# Active Interference Cancellation (AIC)
echo -e -n '\$PMTK286,1*23\r\n'  >> /dev/ttyAMA0

# turn on antenna reporting
echo -e -n '\$CDCMD,33,1*7C\r\n'  >> /dev/ttyAMA0

# hot restart
echo -e -n '\$PMTK101*32\r\n'  >> /dev/ttyAMA0
