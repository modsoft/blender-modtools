"""Maya-style group / ungroup using a tagged Empty as the group node."""

import bpy
from bpy.types import Operator
from mathutils import Vector

from . import origin
from .ops_util import keymap_item, ensure_object_mode, select_only

GROUP_PROP = "modtools_group"


def is_group(obj):
    return obj is not None and obj.type == "EMPTY" and obj.get(GROUP_PROP)


def selection_roots(objects):
    selected = set(objects)
    return [obj for obj in objects if obj.parent not in selected]


def _world_center(context, objects):
    depsgraph = context.evaluated_depsgraph_get()
    measurable = [obj for obj in objects if origin.can_edit_origin(obj)]
    if measurable:
        mins, maxs = origin.combined_world_aabb(measurable, depsgraph)
        for obj in objects:
            if obj in measurable:
                continue
            loc = obj.matrix_world.translation
            mins.x = min(mins.x, loc.x)
            mins.y = min(mins.y, loc.y)
            mins.z = min(mins.z, loc.z)
            maxs.x = max(maxs.x, loc.x)
            maxs.y = max(maxs.y, loc.y)
            maxs.z = max(maxs.z, loc.z)
        return origin.aabb_center(mins, maxs)

    acc = Vector((0.0, 0.0, 0.0))
    for obj in objects:
        acc += obj.matrix_world.translation
    return acc / len(objects)


def _collection_for(obj, context):
    if obj is not None and obj.users_collection:
        return obj.users_collection[0]
    return context.scene.collection


def _parent_keep_world(child, parent):
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world


def _groups_from_selection(objects):
    found = []
    seen = set()
    for obj in objects:
        group = obj if is_group(obj) else (obj.parent if is_group(obj.parent) else None)
        if group is not None and group.name not in seen:
            seen.add(group.name)
            found.append(group)
    return found


class MODTOOLS_OT_group(Operator):
    bl_idname = "modtools.group"
    bl_label = "Group"
    bl_description = (
        "Parent selected objects under a new Empty at the selection center "
        "(Maya Ctrl+G). Nested selection keeps the existing hierarchy"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        ensure_object_mode(context)
        selected = list(context.selected_objects)
        roots = selection_roots(selected)
        if not roots:
            self.report({"WARNING"}, "Nothing to group")
            return {"CANCELLED"}

        parents = {obj.parent for obj in roots}
        common_parent = parents.pop() if len(parents) == 1 else None
        center = _world_center(context, roots)

        empty = bpy.data.objects.new("group", None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.25
        empty.hide_render = True
        empty[GROUP_PROP] = True
        _collection_for(context.view_layer.objects.active, context).objects.link(empty)

        if common_parent is not None:
            _parent_keep_world(empty, common_parent)
        mw = empty.matrix_world.copy()
        mw.translation = center
        empty.matrix_world = mw

        for obj in roots:
            _parent_keep_world(obj, empty)

        select_only(context, [empty], active=empty)
        self.report({"INFO"}, f"Grouped {len(roots)} object(s)")
        return {"FINISHED"}


class MODTOOLS_OT_ungroup(Operator):
    bl_idname = "modtools.ungroup"
    bl_label = "Ungroup"
    bl_description = (
        "Unparent children of a ModTools group Empty and delete the Empty. "
        "Select the group or any of its children"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(_groups_from_selection(context.selected_objects))

    def execute(self, context):
        groups = _groups_from_selection(context.selected_objects)
        ensure_object_mode(context)
        released = []
        for group in groups:
            children = list(group.children)
            grandparent = group.parent
            for child in children:
                _parent_keep_world(child, grandparent)
                released.append(child)
            bpy.data.objects.remove(group, do_unlink=True)

        select_only(context, released, active=released[0] if released else None)
        self.report({"INFO"}, f"Ungrouped {len(groups)} group(s)")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_group,
    MODTOOLS_OT_ungroup,
)

KEYMAP_ITEMS = (
    keymap_item(
        "modtools.group",
        type="G",
        ctrl=True,
        keymap="Object Mode",
        space_type="EMPTY",
        head=True,
    ),
    keymap_item(
        "modtools.ungroup",
        type="G",
        ctrl=True,
        shift=True,
        keymap="Object Mode",
        space_type="EMPTY",
        head=True,
    ),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
