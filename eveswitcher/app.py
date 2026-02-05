"""EVE Online window switcher for X11 with configurable hotkeys and multiple cycle groups."""

import queue
import signal
import subprocess
import sys
import time
from enum import Enum, auto
from pathlib import Path

from Xlib import X

from eveswitcher.config import load_config, save_config, find_config_path
from eveswitcher.groups import GroupManager
from eveswitcher.x11 import X11Connection
from eveswitcher.tray import TrayIcon


class TrayCommand(Enum):
    """Commands that can be sent from tray thread to main thread."""
    SAVE = auto()
    RELOAD = auto()
    EDIT = auto()
    QUIT_SAVE = auto()
    QUIT_NO_SAVE = auto()
    TOGGLE = auto()


class EVESwitcher:
    """Main application class for EVE window switching."""

    def __init__(self):
        self.x11 = X11Connection()
        self._command_queue = queue.Queue()  # Thread-safe command queue
        self._running = True
        self._save_on_exit = True
        self._active = True  # Whether hotkeys are active
        self._exit_from_signal = False  # Track if exit was triggered by signal (Ctrl+C)

        # Load config
        self._load_config()
        self._active = (self.config.default_state == "active")

        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Grab hotkeys
        self._setup_key_grabs()

        # Watch existing windows and do initial scan
        self.x11.watch_all_windows()
        self.manager.scan_windows()

        # Start system tray icon
        self._setup_tray()

        self._print_startup()

    def _load_config(self) -> None:
        """Load or reload configuration."""
        config_path, is_new = find_config_path()
        print(f"Using config: {config_path}")
        self.config = load_config(str(config_path), self.x11.key_to_keycode)
        self.manager = GroupManager(self.config, self.x11)

    def _setup_key_grabs(self) -> None:
        """Setup keyboard grabs for all configured hotkeys."""
        keys = self.manager.get_all_keys()
        self.x11.grab_keys(keys)

    def _setup_tray(self) -> None:
        """Setup system tray icon."""
        self.tray = TrayIcon(
            on_save=self._tray_save,
            on_reload=self._tray_reload,
            on_quit_save=self._tray_quit_save,
            on_quit_no_save=self._tray_quit_no_save,
            on_toggle=self._tray_toggle,
            on_edit=self._tray_edit,
            initial_state=self.config.default_state,
        )
        self.tray.start()

    # Tray callbacks - these run in the tray thread, so they only post to queue
    def _tray_toggle(self, new_state: str) -> None:
        """Handle tray menu: Toggle active/inactive."""
        self._command_queue.put((TrayCommand.TOGGLE, new_state))

    def _tray_save(self) -> None:
        """Handle tray menu: Save Config."""
        self._command_queue.put(TrayCommand.SAVE)

    def _tray_reload(self) -> None:
        """Handle tray menu: Reload Config."""
        self._command_queue.put(TrayCommand.RELOAD)

    def _tray_edit(self) -> None:
        """Handle tray menu: Edit Config."""
        self._command_queue.put(TrayCommand.EDIT)

    def _tray_quit_save(self) -> None:
        """Handle tray menu: Quit (Save)."""
        self._command_queue.put(TrayCommand.QUIT_SAVE)

    def _tray_quit_no_save(self) -> None:
        """Handle tray menu: Quit (No Save)."""
        self._command_queue.put(TrayCommand.QUIT_NO_SAVE)

    def _process_tray_commands(self) -> None:
        """Process any pending commands from tray thread (runs in main thread)."""
        while True:
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                break

            if cmd == TrayCommand.SAVE:
                self._save_config_now()
            elif cmd == TrayCommand.RELOAD:
                self._do_reload()
            elif cmd == TrayCommand.EDIT:
                self._open_config_editor()
            elif cmd == TrayCommand.QUIT_SAVE:
                print("Quitting (save)...")
                self._save_on_exit = True
                self._running = False
            elif cmd == TrayCommand.QUIT_NO_SAVE:
                print("Quitting (no save)...")
                self._save_on_exit = False
                self._running = False
            elif isinstance(cmd, tuple) and cmd[0] == TrayCommand.TOGGLE:
                new_state = cmd[1]
                self._active = (new_state == "active")
                state_str = "active" if self._active else "inactive"
                print(f"EVE Switcher is now {state_str}")

    def _do_reload(self) -> None:
        """Perform config reload (runs in main thread)."""
        print("Reloading config...")
        self.x11.ungrab_all_keys()
        self._load_config()
        self._setup_key_grabs()
        self.x11.watch_all_windows()
        self.manager.scan_windows()
        print("Config reloaded.")
        self.manager.print_status()

    def _open_config_editor(self) -> None:
        """Open the config file in the default text editor."""
        import os
        from pathlib import Path
        config_path = self.config.config_path

        def run_cmd(cmd):
            """Run command, using flatpak-spawn if in Flatpak."""
            if Path("/.flatpak-info").exists():
                return subprocess.run(
                    ["flatpak-spawn", "--host"] + cmd,
                    capture_output=True, text=True
                )
            else:
                return subprocess.run(cmd, capture_output=True, text=True)

        def spawn_cmd(cmd):
            """Spawn command in background, using flatpak-spawn if in Flatpak."""
            if Path("/.flatpak-info").exists():
                subprocess.Popen(
                    ["flatpak-spawn", "--host"] + cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            # Check VISUAL/EDITOR environment variable first
            editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

            if editor:
                print(f"Opening config with '{editor}' (from $VISUAL/$EDITOR): {config_path}")
                spawn_cmd([editor, config_path])
                return

            # Get default text editor from xdg-mime
            result = run_cmd(["xdg-mime", "query", "default", "text/plain"])
            if result.returncode == 0 and result.stdout.strip():
                desktop_file = result.stdout.strip()
                print(f"Opening config with '{desktop_file}' (default for text/plain): {config_path}")
                spawn_cmd(["gtk-launch", desktop_file, config_path])
                return

            # Fallback to xdg-open
            print(f"Opening config with xdg-open (fallback): {config_path}")
            spawn_cmd(["xdg-open", config_path])

        except Exception as e:
            print(f"Failed to open editor: {e}")

    def _check_toggle_key(self, keycode: int, modifiers: int) -> bool:
        """Check if the pressed key matches the toggle state key."""
        toggle_key = self.config.toggle_state_key
        if toggle_key is None:
            return False
        from Xlib import X
        ignore_mask = X.LockMask | X.Mod2Mask
        return toggle_key[0] == keycode and toggle_key[1] == (modifiers & ~ignore_mask)

    def _toggle_state(self) -> None:
        """Toggle the active/inactive state via hotkey."""
        self._active = not self._active
        state_str = "active" if self._active else "inactive"
        print(f"EVE Switcher is now {state_str}")
        # Update tray icon
        if self.tray:
            self.tray.set_state(state_str)

    def _print_startup(self) -> None:
        """Print startup message with keybindings."""
        print("EVE Switcher started")
        if self.config.toggle_state_key:
            print(f"  Toggle: {self.x11.keycode_to_name(self.config.toggle_state_key)}")
        print(f"  Char select: {self.x11.keycode_to_name(self.config.char_select.key_next)}/"
              f"{self.x11.keycode_to_name(self.config.char_select.key_prev)}")
        for group in self.config.groups:
            auto = " (auto-add)" if group.auto_add else ""
            key_next = self.x11.keycode_to_name(group.key_next) if group.key_next else "none"
            key_prev = self.x11.keycode_to_name(group.key_prev) if group.key_prev else "none"
            print(f"  {group.name}{auto}: {key_next}/{key_prev}")
        self.manager.print_status()

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        # Prevent re-entrant calls
        if not self._running:
            return
        self._running = False
        self._save_on_exit = True
        self._exit_from_signal = True

    def _save_config_now(self) -> None:
        """Save config immediately."""
        if self.manager.characters_modified:
            print("Saving config...")
            save_config(self.config, self.x11.keycode_to_name)
            print("Config saved.")
        else:
            print("No config changes to save.")

    def run(self) -> None:
        """Main event loop."""
        while self._running:
            # Process any pending tray commands (thread-safe)
            self._process_tray_commands()

            # Use pending_event check to allow periodic exit checks
            if self.x11.disp.pending_events():
                event = self.x11.next_event()

                if event.type == X.PropertyNotify:
                    if event.atom == self.x11.NET_CLIENT_LIST:
                        self.x11.watch_all_windows()
                        self.manager.scan_windows()
                    elif event.atom in (self.x11.NET_WM_NAME, self.x11.WM_NAME):
                        self.manager.scan_windows()
                    elif event.atom == self.x11.NET_ACTIVE_WINDOW:
                        self.manager.update_indices_from_active()

                elif event.type == X.KeyPress:
                    # Check for toggle key (works regardless of active state)
                    if self._check_toggle_key(event.detail, event.state):
                        self._toggle_state()
                    elif self._active:
                        self.manager.handle_keypress(event.detail, event.state)
            else:
                # Small sleep to avoid busy-waiting when no events
                time.sleep(0.05)

        # Cleanup
        # In Flatpak, there's a race condition where the launcher exits before child
        # output is visible (https://github.com/flatpak/flatpak/issues/529).
        # When exiting via signal (Ctrl+C) in Flatpak, suppress output to avoid
        # messages appearing after the shell prompt.
        suppress_output = self._exit_from_signal and Path("/.flatpak-info").exists()

        if suppress_output:
            # Just do the save silently and exit
            if self._save_on_exit and self.manager.characters_modified:
                save_config(self.config, self.x11.keycode_to_name)
        else:
            print()  # Newline after ^C
            if self._save_on_exit:
                self._save_config_now()
            print("Exiting.")
            sys.stdout.flush()

        self.tray.stop()


def main():
    # Print version on startup
    from eveswitcher import __version__
    print(f"EVE Switcher v{__version__}")

    # Log file path was set up in __init__.py (before GTK imports)
    from eveswitcher import _setup_stderr_redirect
    log_file = _setup_stderr_redirect.log_file
    print(f"Logging to: {log_file}")

    try:
        EVESwitcher().run()
    except KeyboardInterrupt:
        # Signal handler already printed message, just exit cleanly
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
