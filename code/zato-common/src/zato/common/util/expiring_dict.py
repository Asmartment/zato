# -*- coding: utf-8 -*-

"""
Copyright (C) 2022, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

"""
### Original license ###

Copyright (c) 2019 David Parker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# stdlib
from collections.abc import MutableMapping
from time import gmtime

# gevent
from gevent import sleep
from gevent.threading import Thread, Lock

# SortedContainers
from sortedcontainers import SortedKeyList

# ################################################################################################################################
# ################################################################################################################################

class ExpiringDict(MutableMapping):
    def __init__(self, ttl=None, interval=0.100, *args, **kwargs):

        self._store = dict(*args, **kwargs)
        self._keys = SortedKeyList(key=lambda x: x[0])
        self._ttl = ttl
        self._lock = Lock()
        self._interval = interval

        Thread(target=self._worker, daemon=True).start()

    def flush(self):
        now = gmtime()
        max_index = 0
        with self._lock:
            for index, (timestamp, key) in enumerate(self._keys):
                if timestamp > now: # Break as soon as we find a key whose expiration time is in the future
                    max_index = index
                    break
                try:
                    del self._store[key]
                except KeyError:
                    pass  # Ignore it if it was deleted early
            del self._keys[0:max_index]

    def _worker(self):
        while True:
            self.flush()
            sleep(self._interval)

    def __setitem__(self, key, value):
        if self._ttl:
            self._set_with_expire(key, value, self._ttl)
        else:
            self._store[key] = value

    def ttl(self, key, value, ttl):
        self._set_with_expire(key, value, ttl)

    def _set_with_expire(self, key, value, ttl):
        self._lock.acquire()
        self._keys.add((gmtime() + ttl, key))
        self._store[key] = value
        self._lock.release()

    def __delitem__(self, key):
        del self._store[key]

    def __getitem__(self, key):
        return self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

# ################################################################################################################################
# ################################################################################################################################
