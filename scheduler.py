import asyncio
import time

# given a clock time, convert to monotonic loop time
async def _time_time_to_loop_time(when):
    loop = asyncio.get_running_loop()
    return when - time.time() + loop.time()

async def run_at(when, what):
    loop = asyncio.get_running_loop()
    return loop.call_at(await _time_time_to_loop_time(when), what)

async def run_in(delay, what):
    loop = asyncio.get_running_loop()
    return loop.call_later(delay, what)

def _next_interval(t, interval):
    r"""Given a time, find the beginning of the next whole interval.

    :param t: a time in seconds, probably time.time()
    :param b: an interval in seconds
    :return: the time at which the next whole interval will begin
    """
    return ((t + interval) // interval) * interval

async def run_every(interval, what):
    r"""Given an interval in seconds, execute at the top of that interval.

    Especially: if the interval is a fraction of a second, execute
    at the beginning of the second, then at each equal fraction thereof.
    """
    # when does the next interval begin?
    next_top = _next_interval(time.time(), interval)
    # we probably ought to account for the possibility that the next
    #   interval has already passed
    pass

# lame example, but can't think of anything better
async def main():
    await run_at(time.time()+5, lambda: print(f"hello at {time.asctime()}"))
    for s in range(20):
        print(s/2)
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
