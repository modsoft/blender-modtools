"""Maya-style group / ungroup using a tagged Empty as the group node."""

import bpy
from bpy.types import Operator
from mathutils import Vector

from . import origin
from . import settings as mesh_settings
from .ops_util import keymap_item, ensure_object_mode, select_only

GROUP_PROP = "modtools_group"


def is_group(obj):
    return obj is not None and obj.type == "EMPTY" and obj.get(GROUP_PROP)


def selection_roots(objects):
    selected = set(objects)
    return [obj for obj in objects if obj.parent not in selected]


def _selection_aabb(context, objects):
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
        return mins, maxs

    locs = [obj.matrix_world.translation for obj in objects]
    mins = Vector((
        min(loc.x for loc in locs),
        min(loc.y for loc in locs),
        min(loc.z for loc in locs),
    ))
    maxs = Vector((
        max(loc.x for loc in locs),
        max(loc.y for loc in locs),
        max(loc.z for loc in locs),
    ))
    return mins, maxs


def _group_location(context, objects, mode):
    mins, maxs = _selection_aabb(context, objects)
    center = origin.aabb_center(mins, maxs)
    if mode == "BOTTOM":
        return origin.aabb_base(mins, maxs)
    if mode == "TOP":
        return Vector((center.x, center.y, maxs.z))
    return center


def _collection_for(obj, context):
    if obj is not None and obj.users_collection:
        return obj.users_collection[0]
    return context.scene.collection


def _parent_keep_world(child, parent):
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world


def _nearest_group(obj):
    """The group Empty this object belongs to, itself included."""
    node = obj
    while node is not None:
        if is_group(node):
            return node
        node = node.parent
    return None


def _groups_from_selection(objects):
    found = []
    seen = set()
    for obj in objects:
        group = _nearest_group(obj)
        if group is not None and group not in seen:
            seen.add(group)
            found.append(group)
    return found


def _surviving_parent(group, doomed):
    """Nearest ancestor that will still exist once `doomed` groups are removed."""
    parent = group.parent
    while parent is not None and parent in doomed:
        parent = parent.parent
    return parent


class MODTOOLS_OT_group(Operator):
    bl_idname = "modtools.group"
    bl_label = "Group"
    bl_description = (
        "Parent selected objects under a new Empty and select it "
        "(Maya Ctrl+G). Locator position uses the Group dropdown"
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

        settings = mesh_settings.get(context)
        locator = settings.group_locator if settings is not None else "BOTTOM"
        parents = {obj.parent for obj in roots}
        common_parent = parents.pop() if len(parents) == 1 else None
        location = _group_location(context, roots, locator)

        empty = bpy.data.objects.new("group", None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.25
        empty.hide_render = True
        empty[GROUP_PROP] = True
        _collection_for(context.view_layer.objects.active, context).objects.link(empty)
        if empty.name not in context.view_layer.objects:
            context.scene.collection.objects.link(empty)

        if common_parent is not None:
            _parent_keep_world(empty, common_parent)
        mw = empty.matrix_world.copy()
        mw.translation = location
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

        doomed = set(groups)
        released = []
        for group in groups:
            parent = _surviving_parent(group, doomed)
            for child in list(group.children):
                if child in doomed:
                    continue
                _parent_keep_world(child, parent)
                released.append(child)

        for group in groups:
            bpy.data.objects.remove(group, do_unlink=True)

        released = [obj for obj in released if obj is not None]
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
        section="Group",
    ),
    keymap_item(
        "modtools.ungroup",
        type="G",
        ctrl=True,
        shift=True,
        keymap="Object Mode",
        space_type="EMPTY",
        head=True,
        section="Group",
    ),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
