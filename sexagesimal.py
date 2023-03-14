import math

class DecDotSex():
    NUMBER_BASE = 60
    def __init__(self, number, digits=3):
        if isinstance(number, str):
            self.integer, *self.fraction = self.exactly(
                list(self.digitsFromString(number)),
                count=digits+1
            )
            return
        if isinstance(number, int):
            self.integer = number
            self.fraction = []
            return
        if isinstance(number, float):
            self.integer, *self.fraction = self.exactly(
                list(self.digitsFromNumber(number)),
                count=digits+1
            )
            return
        raise TypeError(f"can't convert {type(number)} to {type(self)}")

    def __repr__(self):
        constructor = self.__class__.__name__
        value = str(self)
        return f"{constructor}('{value}')"

    def __str__(self):
        i = str(self.integer)
        f = ",".join(str(d) for d in self.fraction)
        return f"{i};{f}"

#    def __format__(self, format_spec):
#        print(format_spec)
#        return self.__str__()
#
    def __float__(self):
        n = self.integer * 1.0
        denominator = 1
        for digit in self.fraction:
            denominator *= self.NUMBER_BASE
            n += (digit / denominator)
        return n

    def __int__(self):
        return self.integer

    @classmethod
    def digitsFromNumber(cls, f):
        while f != 0:
            f,i = math.modf(f)
            f = abs(f * cls.NUMBER_BASE)
            yield int(i)

    @classmethod
    def digitsFromString(cls, s):
        s = s.strip()
        i,_,f = s.partition(";")
        yield int(i or 0)
        while f:
            d,_,f = f.partition(",")
            yield int(d or 0)

    @classmethod
    def exactly(cls, iter_or_list, count=4):
        iterable = iter(iter_or_list)
        # it would be nice if this could round rather than just truncate
        for i in range(count):
            try:
                yield next(iterable)
            except StopIteration:
                yield 0


if __name__ == '__main__':
    import fileinput

    def main():
        for line in fileinput.input():
            try:
                num = float(line)
                print(f'{DecDotSex(num):>12}')
            except ValueError:
                pass
            try:
                print(float(DecDotSex(line)))
            except ValueError:
                pass

    main()
