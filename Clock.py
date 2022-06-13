import time
from .halfclock import HalfClock

class Clock:
    def __init__(self, hm: HalfClock, st: HalfClock, blink=True):
        self.hm = hm
        self.st = st
        self.local = True
        self.curr_third = -1
        self.curr_minute = -1

    def tick(self, t=None):
        if t is None:
            t = time.time()
        lt = time.localtime(t) if self.local else time.gmtime(t)
        third = int((time%1)*60)

        if third == self.curr_third:
            return
        self.curr_third = third

        separators = not blink or third < 30

        with st as half:
            half.digits(lt.tm_sec, third)
            half.dots(separators, False)

        if lt.tm_min == self.curr_minute:
            return
        self.curr_minute = lt.tm_min

        with hm as half:
            half.digits(lt.tm_hour, lt.tm_min)
            half.dots(False, separators)
            half.colon(separators)

def old_tick():
    # C'est magnifique, mais ce n'est pas la guerre.
    # It is pretty damned fast, though.
    global prev_time
    t = time.time()
    lt = time.localtime(t)
    third = int((t%1)*60)
    if third == prev_time['third']:
        return

    dotbit = 0b10000000

    if BLINK_SEPARATORS and third < prev_time['third']:
        dotbit = 0b10000000
        right_7seg.set_digit_raw(1, dec_to_bits[prev_time['second_right']] | dotbit)
        left_7seg.set_digit_raw(3, dec_to_bits[prev_time['minute_right']] | dotbit)
        left_7seg.colon = True
        left_7seg.show()
    elif BLINK_SEPARATORS and prev_time['third'] < 29 <= third:
        dotbit = 0b00000000
        right_7seg.set_digit_raw(1, dec_to_bits[prev_time['second_right']] | dotbit)
        left_7seg.set_digit_raw(3, dec_to_bits[prev_time['minute_right']] | dotbit)
        left_7seg.colon = False
        left_7seg.show()

    (third_left, third_right) = sex_to_dec[third]
    prev_time['third'] = third
    prev_time['third_right'] = third_right
    right_7seg.set_digit_raw(3, dec_to_bits[third_right])

    if third_left == prev_time['third_left']:
        right_7seg.show()
        return
    prev_time['third_left'] = third_left
    right_7seg.set_digit_raw(2, dec_to_bits[third_left])

    second = lt.tm_sec
    if second == prev_time['second']:
        right_7seg.show()
        return
    (second_left, second_right) = sex_to_dec[second]
    prev_time['second'] = second
    prev_time['second_right'] = second_right
    right_7seg.set_digit_raw(1, dec_to_bits[second_right] | dotbit)

    if second_left == prev_time['second_left']:
        right_7seg.show()
        return
    prev_time['second_left'] = second_left
    right_7seg.set_digit_raw(0, dec_to_bits[second_left])
    right_7seg.show()

    minute = lt.tm_min
    if minute == prev_time['minute']:
        return
    (minute_left, minute_right) = sex_to_dec[minute]
    prev_time['minute'] = minute
    prev_time['minute_right'] = minute_right
    left_7seg.set_digit_raw(3, dec_to_bits[minute_right] | dotbit)

    if minute_left == prev_time['minute_left']:
        left_7seg.show()
        return
    prev_time['minute_left'] = minute_left
    left_7seg.set_digit_raw(2, dec_to_bits[minute_left])

    hour = lt.tm_hour
    if hour == prev_time['hour']:
        left_7seg.show()
        return
    (hour_left, hour_right) = sex_to_dec[hour]
    prev_time['hour'] = hour
    prev_time['hour_right'] = hour_right
    left_7seg.set_digit_raw(1, dec_to_bits[hour_right])

    if hour_left == prev_time['hour_left']:
        left_7seg.show()
        return
    prev_time['hour_left'] = hour_left
    left_7seg.set_digit_raw(0, dec_to_bits[hour_left])
    left_7seg.show()


if __name__ == '__main__':
    def auto_int(n):
        # allow hexadeciaml (or binary, or octal, or decimal) numbers here
        return int(n, 0)

    def main():
        from argparse import ArgumentParser, BooleanOptionalAction
        import argparse, board

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
            type=BooleanOptionalAction,
            help="show/hide separators based on fraction of second"
        )
        argyle.add_argument('time',
            type=float, default=time.time(),
            help="time to display"
        )
