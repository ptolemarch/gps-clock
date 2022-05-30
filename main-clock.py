import sys, signal, threading, traceback, subprocess, time, board, digitalio, adafruit_ssd1306
from adafruit_ht16k33.segments import Seg7x4
from PIL import Image, ImageDraw, ImageFont


# used to stop threads
KEEP_ON_TICKING = True

# I2C
i2c = board.I2C()
LEFT_ADDR = 0x70
RIGHT_ADDR = 0x71
SMALL_ADDR = 0x3C

# configure seven-segment displays
SEVEN_SEG_FREQUENCY = 60  # 180 Hz
BRIGHTNESS = 8 * 0.0625
BLINK_SEPARATORS = True
left_7seg = Seg7x4(i2c, address=LEFT_ADDR)
right_7seg = Seg7x4(i2c, address=RIGHT_ADDR)
left_7seg.brightness = BRIGHTNESS
right_7seg.brightness = BRIGHTNESS

# configure OLED displays
SMALL_OLED_FREQUENCY = 20  # 10 Hz
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

prev_left  = ""
prev_right = ""

def clear():
    left_7seg.fill(0)
    right_7seg.fill(0)
    small_oled.fill(0)
    small_oled.show()
    red_top.value = False
    grn_top.value = False
    red_bot.value = False
    grn_bot.value = False

def display(left, right):
    if right != prev_right:
        right_7seg.print(right)
    else:
        return
    if left != prev_left:
        left_7seg.print(left)
        if left[2] != ":":
            left_7seg.colon = False
#def display(left, right):
#    if right == prev_right and left == prev_left:
#        return
#    left_7seg.print(left)
#    if left[2] != ":":
#        left_7seg.colon = False
#    right_7seg.print(right);

def display_time():
#    print("begin: ", time.time())
    t = time.time()
    lt = time.localtime(t)
    third = int((t%1)*60)

    if BLINK_SEPARATORS and third > 29:
        left = time.strftime("%H%M", lt)
        right = time.strftime("%%S%02i"%third, lt)
    else:
        left = time.strftime("%H:%M.", lt)
        right = time.strftime("%%S.%02i"%third, lt)

    display(left, right)
#    print("  end: ", time.time())

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
def every(delay, task, name):
    global KEEP_ON_TICKING
    next_time = time.time() + delay
    while KEEP_ON_TICKING:
        time.sleep(max(0, next_time - time.time()))
        try:
            task()
        except Exception:
            clear()
            traceback.print_exc()
            sys.exit(1)
            # in production code you might want to have this instead of course:
            # logger.exception("Problem while executing repetitive task.")
        # skip tasks if we are behind schedule:
#        if (time.time() > next_time):
#            print("oops: %s %f"%(name, next_time - time.time()))
#        if (time.time() > next_time):
#            print("oops: %s %f %f"%(name, time.time(), next_time))
        next_time += (time.time() - next_time) // delay * delay + delay

clear()

signal.signal(signal.SIGINT, bye_bye)
signal.signal(signal.SIGTERM, bye_bye)

clock = threading.Thread(name="clock", target=lambda: every(1/SEVEN_SEG_FREQUENCY, display_time, "clock"))
tracking = threading.Thread(name="tracking", target=lambda: every(1/SMALL_OLED_FREQUENCY, display_tracking, "tracking"))
top_light = threading.Thread(name="antenna_light", target=antenna_light)

clock.start()
tracking.start()
top_light.start()

clock.join()
tracking.join()
top_light.join()
clear()
sys.exit(0)
