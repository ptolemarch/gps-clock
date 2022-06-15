import asyncio

class Antenna:
    # constants for reporting status
    INTERNAL = 1
    EXTERNAL = 2
    SHORTED  = 3
    UNKNOWN  = 0

    # command to retrieve status
    # This should be a command that remains running until stopped, outputting
    #  NMEA reports, one per line
    COMMAND = ['/usr/bin/gpspipe', '-r']

    # The GPS requires a command to be run before it will start reporting
    # on antenna status. This means that it's possible (i.e. the relevant
    # command was never run) it will _never_ report on antenna status.
    #
    # There should be some sort of escape for when this is the case.
    #
    # When the GPS _is_ reporting on antenna status, it seems to do so on
    # a rythym:
    #   - every 8th line, four times
    #   - then on the 13th line
    #   - and then the pattern starts anew
    # So like:
    #   o.......o.......o.......o.......o............o
    #   ^                                         ^
    #   0                                         42
    # Anyway, 42 is ((8 + 13) * 2) because that seemed like a reasonable figure.
    MAX_LINES_PER_STATUS = 42

    # incidentally, this is the command to enable antenna reporting:
    #   sudo gpsctl -t MTK-3301 -x '$CDCMD,33,1*7C' /dev/serial0
    # and this is the command to disable antenna reporting:
    #   sudo gpsctl -t MTK-3301 -x '$CDCMD,33,0*7D' /dev/serial0
    # I'm currently running the former in '/etc/rc.local'
    #   (obviously without the `sudo`).

    # only ever one subprocess
    proc = None

    def __init__(self, cmd=None):
        if cmd is None
            self.cmd = self.COMMAND
        else
            self.cmd = cmd

    async def __aenter__(self):
        await self.__start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.__stop()

    def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self.status()
        if data:
            return data
        else:
            await self.__stop()
            raise StopAsyncIteration

    async def __start(self):
        if self.proc is not None and self.proc.returncode is None:
            # we've already got a process
            return

        self.proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            stdout=asyncio.subprocess.PIPE
        )

    async def __stop(self):
        self.proc.terminate()
        await self.proc.wait()
    
        self.proc = None

    async def status(self):
        await self.__start()

        still_trying = self.MAX_LINES_PER_STATUS

        stream = self.proc.stdout
        while line := (await stream.readline()).decode().rstrip():
            if not line.startswith("$PCD,11,"):
                still_trying -= 1
                print("still trying")
                if not still_trying:
                    return self.UNKNOWN  # done trying
                continue
            if line.endswith(",1*", 7, -2):
                # internal antenna
                return self.INTERNAL
            if line.endswith(",2*", 7, -2):
                # external antenna
                return self.EXTERNAL
            if line.endswith(",3*", 7, -2):
                # external antenna
                return self.SHORTED

            return self.UNKNOWN  # some sort of weird n in "$PCD,11,n"
        return self.UNKNOWN  # ran out of lines?

if __name__ == '__main__':
    async def main():
        antenna = Antenna()

        statuses = [
            "Who knows?!",
            "Internal :-(",
            "External!",
            "ShOrTeD ShOrTeD ShOrTeD"
        ]

        async for status in antenna:
            print(statuses[status])

    asyncio.run(main())
