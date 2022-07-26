import math

class DecDotSex:
    NUMBER_BASE = 60
    def __init__(self, number, digits=3):
        if isinstance(number, str):
            self.integer, *self.fraction = self.digitsFromString(number)
            return
        if isinstance(number, int):
            self.integer = number
            self.fraction = []
            return
        if isinstance(number, float):
            self.integer, *self.fraction = self.digitsFromNumber(number)
            return
        raise TypeError(f"can't convert {type(number)} to {type(self)}")

    def __str__(self):
        i = str(self.integer)
        f = ",".join(str(d) for d in self.fraction)
        return f"{i};{f}"

    def __float__(self):
        n = self.integer
        denominator = 1
        for digit in self.fraction:
            denominator *= self.NUMBER_BASE
            n += (digit / denominator)
        return n

    @classmethod
    def digitsFromNumber(cls, f):
        while f != 0:
            f,i = math.modf(f)
            f *= cls.NUMBER_BASE
            yield int(i)

    @classmethod
    def digitsFromString(cls, s):
        s = s.strip()
        i,_,f = s.partition(";")
        yield int(i or 0)
        while f:
            d,_,f = f.partition(",")
            yield int(d or 0)

if __name__ == '__main__':
    import fileinput

    def main():
        for line in fileinput.input():
            try:
                num = float(line)
                print(DecDotSex(num))
            except ValueError:
                pass
            try:
                print(float(DecDotSex(line)))
            except ValueError:
                pass

    main()
