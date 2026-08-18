"""Maya Combine / Separate / Extract."""

import bpy
from bpy.types import Operator

from .ops_util import (
    selected_meshes,
    ensure_object_mode,
    select_only,
)


class MODTOOLS_OT_combine(Operator):
    bl_idname = "modtools.combine"
    bl_label = "Combine"
    bl_description = "Join selected meshes into the active object (Maya Combine)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(selected_meshes(context)) >= 2

    def execute(self, context):
        meshes = selected_meshes(context)
        active = context.view_layer.objects.active
        if active not in meshes:
            active = meshes[0]

        was_edit = context.mode == "EDIT_MESH"
        ensure_object_mode(context)
        select_only(context, meshes, active=active)
        bpy.ops.object.join()
        if was_edit:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError:
                pass

        self.report({"INFO"}, f"Combined {len(meshes)} meshes")
        return {"FINISHED"}


class MODTOOLS_OT_separate(Operator):
    bl_idname = "modtools.separate"
    bl_label = "Separate"
    bl_description = "Split meshes into objects by loose parts (Maya Separate)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(selected_meshes(context))

    def execute(self, context):
        meshes = selected_meshes(context)
        was_edit = context.mode == "EDIT_MESH"
        parts = []

        if was_edit:
            bpy.ops.mesh.separate(type="LOOSE")
            ensure_object_mode(context)
            parts = [obj for obj in context.selected_objects if obj.type == "MESH"]
        else:
            ensure_object_mode(context)
            for obj in list(meshes):
                select_only(context, [obj], active=obj)
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.separate(type="LOOSE")
                bpy.ops.object.mode_set(mode="OBJECT")
                parts.extend(
                    obj for obj in context.selected_objects if obj.type == "MESH"
                )

        unique = []
        seen = set()
        for obj in parts:
            if obj.name not in seen:
                seen.add(obj.name)
                unique.append(obj)
        if unique:
            select_only(context, unique, active=unique[0])

        self.report({"INFO"}, f"Separate: {len(unique)} object(s)")
        return {"FINISHED"}


class MODTOOLS_OT_extract(Operator):
    bl_idname = "modtools.extract"
    bl_label = "Extract"
    bl_description = (
        "Detach selected faces into a new object (Maya Extract). Edit Mode only"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.object is not None

    def execute(self, context):
        bpy.ops.mesh.separate(type="SELECTED")
        self.report({"INFO"}, "Extracted selection")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_combine,
    MODTOOLS_OT_separate,
    MODTOOLS_OT_extract,
)

KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
