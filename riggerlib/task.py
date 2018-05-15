from __future__ import print_function

import random
import string
import time
import hashlib


def generate_random_string(size=8):
    size = int(size)

    def random_string_generator(size):
        choice_chars = string.ascii_letters + string.digits
        for x in range(size):
            yield random.choice(choice_chars)
    return ''.join(random_string_generator(size))


class Task():
    QUEUED = 0
    RUNNING = 1
    FINISHED = 2

    def __init__(self, json_dict):
        self.output = {}
        self._tid = hashlib.sha1("{}{}{}".format(
            str(time.time()), json_dict['hook_name'],
            generate_random_string().encode('ascii')).encode('ascii')
        )
        self.json_dict = json_dict
        self.status = self.QUEUED

    @property
    def tid(self):
        return self._tid
