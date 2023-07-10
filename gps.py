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


# subscript but suppress KeyError
def _s(container, key, default=None):
    with contextlib.suppress(KeyError):
        return container[key]
    return default

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
                antenna = AntennaStatus.lookup(int(_s(values,1,0)))
            )
        return dict()

    def parse_json(self, line):
        report = json.loads(line)
        rclass = _s(report,'class','')

        if rclass == "PPS":
            sec = _s(report,'clock_sec',0) - _s(report,'real_sec',0)
            nsec = (sec * 1e9) + (_s(report,'clock_nsec',0) - _s(report,'real_nsec',0))
            usec = nsec / 1e3
            return dict(
               pps_offset_usec = usec,
            )
        if rclass == "TPV":
            return dict(
                mode = GPSMode.lookup(_s(report,'mode',0)),
                status = GPSStatus.lookup(_s(report,'status',0)),
                latitude = _s(report,'lat',0),
                longitude = _s(report,'lon',0),
                altitude = _s(report,'altMSL',0),
                error_2d = _s(report,'eph',0),
                error_3d = _s(report,'sep',0),
                error_latitude = _s(report,'epy',0),
                error_longitude = _s(report,'epx',0),
                error_altitude = _s(report,'epv',0),
            )
        if rclass == "SKY":
            # TODO: count
            # - GPS (gnssid = 0)
            # - SBAS/WAAS (gnssid = 1)
            # - GLONASS (gnssid = 6)
            # from report['satellites']
            return dict(
                satellites = _s(report,'nSat',0),
                satellites_used = _s(report,'uSat',0),
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
