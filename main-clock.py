import sys, signal, threading, traceback, subprocess, time, board, digitalio, adafruit_ssd1306
from adafruit_ht16k33.segments import Seg7x4
from PIL import Image, ImageDraw, ImageFont
from clock_segments import sex_to_dec, dec_to_bits


# used to stop threads
KEEP_ON_TICKING = True

# I2C
i2c = board.I2C()
LEFT_ADDR = 0x70
RIGHT_ADDR = 0x71
SMALL_ADDR = 0x3C

# configure seven-segment displays
SEVEN_SEG_FREQUENCY = 60 * 10 # 600 Hz
BRIGHTNESS = 8 * 0.0625
BLINK_SEPARATORS = True
left_7seg = Seg7x4(i2c, address=LEFT_ADDR, auto_write=False)
right_7seg = Seg7x4(i2c, address=RIGHT_ADDR, auto_write=False)
left_7seg.brightness = BRIGHTNESS
right_7seg.brightness = BRIGHTNESS

# configure OLED displays
SMALL_OLED_FREQUENCY = 1  # 1 Hz
SMALL_WIDTH = 128
SMALL_HEIGHT = 32  # Change to 64 if needed
small_oled = adafruit_ssd1306.SSD1306_I2C(SMALL_WIDTH, SMALL_HEIGHT, i2c, addr=SMALL_ADDR)

# configure LEDs (on buttons)
RED_TOP_GPIO = board.D6
GRN_TOP_GPIO = board.D12
RED_BOT_GPIO = board.D13
GRN_BOT_GPIO = board.D16
red_top = digitalio.DigitalInOut(RED_TOP_GPIO)
grn_top = digitalio.DigitalInOut(GRN_TOP_GPIO)
red_bot = digitalio.DigitalInOut(RED_BOT_GPIO)
grn_bot = digitalio.DigitalInOut(RED_BOT_GPIO)
red_top.direction = digitalio.Direction.OUTPUT
grn_top.direction = digitalio.Direction.OUTPUT
red_bot.direction = digitalio.Direction.OUTPUT
grn_bot.direction = digitalio.Direction.OUTPUT

def init():
    init_time()
    small_oled.fill(0)
    small_oled.show()
    red_top.value = False
    grn_top.value = False
    red_bot.value = False
    grn_bot.value = False

def clear():
    left_7seg.fill(0)
    left_7seg.show()
    right_7seg.fill(0)
    right_7seg.show()
    small_oled.fill(0)
    small_oled.show()
    red_top.value = False
    grn_top.value = False
    red_bot.value = False
    grn_bot.value = False

prev_time = dict(
    nothing = 'here',
)

def init_time():
    global prev_time
    t = time.time()
    lt = time.localtime(t)
    third = int((t%1)*60)

    prev_time = dict(
        third = third,
        third_right = third % 10,
        third_left = third // 10,
        second = lt.tm_sec,
        second_right = lt.tm_sec % 10,
        second_left = lt.tm_sec // 10,
        minute = lt.tm_min,
        minute_right = lt.tm_min % 10,
        minute_left = lt.tm_min // 10,
        hour = lt.tm_hour,
        hour_right = lt.tm_hour % 10,
        hour_left = lt.tm_hour // 10,
    )

    if BLINK_SEPARATORS and third > 29:
        left_7seg.print(time.strftime("%H%M", lt))
        right_7seg.print(time.strftime("%%S%02i"%third, lt))
    else:
        left_7seg.print(time.strftime("%H:%M.", lt))
        right_7seg.print(time.strftime("%%S.%02i"%third, lt))

