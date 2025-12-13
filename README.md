# EVE Switcher

A fast, keyboard-driven window switcher for EVE Online on Linux. Quickly cycle between your EVE clients using configurable hotkeys, with support for multiple cycling-groups and automatic character discovery.

## Features

- **Global hotkeys** - Switch windows with the press of a button / hotkey, even from inside EVE
- **Multiple cycle groups** - Organize characters by activity (mining, PvP, trading, etc.)
- **Auto-discovery** - New characters can be automatically added to configured "catchall" groups
- **Character select cycling** - Separate hotkeys for character selection screen cycling
- **Persistent configuration** - Character order and groups are saved and can be customized
- **System tray integration** - Quick access to toggle the switcher on/off, to save and reload the config, and to quit with and without saving the config
- **Hot-Reload** - Being able to reload the config / reorder the cycle list while the app is running is a thing that I missed so much in Eve-O-Preview that I started this project.
- **Context-aware** - Remembers your position in each cycle group. Continues to cycle from the currently active client even if you manually switch to another client via the task bar

## Installation

### Requirements

- **X11 display server** - Wayland is not supported
- **System tray** - KDE Plasma, GNOME (with AppIndicator extension), XFCE, etc.

### Flatpak from Source

Build and install locally:

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Platform//48 org.gnome.Sdk//48

