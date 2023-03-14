import asyncio
import json
import sys

# this makes me kinda wish I hadn't named my gpspipe interface "Tracker"...
class ChronycTracking:
    def __init__(self, cmd=None):
        if cmd is None:
            self.cmd = [ "/usr/bin/chronyc", "tracking" ]
        else:
            self.cmd = cmd

    def __aiter__(self):
        return self

    async def __anext__(self):
        proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            stdout=asyncio.subprocess.PIPE
        )
        stream = proc.stdout

        chronyc_tracking = dict()
        async for line in stream:
            line = line.decode().rstrip()
            key, value = (
                kv.rstrip().strip()
                for kv
                in line.split(':', maxsplit=1)
            )
            chronyc_tracking[key] = value

        await proc.wait()
        return chronyc_tracking
            
class ChronyClients:
    pass

async def main():
    async for ct in ChronycTracking():
        print(json.dumps(ct))
        sys.stdout.flush()
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())

