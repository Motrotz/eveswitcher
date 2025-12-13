"""System tray icon for EVE Switcher."""

import os
import sys
import threading
from pathlib import Path

# Fix for Flatpak: pystray saves icons to temp files, but /tmp is sandboxed.
# AppIndicator (on host) can't read them. Use the shared app runtime dir.
if Path("/.flatpak-info").exists():
    flatpak_id = os.environ.get("FLATPAK_ID", "")
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if flatpak_id and xdg_runtime:
        os.environ["TMPDIR"] = f"{xdg_runtime}/app/{flatpak_id}"

import pystray
from PIL import Image


def get_assets_dir() -> Path:
    """Get the path to the assets directory."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - data is extracted to _MEIPASS
        return Path(sys._MEIPASS) / "assets"
    elif Path("/.flatpak-info").exists():
        # Running in Flatpak - assets are in /app/share
        return Path("/app/share")
    else:
        # Running as script/module - assets are in sibling directory
        return Path(__file__).parent.parent / "assets"


class TrayIcon:
    """System tray icon with menu for EVE Switcher."""

    def __init__(self, on_save: callable, on_reload: callable,
                 on_quit_save: callable, on_quit_no_save: callable,
                 on_toggle: callable = None, on_edit: callable = None,
                 initial_state: str = "active"):
        """Initialize the tray icon.

        Args:
            on_save: Callback for "Save Config" menu item
            on_reload: Callback for "Reload Config" menu item
            on_quit_save: Callback for "Quit (Save)" menu item
            on_quit_no_save: Callback for "Quit (No Save)" menu item
            on_toggle: Callback for state toggle, receives new state ("active"/"inactive")
            on_edit: Callback for "Edit Config" menu item
            initial_state: Initial state ("active" or "inactive")
        """
        self._on_save = on_save
        self._on_reload = on_reload
        self._on_quit_save = on_quit_save
        self._on_quit_no_save = on_quit_no_save
        self._on_toggle = on_toggle
        self._on_edit = on_edit

        self._state = initial_state
        self._state_lock = threading.Lock()  # Protect _state from concurrent access
        self._icon = None
        self._thread = None
        self._icon_active = None
        self._icon_inactive = None

    def _load_icon_file(self, filename: str) -> Image.Image:
        """Load a specific icon file.

        Args:
            filename: Name of the icon file (e.g., "icon_active.png")

        Returns:
            PIL Image ready for tray display
        """
        if Path("/.flatpak-info").exists():
            icon_path = Path(f"/app/share/icons/hicolor/64x64/apps/{filename}")
        else:
            icon_path = get_assets_dir() / filename

        if icon_path.exists():
            img = Image.open(icon_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            if img.size != (64, 64):
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img
        else:
            # Fallback: create a simple colored square
            color = (46, 125, 50, 255) if "active" in filename else (21, 101, 192, 255)
            return Image.new('RGBA', (64, 64), color=color)

    def _load_icons(self) -> None:
        """Load both active and inactive icons."""
        self._icon_active = self._load_icon_file("icon_active.png")
        self._icon_inactive = self._load_icon_file("icon_inactive.png")

    def _get_current_icon(self) -> Image.Image:
        """Get the icon for the current state."""
        with self._state_lock:
            state = self._state
        return self._icon_active if state == "active" else self._icon_inactive

    def _get_toggle_text(self) -> str:
        """Get the text for the toggle menu item based on current state."""
        with self._state_lock:
            state = self._state
        return "Deactivate" if state == "active" else "Activate"

    def _create_menu(self) -> pystray.Menu:
        """Create the tray icon menu."""
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: self._get_toggle_text(),
                self._handle_toggle
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Save Config", self._handle_save),
            pystray.MenuItem("Reload Config", self._handle_reload),
            pystray.MenuItem("Edit Config", self._handle_edit),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit (Save)", self._handle_quit_save),
            pystray.MenuItem("Quit (No Save)", self._handle_quit_no_save),
        )

    def _handle_toggle(self, icon, item):
        """Handle state toggle menu click."""
        # Toggle state with lock
        with self._state_lock:
            self._state = "inactive" if self._state == "active" else "active"
            new_state = self._state
        # Update icon
        self._icon.icon = self._get_current_icon()
        # Notify callback (posts to queue, doesn't do heavy work)
        if self._on_toggle:
            self._on_toggle(new_state)

    def _handle_save(self, icon, item):
        """Handle Save Config menu click."""
        self._on_save()

    def _handle_reload(self, icon, item):
        """Handle Reload Config menu click."""
        self._on_reload()

    def _handle_edit(self, icon, item):
        """Handle Edit Config menu click."""
        if self._on_edit:
            self._on_edit()

    def _handle_quit_save(self, icon, item):
        """Handle Quit (Save) menu click."""
        self._on_quit_save()
        # Don't call self.stop() - main loop will handle it after processing quit command

    def _handle_quit_no_save(self, icon, item):
        """Handle Quit (No Save) menu click."""
        self._on_quit_no_save()
        # Don't call self.stop() - main loop will handle it after processing quit command

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        self._load_icons()
        menu = self._create_menu()

        self._icon = pystray.Icon(
            name="eveswitcher",
            icon=self._get_current_icon(),
            title="EVE Switcher",
            menu=menu
        )

        # Check if menu is supported by the backend
        if hasattr(pystray.Icon, 'HAS_MENU') and not pystray.Icon.HAS_MENU:
            print("Warning: Tray menu not supported (XOrg backend).")
            print("  Install 'libappindicator3-dev' and 'PyGObject' for menu support.")

        # Run icon in a separate thread so it doesn't block the main event loop
        # Not a daemon thread - we want to control shutdown explicitly
        self._thread = threading.Thread(target=self._icon.run, daemon=False)
        self._thread.start()

    def stop(self) -> None:
        """Stop the tray icon and wait for thread to finish."""
        if self._icon:
            self._icon.stop()
        if self._thread:
            self._thread.join()

    def set_state(self, state: str) -> None:
        """Set the state and update the icon (called from main thread via hotkey)."""
        with self._state_lock:
            self._state = state
        if self._icon:
            self._icon.icon = self._get_current_icon()
            # Force menu update by recreating it
            self._icon.menu = self._create_menu()
            self._icon.update_menu()
