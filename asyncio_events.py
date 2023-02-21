import asyncio

async def task_numbers(event):
    i = 0
    while True:
        print(i)
        i += 1
        await event.wait()
        print(event.is_set())
        event.clear()
    return

async def task_letters(event):
    a = ord('a')
    z = ord('z')
    i = a
    while True:
        print(chr(i))
        i += 1
        if i > z:
            i = a
        await event.wait()
        print(event.is_set())
        event.clear()
    return

async def synchronizer(event):
    while True:
        event.set()
        #event.clear()
        await asyncio.sleep(1)

async def main():
    event = asyncio.Event()
    L = await asyncio.gather(
        task_numbers(event),
        task_letters(event),
        synchronizer(event),
    )
    print("===")
    print(L)

if __name__ == '__main__':
    asyncio.run(main())
