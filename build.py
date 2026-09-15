#!/usr/bin/env python3
"""Build a portable archive containing only the explicit release files."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text())
destination = root / "dist"
destination.mkdir(exist_ok=True)
archive = destination / f"fullscreen-border-{manifest['version']}.tar.gz"
files = ["manifest.json", "Border.qml", "hypr/fullscreen-border.lua", "configure.py",
         "README.md", "CHANGELOG.md", "LICENSE", "preview.png", "build.py",
         "tests/test_configure.py", "tests/window-selection.test.cjs", "tests/palette.test.lua"]
with tarfile.open(archive, "w:gz") as package:
    for filename in files:
        path = root / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Expected a regular release file: {filename}")
        info = package.gettarinfo(str(path), arcname=f"{manifest['id']}/{filename}")
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        with path.open("rb") as stream:
            package.addfile(info, stream)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(destination / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
print(archive)
