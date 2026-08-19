"""Register tool modules here.

A new tool is a module with `classes`, an optional `KEYMAP_ITEMS`, and
`register` / `unregister`. Import it, reload it, and add it to MODULES.
"""

import importlib
import traceback

from . import origin
from . import ops_util
from . import settings
from . import pivot
from . import group
from . import mesh
from . import normals
from . import modifiers
from . import cleanup
from . import topology
from . import selections

importlib.reload(origin)
importlib.reload(ops_util)
importlib.reload(settings)
importlib.reload(pivot)
importlib.reload(group)
importlib.reload(mesh)
importlib.reload(normals)
importlib.reload(modifiers)
importlib.reload(cleanup)
importlib.reload(topology)
importlib.reload(selections)

MODULES = (
    settings,
    pivot,
    group,
    mesh,
    normals,
    modifiers,
    cleanup,
    topology,
    selections,
)


def iter_keymap_items():
    for mod in MODULES:
        yield from getattr(mod, "KEYMAP_ITEMS", ())


def register():
    for mod in MODULES:
        mod.register()


def unregister():
    for mod in reversed(MODULES):
        try:
            mod.unregister()
        except Exception:
            # One module failing must not strand the rest as registered.
            traceback.print_exc()
