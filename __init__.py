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
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "3D Viewport > Sidebar > ModTools",
    "description": "Various Maya inspired functions and hotkeys in Blender, with a modeling kit toolbar",
    "category": "3D View",
}

import importlib

from . import prefs
from . import tools
from . import ui
from . import keymaps

_modules = (
    prefs,
    tools,
    ui,
    keymaps,
)


def _reload():
    importlib.reload(prefs)
    importlib.reload(tools)
    importlib.reload(ui)
    importlib.reload(keymaps)


def register():
    try:
        unregister()
    except Exception:
        pass
    _reload()
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
