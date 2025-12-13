"""Group management and window assignment for EVE Switcher."""

from eveswitcher.config import Config, Group, CharSelectConfig
from eveswitcher.x11 import X11Connection


class GroupManager:
    """Manages cycle groups and window assignments."""

    def __init__(self, config: Config, x11: X11Connection):
        self.config = config
        self.x11 = x11
        self.char_select = config.char_select

        # Track which characters have been added to config (for persistence)
        self._characters_modified = False

    @property
    def groups(self) -> list[Group]:
        return self.config.groups

    def scan_windows(self) -> None:
        """Scan all windows and assign EVE windows to appropriate groups."""
        windows = self.x11.get_all_windows()

        # Track seen windows to detect closed ones
        seen_logged_in: dict[str, int] = {}  # char_name -> wid
        seen_char_select: list[int] = []

        for wid, title in windows:
            if title == "EVE Launcher":
                # Include launcher in char select if configured
                if self.char_select.include_launcher:
                    seen_char_select.append(wid)
            elif title.startswith("EVE - "):
                char_name = title[6:]  # Strip "EVE - " prefix
                seen_logged_in[char_name] = wid
            elif title == "EVE":
                seen_char_select.append(wid)

        # Update character selection windows
        self._update_char_select(seen_char_select)

        # Update each group
        for group in self.groups:
            self._update_group(group, seen_logged_in)

    def _update_char_select(self, seen_wids: list[int]) -> None:
        """Update character selection screen list."""
        cs = self.char_select
        old_count = len(cs.window_ids)

        # Add new windows
        for wid in seen_wids:
            if wid not in cs.window_ids:
                cs.window_ids.append(wid)
                print(f"+ Char select")

        # Remove closed windows
        cs.window_ids = [w for w in cs.window_ids if w in seen_wids]

        if len(cs.window_ids) < old_count:
            print(f"- Char select closed")

        # Clamp index
        if cs.window_ids:
            cs.current_idx = cs.current_idx % len(cs.window_ids)

    def _update_group(self, group: Group, seen_chars: dict[str, int]) -> None:
        """Update a single group's window list."""
        old_wids = set(group.window_ids)
        new_window_ids = []

        # First, add characters in the order specified in config
        for char_name in group.characters:
            if char_name in seen_chars:
                new_window_ids.append(seen_chars[char_name])

        # For autoAdd groups, add any characters not already in the list
        if group.auto_add:
            for char_name, wid in seen_chars.items():
                if char_name in group.exclude_characters:
                    continue
                if char_name not in group.characters:
                    # New character discovered, add to config
                    group.characters.append(char_name)
                    new_window_ids.append(wid)
                    self._characters_modified = True
                    print(f"+ Auto-added '{char_name}' to group '{group.name}'")

        # Detect changes for logging
        new_wids = set(new_window_ids)
        added = new_wids - old_wids
        removed = old_wids - new_wids

        for wid in added:
            title = self.x11.get_window_title(wid)
            print(f"+ {group.name}: {title}")

        if removed:
            print(f"- {group.name}: {len(removed)} window(s) closed")

        group.window_ids = new_window_ids

        # Clamp index
        if group.window_ids:
            group.current_idx = group.current_idx % len(group.window_ids)

    def cycle_group(self, group: Group, delta: int) -> None:
        """Cycle to the next/previous window in a group."""
        if not group.window_ids:
            print(f"No windows in group '{group.name}'")
            return

        group.current_idx = (group.current_idx + delta) % len(group.window_ids)
        wid = group.window_ids[group.current_idx]
        title = self.x11.activate_window(wid)
        print(f"-> {title}")

    def cycle_char_select(self, delta: int) -> None:
        """Cycle through character selection screens."""
        cs = self.char_select
        if not cs.window_ids:
            print("No char select windows")
            return

        cs.current_idx = (cs.current_idx + delta) % len(cs.window_ids)
        wid = cs.window_ids[cs.current_idx]
        self.x11.activate_window(wid)
        print(f"-> Char select")

    def update_indices_from_active(self) -> None:
        """Update cycling indices based on which EVE window is currently active."""
        active_wid = self.x11.get_active_window()
        if active_wid is None:
            return

        # Check char select
        if active_wid in self.char_select.window_ids:
            self.char_select.current_idx = self.char_select.window_ids.index(active_wid)

        # Check each group
        for group in self.groups:
            if active_wid in group.window_ids:
                group.current_idx = group.window_ids.index(active_wid)

    def get_all_keys(self) -> list[tuple[int, int]]:
        """Get all keys (keycode, modifier_mask) that need to be grabbed."""
        keys = [self.char_select.key_next, self.char_select.key_prev]
        if self.config.toggle_state_key is not None:
            keys.append(self.config.toggle_state_key)
        for group in self.groups:
            if group.key_next is not None:
                keys.append(group.key_next)
            if group.key_prev is not None:
                keys.append(group.key_prev)
        return keys

    def _key_matches(self, key: tuple[int, int] | None, keycode: int, modifiers: int) -> bool:
        """Check if a key binding matches the pressed key."""
        if key is None:
            return False
        key_keycode, key_modifiers = key
        # Ignore lock modifiers (CapsLock, NumLock) when comparing
        from Xlib import X
        ignore_mask = X.LockMask | X.Mod2Mask
        return key_keycode == keycode and key_modifiers == (modifiers & ~ignore_mask)

    def handle_keypress(self, keycode: int, modifiers: int) -> None:
        """Handle a keypress event."""
        # Check char select keys
        if self._key_matches(self.char_select.key_next, keycode, modifiers):
            self.cycle_char_select(1)
            return
        if self._key_matches(self.char_select.key_prev, keycode, modifiers):
            self.cycle_char_select(-1)
            return

        # Check group keys
        for group in self.groups:
            if self._key_matches(group.key_next, keycode, modifiers):
                self.cycle_group(group, 1)
                return
            if self._key_matches(group.key_prev, keycode, modifiers):
                self.cycle_group(group, -1)
                return

    @property
    def characters_modified(self) -> bool:
        """Check if any characters were auto-added (config needs saving)."""
        return self._characters_modified

    def print_status(self) -> None:
        """Print current status of all groups."""
        print(f"Char selects: {len(self.char_select.window_ids)}")
        for group in self.groups:
            print(f"  {group.name}: {len(group.window_ids)} clients")
