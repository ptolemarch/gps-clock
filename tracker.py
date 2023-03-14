import asyncio
from collections import defaultdict

class Tracker:
    def __init__(self, cmd, *parsers):
        self.cmd = cmd
        self.parsers = parsers
        self.proc = None
        self.accumulator = defaultdict(str)

    async def __aenter__(self):
        await self.__start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.__stop()

    def __aiter__(self):
        return self

    async def __anext__(self):
        # yes, this is pretty much intended to be an infinite loop
        # TODO: probably should be trying to clean up after myself, though?
        return await self.track()
        #if data:
        #    return data
        #else:
        #    await self.__stop()
        #    raise StopAsyncIteration

    async def __start(self):
        if self.proc is not None and self.proc.returncode is None:
            # we've already got a process
            return

        self.proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            stdout=asyncio.subprocess.PIPE
        )
        self.stream = self.proc.stdout

    async def __stop(self):
        print('tracker stopped')
        self.proc.terminate()
        await self.proc.wait()

        self.proc = None

    async def track(self):
        await self.__start()

        line = (await self.stream.readline()).decode().rstrip()

        for parser in self.parsers:
            self.accumulator.update(parser.parse(line))

        return self.accumulator

if __name__ == '__main__':
    import json

    class PingFirstLineParser:
        def parse(self, line):
            if not line.startswith("PING "):
                return dict()
            return dict(
                size = line.split()[3].split("(")[0],
            )

    class PingResponseParser:
        def parse(self, line):
            if not line.startswith(" bytes from ", 2):
                return dict()
            return dict(
                time = line.split(sep="=")[-1],
                count = line.split()[0],
            )

    async def main():
        pingTracker = Tracker([
            'ping', '8.8.8.8'
        ], PingFirstLineParser(), PingResponseParser())

        async for status in pingTracker:
            print(json.dumps(status))

    asyncio.run(main())
