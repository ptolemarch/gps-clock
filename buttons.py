import digitalio, enum, collections, itertools, warnings
from collections import defaultdict
from adafruit_debouncer import Debouncer

# dataclasses and their type annotations
from dataclasses import dataclass
from typing import Tuple, FrozenSet
from adafruit_blinka.microcontroller.bcm283x.pin import Pin


class DebouncerConfig:
    # durations of presses:
    short_press_min = 2/60
    long_press_min = 30/60
    xlong_press_min = 5
    # delays between presses:
    repeated_press_max = 10/60
    multiple_press_max = 5/60


class DebouncerValue(enum.Enum):
    DOWN = False   # pressed
    UP = True      # released

    def __bool__(self):
        return bool(self.value)

    @staticmethod
    def is_DOWN(value):
        return not bool(value)

    @staticmethod
    def is_UP(value):
        return bool(value)

    def __str__(self):
        return "DOWN" if self.is_DOWN(self.value) else "UP"


class Press(enum.Enum):
    SHORT = "."
    LONG = "_"
    XLONG = "~"

    def __str__(self):
        return str(self.value)

    @classmethod
    def fromSeconds(cls, seconds):
        if seconds < DebouncerConfig.short_press_min:
            return None
        if seconds < DebouncerConfig.long_press_min:
            return cls.SHORT
        if seconds < DebouncerConfig.xlong_press_min:
            return cls.LONG
        return cls.XLONG


@dataclass(frozen=True)  # therefore hashable
class PressSequence:
    presses: Tuple[Press]

    def __init__(self, presses):
        if isinstance(presses, str):
            object.__setattr__(self, 'presses',
                tuple(Press(c) for c in presses)
            )
        elif isinstance(presses, list):
            object.__setattr__(self, 'presses',
                tuple(self.__no_none(presses))
            )
        elif isinstance(presses, tuple):
            object.__setattr__(self, 'presses',
                tuple(self.__no_none(presses))
            )
        else:
            raise TypeError("can't make a PressSequence out of this")

    def __str__(self):
        return ''.join(*presses)

    def __no_none(self, presses):
        return filter(lambda p: p is not None, presses)
        

@dataclass(frozen=True)  # therefore hashable
class Gesture:
    button: FrozenSet[int]
    presses: PressSequence


class Buttons:
    def __init__(self, *pins):
        self.dbs = [PinnedDebouncer(p) for p in pins]
        self.states = [StartState(self.dbs)]
        self.callbacks = dict()

    def set_callback(self, pins, sequence_str, callback):
        ids = frozenset(pin.id for pin in pins)
        gesture = Gesture(ids, PressSequence(sequence_str))
        self.callbacks[gesture] = callback

    def delete_callback(self, pins, sequence_str):
        ids = frozenset(pin.id for pin in pins)
        gesture = Gesture(ids, PressSequence(sequence_str))
        del self.callback[gesture]

    def get_callback(self, pins, sequence_str):
        ids = frozenset(pin.id for pin in pins)
        gesture = Gesture(ids, PressSequence(sequence_str))
        return self._get_callback(gesture)

    def _get_callback(self, gesture):
        if gesture in self.callbacks:
            return self.callbacks[gesture]
        return lambda: None

    def _handle_callback(self, gesture):
        self._get_callback(gesture)()

    def poll(self):
        new_states = list(itertools.chain.from_iterable(
            state.change() for state in self.states
        ))
        in_progress = list(filter(
            lambda s: not isinstance(s, CollapsibleState),
            new_states
        ))
        starting = list(filter(
            lambda s: isinstance(s, StartState),
            new_states
        ))
        ending = list(filter(
            lambda s: isinstance(s, EndState),
            new_states
        ))

        # handle gestures
        for state in ending:
            self._handle_callback(state.gesture())

        # collect PinnedDebouncers into a new StartState
        dbs = list(itertools.chain.from_iterable(
            s.dbs for s in itertools.chain(starting, ending)
        ))

        # set up new states
        if dbs:
            if len(starting) == 1 and len(ending) == 0:
                self.states = list(itertools.chain(in_progress, starting))
            else:
                self.states = [*in_progress, StartState(dbs)]
        else:
            self.states = list(in_progress)


