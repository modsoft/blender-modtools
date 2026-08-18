"""Origin / bounding-box helpers. Maya pivot ~= Blender object origin."""

import bpy
from mathutils import Matrix, Vector

ORIGIN_TYPES = {
    "MESH",
    "CURVE",
    "SURFACE",
    "FONT",
    "META",
    "LATTICE",
    "GPENCIL",
    "GREASEPENCIL",
}

_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}


def can_edit_origin(obj):
    return (
        obj is not None
        and obj.data is not None
        and obj.type in ORIGIN_TYPES
        and hasattr(obj.data, "transform")
    )


def iter_editable(objects):
    for obj in objects:
        if can_edit_origin(obj):
            yield obj


def ensure_unique_data(obj):
    data = obj.data
    if data is not None and data.users > 1:
        obj.data = data.copy()


def _has_shape_keys(obj):
    return obj.type == "MESH" and obj.data is not None and obj.data.shape_keys is not None


def world_aabb(obj, depsgraph):
    """World-space axis-aligned bounds from the evaluated object (modifiers included)."""
    eval_obj = obj.evaluated_get(depsgraph)
    mat = eval_obj.matrix_world
    bound_box = eval_obj.bound_box
    if not bound_box:
        loc = mat.translation.copy()
        return loc.copy(), loc.copy()
    corners = [mat @ Vector(corner) for corner in bound_box]
    mins = Vector((
        min(c.x for c in corners),
        min(c.y for c in corners),
        min(c.z for c in corners),
    ))
    maxs = Vector((
        max(c.x for c in corners),
        max(c.y for c in corners),
        max(c.z for c in corners),
    ))
    return mins, maxs


def combined_world_aabb(objects, depsgraph):
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in objects:
        obj_min, obj_max = world_aabb(obj, depsgraph)
        mins.x = min(mins.x, obj_min.x)
        mins.y = min(mins.y, obj_min.y)
        mins.z = min(mins.z, obj_min.z)
        maxs.x = max(maxs.x, obj_max.x)
        maxs.y = max(maxs.y, obj_max.y)
        maxs.z = max(maxs.z, obj_max.z)
    return mins, maxs


def aabb_center(mins, maxs):
    return (mins + maxs) * 0.5


def aabb_base(mins, maxs):
    """Bottom-center of a world AABB. Blender is Z-up, so base is min Z."""
    center = aabb_center(mins, maxs)
    return Vector((center.x, center.y, mins.z))


def align_point(mins, maxs, axis, side, center_first, current):
    idx = _AXIS_INDEX[axis]
    center = aabb_center(mins, maxs)
    value = mins[idx] if side == "MIN" else maxs[idx]
    if center_first:
        target = center.copy()
    else:
        target = current.copy()
    target[idx] = value
    return target


def set_origin_world(obj, world_co):
    """Move origin to world_co without moving the mesh or children in world space."""
    world_co = Vector(world_co)
    ensure_unique_data(obj)

    mw = obj.matrix_world.copy()
    local = mw.inverted() @ world_co
    child_world = [(child, child.matrix_world.copy()) for child in obj.children]

    obj.data.transform(Matrix.Translation(-local))
    if hasattr(obj.data, "update"):
        obj.data.update()

    mw.translation = world_co
    obj.matrix_world = mw

    for child, matrix in child_world:
        child.matrix_world = matrix

    obj.update_tag()


def apply_rotation_and_scale(obj):
    """Bake local rotation and scale into geometry. Location / origin stay put."""
    ensure_unique_data(obj)

    mb = obj.matrix_basis
    loc, rot, scale = mb.decompose()
    bake = rot.to_matrix().to_4x4() @ Matrix.Diagonal(scale.to_4d())

    child_world = [(child, child.matrix_world.copy()) for child in obj.children]
    obj.data.transform(bake)
    if hasattr(obj.data, "update"):
        obj.data.update()

    obj.matrix_basis = Matrix.Translation(loc)

    for child, matrix in child_world:
        child.matrix_world = matrix

    obj.update_tag()


def apply_rotation_and_scale_many(context, objects):
    """Bake local rotation and scale. Shape-key meshes go through Blender's apply operator."""
    keyed = []
    for obj in objects:
        if _has_shape_keys(obj):
            keyed.append(obj)
        else:
            apply_rotation_and_scale(obj)
    if keyed:
        _apply_rot_scale_via_ops(context, keyed)


def _apply_rot_scale_via_ops(context, objects):
    view_layer = context.view_layer
    saved_active = view_layer.objects.active
    saved_selected = {obj: obj.select_get() for obj in view_layer.objects}
    try:
        for obj in view_layer.objects:
            obj.select_set(False)
        for obj in objects:
            obj.select_set(True)
        view_layer.objects.active = objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    finally:
        for obj, selected in saved_selected.items():
            try:
                obj.select_set(selected)
            except ReferenceError:
                pass
        view_layer.objects.active = saved_active


def set_origin_world_via_ops(context, pairs):
    """Fallback for meshes with shape keys. pairs: iterable of (obj, world_co)."""
    cursor = context.scene.cursor
    saved_cursor = cursor.location.copy()
    view_layer = context.view_layer
    saved_active = view_layer.objects.active
    saved_selected = {obj: obj.select_get() for obj in view_layer.objects}

    try:
        for obj in view_layer.objects:
            obj.select_set(False)
        for obj, world_co in pairs:
            ensure_unique_data(obj)
            cursor.location = Vector(world_co)
            obj.select_set(True)
            view_layer.objects.active = obj
            bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
            obj.select_set(False)
    finally:
        cursor.location = saved_cursor
        for obj, selected in saved_selected.items():
            try:
                obj.select_set(selected)
            except ReferenceError:
                pass
        view_layer.objects.active = saved_active


def set_origins(context, obj_points):
    """Set each object's origin. Uses ops for shape-key meshes, matrix math otherwise."""
    direct = []
    keyed = []
    for obj, point in obj_points:
        if _has_shape_keys(obj):
            keyed.append((obj, point))
        else:
            direct.append((obj, point))

    for obj, point in direct:
        set_origin_world(obj, point)
    if keyed:
        set_origin_world_via_ops(context, keyed)
