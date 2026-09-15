#!/usr/bin/env python3
"""Connect the native border rules to Omarchy without replacing user config."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

PLUGIN_ID = "gdiab.fullscreen-border"
BEGIN = "-- BEGIN gdiab.fullscreen-border (managed by configure.py)"
END = "-- END gdiab.fullscreen-border"
BLOCK = f'''{BEGIN}
-- Loaded after personal rules so fullscreen colors remain distinguishable.
do
  local path = os.getenv("HOME") .. "/.config/omarchy/plugins/{PLUGIN_ID}/hypr/fullscreen-border.lua"
  local file = io.open(path, "r")
  if file then file:close(); dofile(path) end
end
{END}
'''


class SetupError(Exception):
    pass


def command(*args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise SetupError(f"{' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def atomic_write(path, text):
    mode = path.stat().st_mode & 0o777
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def revised_config(original, action):
    if BEGIN in original or END in original:
        if original.count(BEGIN) != 1 or original.count(END) != 1 or BLOCK not in original:
            raise SetupError("The managed block was edited or is incomplete; leave it intact or remove it manually.")
        return original if action == "install" else original.replace(BLOCK, "", 1)
    if action == "remove":
        return original
    if re.search(r'require\s*\(?\s*[\'\"]hypr\.fullscreen-border[\'\"]', original):
        raise SetupError("A standalone fullscreen-border.lua is already loaded. Remove its require line before migrating; keep a backup.")
    return original + ("" if original.endswith("\n") else "\n") + BLOCK


def configure(action, home, source, run=command):
    plugin = home / ".config/omarchy/plugins" / PLUGIN_ID
    config = home / ".config/hypr/hyprland.lua"
    if source.resolve() != plugin.resolve():
        raise SetupError(f"First install or extract this package at {plugin}; then run its configure.py.")
    if not config.is_file() or config.is_symlink():
        raise SetupError(f"Expected a regular Omarchy Lua config at {config}.")
    original = config.read_text()
    updated = revised_config(original, action)
    run("omarchy", "plugin", "validate", str(plugin))
    errors = run("hyprctl", "configerrors")
    if errors:
        raise SetupError("Fix the existing Hyprland configuration errors first:\n" + errors)
    entries = json.loads(run("omarchy-shell", "shell", "listPlugins"))
    was_enabled = any(x.get("id") == PLUGIN_ID and x.get("enabled") for x in entries)
    backup = None
    if updated != original:
        backup_dir = home / ".local/state/omarchy/fullscreen-border-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=backup_dir)) / "hyprland.lua"
        shutil.copy2(config, backup)
        # Refuse to overwrite a concurrent edit after the preflight checks.
        if config.read_text() != original:
            raise SetupError("Hyprland config changed during setup; retry using the new version.")
        atomic_write(config, updated)
    try:
        run("hyprctl", "reload")
        errors = run("hyprctl", "configerrors")
        if errors:
            raise SetupError("Hyprland rejected the configuration:\n" + errors)
        if action == "install":
            run("omarchy-shell", "shell", "rescanPlugins")
            # Discovery is asynchronous. Wait only for this plugin to appear.
            for attempt in range(30):
                entries = json.loads(run("omarchy-shell", "shell", "listPlugins"))
                if any(x.get("id") == PLUGIN_ID for x in entries):
                    break
                time.sleep(.1)
            else:
                raise SetupError("The shell did not discover the plugin.")
            run("omarchy", "plugin", "enable", PLUGIN_ID)
        elif was_enabled:
            run("omarchy", "plugin", "disable", PLUGIN_ID)
    except Exception as error:
        details = []
        if updated != original:
            if config.read_text() == updated:
                atomic_write(config, original)
                try:
                    run("hyprctl", "reload")
                    errors = run("hyprctl", "configerrors")
                    if errors:
                        details.append("Restored config reports: " + errors)
                except Exception as rollback_error:
                    details.append("Reload after rollback failed: " + str(rollback_error))
            else:
                details.append("Config changed concurrently; preserved it. Original backup: " + str(backup))
        try:
            run("omarchy", "plugin", "enable" if was_enabled else "disable", PLUGIN_ID)
        except Exception as rollback_error:
            details.append("Could not restore prior plugin enablement: " + str(rollback_error))
        raise SetupError(str(error) + ("\n" + "\n".join(details) if details else "")) from error
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "remove"], help="Install both border modes or undo the integration without deleting files")
    args = parser.parse_args()
    try:
        backup = configure(args.action, Path.home(), Path(__file__).resolve().parent)
    except (SetupError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Fullscreen Border: {error}\n")
    print("Fullscreen Border installed." if args.action == "install" else "Fullscreen Border disabled and native rules detached; package files retained.")
    if backup:
        print(f"Config backup: {backup}")
    if args.action == "install":
        print(f"Check runtime: omarchy-shell {PLUGIN_ID} state")


if __name__ == "__main__":
    main()
