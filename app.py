"""
Launch the Qt Quick vault.

The CustomTkinter window is ``tk_app.py``. ``python app.py`` opens Qt.
"""
import os
import sys

# Sibling modules when launched from source with a non-repo cwd.
# Frozen builds use sys._MEIPASS (modules live in the PYZ archive).
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _ROOT = sys._MEIPASS
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main():
    from qt_ui.main import main as run_qt
    run_qt()


if __name__ == "__main__":
    main()
