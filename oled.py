import asyncio, textwrap, board, digitalio, adafruit_ssd1306
from functools import lru_cache
from warnings import warn
from dataclasses import dataclass
from typing import Tuple
from enum import Enum
from math import floor
from PIL import Image, ImageDraw, ImageFont
from textwrap import dedent

from clock import sleep_until_interval
#from scheduler import run_in

# to convert TTF to PIL:
#    otf2bdf -r 50 -c M -p 18 -o B612Mono.bdf B612Mono-Regular.ttf
#    pilfont.py B612Mono.bdf 
# you can also just use ImageFont.truetype(), but it looks like shit
#   (whether or not you use RAQM)
# To get sizes to (approximately) match ImageFont.truetype(), use -r 72
# To get sizes that (approximately) match BDF bitmap font sizes, use -r 50

# UW ttyp0 bitmap font:
#  https://people.mpi-inf.mpg.de/~uwe/misc/uw-ttyp0/

# see latin1(7) for chars like micro, superscript 1,2,3, etc.

# object containing
#  - particular oled
#  - abstractions necessary to update that display?
#    - careful not to be overly general
#    - but there are probably some patterns I'll use
#      across both displays and all modes, and those
#      might be nicely abstractable
#  - a lock for it (?)

# also definitely need an an object somewhere to handle
#  - a lock on the I2C bus itself

# task to
#  - get status from somewhere
#    - possibly an event?
#  - update OLED with this stuff
#  - blink to show heading of what's being displayed

class WritAlign(Enum):
    TOP = "top"        # actually, at the moment, anything other than TOP
    MIDDLE = "middle"  #  will be considered BOTTOM
    BOTTOM = "bottom"

@dataclass(frozen=True)  # therefore hashable
class Writ:
    size: Tuple[int, int]
    align: WritAlign
    font: str
    text: Tuple[str, ...]

# this is here entirely because an ImageFont itself cannot be hashed
@lru_cache
def _gen_font(font_filename):
    return ImageFont.load(font_filename)

# just a guess, but I think that it's probably bad to use @lru_cache on
# an async function, since an async function actually returns a coroutine,
# and I certainly don't want to cache the coroutine itself
@lru_cache
def _gen_image(writ):
    width, height = writ.size
    align = writ.align
    font = _gen_font(writ.font)
    text = writ.text

    # figure out how to space lines
    # - the idea is that each line occupies the same amount of space
    # - in particular, if the top of one line is at the top of the display
    #   (because writ.align == WritAlign.TOP), then the bottom of the
    #   bottom line will NOT be at the bottom of the display (unless
    #   spacing comes to 0)
    # - ImageFont.getbbox() works weirdly when given multi-line text. Which
    #   is the main reason we're not doing that (and not using
    #   ImageDraw.multiline_text())
    
    # these will be the maximum dimensions across all lines
    left, top, right, bottom = map(max, zip(*map(font.getbbox, text)))
    line_width = right - left
    line_height = bottom - top
    line_count = len(text)

    text_width = line_width
    text_height = line_height * line_count

    if text_width > width:
        warn("text wider than OLED")
    if text_height > height:
        warn("text taller than OLED")

    height_surplus = height - text_height
    spacing = floor(height_surplus / line_count)

    image = Image.new("1", (width, height))
    draw = ImageDraw.Draw(image)
    # figure out where to position lines
    # for now, always all the way to the left
    position_x = 0
    position_y = 0 if align == WritAlign.TOP else spacing
    for t in text:
        draw.text((0,position_y), t, fill=255, font=font, spacing=spacing)
        position_y += line_height + spacing

    return image


class OLED:
    def __init__(
        self,
        size,
        i2c,
        address,
        value_font_filename="fonts/uw-ttyp0-1.3/genbdf/t0-18-i01.pil",
        label_font_filename="fonts/uw-ttyp0-1.3/genbdf/t0-11-i01.pil",
    ):
        self.size = size
        self.i2c = i2c
        self.address = address
        self.value_font_filename = value_font_filename
        self.label_font_filename = label_font_filename
        self.__initialized = False

    async def __initialize(self):
        if self.__initialized:
            return
        self.__initialized = True

        self.ssd1306 = adafruit_ssd1306.SSD1306_I2C(
            *self.size,
            self.i2c,
            addr=self.address
        )

    async def clear(self):
        await self.__initialize()
        self.ssd1306.fill(0)
        self.ssd1306.show()

    async def fill(self):
        await self.__initialize()
        self.ssd1306.fill(1)
        self.ssd1306.show()

    def __show(self, image):
        self.ssd1306.image(image)
        self.ssd1306.show()

    async def update(self, value, label):
        await self.__initialize()

        self.__show(_gen_image(Writ(
            size=self.size,
            align=WritAlign.TOP,
            font=self.value_font_filename,
            text=value
        )))

        await sleep_until_interval(1/2)

        self.__show(_gen_image(Writ(
            size=self.size,
            align=WritAlign.BOTTOM,
            font=self.label_font_filename,
            text=label
        )))

        
async def main():
    i2c = board.I2C()
    lol = OLED((128,64), i2c, 0x3d)

    await lol.update((
        " 41;39,55,7",
        "-83;42,12,12",
        "213.2"
    ),(
        "Latitude",
        "Longitude",
        "Altitude"
    ))

    await asyncio.sleep(0.5)
    await lol.clear()

#        lol = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3d)
#        image = Image.new("1", (128, 64))
#        draw = ImageDraw.Draw(image)
#        font = ImageFont.load("fonts/ttyp0/uw-ttyp0-1.3/genbdf/t0-18-i01.pil")
#
#        # latitude, then longitude:
#        # "In Cartography, tradition has been to write co-ordinates as latitude followed by longitude."
#        #  https://www.trekview.org/blog/2022/latitude-longitude-standard/
#        text = textwrap.dedent("""\
#            Lat:  41;39,55,7
#            Lon: -83;42,12,12
#            Alt: 213.2
#        """)
#        draw.multiline_text((0,0), text, font=font, spacing=1, fill=255)
#
#        lol.image(image)
#        lol.show()
        

# small OLED:
#  big: B612Mono-24.pil


if __name__ == '__main__':
    asyncio.run(main())

