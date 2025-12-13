"""EVE Switcher - X11 hotkey-based window switcher for EVE Online."""

import os
import sys
from pathlib import Path

__version__ = "1.0.0"

# Set up logging directory and redirect stderr BEFORE any GTK imports
# This suppresses GTK warnings from the console - relevant for the PyInstaller build
def _setup_stderr_redirect():
    if Path("/.flatpak-info").exists():
        log_dir = Path.home() / ".var" / "app" / "io.github.motrotz.eveswitcher" / "data"
    else:
        log_dir = Path.home() / ".local" / "share" / "eveswitcher"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "eveswitcher.log"

    # Store original stderr and log path for later access
    _setup_stderr_redirect.original_stderr = sys.stderr
    _setup_stderr_redirect.log_file = log_file

    # Open log file and redirect stderr
    log_handle = open(log_file, 'a')
    os.dup2(log_handle.fileno(), sys.stderr.fileno())

_setup_stderr_redirect()
