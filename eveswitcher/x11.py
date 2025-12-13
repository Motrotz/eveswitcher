"""X11 window operations for EVE Switcher."""

from Xlib import X, display, XK, error

# Track failed key grabs to report after sync
_failed_grabs = []


def _handle_grab_error(err, request):
    """Handle X errors, tracking failed key grabs."""
    if isinstance(err, error.BadAccess):
        _failed_grabs.append(request)
        return
    print(f"X protocol error: {err}")


class X11Connection:
    """Wrapper for X11 display and window operations."""

    # Modifier name mappings
    MODIFIER_MAP = {
        "ctrl": X.ControlMask,
        "control": X.ControlMask,
        "shift": X.ShiftMask,
        "alt": X.Mod1Mask,
        "super": X.Mod4Mask,
        "win": X.Mod4Mask,
        "meta": X.Mod4Mask,
    }

    def __init__(self):
        self.disp = display.Display()
        self.disp.set_error_handler(_handle_grab_error)
        self.root = self.disp.screen().root

        # Intern commonly used atoms
        self.NET_CLIENT_LIST = self.disp.intern_atom('_NET_CLIENT_LIST')
        self.NET_WM_NAME = self.disp.intern_atom('_NET_WM_NAME')
        self.NET_ACTIVE_WINDOW = self.disp.intern_atom('_NET_ACTIVE_WINDOW')
        self.WM_NAME = self.disp.intern_atom('WM_NAME')

        # Setup event mask on root window
        self.root.change_attributes(
            event_mask=X.PropertyChangeMask | X.SubstructureNotifyMask
        )

    def key_to_keycode(self, key_name: str) -> tuple[int, int] | None:
        """Convert a key name (e.g. 'F13', 'Ctrl+Tab') to (keycode, modifier_mask).

        Supports modifiers: Ctrl/Control, Shift, Alt, Super/Win/Meta
        Examples: "F13", "Ctrl+Tab", "Shift+F13", "Ctrl+Shift+a"

        Returns None if the key is not recognized.
        """
        modifier_mask = 0
        key_part = key_name

        # Check for modifier+key pattern (supports + or space as separator)
        if "+" in key_name or " " in key_name:
            parts = [p.strip() for p in key_name.replace("+", " ").split()]
            key_part = parts[-1]  # Last part is the actual key
            for mod in parts[:-1]:
                mod_lower = mod.lower()
                if mod_lower in self.MODIFIER_MAP:
                    modifier_mask |= self.MODIFIER_MAP[mod_lower]
                else:
                    print(f"Warning: Unknown modifier '{mod}' in '{key_name}'")
                    return None

        # Try the key as-is first, then try with different capitalizations
        keysym = XK.string_to_keysym(key_part)
        if keysym == 0:
            # Try capitalizing first letter (e.g., "tab" -> "Tab", "f13" -> "F13")
            keysym = XK.string_to_keysym(key_part.capitalize())
        if keysym == 0:
            # Try uppercase (e.g., "f13" -> "F13")
            keysym = XK.string_to_keysym(key_part.upper())
        if keysym == 0:
            print(f"Warning: Unknown key '{key_part}' - ignoring this keybinding")
            return None

        return (self.disp.keysym_to_keycode(keysym), modifier_mask)

    def keycode_to_name(self, key: int | tuple[int, int]) -> str:
        """Convert an X11 keycode (or keycode+modifier tuple) back to a key name."""
        if isinstance(key, tuple):
            keycode, modifier_mask = key
        else:
            keycode, modifier_mask = key, 0

        keysym = self.disp.keycode_to_keysym(keycode, 0)

        # Build base key name
        # Handle function keys (keysym_to_string doesn't handle F13+)
        # USB HID standard defines F1-F24 only
        if XK.XK_F1 <= keysym <= XK.XK_F24:
            base_name = f"F{keysym - XK.XK_F1 + 1}"
        else:
            # Handle special keys that return control characters
            special_keys = {
                XK.XK_Tab: "Tab",
                XK.XK_Return: "Return",
                XK.XK_Escape: "Escape",
                XK.XK_BackSpace: "BackSpace",
                XK.XK_space: "space",
            }
            if keysym in special_keys:
                base_name = special_keys[keysym]
            else:
                name = XK.keysym_to_string(keysym)
                base_name = name if name else f"keycode_{keycode}"

        # Add modifier prefix if present
        if modifier_mask:
            mods = []
            if modifier_mask & X.ControlMask:
                mods.append("Ctrl")
            if modifier_mask & X.ShiftMask:
                mods.append("Shift")
            if modifier_mask & X.Mod1Mask:
                mods.append("Alt")
            if modifier_mask & X.Mod4Mask:
                mods.append("Super")
            return "+".join(mods + [base_name])
        return base_name

    def get_all_windows(self) -> list[tuple[int, str]]:
        """Get all client windows with their titles.

        Returns:
            List of (window_id, title) tuples
        """
        result = []
        try:
            client_list = self.root.get_full_property(
                self.NET_CLIENT_LIST, X.AnyPropertyType
            )
            if client_list:
                for wid in client_list.value:
                    title = self.get_window_title(wid)
                    result.append((wid, title))
        except Exception:
            pass
        return result

    def get_window_title(self, wid: int) -> str:
        """Get the title of a window by its ID."""
        try:
            win = self.disp.create_resource_object('window', wid)
            name = win.get_full_property(self.NET_WM_NAME, 0)
            if name:
                return name.value.decode('utf-8', errors='ignore')
            name = win.get_full_property(self.WM_NAME, 0)
            if name:
                return name.value.decode('latin-1', errors='ignore')
        except Exception:
            pass
        return ""

    def activate_window(self, wid: int) -> str:
        """Activate (focus and raise) a window. Returns the window title."""
        try:
            win = self.disp.create_resource_object('window', wid)
            win.set_input_focus(X.RevertToParent, X.CurrentTime)
            win.configure(stack_mode=X.Above)
            # Also use _NET_ACTIVE_WINDOW for better WM compatibility
            self.root.send_event(
                event=display.event.ClientMessage(
                    window=win,
                    client_type=self.NET_ACTIVE_WINDOW,
                    data=(32, [2, X.CurrentTime, 0, 0, 0])
                ),
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask
            )
            self.disp.flush()
            return self.get_window_title(wid)
        except Exception as e:
            print(f"Activate error: {e}")
            return ""

    def get_active_window(self) -> int | None:
        """Get the currently active window ID."""
        try:
            active = self.root.get_full_property(
                self.NET_ACTIVE_WINDOW, X.AnyPropertyType
            )
            if active and active.value:
                return active.value[0]
        except Exception:
            pass
        return None

    def grab_keys(self, keys: list[tuple[int, int]]) -> None:
        """Grab global hotkeys on the root window.

        Args:
            keys: List of (keycode, modifier_mask) tuples
        """
        global _failed_grabs
        # Lock modifier masks (CapsLock, NumLock) that should be ignored
        num_lock = X.Mod2Mask
        caps_lock = X.LockMask
        lock_combos = [0, caps_lock, num_lock, caps_lock | num_lock]

        for keycode, base_modifiers in keys:
            _failed_grabs = []  # Reset for each key
            key_name = self.keycode_to_name((keycode, base_modifiers))

            # Grab with all combinations of lock modifiers
            for lock_mods in lock_combos:
                modifiers = base_modifiers | lock_mods
                self.root.grab_key(
                    keycode, modifiers, True, X.GrabModeAsync, X.GrabModeAsync
                )

            self.disp.sync()  # Force error processing

            if _failed_grabs:
                print(f"Warning: Could not grab '{key_name}' - already in use by another application")

        self.disp.flush()

    def ungrab_all_keys(self) -> None:
        """Ungrab all keys from the root window."""
        self.root.ungrab_key(X.AnyKey, X.AnyModifier)
        self.disp.flush()

    def watch_window(self, wid: int) -> None:
        """Subscribe to property changes on a window."""
        try:
            win = self.disp.create_resource_object('window', wid)
            win.change_attributes(event_mask=X.PropertyChangeMask)
        except Exception:
            pass

    def watch_all_windows(self) -> None:
        """Subscribe to property changes on all client windows."""
        try:
            client_list = self.root.get_full_property(
                self.NET_CLIENT_LIST, X.AnyPropertyType
            )
            if client_list:
                for wid in client_list.value:
                    self.watch_window(wid)
        except Exception:
            pass

    def next_event(self):
        """Get the next X11 event (blocking)."""
        return self.disp.next_event()
