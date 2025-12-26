from __future__ import annotations

from rq import Connection, Worker
from rq.worker import SimpleWorker

from worker.db import get_engine
from worker.events import get_redis
from worker.models import Base


def main():
    # Local dev convenience: ensure tables exist even if API hasn't started yet.
    Base.metadata.create_all(get_engine())

    redis_conn = get_redis()
    with Connection(redis_conn):
        # On macOS, forking a work-horse process can segfault when provider SDKs import/use
        # native libs. SimpleWorker runs jobs in-process (no fork), while we still keep
        # provider calls isolated via multiprocessing in worker.jobs.
        w = SimpleWorker(["default"])  # type: ignore[call-arg]
        w.work(with_scheduler=False)


if __name__ == "__main__":
    main()
