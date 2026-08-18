"""Planar-edge select (un-triangulate) and quadrangulate."""

from math import radians

import bmesh
import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import edit_meshes, ensure_object_mode, select_only

_FACE_JOIN = 40.0
_SHAPE_JOIN = 40.0


def _prepare_edit(context):
    meshes = edit_meshes(context)
    if not meshes:
        return None
    if context.mode != "EDIT_MESH":
        ensure_object_mode(context)
        select_only(context, meshes)
        bpy.ops.object.mode_set(mode="EDIT")
    return meshes


def _select_planar_edges(obj, angle_deg):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    for vert in bm.verts:
        vert.select = False
    for edge in bm.edges:
        edge.select = False
    for face in bm.faces:
        face.select = False

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
            edge.verts[0].select = True
            edge.verts[1].select = True
            count += 1

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return count


def _faces_for_join(bm):
    selected = [face for face in bm.faces if face.select]
    if selected:
        return selected

    from_edges = []
    seen = set()
    for edge in bm.edges:
        if not edge.select:
            continue
        for face in edge.link_faces:
            if face.index not in seen:
                seen.add(face.index)
                from_edges.append(face)
    if from_edges:
        return from_edges

    from_verts = []
    seen.clear()
    for vert in bm.verts:
        if not vert.select:
            continue
        for face in vert.link_faces:
            if face.index not in seen:
                seen.add(face.index)
                from_verts.append(face)
    if from_verts:
        return from_verts

    return list(bm.faces)


def _quadrangulate(obj, from_object):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    tris_before = sum(1 for face in bm.faces if len(face.verts) == 3)
    try:
        faces = list(bm.faces) if from_object else _faces_for_join(bm)
        tris = [face for face in faces if len(face.verts) == 3]
        if not tris:
            return 0
        bmesh.ops.join_triangles(
            bm,
            faces=tris,
            angle_face_threshold=radians(_FACE_JOIN),
            angle_shape_threshold=radians(_SHAPE_JOIN),
        )
    except TypeError:
        pass
    finally:
        bm.normal_update()
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

    tris_after = sum(1 for face in obj.data.polygons if len(face.vertices) == 3)
    return max(0, (tris_before - tris_after) // 2)


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

        meshes = _prepare_edit(context)
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
        from_object = context.mode != "EDIT_MESH"
        meshes = _prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        pairs = 0
        for obj in meshes:
            pairs += _quadrangulate(obj, from_object)

        if pairs:
            self.report({"INFO"}, f"Joined {pairs} triangle pair(s) into quads")
        else:
            self.report({"INFO"}, "No triangle pairs to join")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_select_planar_edges,
    MODTOOLS_OT_quadrangulate,
)

KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
