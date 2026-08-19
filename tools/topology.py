"""Planar-edge select (un-triangulate) and quadrangulate."""

from math import radians

import bmesh
import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import edit_meshes, keymap_item, leave_edit, prepare_edit

_FACE_JOIN = radians(40.0)
_SHAPE_JOIN = radians(40.0)


def _select_planar_edges(obj, angle_deg):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.normal_update()

    for face in bm.faces:
        face.select = False
    for edge in bm.edges:
        edge.select = False
    for vert in bm.verts:
        vert.select = False

    thresh = radians(angle_deg)
    count = 0
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            continue
        face_a, face_b = edge.link_faces
        if face_a.normal.length < 1e-8 or face_b.normal.length < 1e-8:
            continue
        if face_a.normal.angle(face_b.normal) <= thresh:
            edge.select = True
            count += 1

    bm.select_mode = {"EDGE"}
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return count


def _faces_for_join(bm):
    """Faces the user is pointing at, whatever component mode they are in."""
    faces = [face for face in bm.faces if face.select]
    if faces:
        return faces

    for source in (bm.edges, bm.verts):
        seen = set()
        for element in source:
            if not element.select:
                continue
            for face in element.link_faces:
                if face not in seen:
                    seen.add(face)
                    faces.append(face)
        if faces:
            return faces

    return list(bm.faces)


def _quadrangulate(obj, whole_mesh):
    bm = bmesh.from_edit_mesh(obj.data)
    faces = list(bm.faces) if whole_mesh else _faces_for_join(bm)
    tris = [face for face in faces if len(face.verts) == 3]
    if not tris:
        return 0

    tris_before = len(tris)
    try:
        bmesh.ops.join_triangles(
            bm,
            faces=tris,
            angle_face_threshold=_FACE_JOIN,
            angle_shape_threshold=_SHAPE_JOIN,
        )
        # A joined pair leaves one freed face and one that is now a quad.
        tris_after = sum(
            1 for face in tris if face.is_valid and len(face.verts) == 3
        )
    finally:
        bm.normal_update()
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

    return (tris_before - tris_after) // 2


class MODTOOLS_OT_select_planar_edges(Operator):
    bl_idname = "modtools.select_planar_edges"
    bl_label = "Select Planar Edges"
    bl_description = (
        "Select edges between nearly coplanar faces (triangulation internals). "
        "Dissolve (Ctrl+X) to un-triangulate"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(edit_meshes(context))

    def execute(self, context):
        settings = mesh_settings.get(context)
        if settings is None:
            self.report({"WARNING"}, "Reload ModTools to finish enabling")
            return {"CANCELLED"}

        # Stays in Edit Mode on purpose: the result is an edge selection.
        meshes, _entered = prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        context.tool_settings.mesh_select_mode = (False, True, False)
        total = 0
        for obj in meshes:
            total += _select_planar_edges(obj, settings.planar_angle)

        if total:
            self.report(
                {"INFO"},
                f"Selected {total} planar edge(s). Dissolve (Ctrl+X) to un-triangulate",
            )
        else:
            self.report({"INFO"}, "No planar edges found")
        return {"FINISHED"}


class MODTOOLS_OT_quadrangulate(Operator):
    bl_idname = "modtools.quadrangulate"
    bl_label = "Quadrangulate"
    bl_description = (
        "Merge triangles into quads where they form a clean quad "
        "(Maya Mesh > Quadrangulate). Object Mode: whole mesh. "
        "Edit Mode: selection, or all if nothing is selected"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(edit_meshes(context))

    def execute(self, context):
        whole_mesh = context.mode != "EDIT_MESH"
        meshes, entered = prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        pairs = 0
        for obj in meshes:
            pairs += _quadrangulate(obj, whole_mesh)
        leave_edit(context, entered)

        if pairs:
            self.report({"INFO"}, f"Joined {pairs} triangle pair(s) into quads")
        else:
            self.report({"INFO"}, "No triangle pairs to join")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_select_planar_edges,
    MODTOOLS_OT_quadrangulate,
)

KEYMAP_ITEMS = (
    keymap_item("modtools.select_planar_edges", section="Topology"),
    keymap_item("modtools.quadrangulate", section="Topology"),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
