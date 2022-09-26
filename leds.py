import digitalio, enum
from collections import namedtuple

# for main()
from argparse import ArgumentParser, BooleanOptionalAction
import board

class LED:
    SubLEDs = namedtuple('SubLEDs', ('red', 'green'))

    def __init__(self, red, green):
        self.sub_leds = self.SubLEDs(*(digitalio.DigitalInOut(pin) for pin in (red, green)))
        for pin in self.sub_leds:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False

    def off(self):
        self.sub_leds.red.value = False
        self.sub_leds.green.value = False

    def red(self):
        self.sub_leds.red.value = True
        self.sub_leds.green.value = False

    def green(self):
        self.sub_leds.red.value = False
        self.sub_leds.green.value = True

    def amber(self):
        self.sub_leds.red.value = True
        self.sub_leds.green.value = True


def main():
    argyle = ArgumentParser()
    argyle.add_argument('led',
        choices=['top', 'bottom'],
        default='top',
        help="which led to change?"
    )
    argyle.add_argument('color',
        choices=['off', 'red', 'green', 'amber'],
        default='off',
        help="What color?"
    )
    args = argyle.parse_args()

    led = LED(*dict(
        top = (board.D6, board.D12),
        bottom = (board.D13, board.D16),
    )[args.led])

    getattr(led, args.color)()

if __name__ == '__main__':
    main()