class PinnedDebouncer:
    def __init__(self, pin):
        dio = digitalio.DigitalInOut(pin)
        dio.direction = digitalio.Direction.INPUT
        dio.pull = digitalio.Pull.UP
        self.db = Debouncer(dio, interval=DebouncerConfig.short_press_min)
        self.pin = pin

    def update(self, new_state=None):
        self.db.update(new_state)
        self.fell = self.db.fell
        self.rose = self.db.rose
        self.current_duration = self.db.current_duration
        self.last_duration = self.db.last_duration
        self.value = self.db.value

    @property
    def down(self):
        return DebouncerValue.is_DOWN(self.value)

    @property
    def up(self):
        return DebouncerValue.is_UP(self.value)

    def __str__(self):
        pin = self.pin.id
        value = DebouncerValue(self.db.value)
        duration = self.db.current_duration

        return f"[{pin}: {value} for {duration}]"


# used in SomeDownState and SomeUpState, below
class WTFError(Exception):
    pass


class DebouncerGroupState:
    def __init__(self, dbs, history=None):
        if history is None:
            history = []
        if not len(dbs):
            raise ValueError("no debouncers!")
        self.dbs = dbs
        self.history = history

    def poll(self):
        for db in self.dbs:
            db.update()

    @classmethod
    def transition_from(cls, other):
        trans_from = type(other).__name__
        trans_to = cls.__name__
        return cls(other.dbs, other.history)


class CollapsibleState(DebouncerGroupState):
    pass

class StartState(CollapsibleState):  # no gesture has begun
    def change(self):
        super().poll()

        dbs_pressed = [db.fell for db in self.dbs]
        # all pressed
        if all(dbs_pressed):
            return [AllDownState.transition_from(self)]
        # some pressed
        if any(dbs_pressed):
            return [SomeDownState.transition_from(self)]

        # still waiting for a gesture to begin
        return [self]


class SomeDownState(DebouncerGroupState):
    def change(self):
        super().poll()

        # all down
        if all(db.down for db in self.dbs):
            return [AllDownState.transition_from(self)]

        # more pressed
        if any(db.fell for db in self.dbs):
            return [self]

        dbs_released = [db.rose for db in self.dbs]
        # (all released: impossible, because not all are even down)
        if all(dbs_released):
            raise WTFError("they can't ALL have risen...")
        # some released: split the DebouncerGroup
        if any(dbs_released):
            # group one:
            # - the ones that are still down
            # - the ones that have been released
            # group two:
            # - the ones that never went down
            some_up_dbs = list(filter(
                lambda p:DebouncerValue.is_DOWN(p.value) or p.rose,
                self.dbs
            ))
            all_up_dbs = list(filter(
                lambda p:DebouncerValue.is_UP(p.value) and not p.rose,
                self.dbs
            ))
            return [
                SomeUpState(some_up_dbs, self.history),
                (AllUpState(all_up_dbs, self.history)
                 if self.history else StartState(all_up_dbs))
            ]

        # we're done waiting for unanimity: split the DebouncerGroup
        pressed_duration = min(db.current_duration for db in self.dbs if db.down)
        if pressed_duration >= DebouncerConfig.multiple_press_max:
            down_dbs = list(filter(
                lambda p:DebouncerValue.is_DOWN(p.value),
                self.dbs
            ))
            up_dbs = list(filter(
                lambda p:DebouncerValue.is_UP(p.value),
                self.dbs
            ))
            return [
                AllDownState(down_dbs, self.history),
                (AllUpState(up_dbs, self.history)
                 if self.history else StartState(up_dbs))
            ]
        
        # we're not done waiting for unanimity
        return [self]


