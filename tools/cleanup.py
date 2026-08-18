"""Mesh cleanup: select issues, and fix the ones that have a safe automatic repair."""

from collections import defaultdict
from math import radians

import bmesh
import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import edit_meshes, ensure_object_mode, select_only

_AREA_EPS = 1e-12
_LEN_EPS = 1e-12
_DEGEN_DIST = 1e-4


def _any_enabled(settings):
    return any(
        (
            settings.cleanup_ngons,
            settings.cleanup_nonmanifold,
            settings.cleanup_loose,
            settings.cleanup_zero_area,
            settings.cleanup_lamina,
            settings.cleanup_tris,
            settings.cleanup_quads,
            settings.cleanup_interior,
        )
    )


def _any_fixable(settings):
    return any(
        (
            settings.cleanup_ngons,
            settings.cleanup_quads,
            settings.cleanup_loose,
            settings.cleanup_zero_area,
            settings.cleanup_lamina,
            settings.cleanup_interior,
        )
    )


def _select_only_names(settings):
    names = []
    if settings.cleanup_tris:
        names.append("Tris")
    if settings.cleanup_nonmanifold:
        names.append("Non-manifold")
    return names


def _select_face(face):
    face.select = True


def _mark_issues(obj, settings):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    for vert in bm.verts:
        vert.select = False
    for edge in bm.edges:
        edge.select = False
    for face in bm.faces:
        face.select = False

    count = 0

    if settings.cleanup_ngons:
        for face in bm.faces:
            if len(face.verts) > 4:
                _select_face(face)
                count += 1

    if settings.cleanup_tris:
        for face in bm.faces:
            if len(face.verts) == 3:
                _select_face(face)
                count += 1

    if settings.cleanup_quads:
        for face in bm.faces:
            if len(face.verts) == 4:
                _select_face(face)
                count += 1

    if settings.cleanup_nonmanifold:
        for edge in bm.edges:
            if not edge.is_manifold:
                edge.select = True
                count += 1
        for vert in bm.verts:
            if not vert.is_manifold:
                vert.select = True
                count += 1

    if settings.cleanup_loose:
        for vert in bm.verts:
            if not vert.link_edges:
                vert.select = True
                count += 1
        for edge in bm.edges:
            if not edge.link_faces:
                edge.select = True
                for vert in edge.verts:
                    vert.select = True
                count += 1

    if settings.cleanup_zero_area:
        for face in bm.faces:
            if face.calc_area() < _AREA_EPS:
                _select_face(face)
                count += 1
        for edge in bm.edges:
            if edge.calc_length() < _LEN_EPS:
                edge.select = True
                for vert in edge.verts:
                    vert.select = True
                count += 1

    if settings.cleanup_lamina:
        buckets = defaultdict(list)
        for face in bm.faces:
            key = tuple(sorted(vert.index for vert in face.verts))
            buckets[key].append(face)
        for faces in buckets.values():
            if len(faces) > 1:
                for face in faces:
                    _select_face(face)
                    count += 1

    if settings.cleanup_interior:
        for face in bm.faces:
            if face.edges and all(len(edge.link_faces) > 2 for edge in face.edges):
                _select_face(face)
                count += 1

    bm.select_flush(False)
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return count


def _fix_loose(bm):
    edges = [edge for edge in bm.edges if not edge.link_faces]
    n = len(edges)
    if edges:
        bmesh.ops.delete(bm, geom=edges, context="EDGES")
    verts = [vert for vert in bm.verts if not vert.link_edges]
    n += len(verts)
    if verts:
        bmesh.ops.delete(bm, geom=verts, context="VERTS")
    return n


def _fix_lamina(bm):
    buckets = defaultdict(list)
    for face in bm.faces:
        key = tuple(sorted(vert.index for vert in face.verts))
        buckets[key].append(face)
    to_delete = []
    for faces in buckets.values():
        if len(faces) > 1:
            to_delete.extend(faces[1:])
    n = len(to_delete)
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="FACES")
    return n


def _fix_interior(bm):
    interior = [
        face
        for face in bm.faces
        if face.edges and all(len(edge.link_faces) > 2 for edge in face.edges)
    ]
    n = len(interior)
    if interior:
        bmesh.ops.delete(bm, geom=interior, context="FACES")
    return n


def _fix_ngons(bm):
    """Tessellate n-gons into quads where possible, tris otherwise.

    Cylinder caps: poke (center vert) then join coplanar tris into quads.
    Fallback is beauty triangulate if poke cannot run.
    """
    ngons = [face for face in bm.faces if len(face.verts) > 4]
    if not ngons:
        return 0
    count = len(ngons)
    try:
        result = bmesh.ops.poke(bm, faces=ngons)
        new_faces = result.get("faces", [])
    except Exception:
        result = bmesh.ops.triangulate(
            bm,
            faces=ngons,
            quad_method="BEAUTY",
            ngon_method="BEAUTY",
        )
        new_faces = result.get("faces", [])

    new_faces = [face for face in new_faces if getattr(face, "is_valid", True)]
    if new_faces:
        try:
            bmesh.ops.join_triangles(
                bm,
                faces=new_faces,
                angle_face_threshold=radians(40.0),
                angle_shape_threshold=radians(90.0),
            )
        except TypeError:
            pass
    return count


