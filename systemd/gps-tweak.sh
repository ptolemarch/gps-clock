#! /bin/bash

# /dev/serial0 is a symlink to /dev/ttyAMA0,
#  but if we use /dev/ttyAMA0 directly, we get this error:
#      gpsctl:ERROR: SER: /dev/ttyAMA0 already opened by another process
#      gpsctl:ERROR: initial GPS device /dev/ttyAMA0 open failed
serial=/dev/serial0

die() {
	retval=$1 ; shift
	message="$2" ; shift
	echo "$message" 1>&2
	exit $retval
}

# Sleep briefly to let gpsd get on its feet.
sleep 0.5

# full cold restart -- don't do this!
# (Documented here in case I need it in the future.)
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
#gpsctl -x '$PMTK869,1,0*34' "$serial" \

# baud rate to 115200,
#  which helps chrony to align PPS with GPS,
#  and therefore really to make the time signal much, much better
gpsctl -x '$PMTK251,115200*1F' "$serial" \
	|| die 3 "can't set baud rate" 1>&2

# Honestly, I have no idea whether enabling SBAS, DGPS, or AIC helps
#  a whit. They all seem neat, though.
# enable SBAS
gpsctl -x '$PMTK313,1*2E' "$serial" \
	|| die 4 "can't enable SBAS" 1>&2
# DGPS via WAAS (satellite)
gpsctl -x '$PMTK301,2*2E' "$serial" \
	|| die 5 "can't enable DGPS via WAAS" 1>&2
# Active Interference Cancellation (AIC)
gpsctl -x '$PMTK286,1*23' "$serial" \
	|| die 6 "can't enable AIC" 1>&2

# Without this, there's no way to tell whether the system is using
#  the external GPS antenna.
# turn on antenna reporting
gpsctl -x '$CDCMD,33,1*7C' "$serial" \
	|| die 7 "can't turn on antenna reporting" 1>&2

# hot restart  -- let's maybe not do this
#gpsctl -x '$PMTK101*32' "$serial" \
