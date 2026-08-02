"""
Run blocking work off the Tk main thread and marshal results back safely.
"""
import threading
import tkinter as tk
from tkinter import messagebox


def is_busy(widget) -> bool:
    return bool(getattr(widget, "_async_busy", False))


def run_async(widget, work_fn, on_success, on_error=None):
    """
    Run work_fn() in a daemon thread.
    on_success(result) and on_error(exc) are called on the main thread.
    """
    if is_busy(widget):
        return False

    widget._async_busy = True

    def _finish(result=None, error=None):
        widget._async_busy = False
        if error is not None:
            if on_error:
                on_error(error)
            else:
                messagebox.showerror("Error", str(error))
        else:
            on_success(result)

    def _worker():
        try:
            result = work_fn()
            widget.after(0, lambda r=result: _finish(r, None))
        except Exception as exc:
            widget.after(0, lambda e=exc: _finish(None, e))

    threading.Thread(target=_worker, daemon=True).start()
    return True
