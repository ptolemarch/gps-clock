import digitalio, time, enum, collections
from adafruit_debouncer import Debouncer

# Note on implementation and design:
# It would probably be better to use adafruit_debouncer.Button, if I could,
# rather than the lower-level adafruit_debouncer.Debouncer. I'm certainly
# reproducing here logic that already exists in Button. The reason I'm not
# using Button is twofold:
# - While Button makes a nice distinction between presses and long presses,
#   I'd like to have a third category of super-long presses.
# - I also want to be able to recognize simultaneous (or, rather,
#   near-simultaneous) presses of both buttons. On a reasonably fast update()
#   loop, this becomes difficult. (1/60 of a second is a pretty short time,
#   even for fingers that are right next to each other.)
# - This means that, even using Button, I'd have to be doing my own timing,
#   at which point it feels like I should just use Debouncer itself.
# (I intend to use the gesture of a five-second-long two-button press as the
# instruction to shut down the computer.)

# After about two day's worth of over-thinking this, I think I've come up
# with a way of reducing this from massively overengineered to merely clearly
# overengineered. Here's the plan:
# - For now I'm going to use the word, "gesture", to refer to a single event,
#   which may consist of a single button press or a related series of presses.
# - A button "press" has two components, in this order: First, the button goes
#   "down", and then it goes "up". In the case of the "super-long press", the
#   up component is inferred/skipped/ignored.
# - Buttons are assigned numbers based upon their order in the *pins argument.
#   These numbers are powers of two.
# - A single gesture is reported as coming from some particular button,
#   identified by number.
# - A gesture consists of a sequence of presses. The gesture is complete when
#   the button goes up and then does NOT go down within repeated_press_max.
# - A gesture may consist of multiple physical buttons, but it is always
#   reported as coming from some particular button. In the case of multiple
#   physical butons, the button number is the sum of the numbers of the
#   component physical buttons.
# - For a gesture to consist of multiple physical buttons, each button must go
#   down within multiple_press_max and then go up within multiple_press_max.
# - A gesture consisting of multiple physical buttons is identified at the
#   END of the button presses of which it's comprised.

# tunable durations:
# - short press minimum  (used as Debouncer().interval)
# -   "     "   maximum
# - long press minimum
# - super-long press minimum
# - maximum delay between presses to count as a repeated press
# -    "      "      "       "    "    "   "  " multiple press

class ButtonConfig:
    short_press_min = 2/60
    long_press_min = 30/60
    xlong_press_min = 5
    repeated_press_max = 20/60
    multiple_press_max = 5/60

class PressLength(enum.Enum):
    SHORT = "."
    LONG = "_"
    XLONG = "~"

    def __str__(self):
        return str(self.value)

    @classmethod
    def fromSeconds(cls, seconds):
        if seconds < ButtonConfig.long_press_min:
            return cls.SHORT
        if seconds < ButtonConfig.xlong_press_min:
            return cls.LONG
        return cls.XLONG


# a Press, or a Sequence, is identified solely by its timing
# a Gesture is idenitifed solely by its PressLengths

class Press:
    def __init__(self, begin, end):
        self.begin = begin
        self.end = end
    def __eq__(self, other):
        print("comparing presses")
        print(f" self.begin: {self.begin}")
        print(f"   self.end: {self.end}")
        print(f"other.begin: {other.begin} ({self.begin - other.begin})")
        print(f"  other.end: {other.end} ({self.end - other.end})")
        return (
            abs(self.begin - other.begin) <= ButtonConfig.multiple_press_max
            and
            abs(self.end - other.end) <= ButtonConfig.multiple_press_max
        )
    def __hash__(self):
        return hash((self.begin, self.end))
    def length(self):
        return PressLength.fromSeconds(self.end - self.begin)

class Sequence:
    def __init__(self, *presses):
        self.presses = presses
    def __eq__(self, other):
#        print("comparing sequences")
#        print(f" self.presses: {self.presses}")
#        print(f"other.presses: {other.presses}")
        return self.presses == other.presses
    def __hash__(self):
        return hash(self.presses)
    def __bool__(self):
        return True if len(self.presses) else False
    def lengths(self):
        return tuple(p.length() for p in self.presses)

class Gesture:
    def __init__(self, *lengths):
        self.lengths = lengths
    def __eq__(self, other):
        return self.lengths == other.lengths
    def __hash__(self):
        return hash(self.lengths)
    def __str__(self):
        return "".join(str(l) for l in self.lengths)
    def __bool__(self):
        return True if len(self.lengths) else False

    @classmethod
    def fromString(cls, string):
        return cls(*(PressLength(s) for s in string))

    @classmethod
    def fromSequence(cls, sequence):
        return cls(*(sequence.lengths()))
    

class Button:
    def __init__(self, pin):
        dio = digitalio.DigitalInOut(pin)
        # these next two lines, for direction and pull, must come in this order
        dio.direction = digitalio.Direction.INPUT
        dio.pull = digitalio.Pull.UP
        self.db = Debouncer(dio, interval=ButtonConfig.short_press_min)
        self.presses = []
        self.last_fall_time = time.time()
        self.last_rise_time = time.time()

    # - update
    # - keep account of what's going on
    # - if we're at the end of a sequence, return it
    def poll(self):
        self.db.update()
        now = time.time()

        if self.db.fell:
            print("fell")
            self.last_fall_time = now - self.db.current_duration
            return

        if self.db.rose and self.last_fall_time:
            print("rose")
            self.last_rise_time = now - self.db.current_duration
            self.presses.append(Press(
                self.last_fall_time,
                self.last_rise_time,
            ))
            return

        if (
            self.db.value  # button not currently held down
            and
            self.last_rise_time + ButtonConfig.repeated_press_max < now
        ):
            # at the end of a Sequence
            sequence = Sequence(*(self.presses))
            self.presses = []
            return sequence

        if (
            not self.db.value  # button currently held down
            and
            self.last_fall_time
            and
            self.last_fall_time + ButtonConfig.xlong_press_min < now
        ):
            # xlong press always ends a Sequence
            self.last_rise_time = now
            sequence = Sequence(*(self.presses), Press(
                self.last_fall_time,
                self.last_rise_time
            ))
            self.last_fall_time = 0
            self.presses = []
            return sequence

        return



class Buttons:
    def __init__(self, handler, *buttons):
        self.buttons = buttons
        self.handler = handler
#        if pins is None:
#            pins = board.D18, board.D5
#        self.buttons = [Button(p, 2**n) for n, p in enumerate(pins)]

    def poll(self):
        # collect sequences into buttons
        sequences = collections.defaultdict(int)  # apparently the same as lambda:0
        for n, b in enumerate(self.buttons):
            sequence = b.poll()
            if not sequence:
                continue
            print(f"-- button {2**n} -- {Gesture.fromSequence(sequence)} -- {hash(sequence)}")
            sequences[sequence] += 2**n

        # call handler
        for sequence, number in sequences.items():
            gesture = Gesture.fromSequence(sequence)
            if not gesture:
                continue
            self.handler.handle(number, gesture)

if __name__ == '__main__':
    import board

    class Handler:
        def handle(self, button, gesture):
            print(f"[Button {button}]: {gesture}")

    def main():
        buttons = Buttons(Handler(), Button(board.D18), Button(board.D5))

        while True:
            time.sleep(1/60)
            buttons.poll()

    main()
