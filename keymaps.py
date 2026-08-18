"""Register add-on keymaps so they show up under Preferences > Keymap > Add-on.

Each tool module can export KEYMAP_ITEMS, a list of dicts:

    {
        "idname": "modtools.hello",
        "type": "F5",            # or "NONE" to leave unbound
        "value": "PRESS",
        "ctrl": False,
        "shift": False,
        "alt": False,
        "keymap": "3D View",
        "space_type": "VIEW_3D",
    }
"""

import bpy

from . import tools

_addon_keymaps = []


def register():
    unregister()

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return

    for spec in tools.iter_keymap_items():
        km = kc.keymaps.new(
            name=spec.get("keymap", "3D View"),
            space_type=spec.get("space_type", "VIEW_3D"),
        )
        kmi = km.keymap_items.new(
            spec["idname"],
            spec.get("type", "NONE"),
            spec.get("value", "PRESS"),
            ctrl=spec.get("ctrl", False),
            shift=spec.get("shift", False),
            alt=spec.get("alt", False),
            head=spec.get("head", False),
        )
        _addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _addon_keymaps.clear()


def _user_item(km_addon, kmi_addon):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    if kc is None:
        return km_addon, kmi_addon

    km = kc.keymaps.get(km_addon.name)
    if km is None:
        return km_addon, kmi_addon

    for kmi in km.keymap_items:
        if kmi.idname == kmi_addon.idname:
            return km, kmi
    return km_addon, kmi_addon


def draw_preferences(layout, context):
    if not _addon_keymaps:
        layout.label(text="Reload ModTools to register shortcuts.")
        return

    try:
        from rna_keymap_ui import draw_kmi
    except ImportError:
        layout.label(text="Right-click a Pivot Tools button → Assign Shortcut.")
        return

    wm = context.window_manager
    kc = wm.keyconfigs.user or wm.keyconfigs.addon
    if kc is None:
        return

    col = layout.column()
    for km_addon, kmi_addon in _addon_keymaps:
        km, kmi = _user_item(km_addon, kmi_addon)
        col.context_pointer_set("keymap", km)
        draw_kmi([], kc, km, kmi, col, 0)
