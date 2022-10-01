import asyncio, time
from itertools import chain
from adafruit_ht16k33.segments import Seg7x4

# for main()
from argparse import ArgumentParser, BooleanOptionalAction
import board, signal

async def sleep_until_interval(interval, result=None):
    r"""Given an interval, sleep until the beginning of the next whole
    interval.

    :param interval: an interval, expressed in seconds
    :param result: returned when done sleeping
    :return: result, if passed, else None
    """
    now = time.time()

    # when is the next interval?
    when = ((now + interval) // interval) * interval
    delay = when - now

    return await asyncio.sleep(delay, result)


class ClockConfig:
    #   -- 1 --            -- A --
    #  |       |          |       |
    # 32       2          F       B
    #  |       |          |       |
    #   --64 --            -- G --   0bHGFEDCBA
    #  |       |          |       |
    # 16       4          E       C
    #  |       |          |       |
    #   -- 8 --  128       -- D --  H

    A      = 0b00000001
    B      = 0b00000010
    C      = 0b00000100
    D      = 0b00001000
    E      = 0b00010000
    F      = 0b00100000
    G      = 0b01000000
    DOT    = 0b10000000
    NO_DOT = 0b00000000

    BITS = [
        (A | B | C | D | E | F),          # 0
        (B | C),                          # 1
        (A | B | G | E | D),              # 2
        (A | B | G | C | D),              # 3
        (F | G | B | C),                  # 4
        (A | F | G | C | D),              # 5
        (A | F | G | C | D | E),          # 6
        (A | B | C),                      # 7
        (A | B | G | E | D | C | G | F),  # 8
        (G | F | A | B | C | D),          # 9
    ]

    CLOCK_DOT_PATTERN = (  # 21:45.36.19
        NO_DOT, NO_DOT,  # 21:
        NO_DOT, DOT,     # 45.
        NO_DOT, DOT,     # 36.
        NO_DOT, NO_DOT,  # 19
    )

    BRIGHTNESS_MULTIPLIER = 0.0625   # 1/16
    BRIGHTNESS = 8           # 8/16

    BLINK_SEPARATORS = True

    LOCAL_TIME = True


class Clock:
    def __init__(self, i2c, *addrs,
            brightness=ClockConfig.BRIGHTNESS,
            blink=ClockConfig.BLINK_SEPARATORS,
            local=ClockConfig.LOCAL_TIME
        ):
        self.seg7x4 = Seg7x4(i2c, addrs, auto_write=False)
        self.seg7x4.brightness = brightness * ClockConfig.BRIGHTNESS_MULTIPLIER

        self.blink = blink
        self.local = local

        self.curr_seg7s = [ClockConfig.NO_DOT] * (len(addrs) * 4)
        self.curr_colon = False

        self.keep_ticking = True

    def tick(self):
        t = time.time()
        _, _, _, hours, minutes, seconds, _, _, _ = \
            time.localtime(t) if self.local else time.gmtime(t)
        thirds = int((t%1)*60)
        separators = not self.blink or thirds < 30

        seg7s = list(map(lambda bits: bits[0] | bits[1], zip(
            [ClockConfig.BITS[digit] for digit in chain.from_iterable(
                divmod(part, 10) for part in (hours, minutes, seconds, thirds)
            )],
            ClockConfig.CLOCK_DOT_PATTERN
        )))

        show = False
        for i, (old, new) in enumerate(zip(self.curr_seg7s, seg7s)):
            if old == new:
                continue
            self.seg7x4.set_digit_raw(i, new)
            show = True
        if separators is not self.curr_colon:
            self.seg7x4.colon = separators
            show = True

        if show:
            self.seg7x4.show()

    def stop(self):
        self.keep_ticking = False

    async def start(self):
        while self.keep_ticking:
            self.tick()
            await sleep_until_interval(1/60)

        # clear
        self.seg7x4.fill(0)
        self.seg7x4.show()


async def main():
    def auto_int(n):
        # allow hexadeciaml (or binary, or octal, or decimal) numbers here
        return int(n, 0)

    def brightness(n):
        i = int(n)
        if i < 0 or i > 16:
            raise ValueError("invalid brightness")
        return i

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

    clock = Clock(
        i2c,
        *(args.address),
        brightness=args.brightness,
        blink=args.blink_separators,
        local=not(args.universal_time)
    )

    def stop_clock(signal_received, stack_frame):
        clock.stop()

    signal.signal(signal.SIGINT, stop_clock)
    signal.signal(signal.SIGTERM, stop_clock)

    await clock.start()

if __name__ == '__main__':
    asyncio.run(main())
