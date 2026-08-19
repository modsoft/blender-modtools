"""Maya-named normals ops. Harden/soften = sharp edges, not shade flat."""

import math

import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import (
    ensure_object_mode,
    keymap_item,
    restore_state,
    run_on_meshes_edit,
    save_state,
    select_only,
    selected_meshes,
)


def _meshes_or_report(operator, context):
    meshes = selected_meshes(context)
    if not meshes:
        operator.report({"WARNING"}, "Select a mesh")
        return None
    return meshes


class _NormalsOp(Operator):
    """Base for normals tools. Greys out unless a mesh is selected."""

    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(selected_meshes(context))


class MODTOOLS_OT_soften_edge(_NormalsOp):
    bl_idname = "modtools.soften_edge"
    bl_label = "Soften Edge"
    bl_description = (
        "Clear sharp edges and shade smooth. Object mode: all edges. "
        "Edit mode: selected edges"
    )

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        in_object = context.mode != "EDIT_MESH"
        run_on_meshes_edit(
            context,
            meshes,
            lambda: bpy.ops.mesh.mark_sharp(clear=True),
            select_all=in_object,
        )
        if in_object:
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.mesh.faces_shade_smooth()
        self.report({"INFO"}, "Soften Edge")
        return {"FINISHED"}


class MODTOOLS_OT_harden_edge(_NormalsOp):
    bl_idname = "modtools.harden_edge"
    bl_label = "Harden Edge"
    bl_description = (
        "Mark sharp edges and keep smooth shading. Object mode: all edges. "
        "Edit mode: selected edges"
    )

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        in_object = context.mode != "EDIT_MESH"
        run_on_meshes_edit(
            context,
            meshes,
            lambda: bpy.ops.mesh.mark_sharp(clear=False),
            select_all=in_object,
        )
        if in_object:
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.mesh.faces_shade_smooth()
        self.report({"INFO"}, "Harden Edge")
        return {"FINISHED"}


class MODTOOLS_OT_smooth_by_angle(_NormalsOp):
    bl_idname = "modtools.smooth_by_angle"
    bl_label = "Smooth by Angle"
    bl_description = (
        "Shade smooth and mark sharp edges by the Angle field. "
        "One-shot (no modifier). Existing sharp edges are kept"
    )

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        settings = mesh_settings.get(context)
        degrees = settings.smooth_angle if settings else 30.0

        state = save_state(context)
        ensure_object_mode(context)
        select_only(context, meshes)
        try:
            bpy.ops.object.shade_smooth_by_angle(
                angle=math.radians(degrees), keep_sharp_edges=True
            )
        finally:
            restore_state(context, state)

        self.report({"INFO"}, f"Smooth by Angle ({degrees:.0f}°)")
        return {"FINISHED"}


class MODTOOLS_OT_unlock_normals(_NormalsOp):
    bl_idname = "modtools.unlock_normals"
    bl_label = "Unlock Normals"
    bl_description = "Clear custom split normals so soften/harden can affect shading"

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        run_on_meshes_edit(
            context,
            meshes,
            lambda: bpy.ops.mesh.customdata_custom_splitnormals_clear(),
            select_all=False,
        )
        self.report({"INFO"}, "Unlocked custom normals")
        return {"FINISHED"}


class MODTOOLS_OT_reverse_normals(_NormalsOp):
    bl_idname = "modtools.reverse_normals"
    bl_label = "Reverse"
    bl_description = "Flip face normals. Object mode: all faces. Edit mode: selected"

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        in_object = context.mode != "EDIT_MESH"
        run_on_meshes_edit(
            context,
            meshes,
            lambda: bpy.ops.mesh.flip_normals(),
            select_all=in_object,
        )
        self.report({"INFO"}, "Reversed normals")
        return {"FINISHED"}


class MODTOOLS_OT_recalculate_normals(_NormalsOp):
    bl_idname = "modtools.recalculate_normals"
    bl_label = "Recalculate"
    bl_description = (
        "Make normals consistent, pointing out. Object mode: all faces. "
        "Edit mode: selected"
    )

    def execute(self, context):
        meshes = _meshes_or_report(self, context)
        if not meshes:
            return {"CANCELLED"}
        in_object = context.mode != "EDIT_MESH"
        run_on_meshes_edit(
            context,
            meshes,
            lambda: bpy.ops.mesh.normals_make_consistent(inside=False),
            select_all=in_object,
        )
        self.report({"INFO"}, "Recalculated normals")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_soften_edge,
    MODTOOLS_OT_harden_edge,
    MODTOOLS_OT_smooth_by_angle,
    MODTOOLS_OT_unlock_normals,
    MODTOOLS_OT_reverse_normals,
    MODTOOLS_OT_recalculate_normals,
)

KEYMAP_ITEMS = (
    keymap_item("modtools.soften_edge", section="Normals"),
    keymap_item("modtools.harden_edge", section="Normals"),
    keymap_item("modtools.smooth_by_angle", section="Normals"),
    keymap_item("modtools.unlock_normals", section="Normals"),
    keymap_item("modtools.reverse_normals", section="Normals"),
    keymap_item("modtools.recalculate_normals", section="Normals"),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
