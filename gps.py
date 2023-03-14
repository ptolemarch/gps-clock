import asyncio, json, contextlib
from enum import Enum
from collections import defaultdict

from tracker import Tracker

# for main()
import sys


class Lookupable:
    @classmethod
    def lookup(cls, value):
        # the order above matters for this trick to work
        members = list(cls)
        if value > len(members)-1:
            value = 0
        return members[value]


class AntennaStatus(Lookupable, Enum):
    UNKNOWN = "unknown"
    INTERNAL = "internal"
    EXTERNAL = "external"
    SHORTED = "shorted"


class GPSMode(Lookupable, Enum):
    UNKNOWN = "unknown"
    NO_FIX = "no_fix"
    FIX_2D = "fix_2d"
    FIX_3D = "fix_3d"


# gpsmon(1) calls this "Quality". My GPS is capable of
# - UNKNOWN ("Fix not available")
# - NORMAL ("GPS fix")
# - DGPS ("Differential GPS fix") https://en.wikipedia.org/wiki/Differential_GPS
class GPSStatus(Lookupable, Enum):
    UNKNOWN = "unknown"
    NORMAL = "normal"
    DGPS = "DGPS"
    RTK_FIXED = "RTK_fixed"
    RTK_FLOATING = "RTK_floating"
    DR = "DR"
    GNSSDR = "GNSSDR"
    TIME = "time (surveyed)"
    SIMULATED = "simulated"
    PY = "p(y)"


class JSONEncodeGPS(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


# NMEA reference: https://cdn-shop.adafruit.com/product-files/1059/CD+PA1616D+Datasheet+v.05.pdf
# (also theoretically https://gpsd.io/NMEA.html)
# GPSd JSON reference: https://gpsd.io/gpsd_json.html
class GPSPipeParser:
    def parse(self, line):
        if line.startswith("$"):
            return self.parse_nmea(line)
        if line.startswith("{"):
            return self.parse_json(line)
        return dict()

    def parse_nmea(self, line):
        sentence, checksum = line[1:].rsplit(sep="*", maxsplit=1)
        header, *values = sentence.split(",")

        # incidentally, this is the command to enable antenna reporting:
        #   sudo gpsctl -t MTK-3301 -x '$CDCMD,33,1*7C' /dev/serial0
        # and this is the command to disable antenna reporting:
        #   sudo gpsctl -t MTK-3301 -x '$CDCMD,33,0*7D' /dev/serial0
        # I'm currently running the former in '/etc/rc.local'
        #   (obviously without the `sudo`).

        if header == "PCD":
            return dict(
                antenna = AntennaStatus.lookup(int(values[1]))
            )
        return dict()

    def parse_json(self, line):
        report = json.loads(line)
        rclass = report['class']

        if rclass == "PPS":
            sec = report['clock_sec'] - report['real_sec']
            nsec = (sec * 1e9) + (report['clock_nsec'] - report['real_nsec'])
            usec = nsec / 1e3
            return dict(
               pps_offset_usec = usec,
            )
        if rclass == "TPV":
            return dict(
                mode = GPSMode.lookup(report['mode']),
                status = GPSStatus.lookup(report['status']),
                latitude = report['lat'],
                longitude = report['lon'],
                altitude = report['altMSL'],
                error_2d = report['eph'],
                error_3d = report['sep'],
                error_latitude = report['epy'],
                error_longitude = report['epx'],
                error_altitude = report['epv'],
            )
        if rclass == "SKY":
            # TODO: count
            # - GPS (gnssid = 0)
            # - SBAS/WAAS (gnssid = 1)
            # - GLONASS (gnssid = 6)
            # from report['satellites']
            return dict(
                satellites = report['nSat'],
                satellites_used = report['uSat'],
            )
        return dict()


class GPS:
    # command to retrieve GPS info
    # This should be a command that remains running until stopped, outputting
    #  reports as NMEA or JSON sentences, one per line
    COMMAND = ['/usr/bin/gpspipe', '--nmea', '--json']
    def __init__(self, cmd=None):
        if cmd is None:
            self.cmd = self.COMMAND
        else:
            self.cmd = cmd

        self.info = defaultdict(str)  # we know nothing at first
        self.tracker = Tracker(self.cmd, GPSPipeParser())

    async def run(self):
        async for gps in self.tracker:
            self.info = gps


async def main():
    gps = GPS()

    gps_task = asyncio.create_task(gps.run())

    while True:
        await asyncio.sleep(1)
        print(json.dumps(gps.info, cls=JSONEncodeGPS))
        sys.stdout.flush()  # so I can, e.g., pipe to jq(1)

    await gps_task


if __name__ == '__main__':
    asyncio.run(main())