def display_time():
    # C'est magnifique, mais ce n'est pas la guerre.
    # It is pretty damned fast, though.
    global prev_time
    t = time.time()
    lt = time.localtime(t)
    third = int((t%1)*60)
    if third == prev_time['third']:
        return

    dotbit = 0b10000000

    if BLINK_SEPARATORS and third < prev_time['third']:
        dotbit = 0b10000000
        right_7seg.set_digit_raw(1, dec_to_bits[prev_time['second_right']] | dotbit)
        left_7seg.set_digit_raw(3, dec_to_bits[prev_time['minute_right']] | dotbit)
        left_7seg.colon = True
        left_7seg.show()
    elif BLINK_SEPARATORS and prev_time['third'] < 29 <= third:
        dotbit = 0b00000000
        right_7seg.set_digit_raw(1, dec_to_bits[prev_time['second_right']] | dotbit)
        left_7seg.set_digit_raw(3, dec_to_bits[prev_time['minute_right']] | dotbit)
        left_7seg.colon = False
        left_7seg.show()

    (third_left, third_right) = sex_to_dec[third]
    prev_time['third'] = third
    prev_time['third_right'] = third_right
    right_7seg.set_digit_raw(3, dec_to_bits[third_right])

    if third_left == prev_time['third_left']:
        right_7seg.show()
        return
    prev_time['third_left'] = third_left
    right_7seg.set_digit_raw(2, dec_to_bits[third_left])

    second = lt.tm_sec
    if second == prev_time['second']:
        right_7seg.show()
        return
    (second_left, second_right) = sex_to_dec[second]
    prev_time['second'] = second
    prev_time['second_right'] = second_right
    right_7seg.set_digit_raw(1, dec_to_bits[second_right] | dotbit)

    if second_left == prev_time['second_left']:
        right_7seg.show()
        return
    prev_time['second_left'] = second_left
    right_7seg.set_digit_raw(0, dec_to_bits[second_left])
    right_7seg.show()

    minute = lt.tm_min
    if minute == prev_time['minute']:
        return
    (minute_left, minute_right) = sex_to_dec[minute]
    prev_time['minute'] = minute
    prev_time['minute_right'] = minute_right
    left_7seg.set_digit_raw(3, dec_to_bits[minute_right] | dotbit)

    if minute_left == prev_time['minute_left']:
        left_7seg.show()
        return
    prev_time['minute_left'] = minute_left
    left_7seg.set_digit_raw(2, dec_to_bits[minute_left])

    hour = lt.tm_hour
    if hour == prev_time['hour']:
        left_7seg.show()
        return
    (hour_left, hour_right) = sex_to_dec[hour]
    prev_time['hour'] = hour
    prev_time['hour_right'] = hour_right
    left_7seg.set_digit_raw(1, dec_to_bits[hour_right])

    if hour_left == prev_time['hour_left']:
        left_7seg.show()
        return
    prev_time['hour_left'] = hour_left
    left_7seg.set_digit_raw(0, dec_to_bits[hour_left])
    left_7seg.show()

def bye_bye(signal_received, frame):
    global KEEP_ON_TICKING
    KEEP_ON_TICKING = False

tracking_font = ImageFont.load('/home/ptolemarch/Fonts/B612Mono.pil')
small_oled_image = Image.new("1", (small_oled.width, small_oled.height))
small_oled_draw = ImageDraw.Draw(small_oled_image)

def display_tracking():
    small_oled_draw.rectangle((0, 0, small_oled.width, small_oled.height), outline=0, fill=0)

    seconds = ""
    sign = ""

    tracking = subprocess.Popen([
        "/usr/bin/chronyc", "tracking"
    ], stdout=subprocess.PIPE, universal_newlines=True)
    for line in tracking.stdout:
        if not line.startswith("System time "):
            continue
        words = line.rsplit()
        seconds = words[3]
        sign = 1 if words[5] == "fast" else -1
        break

    microseconds = sign * round(float(seconds) * 1000000, 3)
    text = "%+4.3f\xB5s"%(microseconds)
    (font_width, font_height) = tracking_font.getsize(text)
    small_oled_draw.text(
        (small_oled.width // 2 - font_width // 2, small_oled.height // 2 - font_height // 2),
        text,
        font=tracking_font,
        fill=255,
    )

    small_oled.image(small_oled_image)
    small_oled.show()


def antenna_light():
    global KEEP_ON_TICKING
    gpspipe = subprocess.Popen([
        "/usr/bin/gpspipe", "-r"
    ], stdout=subprocess.PIPE, universal_newlines=True)

    # TODO: if dies, restart?
    while KEEP_ON_TICKING and (gpspipe.poll() is None):
        line = gpspipe.stdout.readline().rstrip()
        if line.startswith("$PCD"):
            if line.endswith("1*", 0, -2):
                # internal antenna
                red_top.value = True
                grn_top.value = False
            elif line.endswith("2*", 0, -2):
                # active antenna
                red_top.value = False
                grn_top.value = True
            elif line.endswith("3*", 0, -2):
                # active antenna shorted
                red_top.value = True
                grn_top.value = True
            else:
                # WTF?
                red_top.value = False
                grn_top.value = False

## This next bit is adapted from Stack Overflow
##   https://stackoverflow.com/a/49801719
def every(delay, task, lock):
    global KEEP_ON_TICKING
    next_time = time.time() + delay
    while KEEP_ON_TICKING:
        time.sleep(max(0, next_time - time.time()))
        try:
            lock.acquire()
            task()
            lock.release()
        except Exception:
            clear()
            traceback.print_exc()
            sys.exit(1)
            # in production code you might want to have this instead of course:
            # logger.exception("Problem while executing repetitive task.")
        # skip tasks if we are behind schedule:
        next_time += (time.time() - next_time) // delay * delay + delay

init()

signal.signal(signal.SIGINT, bye_bye)
signal.signal(signal.SIGTERM, bye_bye)

lock = threading.Lock()

clock = threading.Thread(name="clock", target=lambda: every(1/SEVEN_SEG_FREQUENCY, display_time, lock))
tracking = threading.Thread(name="tracking", target=lambda: every(1/SMALL_OLED_FREQUENCY, display_tracking, lock))
top_light = threading.Thread(name="antenna_light", target=antenna_light)

clock.start()
tracking.start()
top_light.start()

clock.join()
tracking.join()
top_light.join()
clear()
sys.exit(0)
