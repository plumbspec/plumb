"""The program ``adapters/java/sample/App.java`` is, written in Python.

Same call structure and nothing else: one door, a helper only it reaches, and two leaves that
helper calls. What each adapter draws over it has to be the same picture (``dev07-1-3-sr08``).
"""


def handle_request(n):
    return work(n)


def work(n):
    return dense(n) + sparse(n)


def dense(n):
    return {1: 1, 2: 3, 3: 5}.get(n, 0)


def sparse(n):
    return {1: 9, 500: 2, 100000: 7}.get(n, 1)
