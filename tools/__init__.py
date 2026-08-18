"""Register tool modules here. Copy hello.py as the starting point for a new tool."""

import importlib

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
from . import hello

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
importlib.reload(hello)

MODULES = (
    hello,
    settings,
    pivot,
    group,
    mesh,
    normals,
    modifiers,
    cleanup,
    topology,
)


def iter_keymap_items():
    for mod in MODULES:
        yield from getattr(mod, "KEYMAP_ITEMS", ())


def register():
    for mod in MODULES:
        mod.register()


def unregister():
    for mod in reversed(MODULES):
        mod.unregister()
