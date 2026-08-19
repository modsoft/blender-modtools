"""Selection / mode helpers shared by operators."""

import bpy


def keymap_item(idname, **kwargs):
    spec = {
        "idname": idname,
        "type": "NONE",
        "value": "PRESS",
        "ctrl": False,
        "shift": False,
        "alt": False,
        "keymap": "3D View",
        "space_type": "VIEW_3D",
        "head": False,
        "section": "Tools",
    }
    spec.update(kwargs)
    return spec


def selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def edit_meshes(context):
    if context.mode == "EDIT_MESH":
        return [obj for obj in context.objects_in_mode if obj.type == "MESH"]
    return selected_meshes(context)


def ensure_object_mode(context):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def prepare_edit(context):
    """Enter Edit Mode on the meshes an operator should act on.

    Returns (meshes, entered) where `entered` is True when this call switched
    modes, so the caller can decide whether to switch back with leave_edit().
    """
    meshes = edit_meshes(context)
    if not meshes:
        return [], False
    if context.mode == "EDIT_MESH":
        return meshes, False
    ensure_object_mode(context)
    select_only(context, meshes)
    bpy.ops.object.mode_set(mode="EDIT")
    return meshes, True


def leave_edit(context, entered):
    if entered and context.mode == "EDIT_MESH":
        bpy.ops.object.mode_set(mode="OBJECT")


def deselect_all_objects(context):
    for obj in context.view_layer.objects:
        try:
            obj.select_set(False)
        except ReferenceError:
            continue


def select_only(context, objects, active=None):
    valid = [obj for obj in objects if obj is not None]
    keep = set(valid)
    for obj in list(context.view_layer.objects):
        if obj is None:
            continue
        try:
            obj.select_set(obj in keep)
        except ReferenceError:
            continue
    if active is None and valid:
        active = valid[0]
    if active is not None:
        try:
            context.view_layer.objects.active = active
        except (ReferenceError, TypeError):
            pass


def save_state(context):
    return {
        "mode": context.mode,
        "active": context.view_layer.objects.active,
        "selected": {obj: obj.select_get() for obj in context.view_layer.objects},
    }


def restore_state(context, state):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj, selected in state["selected"].items():
        try:
            obj.select_set(selected)
        except ReferenceError:
            pass
    active = state["active"]
    if active is not None:
        try:
            context.view_layer.objects.active = active
        except ReferenceError:
            pass
    if state["mode"] == "EDIT_MESH":
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except RuntimeError:
            pass


def run_on_meshes_edit(context, meshes, fn, *, select_all=False):
    """Run fn() in Edit Mode. Object mode: edit all meshes with everything selected.

    Edit mode: run in place so the current component selection is used.
    """
    if not meshes:
        return False

    in_edit = context.mode == "EDIT_MESH"
    if in_edit:
        fn()
        return True

    ensure_object_mode(context)
    select_only(context, meshes)
    bpy.ops.object.mode_set(mode="EDIT")
    if select_all:
        bpy.ops.mesh.select_all(action="SELECT")
    fn()
    bpy.ops.object.mode_set(mode="OBJECT")
    select_only(context, meshes)
    return True
