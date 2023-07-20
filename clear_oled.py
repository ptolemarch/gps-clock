import asyncio

import board

from oled import OLED
from led import LED

async def main():
    i2c = board.I2C()
    await OLED((128, 32), i2c, 0x3c).clear()
    await OLED((128, 64), i2c, 0x3d).clear()
    #LED(board.D6, board.D12).red(),
    #LED(board.D13, board.D16).red(),

asyncio.run(main())
