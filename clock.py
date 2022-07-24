import time
from halfclock import HalfClock

# FWIW, newer versions of adafruit_ht16k33.segments.Seg7x4 support multiple
# displays in a single object. Might eventually want to reorganize
# this and HalfClock to use that. See
#   https://docs.circuitpython.org/projects/ht16k33/en/latest/api.html#adafruit-ht16k33-segments

class Clock:
    def __init__(self, hm: HalfClock, st: HalfClock, blink=True):
        self.hm = hm
        self.st = st
        self.local = True
        self.blink = blink
        self.curr_third = -1
        self.curr_minute = -1

    def tick(self, t=None):
        if t is None:
            t = time.time()
        lt = time.localtime(t) if self.local else time.gmtime(t)
        third = int((t%1)*60)

        if third == self.curr_third:
            return
        self.curr_third = third

        separators = not self.blink or third < 30

        with self.st as half:
            half.digits(lt.tm_sec, third)
            half.dots(separators, False)

        if lt.tm_min == self.curr_minute:
            return
        self.curr_minute = lt.tm_min

        with self.hm as half:
            half.digits(lt.tm_hour, lt.tm_min)
            half.dots(False, separators)
            half.colon(separators)

if __name__ == '__main__':
    def auto_int(n):
        # allow hexadeciaml (or binary, or octal, or decimal) numbers here
        return int(n, 0)

    def brightness(n):
        i = int(n)
        if i < 0 or i > 16:
            raise ValueError("invalid brightness")
        return i

    def main():
        from argparse import ArgumentParser, BooleanOptionalAction
        import board

        argyle = ArgumentParser()
        argyle.add_argument('-a', '--address',
            type=auto_int, nargs=2, default=[0x70, 0x71],
            help="I2C addresses of seven-segment displays"
        )
        argyle.add_argument('-b', '--brightness',
            type=brightness, default=8,
            help="brightness (0-16)"
        )
        argyle.add_argument('-s', '--blink-separators',
            action=BooleanOptionalAction,
            help="show/hide separators based on fraction of second"
        )
        argyle.add_argument('-u', '--universal-time',
            action=BooleanOptionalAction,
            help="show UTC rather than local time"
        )
        argyle.add_argument('time',
            type=float, nargs='?', default=time.time(),
            help="time to display"
        )
        args = argyle.parse_args()

        print("parsed args")

        i2c = board.I2C()
        hm = HalfClock(i2c, args.address[0], args.brightness)
        st = HalfClock(i2c, args.address[1], args.brightness)

        clock = Clock(hm, st, args.blink_separators)
        clock.local = not args.universal_time
        clock.tick(args.time)

    main()
