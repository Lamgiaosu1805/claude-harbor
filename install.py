#!/usr/bin/env python3
"""Build and install Claude Harbor. Profile/login data is installed at first launch."""
import shutil
from pathlib import Path
from build import build
app=build();destination=Path.home()/'Applications'/app.name
if destination.exists():
    backup=destination.with_name('Claude Harbor.previous.app')
    if backup.exists():shutil.rmtree(backup)
    destination.rename(backup)
shutil.copytree(app,destination)
print(destination)
