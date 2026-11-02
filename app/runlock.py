"""One monitoring run at a time for the whole server.

All browser sessions share one cached detector and its tracker, so two runs at once would corrupt each other's IDs.
A run holds this lock and refreshes a heartbeat; a lock whose heartbeat is older than STALE seconds is treated as free
(a crashed or closed tab cannot block the app).
"""
import threading
import time

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

STALE = 4.0


@st.cache_resource
def _state():
    return {"owner": None, "source": None, "beat": 0.0, "mutex": threading.Lock()}


def me():
    ctx = get_script_run_ctx()
    return ctx.session_id if ctx else "local"


def holder():
    """The active run as {'owner', 'source'} or None."""
    s = _state()
    if s["owner"] and time.time() - s["beat"] < STALE:
        return {"owner": s["owner"], "source": s["source"], "mine": s["owner"] == me()}
    return None


def acquire(source):
    s = _state()
    with s["mutex"]:
        h = holder()
        if h and not h["mine"]:
            return False
        s.update(owner=me(), source=source, beat=time.time())
        return True


def beat():
    s = _state()
    if s["owner"] == me():
        s["beat"] = time.time()


def release():
    s = _state()
    with s["mutex"]:
        if s["owner"] == me():
            s.update(owner=None, source=None, beat=0.0)
