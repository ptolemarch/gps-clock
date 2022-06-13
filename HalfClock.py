from adafruit_ht16k33.segments import Seg7x4

#   -- 1 --            -- A --      
#  |       |          |       |
# 32       2          F       B
#  |       |          |       |
#   --64 --            -- G --   0bHGFEDCBA
#  |       |          |       |
# 16       4          E       C
#  |       |          |       |
#   -- 8 --  128       -- D --  H

class HalfClock:
    A = 0b00000001
    B = 0b00000010
    C = 0b00000100
    D = 0b00001000
    E = 0b00010000
    F = 0b00100000
    G = 0b01000000
    DOT = 0b10000000
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

    BRIGHTNESS_MULTIPLIER = 0.0625   # 1/16

    def __init__(self, i2c, address, brightness=8):
        self.seg7x4 = Seg7x4(i2c, address, auto_write=False)
        self.seg7x4.brightness = brightness * self.BRIGHTNESS_MULTIPLIER

        self.curr_seg7s = [self.NO_DOT, self.NO_DOT, self.NO_DOT, self.NO_DOT]
        self.curr_colon = False

    def __enter__(self):
        self.do = dict(
            digits = [],
            dots = [],
            colon = [],
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.show()

    def digits(self, left, right):
        self.do['digits'] = list(map(lambda _: self.BITS[_],(
            *divmod(left, 10), *divmod(right, 10)
        )))

    def dots(self, left, right):
        self.do['dots'] = [
            self.NO_DOT,
            self.DOT if left else self.NO_DOT, 
            self.NO_DOT,
            self.DOT if right else self.NO_DOT, 
        ]

    def colon(self, colon):
        self.do['colon'] = colon

    def show(self):
        seg7s = list(map(
            lambda t: t[0] | t[1],
            zip(self.do['digits'], self.do['dots'])
        ))
        changed = map(
            lambda t: False if t[0] == t[1] else t[1],
            zip(self.curr_seg7s, seg7s)
        )
        for i, seg7 in enumerate(changed):
            if not seg7:
                continue
            self.seg7x4.set_digit_raw(i, seg7)
        if self.do['colon'] is not self.curr_colon:
            self.seg7x4.colon = self.do['colon'] 
        self.curr_seg7s = seg7s
        self.curr_colon = self.do['colon']
        self.seg7x4.show()

    def clear(self):
        self.seg7x4.fill(0)
        self.seg7x4.show()


if __name__ == '__main__':
    def auto_int(n):
        # allow hexadeciaml (or binary, or octal, or decimal) numbers here
        return int(n, 0)

    def sexagesimal(n):
        i = int(n)
        if i < 0 or i > 59:
            raise ValueError("not a sexagesimal digit")
        return i

    def brightness(n):
        i = int(n)
        if i < 0 or i > 16:
            raise ValueError("invalid brightness")
        return i

    def main():
        from argparse import ArgumentParser, BooleanOptionalAction
        import argparse, board

        argyle = ArgumentParser()
        argyle.add_argument('-a', '--address',
            type=auto_int, default=0x70,
            help="I2C address of seven-segment display"
        )
        argyle.add_argument('-c', '--colon',
            action=BooleanOptionalAction,
            help="display separator colon"
        )
        argyle.add_argument('-d', '--dots',
            action=BooleanOptionalAction,
            help="display separator dots"
        )
        argyle.add_argument('-b', '--brightness',
            type=brightness, default=8,
            help="brightness (0-16)"
        )
        argyle.add_argument('digit',
            type=sexagesimal, nargs=2,
            help="sexagesimal digits to display"
        )
        args = argyle.parse_args()

        i2c = board.I2C()
        hc = HalfClock(i2c, args.address, args.brightness)

        with hc as half:
            half.digits(*args.digit)
            half.dots(args.dots, args.dots)
            half.colon(args.colon)

    main()