def _fix_quads(bm):
    quads = [face for face in bm.faces if len(face.verts) == 4]
    if not quads:
        return 0
    count = len(quads)
    bmesh.ops.triangulate(
        bm,
        faces=quads,
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    return count


def _fix_issues(obj, settings):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    n_loose = n_degen = n_lamina = n_interior = n_ngons = n_quads = 0
    try:
        if settings.cleanup_loose:
            n_loose = _fix_loose(bm)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

        if settings.cleanup_zero_area:
            verts_before = len(bm.verts)
            faces_before = len(bm.faces)
            bmesh.ops.dissolve_degenerate(bm, dist=_DEGEN_DIST)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            leftover = [face for face in bm.faces if face.calc_area() < _AREA_EPS]
            if leftover:
                bmesh.ops.delete(bm, geom=leftover, context="FACES")
                bm.faces.ensure_lookup_table()
            n_degen = (verts_before - len(bm.verts)) + (faces_before - len(bm.faces))

        if settings.cleanup_lamina:
            n_lamina = _fix_lamina(bm)
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()

        if settings.cleanup_interior:
            n_interior = _fix_interior(bm)
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()

        if settings.cleanup_ngons:
            n_ngons = _fix_ngons(bm)
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()

        if settings.cleanup_quads:
            n_quads = _fix_quads(bm)
    finally:
        bm.normal_update()
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

    return {
        "loose": n_loose,
        "degenerate": n_degen,
        "lamina": n_lamina,
        "interior": n_interior,
        "ngons": n_ngons,
        "quads": n_quads,
    }


def _prepare_edit(context):
    meshes = edit_meshes(context)
    if not meshes:
        return None
    if context.mode != "EDIT_MESH":
        ensure_object_mode(context)
        select_only(context, meshes)
        bpy.ops.object.mode_set(mode="EDIT")
    context.tool_settings.mesh_select_mode = (True, True, True)
    return meshes


class MODTOOLS_OT_cleanup_select(Operator):
    bl_idname = "modtools.cleanup_select"
    bl_label = "Select Issues"
    bl_description = (
        "Enter Edit Mode and select geometry matching the cleanup checkboxes"
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
        if not _any_enabled(settings):
            self.report({"WARNING"}, "Enable at least one cleanup checkbox")
            return {"CANCELLED"}

        meshes = _prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        total = 0
        for obj in meshes:
            total += _mark_issues(obj, settings)

        if total:
            self.report({"INFO"}, f"Selected issues on {len(meshes)} mesh(es)")
        else:
            self.report({"INFO"}, "No issues found")
        return {"FINISHED"}


class MODTOOLS_OT_cleanup_fix(Operator):
    bl_idname = "modtools.cleanup_fix"
    bl_label = "Fix Issues"
    bl_description = (
        "Fix checked issues: tessellate n-gons, triangulate quads, delete loose, "
        "degenerate, lamina, and interior. Tris and non-manifold are selected only"
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
        if not _any_enabled(settings):
            self.report({"WARNING"}, "Enable at least one cleanup checkbox")
            return {"CANCELLED"}

        meshes = _prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        totals = {
            "loose": 0,
            "degenerate": 0,
            "lamina": 0,
            "interior": 0,
            "ngons": 0,
            "quads": 0,
        }
        if _any_fixable(settings):
            for obj in meshes:
                result = _fix_issues(obj, settings)
                for key, value in result.items():
                    totals[key] += value

        leftover = 0
        for obj in meshes:
            leftover += _mark_issues(obj, settings)

        parts = []
        if totals["ngons"]:
            parts.append(f"n-gons {totals['ngons']}")
        if totals["quads"]:
            parts.append(f"quads {totals['quads']}")
        if totals["loose"]:
            parts.append(f"loose {totals['loose']}")
        if totals["degenerate"]:
            parts.append(f"degenerate {totals['degenerate']}")
        if totals["lamina"]:
            parts.append(f"lamina {totals['lamina']}")
        if totals["interior"]:
            parts.append(f"interior {totals['interior']}")

        skipped = _select_only_names(settings)
        if skipped:
            parts.append("selected " + ", ".join(skipped) + " (no auto-fix)")
        elif leftover and not any(totals.values()):
            parts.append("nothing to auto-fix")

        if parts:
            self.report({"INFO"}, "Fix: " + "; ".join(parts))
        else:
            self.report({"INFO"}, "Nothing to fix")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_cleanup_select,
    MODTOOLS_OT_cleanup_fix,
)

KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
