import board
from adafruit_ht16k33.segments import Seg7x4

import time
import timeit

from halfclock import HalfClock
from clock import Clock

from clock_segments import sex_to_dec, dec_to_bits

if __name__ == '__main__':
    def new_ticker():
        i2c = board.I2C()
        hm = HalfClock(i2c, 0x70)
        st = HalfClock(i2c, 0x71)
        clock = Clock(hm, st)

        return clock.tick


    def old_ticker():
        # configure seven-segment displays
        BRIGHTNESS = 8 * 0.0625
        BLINK_SEPARATORS = True
        i2c = board.I2C()
        left_7seg = Seg7x4(i2c, address=0x70, auto_write=False)
        right_7seg = Seg7x4(i2c, address=0x71, auto_write=False)
        left_7seg.brightness = BRIGHTNESS
        right_7seg.brightness = BRIGHTNESS

        prev_time = dict(
            nothing = 'here',
        )

        def init_time():
            nonlocal prev_time
            t = time.time()
            lt = time.localtime(t)
            third = int((t%1)*60)

            prev_time = dict(
                third = third,
                third_right = third % 10,
                third_left = third // 10,
                second = lt.tm_sec,
                second_right = lt.tm_sec % 10,
                second_left = lt.tm_sec // 10,
                minute = lt.tm_min,
                minute_right = lt.tm_min % 10,
                minute_left = lt.tm_min // 10,
                hour = lt.tm_hour,
                hour_right = lt.tm_hour % 10,
                hour_left = lt.tm_hour // 10,
            )

            if BLINK_SEPARATORS and third > 29:
                left_7seg.print(time.strftime("%H%M", lt))
                right_7seg.print(time.strftime("%%S%02i"%third, lt))
            else:
                left_7seg.print(time.strftime("%H:%M.", lt))
                right_7seg.print(time.strftime("%%S.%02i"%third, lt))

        def display_time():
            # C'est magnifique, mais ce n'est pas la guerre.
            # It is pretty damned fast, though.
            nonlocal prev_time
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

        init_time()
        return display_time


    def main():
        old_tick = old_ticker()
        new_tick = new_ticker()

        number = 1_000_000

        print(f"=== begun at {time.strftime('%c')}")

        print(f"--- old ticker (x{number}):")
        result = timeit.timeit(old_tick, number=number)
        print(f"    {result}")

        print(f"+++ new ticker (x{number}):")
        result = timeit.timeit(new_tick, number=number)
        print(f"    {result}")

        print(f"+++ new ticker (x{number}):")
        result = timeit.timeit(new_tick, number=number)
        print(f"    {result}")

        print(f"--- old ticker (x{number}):")
        result = timeit.timeit(old_tick, number=number)
        print(f"    {result}")

        print(f"--- old ticker (x{number}):")
        result = timeit.timeit(old_tick, number=number)
        print(f"    {result}")

        print(f"+++ new ticker (x{number}):")
        result = timeit.timeit(new_tick, number=number)
        print(f"    {result}")

        print(f"+++ new ticker (x{number}):")
        result = timeit.timeit(new_tick, number=number)
        print(f"    {result}")

        print(f"--- old ticker (x{number}):")
        result = timeit.timeit(old_tick, number=number)
        print(f"    {result}")

        print(f"=== ended at {time.strftime('%c')}")

    main()

# === begun at Sun Jun 12 22:28:06 2022
# --- old ticker (x1000000):
#     23.383717388962395
# +++ new ticker (x1000000):
#     24.496655486989766
# +++ new ticker (x1000000):
#     24.49230616306886
# --- old ticker (x1000000):
#     23.545352958026342
# --- old ticker (x1000000):
#     23.243139944970608
# +++ new ticker (x1000000):
#     24.033728154026903
# +++ new ticker (x1000000):
#     23.957943573012017
# --- old ticker (x1000000):
#     23.183907811064273
# === ended at Sun Jun 12 22:31:17 2022
