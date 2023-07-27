#! /bin/bash

serial=/dev/ttyAMA0  # major 204, minor 64

die() {
	retval=$1 ; shift
	message="$2" ; shift
	echo "$message" 1>&2
	exit $retval
}

while ! [[ -c "$serial" ]] ; do
	echo "No character special file at [$serial]. Waiting..." 1>&2
	sleep 0.1
done

#if [[ -c "$serial" ]] ; then : else
#	echo "NO character special file at [$serial]" 1>&2
#	exit 1
#fi

serial_major=$(stat -c %t "$serial")
serial_minor=$(stat -c %T "$serial")
if [[ "$serial_major" = "cc" ]] && [[ "$serial_minor" = "40" ]] ; then : ; else
	echo "character special file at [$serial] has weird device numbers:" 1>&2
	echo "    major: [$serial_major] (expected cc hex = 204 dec)" 1>&2
	echo "    minor: [$serial_minor] (expected 40 hex =  64 dec)" 1>&2
	exit 2
fi

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
#echo -e -n '\$PMTK869,1,0*34\r\n'  >> "$serial"

# baud rate
echo -e -n '\$PMTK251,115200*1F\r\n'  >> "$serial" \
	|| die 3 "can't set baud rate" 1>&2
sleep 0.5

# enable SBAS
echo -e -n '\$PMTK313,1*2E\r\n'  >> "$serial" \
	|| die 4 "can't enable SBAS" 1>&2
sleep 0.5

# DGPS via WAAS (satellite)
echo -e -n '\$PMTK301,2*2E\r\n'  >> "$serial" \
	|| die 5 "can't enable DGPS via WAAS" 1>&2
sleep 0.5

# Active Interference Cancellation (AIC)
echo -e -n '\$PMTK286,1*23\r\n'  >> "$serial" \
	|| die 6 "can't enable AIC" 1>&2
sleep 0.5

# turn on antenna reporting
echo -e -n '\$CDCMD,33,1*7C\r\n'  >> "$serial" \
	|| die 7 "can't turn on antenna reporting" 1>&2
sleep 0.5

# hot restart  -- let's maybe not do this
#echo -e -n '\$PMTK101*32\r\n'  >> "$serial"
