"""Maya Bonus Tools-style pivot operators. Each one is hotkeyable."""

import bpy
from bpy.props import BoolProperty, PointerProperty
from bpy.types import Operator, PropertyGroup

from . import origin


class ModToolsPivotSettings(PropertyGroup):
    center_first: BoolProperty(
        name="Center Pivot First",
        description="Put the origin on the bounding-box center, then snap the chosen axis to min/max",
        default=True,
    )
    individual: BoolProperty(
        name="Individual Bounding Boxes",
        description="Use each object's own bounds. Off: one combined box for the whole selection",
        default=True,
    )


def _ensure_object_mode(context):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _editable_selection(context):
    return list(origin.iter_editable(context.selected_objects))


def _zero_local(context, objects):
    origin.apply_rotation_and_scale_many(context, objects)


def _report_skip(operator, processed, selected_count):
    skipped = selected_count - processed
    if processed == 0:
        operator.report({"WARNING"}, "Select mesh, curve, or similar objects")
        return {"CANCELLED"}
    if skipped:
        operator.report(
            {"INFO"},
            f"Updated {processed} object(s), skipped {skipped}",
        )
    else:
        operator.report({"INFO"}, f"Updated {processed} object(s)")
    return {"FINISHED"}


def _execute_align(operator, context, axis, side):
    _ensure_object_mode(context)
    selected_count = len(context.selected_objects)
    objects = _editable_selection(context)
    if not objects:
        return _report_skip(operator, 0, selected_count)

    settings = context.window_manager.modtools_pivot
    depsgraph = context.evaluated_depsgraph_get()
    pairs = []
    if settings.individual:
        for obj in objects:
            mins, maxs = origin.world_aabb(obj, depsgraph)
            current = obj.matrix_world.translation.copy()
            target = origin.align_point(
                mins, maxs, axis, side, settings.center_first, current
            )
            pairs.append((obj, target))
    else:
        mins, maxs = origin.combined_world_aabb(objects, depsgraph)
        for obj in objects:
            current = obj.matrix_world.translation.copy()
            target = origin.align_point(
                mins, maxs, axis, side, settings.center_first, current
            )
            pairs.append((obj, target))

    origin.set_origins(context, pairs)
    return _report_skip(operator, len(objects), selected_count)


class MODTOOLS_OT_pivot_keep_offset_zero_local(Operator):
    bl_idname = "modtools.pivot_keep_offset_zero_local"
    bl_label = "Keep Pivot Offset and Zero Local Values"
    bl_description = (
        "Keep the origin where it is. Bake rotation and scale so local rot/scale are identity. "
        "Location stays as the origin position"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        selected_count = len(context.selected_objects)
        objects = _editable_selection(context)
        _zero_local(context, objects)
        return _report_skip(self, len(objects), selected_count)


class MODTOOLS_OT_pivot_center_zero_local(Operator):
    bl_idname = "modtools.pivot_center_zero_local"
    bl_label = "Center Pivot and Zero Local Values"
    bl_description = (
        "Move origin to the world bounding-box center, then bake rotation and scale"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        selected_count = len(context.selected_objects)
        objects = _editable_selection(context)
        if not objects:
            return _report_skip(self, 0, selected_count)

        depsgraph = context.evaluated_depsgraph_get()
        pairs = []
        for obj in objects:
            mins, maxs = origin.world_aabb(obj, depsgraph)
            pairs.append((obj, origin.aabb_center(mins, maxs)))
        origin.set_origins(context, pairs)
        _zero_local(context, objects)
        return _report_skip(self, len(objects), selected_count)


class MODTOOLS_OT_pivot_base_zero_local(Operator):
    bl_idname = "modtools.pivot_base_zero_local"
    bl_label = "Move Pivot to Base and Zero Local Values"
    bl_description = (
        "Move origin to the bottom-center of the world bounding box (min Z), "
        "then bake rotation and scale"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        selected_count = len(context.selected_objects)
        objects = _editable_selection(context)
        if not objects:
            return _report_skip(self, 0, selected_count)

        depsgraph = context.evaluated_depsgraph_get()
        pairs = []
        for obj in objects:
            mins, maxs = origin.world_aabb(obj, depsgraph)
            pairs.append((obj, origin.aabb_base(mins, maxs)))
        origin.set_origins(context, pairs)
        _zero_local(context, objects)
        return _report_skip(self, len(objects), selected_count)


class MODTOOLS_OT_pivot_origin_zero_all(Operator):
    bl_idname = "modtools.pivot_origin_zero_all"
    bl_label = "Move Pivot to Origin and Zero All Values"
    bl_description = (
        "Move origin to world (0, 0, 0) and bake rotation and scale. "
        "Mesh stays put; unparented objects get identity transforms"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        selected_count = len(context.selected_objects)
        objects = _editable_selection(context)
        if not objects:
            return _report_skip(self, 0, selected_count)

        origin.set_origins(context, [(obj, (0.0, 0.0, 0.0)) for obj in objects])
        _zero_local(context, objects)
        return _report_skip(self, len(objects), selected_count)


class MODTOOLS_OT_pivot_align_min_x(Operator):
    bl_idname = "modtools.pivot_align_min_x"
    bl_label = "Align Pivot Min X"
    bl_description = "Snap origin to the minimum X of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "X", "MIN")


class MODTOOLS_OT_pivot_align_max_x(Operator):
    bl_idname = "modtools.pivot_align_max_x"
    bl_label = "Align Pivot Max X"
    bl_description = "Snap origin to the maximum X of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "X", "MAX")


class MODTOOLS_OT_pivot_align_min_y(Operator):
    bl_idname = "modtools.pivot_align_min_y"
    bl_label = "Align Pivot Min Y"
    bl_description = "Snap origin to the minimum Y of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "Y", "MIN")


class MODTOOLS_OT_pivot_align_max_y(Operator):
    bl_idname = "modtools.pivot_align_max_y"
    bl_label = "Align Pivot Max Y"
    bl_description = "Snap origin to the maximum Y of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "Y", "MAX")


class MODTOOLS_OT_pivot_align_min_z(Operator):
    bl_idname = "modtools.pivot_align_min_z"
    bl_label = "Align Pivot Min Z"
    bl_description = "Snap origin to the minimum Z of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "Z", "MIN")


class MODTOOLS_OT_pivot_align_max_z(Operator):
    bl_idname = "modtools.pivot_align_max_z"
    bl_label = "Align Pivot Max Z"
    bl_description = "Snap origin to the maximum Z of the bounding box"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _execute_align(self, context, "Z", "MAX")


classes = (
    ModToolsPivotSettings,
    MODTOOLS_OT_pivot_keep_offset_zero_local,
    MODTOOLS_OT_pivot_center_zero_local,
    MODTOOLS_OT_pivot_base_zero_local,
    MODTOOLS_OT_pivot_origin_zero_all,
    MODTOOLS_OT_pivot_align_min_x,
    MODTOOLS_OT_pivot_align_max_x,
    MODTOOLS_OT_pivot_align_min_y,
    MODTOOLS_OT_pivot_align_max_y,
    MODTOOLS_OT_pivot_align_min_z,
    MODTOOLS_OT_pivot_align_max_z,
)

KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.modtools_pivot = PointerProperty(type=ModToolsPivotSettings)


def unregister():
    if hasattr(bpy.types.WindowManager, "modtools_pivot"):
        del bpy.types.WindowManager.modtools_pivot
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
