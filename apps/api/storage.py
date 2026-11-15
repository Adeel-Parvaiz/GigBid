"""Serialize use of each SQLite connection shared by API and background threads."""
from functools import wraps


def serialized(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._db_lock:
            return method(self, *args, **kwargs)
    return guarded
