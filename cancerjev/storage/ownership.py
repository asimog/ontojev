from __future__ import annotations

import portalocker


class OwnershipError(RuntimeError):
    pass


class ResearchOwnership:
    def __init__(self, lock_path):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = portalocker.Lock(
            lock_path,
            mode="a+",
            timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        )

    def __enter__(self):
        try:
            self._handle = self._lock.acquire()
        except portalocker.exceptions.LockException as exc:
            raise OwnershipError("Another CancerJEV research process owns this data directory.") from exc
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._lock.release()
