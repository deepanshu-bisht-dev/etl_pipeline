"""
A minimal background scheduler using only the standard library's
`threading` module — this avoids pulling in APScheduler or Celery/Redis
just to run a function every N seconds, which keeps the whole project to
a `pip install -r requirements.txt` with two packages.
"""
import threading
import time

import config
import database
from etl.pipeline import run_pipeline

_stop_event = threading.Event()
_thread = None


def _loop():
    interval = config.AUTO_RUN_INTERVAL_SECONDS
    if not interval:
        return
    while not _stop_event.wait(interval):
        database.log(None, "info", f"Scheduler triggering automatic run (every {interval}s)")
        run_pipeline(trigger="scheduled")


def start():
    global _thread
    if config.AUTO_RUN_INTERVAL_SECONDS <= 0:
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def stop():
    _stop_event.set()
