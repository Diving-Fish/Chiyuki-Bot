import time
import random


def hash(qq: int):
    days = int(time.strftime("%d", time.localtime(time.time()))) + 31 * int(
        time.strftime("%m", time.localtime(time.time()))) + 77
    random.seed(days * qq)
    return random.randint(114514, 1919810)
