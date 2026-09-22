"""Every shape a runtime may or may not give a frame of its own (`dev07-1-3`).

Not a project that does anything: a project that is *written* in the constructs whose frames
differ between runtimes. Comprehensions were inlined in CPython 3.12 and had frames before it;
a lambda has one today. What each of them is named must not depend on that.

`handle` is the door. Everything below it is reached from there, so one traced call covers the set.
"""


def handle(n):
    return Work(n).run()


class Work:
    def __init__(self, n):
        self.n = n

    def run(self):
        squares = [x * x for x in range(self.n)]
        pairs = {x: x + 1 for x in range(2)}
        uniq = {x for x in range(2)}
        streamed = sum(x for x in range(2))
        add = lambda a, b: a + b

        def helper():
            return add(len(squares) + len(pairs) + len(uniq) + streamed, 1)

        return helper()
