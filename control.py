import time, asyncio, signal, contextlib, json, sys
from collections import defaultdict

import board

from gps import GPS, AntennaStatus, GPSMode
from chrony import ChronycTracking
from buttons import Buttons
from clock import Clock
from oled import OLED
from led import LED

from util import dotdict
from sexagesimal import DecDotSex

class Config:
    buttons = dotdict(
        top = board.D18,
        bottom = board.D5
    )
    clock = dotdict(
        i2c = (0x70, 0x71),
        brightness = 12,  # 0 .. 16
        blink = True,
        local = True
    )
    oled = dotdict(
        little = dotdict(
            i2c = 0x3c,
            size = (128, 32),
            font = dotdict(
                value='fonts/profont/ProFont_r400-29.pil',
                label='fonts/profont/ProFont_r400-11.pil',
            ),
        ),
        big = dotdict(
            i2c = 0x3d,
            size = (128, 64),
            font = dotdict(
                #value='fonts/uw-ttyp0-1.3/genbdf/t0-18b-i01.pil',
                #label='fonts/uw-ttyp0-1.3/genbdf/t0-11-i01.pil',
                value='fonts/ProFontmedium-17.pil',
                label='fonts/profont/ProFont_r400-11.pil',
            ),
        ),
    )
    led = dotdict(
        top = dotdict(
            pins = (board.D6, board.D12)
        ),
        bottom = dotdict(
            pins = (board.D13, board.D16)
        ),
    )


# set up button callbacks
# - shut down (and restart?) whole system
# - shut down (and restart?) this app
class Control:
    def __init__(self):
        self.i2c = board.I2C()

        # this is starting to get inconsistent
        # - gps and tracking should work more similarly
        # - the rest of these should probably be
        #   initialized in their respective tasks
        self.gps = GPS()
        self.chronyc_tracking = defaultdict(str)
        self.clock = Clock(
            self.i2c,
            *(Config.clock.i2c),
            brightness=Config.clock.brightness,
            blink=Config.clock.blink,
            local=Config.clock.local,
        )
        self.oled = dict(
            little = OLED(
                Config.oled.little.size,
                self.i2c,
                Config.oled.little.i2c,
            ),
            big = OLED(
                Config.oled.big.size,
                self.i2c,
                Config.oled.big.i2c,
            ),
        )
        self.led = dict(
            top = LED(*Config.led.top.pins),
            bottom = LED(*Config.led.bottom.pins),
        )

        self.tasks = list()

    def stop(self):
        for t in self.tasks:
            t.cancel()

    async def run(self):
        self.tasks = [asyncio.create_task(aw[1], name=aw[0]) for aw in (
            ("gps", self.gps_task()),
            ("chronyc_tracking", self.chronyc_tracking_task()),
            ("buttons", self.buttons_task()),
            ("clock", self.clock_task()),
            ("big_oled", self.big_oled_task()),
            ("little_oled", self.little_oled_task()),
            ("top_led", self.top_led_task()),
            ("bottom_led", self.bottom_led_task()),
        )]

        await asyncio.gather(*(self.tasks))

    async def gps_task(self):
        await self.gps.run()

    async def chronyc_tracking_task(self):
        async for t in ChronycTracking():
            self.chronyc_tracking = t
            await self.sleep_until_interval(5)

    async def buttons_task(self):
        t = Config.buttons.top
        b = Config.buttons.bottom
        buttons = Buttons(t, b)
        buttons.set_callback([t, b], "_", lambda: self.clock.toggle_local())
        while True:
            await self.sleep_until_interval(1/60)
            buttons.poll()

    async def clock_task(self):
        try:
            while True:
                self.clock.tick()
                await self.sleep_until_interval(1/60)
        finally:
            self.clock.clear()

    async def big_oled_task(self):
        oled = self.oled['big']
        try:
            while True:
                await self.sleep_until_interval(2)
                await oled.write('top', Config.oled.big.font.label, (
                    'Latitude',
                    'Longitude',
                    'Altitude     Sats',
                ))
                await asyncio.sleep(0.2)

                # this is gonna want real __format__ support someday
                await oled.write('bottom', Config.oled.big.font.value, (
                    ' ' + str(DecDotSex(self.gps.info['latitude'])),
                    str(DecDotSex(self.gps.info['longitude'])),
                    str(self.gps.info['altitude'])
                    + '  ' + str(self.gps.info['satellites_used'])
                    + '/' + str(self.gps.info['satellites'])
                    ,
                ))
                await self.sleep_until_interval(2, 1)
                await oled.clear()
        finally:
            await oled.clear()

    async def little_oled_task(self):
        oled = self.oled['little']
        try:
            while True:
                await self.sleep_until_interval(2)
                await oled.write('top', Config.oled.little.font.label, (
                    "PPS Offset",
                ))
                await asyncio.sleep(0.2)

                # the comma at the end is *not* optional, for Python reasons
                await oled.write('bottom', Config.oled.little.font.value, (
                    "%+4.3f\xB5s"%(self.gps.info['pps_offset_usec']),
                ))
                await self.sleep_until_interval(2, 1)
                await oled.clear()
        finally:
            await oled.clear()

    async def top_led_task(self):
        led = self.led['top']
        stratum = 0
        try:
            while True:
                await self.sleep_until_interval(1)

                try:
                    new_stratum = int(self.chronyc_tracking['Stratum'])
                except ValueError:
                    new_stratum = 0

                if new_stratum == stratum:
                    continue
                stratum = new_stratum

                if stratum == 0:
                    led.off()
                elif stratum == 1:
                    led.green()
                elif stratum > 1:
                    led.amber()
                elif stratum == AntennaStatus.SHORTED:
                    led.red()
        finally:
            led.off()

    async def bottom_led_task(self):
        led = self.led['bottom']
        antenna = AntennaStatus.UNKNOWN
        try:
            while True:
                await self.sleep_until_interval(1)

                new_antenna = self.gps.info['antenna']
                if new_antenna == antenna:
                    continue
                antenna = new_antenna

                if antenna == AntennaStatus.UNKNOWN:
                    led.off()
                elif antenna == AntennaStatus.EXTERNAL:
                    led.green()
                elif antenna == AntennaStatus.INTERNAL:
                    led.amber()
                elif antenna == AntennaStatus.SHORTED:
                    led.red()
        finally:
            led.off()


    async def sleep_until_interval(self, interval, offset=0, result=None):
        r"""Given an interval, sleep until the beginning of the next whole
        interval.

        :param interval: an interval, expressed in seconds
        :param result: returned when done sleeping
        :return: None
        """
        now = time.time()

        # when is the next interval?
        when = ((now + interval) // interval) * interval
        delay = when - now + offset

        return await asyncio.sleep(delay, result=result)


async def main():
    control = Control()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, control.stop)
    loop.add_signal_handler(signal.SIGTERM, control.stop)
    #loop.add_signal_handler(signal.SIGQUIT, control.stop)

    with contextlib.suppress(asyncio.CancelledError):
        await control.run()



if __name__ == '__main__':
    asyncio.run(main())


