"""Maya Combine / Separate / Extract."""

import bpy
from bpy.types import Operator

from .ops_util import (
    deselect_all_objects,
    selected_meshes,
    ensure_object_mode,
    keymap_item,
    select_only,
)


def _has_selected_faces(context):
    """Cheap enough for poll(): total_face_sel is a counter Blender keeps live."""
    return any(
        obj.type == "MESH" and obj.data.total_face_sel
        for obj in context.objects_in_mode
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
        parts = []
        if context.mode == "EDIT_MESH":
            bpy.ops.mesh.separate(type="LOOSE")
            ensure_object_mode(context)
            parts = [obj for obj in context.selected_objects if obj.type == "MESH"]
        else:
            meshes = selected_meshes(context)
            ensure_object_mode(context)
            deselect_all_objects(context)
            for obj in meshes:
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.separate(type="LOOSE")
                bpy.ops.object.mode_set(mode="OBJECT")
                for part in list(context.selected_objects):
                    if part.type == "MESH":
                        parts.append(part)
                    part.select_set(False)

        unique = list(dict.fromkeys(parts))
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
        return context.mode == "EDIT_MESH" and _has_selected_faces(context)

    def execute(self, context):
        if not _has_selected_faces(context):
            self.report({"WARNING"}, "Select faces to extract")
            return {"CANCELLED"}
        bpy.ops.mesh.separate(type="SELECTED")
        self.report({"INFO"}, "Extracted selection")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_combine,
    MODTOOLS_OT_separate,
    MODTOOLS_OT_extract,
)

KEYMAP_ITEMS = (
    keymap_item(
        "modtools.combine",
        keymap="Object Mode",
        space_type="EMPTY",
        section="Mesh",
    ),
    keymap_item(
        "modtools.separate",
        keymap="Object Mode",
        space_type="EMPTY",
        section="Mesh",
    ),
    keymap_item(
        "modtools.extract",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh",
    ),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
