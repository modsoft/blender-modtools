"""Apply all modifiers and focus the Properties modifier stack."""

import bpy
from bpy.types import Operator

from .ops_util import ensure_object_mode, select_only, save_state, restore_state


class MODTOOLS_OT_apply_all_modifiers(Operator):
    bl_idname = "modtools.apply_all_modifiers"
    bl_label = "Apply All Modifiers"
    bl_description = "Apply every modifier on selected objects, top to bottom"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.modifiers]
        if not objects:
            self.report({"WARNING"}, "No modifiers on the selection")
            return {"CANCELLED"}

        ensure_object_mode(context)
        state = save_state(context)
        applied = 0
        errors = []

        for obj in objects:
            if obj.data is not None and obj.data.users > 1:
                obj.data = obj.data.copy()
            select_only(context, [obj], active=obj)
            names = [mod.name for mod in obj.modifiers]
            for name in names:
                try:
                    with context.temp_override(
                        object=obj,
                        active_object=obj,
                        selected_objects=[obj],
                        selected_editable_objects=[obj],
                    ):
                        bpy.ops.object.modifier_apply(modifier=name)
                    applied += 1
                except RuntimeError as exc:
                    errors.append(f"{obj.name} ({name}): {exc}")
                    break

        restore_state(context, state)
        if errors:
            self.report({"WARNING"}, f"Applied {applied}. " + " | ".join(errors[:3]))
        else:
            self.report({"INFO"}, f"Applied {applied} modifier(s)")
        return {"FINISHED"}


class MODTOOLS_OT_focus_modifiers(Operator):
    bl_idname = "modtools.focus_modifiers"
    bl_label = "Focus Modifier Stack"
    bl_description = "Switch the Properties editor to the Modifiers tab"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if context.object is None:
            self.report({"WARNING"}, "No active object")
            return {"CANCELLED"}
        for area in context.screen.areas:
            if area.type == "PROPERTIES":
                area.spaces.active.context = "MODIFIER"
                self.report({"INFO"}, "Properties: Modifiers")
                return {"FINISHED"}
        self.report({"WARNING"}, "No Properties editor in this workspace")
        return {"CANCELLED"}


classes = (
    MODTOOLS_OT_apply_all_modifiers,
    MODTOOLS_OT_focus_modifiers,
)

KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