class AllDownState(DebouncerGroupState):  # a press has begun
    def change(self):
        super().poll()

        dbs_released = [db.rose for db in self.dbs]
        # all released
        if all(dbs_released):
            return [AllUpState.transition_from(self)]
        # some released
        if any(dbs_released):
            return [SomeUpState.transition_from(self)]

        # long press (which necessarily ends the gesture)
        pressed_duration = min(db.current_duration for db in self.dbs if db.down)
        if pressed_duration >= DebouncerConfig.xlong_press_min:
            return [EndState.transition_from(self)]

        # not yet a long press, but we're still counting duration.
        # This could yet resolve into a short, long, or xlong press
        return [self]


class SomeUpState(DebouncerGroupState):
    def change(self):
        super().poll()

        # all up
        if all(db.up for db in self.dbs):
            return [AllUpState.transition_from(self)]

        # more released
        if any(db.rose for db in self.dbs):
            return [self]

        dbs_pressed = [db.fell for db in self.dbs]
        # (all pressed: impossible, because not all are even up)
        if all(dbs_pressed):
            raise WTFError("they can't ALL have fallen...")
        # some pressed: split the DebouncerGroup
        if any(dbs_pressed):
            # group one:
            # - the ones that are still up
            # - the ones that have been pressed
            # group two:
            # - the ones that never went up
            some_down_dbs = list(filter(
                lambda p:DebouncerValue.is_UP(p.value) or p.fell,
                self.dbs
            ))
            all_down_dbs = list(filter(
                lambda p:DebouncerValue.is_DOWN(p.value) and not p.fell,
                self.dbs
            ))
            return [
                SomeDownState(some_down_dbs, self.history),
                AllDownState(all_down_dbs, self.history)
            ]

        # we're done waiting for unanimity: split the DebouncerGroup
        released_duration = min(db.current_duration for db in self.dbs if db.up)
        if released_duration >= DebouncerConfig.multiple_press_max:
            up_dbs = list(filter(
                lambda p:DebouncerValue.is_UP(p.value),
                self.dbs
            ))
            down_dbs = list(filter(
                lambda p:DebouncerValue.is_DOWN(p.value),
                self.dbs
            ))
            return [
                AllUpState(up_dbs, self.history),
                AllDownState(down_dbs, self.history),
            ]
        
        # we're not done waiting for unanimity
        return [self]


class AllUpState(DebouncerGroupState):  # a press has ended
    def __init__(self, dbs, history=None):
        if history is None:
            history = []
        press_duration = min(
            (db.last_duration for db in dbs if db.up),
            default=0
        )
        if press_duration:
            history.append(Press.fromSeconds(press_duration))

        super().__init__(dbs, history)

    def change(self):
        super().poll()
        
        dbs_pressed = [db.fell for db in self.dbs]
        # all pressed
        if all(dbs_pressed):
            return [AllDownState.transition_from(self)]
        # some pressed
        if any(dbs_pressed):
            return [SomeDownState.transition_from(self)]

        # done with gesture
        released_duration = min(db.current_duration for db in self.dbs if db.up)
        if released_duration >= DebouncerConfig.repeated_press_max:
            return [EndState.transition_from(self)]

        # still waiting for a potential multi-press gesture
        return [self]


class EndState(CollapsibleState):  # the gesture has ended
    def __init__(self, dbs, history=None):
        if history is None:
            history = []
        # only way we get here with all buttons *down* is XLONG press
        if all(DebouncerValue.is_DOWN(db.value) for db in dbs):
            history.append(Press.XLONG)
        super().__init__(dbs, history)

    def change(self):  # this really never ought to get called
        raise WTFError("why are you asking an EndState to change?!")

    def gesture(self):
        sequence = PressSequence(tuple(self.history))
        return Gesture(frozenset(db.pin.id for db in self.dbs), sequence)


def main():
    keep_on_ticking = True
    def stop_ticking():
        nonlocal keep_on_ticking
        keep_on_ticking = False

    buttons = Buttons(board.D18, board.D5)
    buttons.set_callback([board.D18], ".", lambda: print("-"*70, "boop"))
    buttons.set_callback([board.D5], ".", lambda: print("-"*70, "beep"))

    buttons.set_callback([board.D18, board.D5], "~", stop_ticking)

    while keep_on_ticking:
        time.sleep(1/60)
        buttons.poll()

if __name__ == "__main__":
    import board, time

    main()
