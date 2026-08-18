import importlib

from . import panel

importlib.reload(panel)

_modules = (panel,)


def register():
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