git clone --recurse-submodules https://github.com/Motrotz/eveswitcher.git
cd eveswitcher/flatpak
flatpak-builder --user --install --force-clean build-dir io.github.motrotz.eveswitcher.yml
flatpak run io.github.motrotz.eveswitcher
```
### Flatpak from Flathub
Not yet possible 
> **Note:** A Flathub release is planned once more features are added, since a pure tray applet is not permitted on Flathub. 

### From Source

Requirements:
- Python 3.10 or newer
- X11 (Wayland not supported)
- PyGObject and AppIndicator libraries for system tray

#### Standalone Binary (PyInstaller)

Build a single executable:

```bash
sudo apt install python3-gi python3-venv libappindicator3-1
git clone https://github.com/Motrotz/eveswitcher.git
cd eveswitcher
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install pyinstaller
pyinstaller --onefile --add-data "assets:assets" eveswitcher/__main__.py --name eveswitcher
./dist/eveswitcher
```

#### Development Install

Run directly from source:

```bash
sudo apt install python3-gi python3-venv libappindicator3-1
git clone https://github.com/Motrotz/eveswitcher.git
cd eveswitcher
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .
eveswitcher
# or: python -m eveswitcher
```

## Quick Start

1. Launch EVE Switcher - it will run in your system tray
2. Log in to your EVE clients
3. Use the default hotkeys to cycle between windows:
   - **F13** / **F14**: Cycle forward/backward through logged-in clients
   - **Ctrl+F13** / **Ctrl+F14**: Cycle forward/backward through character selection screens
   - **Ctrl+e**: Toggle active/inactive state

The first time you run EVE Switcher, a default configuration file will be created at `~/.config/eveswitcher/config.json`.

## Configuration

### Config File Location

EVE Switcher looks for `config.json` in the following order:

1. **Portable mode**: `config.json` in the same directory as the executable
2. **User config**: `~/.config/eveswitcher/config.json`

If no config file is found, a default one is created at `~/.config/eveswitcher/config.json`.

### Editing the Config

Edit your config file to customize your setup.

### Basic Example

```json
{
  "EveSwitcher": "v1",
  "defaultState": "active",
  "toggleStateKey": "Ctrl+e",
  "CharacterSelection": {
    "cycle_next": "Ctrl+F13",
    "cycle_prev": "Ctrl+F14"
  },
  "default": {
    "autoAdd": true,
    "cycle_next": "F13",
    "cycle_prev": "F14",
    "characters": [],
    "excludeCharacters": []
  }
}
```

### Multiple Groups Example

Create separate cycle groups for different activities:

```json
{
  "EveSwitcher": "v1",
  "defaultState": "active",
  "toggleStateKey": "Ctrl+e",
  "CharacterSelection": {
    "cycle_next": "Ctrl+F13",
    "cycle_prev": "Ctrl+F14"
  },
  "mining": {
    "autoAdd": false,
    "cycle_next": "F13",
    "cycle_prev": "F14",
    "characters": ["Miner One", "Miner Two", "Miner Three"],
    "excludeCharacters": []
  },
  "pvp": {
    "autoAdd": false,
    "cycle_next": "F17",
    "cycle_prev": "F18",
    "characters": ["Main PvP", "Scout Alt"],
    "excludeCharacters": []
  }
}
```

### Configuration Fields

**Global Settings**
- `defaultState`: Initial state on startup - `"active"` (default) or `"inactive"`
- `toggleStateKey`: Hotkey to toggle active/inactive state (default: `Ctrl+e`)

**CharacterSelection**
- `cycle_next` / `cycle_prev`: Hotkeys for cycling through character selection screens
- `includeLauncher`: If `true`, include the EVE Launcher in character selection cycling (default: `false`)

**Groups** (e.g., "mining", "pvp", "default")
- `autoAdd`: If `true`, all characters not in `excludeCharacters` are automatically added
- `cycle_next`: Hotkey to cycle forward (optional, omit or set to `null` to disable)
- `cycle_prev`: Hotkey to cycle backward (optional, omit or set to `null` to disable)
- `characters`: List of character names in the order you want to cycle through them
- `excludeCharacters`: Characters to exclude from this group (only used if `autoAdd` is `true`)

Groups without keybindings can be used as a "catchall" to collect character names via auto-add for easy copy/paste into other groups.
```json
"newAlts": {
  "autoAdd": true,
  "characters": [], // New characters will appear here after saving the config.
  "excludeCharacters": []
}
```

### Supported Keys

Use any valid X11 keysym name, optionally with modifiers:

**Basic keys:**
- Function keys: `F1`, `F2`, ... `F24`
- Letters: `a`, `b`, ... `z`
- Numbers `0-9`
- Special keys: `space`, `Return`, `Tab`, `Escape`, `BackSpace`, etc.

**Modifiers:** `Ctrl`, `Control`, `Shift`, `Alt`, `Super`, `Win`, `Meta`

**Examples:**
- `F13`, `Tab`, `space`
- `Ctrl+Tab`, `Shift+F13`, `Alt+a`
- `Ctrl+Shift+Tab` (multiple modifiers)

**Notes:**
- Key combinations already grabbed by your window manager (or another program grabbing keys globally) cannot be used (e.g., `Alt+Tab`). Function keys `F13`-`F24` are usually safe.
- Combinations of two regular keys (e.g., `q+w`) are not supported.
- Left/right modifier distinction is not supported. `Ctrl` matches both Left Ctrl and Right Ctrl (same for `Shift`, `Alt`, `Super`).
- While some legacy keyboards supported up to F35 (see [historical scan codes](https://aeb.win.tue.nl/linux/kbd/scancodes-5.html)), modern USB HID keyboards only define F1-F24. EVE Switcher supports F1-F24. (Yes, I also learned about those keyboards today, while doing research on keysym...)

## System Tray

The tray icon indicates the current state:
- **Green icon** - Active: hotkeys are being processed
- **Blue icon** - Inactive: hotkeys are ignored

Right-click the tray icon to access:
- **Activate/Deactivate** - Toggle hotkey processing on/off
- **Save Config** - Manually save character additions to disk
- **Reload Config** - Reload configuration from disk and rescan windows
- **Edit Config** - Open the config file in your default text editor
- **Quit (Save)** - Exit and save any auto-added characters
- **Quit (No Save)** - Exit without saving changes

## How It Works

EVE Switcher detects EVE Online windows by their title:
- **Logged-in clients**: Titles starting with "EVE - " (e.g., "EVE - Character Name")
- **Character selection screens**: Titles exactly matching "EVE"
- **EVE Launcher**: The launcher is omitted by default, but it can be included in the character selection cycling by adding `"includeLauncher": true` to the `CharacterSelection` section

When you log in a character:
1. EVE Switcher detects the window title change
2. If a group has `autoAdd: true`, the character is automatically added
3. The character is appended to the group's `characters` list
4. Press the configured hotkey to cycle to that character

## Troubleshooting

### Hotkeys don't work
- Check that your keys aren't already bound to other actions
- Try different function keys (F13-F24 are usually safe)
- Verify your key names are valid X11 keysym names

### Tray icon doesn't appear
- Ensure your desktop environment supports system trays
- For GNOME: Install "AppIndicator and KStatusNotifierItem Support" extension

### Characters aren't auto-discovered
- Verify `autoAdd: true` in your group config
- Ensure the character name isn't in `excludeCharacters`
- Click "Reload Config" in the tray menu after logging in

## Privacy Considerations

EVE Switcher logs information to help with debugging. Before using this application, please understand what data is stored (locally on your machine) and decide if this is OK with you.

### What gets logged

EVE Switcher writes a log file to:
- **Standard install**: `~/.local/share/eveswitcher/eveswitcher.log`
- **Flatpak install**: `~/.var/app/io.github.motrotz.eveswitcher/data/eveswitcher.log`

This log file may contain:
- **Character names** from your EVE window titles (e.g., "EVE - YourCharacter")
- GTK system messages
- Error messages if something goes wrong

The log file grows over time and is not automatically cleared.

### Why this matters

If you have characters whose identity you want to keep private (such as spy alts, ISD volunteers, or accounts you don't want linked to your main), be aware that:
- Anyone with access to your user account can read this log file
- The log persists across sessions, building a history of all characters you've played
- If your system is compromised or shared, this information could be exposed

### What you can do

- Periodically delete the log file if you're concerned about historical data
- Be aware of who has access to your home directory
- If strict privacy is required, consider whether this tool is appropriate for your use case

### Config file permissions

The config file at `~/.config/eveswitcher/config.json` contains your character names and is created with your system's default file permissions. On most Linux systems this means only your user can read it, but if you've changed your umask or use a shared system, verify the permissions are appropriate.

In portable mode (PyInstaller binary with `config.json` in the same directory), the config file is stored alongside the application. If you run EVE Switcher from a USB drive or shared folder, anyone with access to that location can read your config file and see your character names.

## Contributing

Pull requests are welcome! If you'd like to contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

For larger changes, consider opening an issue first to discuss the approach.

## Bug Reports

If you encounter a bug, please open an issue at https://github.com/motrotz/eveswitcher/issues

To help diagnose the problem, please include:
- What you were doing when the bug occurred
- What you expected to happen
- What actually happened
- Your desktop environment (KDE, GNOME, XFCE, etc.)
- How you installed EVE Switcher (Flatpak, PyInstaller, source)
- Relevant log output from `~/.local/share/eveswitcher/eveswitcher.log` (or the Flatpak equivalent)

**Note**: The log file contains your character names. If you're sharing logs publicly, redact any names you want to keep private.

## License

WTFPL