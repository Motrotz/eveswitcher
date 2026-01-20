"""Configuration loading and saving for EVE Switcher."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG = {
    "EveSwitcher": "v1",
    "defaultState": "active",
    "toggleStateKey": "Ctrl+e",
    "CharacterSelection": {
        "includeLauncher": False,
        "cycle_next": "Ctrl+F13",
        "cycle_prev": "Ctrl+F14"
    },
    "default": {
        "autoAdd": True,
        "cycle_next": "F13",
        "cycle_prev": "F14",
        "minimizeOnSwitch": False,
        "characters": [],
        "excludeCharacters": []
    }
}


def get_app_dir() -> Path:
    """Get the directory where the application is located."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running as script/module - assets are in sibling directory
        return Path(__file__).parent.parent


def get_user_config_dir() -> Path:
    """Get the user config directory (~/.config/eveswitcher)."""
    return Path.home() / ".config" / "eveswitcher"


def find_config_path() -> tuple[Path, bool]:
    """Find the config file path in priority order.

    Returns:
        Tuple of (config_path, is_new) where is_new indicates if default was created
    """
    # Priority 1: Config in same folder as application
    app_config = get_app_dir() / "config.json"
    if app_config.exists():
        return app_config, False

    # Priority 2: User config directory
    user_config = get_user_config_dir() / "config.json"
    if user_config.exists():
        return user_config, False

    # Priority 3: Create default config in user directory
    user_config.parent.mkdir(parents=True, exist_ok=True)
    with open(user_config, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
        f.write('\n')
    print(f"Created default config at {user_config}")
    return user_config, True


@dataclass
class Group:
    """A cycle group with its own keybindings and character list."""
    name: str
    auto_add: bool
    key_next: tuple[int, int] | None  # (keycode, modifier_mask) or None if disabled
    key_prev: tuple[int, int] | None  # (keycode, modifier_mask) or None if disabled
    characters: list[str] = field(default_factory=list)
    exclude_characters: list[str] = field(default_factory=list)
    minimize_on_switch: bool = False
    window_ids: list[int] = field(default_factory=list)
    current_idx: int = 0


@dataclass
class CharSelectConfig:
    """Configuration for character selection screen cycling."""
    key_next: tuple[int, int]  # (keycode, modifier_mask)
    key_prev: tuple[int, int]  # (keycode, modifier_mask)
    include_launcher: bool = False  # Whether to include EVE Launcher in char select cycling
    window_ids: list[int] = field(default_factory=list)
    current_idx: int = 0


@dataclass
class Config:
    """Full configuration with all groups."""
    groups: list[Group]
    char_select: CharSelectConfig
    config_path: str
    default_state: str = "active"  # "active" or "inactive"
    toggle_state_key: tuple[int, int] | None = None  # (keycode, modifier_mask)


def load_config(config_path: str, key_to_keycode) -> Config:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config.json
        key_to_keycode: Function to convert key name (e.g. "F13") to X11 keycode

    Returns:
        Config object with parsed groups and char select config
    """
    with open(config_path, 'r') as f:
        data = json.load(f)

    groups = []
    char_select = None
    default_state = data.get("defaultState", "active")
    if default_state not in ("active", "inactive"):
        print(f"Warning: Invalid defaultState '{default_state}', defaulting to 'active'")
        default_state = "active"

    # Parse toggle state key
    toggle_state_key = None
    toggle_key_name = data.get("toggleStateKey")
    if toggle_key_name:
        toggle_state_key = key_to_keycode(toggle_key_name)

    for key, value in data.items():
        if key in ("EveSwitcher", "defaultState", "toggleStateKey"):
            # Version marker and global settings, skip
            continue
        elif key == "CharacterSelection":
            char_select = CharSelectConfig(
                key_next=key_to_keycode(value["cycle_next"]),
                key_prev=key_to_keycode(value["cycle_prev"]),
                include_launcher=value.get("includeLauncher", False),
            )
        else:
            # It's a group - keybindings are optional
            key_next_name = value.get("cycle_next")
            key_prev_name = value.get("cycle_prev")
            # Treat "none", "null" (any case) as disabled
            if isinstance(key_next_name, str) and key_next_name.lower() in ("none", "null"):
                key_next_name = None
            if isinstance(key_prev_name, str) and key_prev_name.lower() in ("none", "null"):
                key_prev_name = None
            group = Group(
                name=key,
                auto_add=value.get("autoAdd", False),
                key_next=key_to_keycode(key_next_name) if key_next_name else None,
                key_prev=key_to_keycode(key_prev_name) if key_prev_name else None,
                characters=value.get("characters", []),
                exclude_characters=value.get("excludeCharacters", []),
                minimize_on_switch=value.get("minimizeOnSwitch", False),
            )
            groups.append(group)

    if char_select is None:
        raise ValueError("Missing CharacterSelection in config")

    return Config(groups=groups, char_select=char_select, config_path=config_path,
                  default_state=default_state, toggle_state_key=toggle_state_key)


def save_config(config: Config, key_to_name) -> None:
    """Save configuration back to JSON file.

    Args:
        config: Config object to save
        key_to_name: Function to convert X11 keycode back to key name
    """
    # Read original to preserve order and version marker
    with open(config.config_path, 'r') as f:
        data = json.load(f)

    # Update character lists for each group
    for group in config.groups:
        if group.name in data:
            data[group.name]["characters"] = group.characters

    with open(config.config_path, 'w') as f:
        json.dump(data, f, indent=4)
        f.write('\n')
