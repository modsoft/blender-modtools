# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "ModTools",
    "author": "Trey",
    "version": (0, 2, 1),
    "blender": (5, 2, 0),
    "location": "3D Viewport > Sidebar > ModTools",
    "description": "Various Maya inspired functions and hotkeys in Blender, with a modeling kit toolbar",
    "category": "3D View",
}

import importlib
import os
import re

from . import update
from . import prefs
from . import tools
from . import ui
from . import keymaps

# Re-import submodules on enable so toggling the add-on picks up edits.
# Turn this off for a release build.
DEV_RELOAD = True

_modules = (
    update,
    prefs,
    tools,
    ui,
    keymaps,
)


def _reload():
    for mod in _modules:
        importlib.reload(mod)


def _check_manifest_version():
    """bl_info and blender_manifest.toml carry the version separately."""
    path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return

    for key, expected in (
        ("version", ".".join(str(part) for part in bl_info["version"])),
        ("blender_version_min", ".".join(str(part) for part in bl_info["blender"])),
    ):
        match = re.search(rf'^{key}\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match and match.group(1) != expected:
            print(
                f"ModTools: blender_manifest.toml {key} is {match.group(1)}, "
                f"bl_info says {expected}"
            )


def register():
    try:
        unregister()
    except Exception:
        pass
    if DEV_RELOAD:
        _reload()
    _check_manifest_version()
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
