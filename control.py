import time, asyncio, signal, contextlib, json, sys
from collections import defaultdict

import systemd.daemon
import board

from multibutton_debouncer import MultiButton

from gps import GPS, AntennaStatus, GPSMode
from chrony import ChronycTracking
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
                value_8='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-29.pil',
                value_11='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-22.pil',
                value_13='/home/ptolemarch/gps-clock/fonts/ProFontmedium-17.pil',
                value_18='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-15.pil',
                value_n='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-12.pil',
                label='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-11.pil',
            ),
        ),
        big = dotdict(
            i2c = 0x3d,
            size = (128, 64),
            font = dotdict(
                #value='fonts/uw-ttyp0-1.3/genbdf/t0-18b-i01.pil',
                #label='fonts/uw-ttyp0-1.3/genbdf/t0-11-i01.pil',
                value='/home/ptolemarch/gps-clock/fonts/ProFontmedium-17.pil',
                label='/home/ptolemarch/gps-clock/fonts/profont/ProFont_r400-11.pil',
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
            ("systemd", self.systemd_task()),
            ("gps", self.gps_task()),
            ("chronyc_tracking", self.chronyc_tracking_task()),
            ("buttons", self.buttons_task()),
            ("clock", self.clock_task()),
            ("little_oled", self.little_oled_task()),
            ("big_oled", self.big_oled_task()),
            ("top_led", self.top_led_task()),
            ("bottom_led", self.bottom_led_task()),
        )]

        await asyncio.gather(*(self.tasks))

    async def systemd_task(self):
        systemd.daemon.notify('READY=1')
        while True:
            await asyncio.sleep(1)
            systemd.daemon.notify('WATCHDOG=1')

    async def gps_task(self):
        await self.gps.run()

    async def chronyc_tracking_task(self):
        async for t in ChronycTracking():
            self.chronyc_tracking = t
            await self.sleep_until_interval(5)

    async def buttons_task(self):
        t = Config.buttons.top
        b = Config.buttons.bottom
        buttons = MultiButton(t, b)
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

    async def little_oled_task(self):
        oled = self.oled['little']
        try:
            while True:
                # four-second loop
                await self.sleep_until_interval(4)
                await oled.write('top', Config.oled.little.font.label, (
                    "PPS Offset",
                ))
                await asyncio.sleep(0.5)

                text = "\xB1\xBF\xD8?\xB5s"
                with contextlib.suppress(TypeError, ValueError):
                    offset = self.gps.info['pps_offset_usec']
                    text = "%+4.3f\xB5s"%(offset)

                # TODO: just realized that this should instead be, like,
                # converting from usec to sec to minutes, etc.
                length = len(text)
                if length <= 8:
                    font = Config.oled.little.font.value_8
                elif length <= 11:
                    # This barely fits 11 characters, and I'm okay with that.
                    # (The +/- at the front will be slightly cut off.)
                    font = Config.oled.little.font.value_11
                elif length <= 13:
                    font = Config.oled.little.font.value_13
                elif length <= 18:
                    font = Config.oled.little.font.value_18
                else:
                    font = Config.oled.little.font.value_n

                # the comma at the end is *not* optional, for Python reasons
                # TODO: it'd be awfully nice to fix that
                await oled.write('bottom', font, (
                    text,
                ))

                await asyncio.sleep(1)
                await oled.clear()
        finally:
            await oled.clear()

    async def big_oled_task(self):
        oled = self.oled['big']
        try:
            while True:
                # four-second loop, but start on second 2
                await self.sleep_until_interval(4, 2)
                await oled.write('top', Config.oled.big.font.label, (
                    'Latitude',
                    'Longitude',
                    'Altitude     Sats',
                ))
                await asyncio.sleep(0.5)

                # TODO: this is gonna want real __format__ support someday
                with contextlib.suppress(TypeError, ValueError):
                    await oled.write('bottom', Config.oled.big.font.value, (
                        ' ' + str(DecDotSex(self.gps.info['latitude'])),
                        str(DecDotSex(self.gps.info['longitude'])),
                        str(self.gps.info['altitude'])
                        + '  ' + str(self.gps.info['satellites_used'])
                        + '/' + str(self.gps.info['satellites'])
                        # TODO: it'd be awfully nice to fix this:
                        , # non-optional comma!
                    ))
                await asyncio.sleep(1)
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


    async def sleep_until_interval(self, interval, offset=0, result=None, debug=None):
        r"""Given an interval, sleep until the beginning of the next whole
        interval.

        :param interval: an interval, expressed in seconds
        :param result: returned when done sleeping
        :return: None
        """
        now = time.time()

        # when is the next interval?
        when = ((now + interval) // interval) * interval
        delay = (when + offset) - now

        if debug:
            print(f'( {now} + {interval} ) = {now + interval}')
            print(f'( {now} + {interval} ) // interval = {(now + interval) // interval}')
            print(f'( ( {now} + {interval} ) // interval ) * interval ) = {((now + interval) // interval) * interval}')
            print(f'sleep for {delay}s; when:{when}; offset:{offset}; now:{now}')
        return await asyncio.sleep(delay, result=result)


async def main():
    control = Control()

    loop = asyncio.get_running_loop()

    loop.add_signal_handler(signal.SIGINT, control.stop)
    loop.add_signal_handler(signal.SIGTERM, control.stop)
    #loop.add_signal_handler(signal.SIGQUIT, control.stop)


    # SIGABRT would mostly be sent by systemd after failing
    # to get a watchdog ping. Which probably means something's gone
    # pretty wrong, and this won't help much anyway. But here goes.
    loop.add_signal_handler(signal.SIGABRT, control.stop)

    with contextlib.suppress(asyncio.CancelledError):
        await control.run()



if __name__ == '__main__':
    asyncio.run(main())


