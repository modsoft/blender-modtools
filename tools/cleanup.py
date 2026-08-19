"""Mesh cleanup: select issues, and fix the ones that have a safe automatic repair."""

from collections import defaultdict
from math import radians

import bmesh
import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import edit_meshes, keymap_item, leave_edit, prepare_edit

_AREA_EPS = 1e-12
_LEN_EPS = 1e-12
_DEGEN_DIST = 1e-4
_NGON_JOIN_FACE = radians(40.0)
_NGON_JOIN_SHAPE = radians(90.0)

# Mesh name -> (scope selection, the selection we wrote, element counts).
# Select Issues both reads and writes the component selection, so without this
# a second press would narrow the scope onto the issues the first press found.
_scope_memo = {}


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


def _wants_faces(settings):
    return any(
        (
            settings.cleanup_ngons,
            settings.cleanup_tris,
            settings.cleanup_quads,
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


class _Scope:
    """The elements cleanup is allowed to touch.

    An unrestricted scope is the whole mesh. A restricted one is built from the
    user's component selection and grows as fixes create new geometry.
    """

    def __init__(self, bm, verts=None, edges=None, faces=None):
        self.bm = bm
        self.restricted = verts is not None
        self.verts = verts if verts is not None else set()
        self.edges = edges if edges is not None else set()
        self.faces = faces if faces is not None else set()

    def iter_faces(self):
        if not self.restricted:
            return list(self.bm.faces)
        return [face for face in self.faces if face.is_valid]

    def iter_edges(self):
        if not self.restricted:
            return list(self.bm.edges)
        return [edge for edge in self.edges if edge.is_valid]

    def iter_verts(self):
        if not self.restricted:
            return list(self.bm.verts)
        return [vert for vert in self.verts if vert.is_valid]

    def add_faces(self, faces):
        if not self.restricted:
            return
        for face in faces:
            if not face.is_valid:
                continue
            self.faces.add(face)
            self.edges.update(face.edges)
            self.verts.update(face.verts)

    def has_faces(self):
        return not self.restricted or any(face.is_valid for face in self.faces)


def _ensure_tables(bm):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.index_update()
    bm.faces.index_update()


def _selection_indices(bm):
    return (
        frozenset(vert.index for vert in bm.verts if vert.select),
        frozenset(edge.index for edge in bm.edges if edge.select),
        frozenset(face.index for face in bm.faces if face.select),
    )


def _element_counts(bm):
    return (len(bm.verts), len(bm.edges), len(bm.faces))


def _expand_scope(bm, verts, edges, faces):
    """Complete a raw component selection into a consistent vert/edge/face set."""
    if faces:
        for face in faces:
            edges.update(face.edges)
            verts.update(face.verts)
        return verts, edges, faces

    if edges:
        for edge in edges:
            verts.update(edge.verts)
        faces = {
            face
            for face in bm.faces
            if face.edges and all(edge in edges for edge in face.edges)
        }
        return verts, edges, faces

    edges = {
        edge for edge in bm.edges if edge.verts[0] in verts and edge.verts[1] in verts
    }
    faces = {face for face in bm.faces if all(vert in verts for vert in face.verts)}
    return verts, edges, faces


def _scope_from_indices(bm, indices):
    verts = {bm.verts[i] for i in indices[0] if i < len(bm.verts)}
    edges = {bm.edges[i] for i in indices[1] if i < len(bm.edges)}
    faces = {bm.faces[i] for i in indices[2] if i < len(bm.faces)}
    return _Scope(bm, *_expand_scope(bm, verts, edges, faces))


def _resolve_scope(obj, bm, restrict):
    """Scope for this run, plus the raw selection it came from."""
    if not restrict:
        return _Scope(bm), None

    current = _selection_indices(bm)
    if not any(current):
        _scope_memo.pop(obj.data.name, None)
        return _Scope(bm), None

    source = current
    remembered = _scope_memo.get(obj.data.name)
    if remembered is not None:
        previous_source, previous_marked, counts = remembered
        if counts == _element_counts(bm) and previous_marked == current:
            source = previous_source

    return _scope_from_indices(bm, source), source


def _remember_scope(obj, bm, source):
    if source is None:
        _scope_memo.pop(obj.data.name, None)
        return
    _scope_memo[obj.data.name] = (
        source,
        _selection_indices(bm),
        _element_counts(bm),
    )


def _clear_selection(bm):
    for face in bm.faces:
        face.select = False
    for edge in bm.edges:
        edge.select = False
    for vert in bm.verts:
        vert.select = False


def _mark_issues(obj, bm, scope, settings, source):
    """Select everything matching the checkboxes. Returns (count, element kinds)."""
    _clear_selection(bm)

    count = 0
    kinds = set()
    faces = scope.iter_faces()
    edges = scope.iter_edges()
    verts = scope.iter_verts()

    def mark_face(face):
        nonlocal count
        face.select = True
        kinds.add("FACE")
        count += 1

    def mark_edge(edge):
        nonlocal count
        edge.select = True
        kinds.add("EDGE")
        count += 1

    def mark_vert(vert):
        nonlocal count
        vert.select = True
        kinds.add("VERT")
        count += 1

    if settings.cleanup_ngons:
        for face in faces:
            if len(face.verts) > 4:
                mark_face(face)

    if settings.cleanup_tris:
        for face in faces:
            if len(face.verts) == 3:
                mark_face(face)

    if settings.cleanup_quads:
        for face in faces:
            if len(face.verts) == 4:
                mark_face(face)

    if settings.cleanup_nonmanifold:
        for edge in edges:
            if not edge.is_manifold:
                mark_edge(edge)
        for vert in verts:
            if not vert.is_manifold:
                mark_vert(vert)

    if settings.cleanup_loose:
        for vert in verts:
            if not vert.link_edges:
                mark_vert(vert)
        for edge in edges:
            if not edge.link_faces:
                mark_edge(edge)

    if settings.cleanup_zero_area:
        for face in faces:
            if face.calc_area() < _AREA_EPS:
                mark_face(face)
        for edge in edges:
            if edge.calc_length() < _LEN_EPS:
                mark_edge(edge)

    if settings.cleanup_lamina:
        for group in _lamina_groups(faces).values():
            if len(group) > 1:
                for face in group:
                    mark_face(face)

    if settings.cleanup_interior:
        for face in _interior_faces(faces):
            mark_face(face)

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    _remember_scope(obj, bm, source)
    return count, kinds


def _lamina_groups(faces):
    buckets = defaultdict(list)
    for face in faces:
        key = tuple(sorted(vert.index for vert in face.verts))
        buckets[key].append(face)
    return buckets


def _interior_faces(faces):
    return [
        face
        for face in faces
        if face.edges and all(len(edge.link_faces) > 2 for edge in face.edges)
    ]


def _fix_loose(bm, scope):
    edges = [edge for edge in scope.iter_edges() if not edge.link_faces]
    n = len(edges)
    if edges:
        bmesh.ops.delete(bm, geom=edges, context="EDGES")
    verts = [vert for vert in scope.iter_verts() if not vert.link_edges]
    n += len(verts)
    if verts:
        bmesh.ops.delete(bm, geom=verts, context="VERTS")
    return n


def _fix_lamina(bm, scope):
    to_delete = []
    for group in _lamina_groups(scope.iter_faces()).values():
        if len(group) > 1:
            to_delete.extend(group[1:])
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="FACES")
    return len(to_delete)


def _fix_interior(bm, scope):
    interior = _interior_faces(scope.iter_faces())
    if interior:
        bmesh.ops.delete(bm, geom=interior, context="FACES")
    return len(interior)


def _fix_ngons(bm, scope):
    """Tessellate n-gons into quads where possible, tris otherwise.

    Poking adds a center vertex (good for cylinder caps), then coplanar tris are
    joined back into quads.
    """
    ngons = [face for face in scope.iter_faces() if len(face.verts) > 4]
    if not ngons:
        return 0
    count = len(ngons)

    new_faces = bmesh.ops.poke(bm, faces=ngons).get("faces", [])
    new_faces = [face for face in new_faces if face.is_valid]
    if new_faces:
        joined = bmesh.ops.join_triangles(
            bm,
            faces=new_faces,
            angle_face_threshold=_NGON_JOIN_FACE,
            angle_shape_threshold=_NGON_JOIN_SHAPE,
        ).get("faces", [])
        new_faces.extend(face for face in joined if face.is_valid)
    scope.add_faces(new_faces)
    return count


def _fix_quads(bm, scope):
    quads = [face for face in scope.iter_faces() if len(face.verts) == 4]
    if not quads:
        return 0
    result = bmesh.ops.triangulate(
        bm,
        faces=quads,
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    scope.add_faces(result.get("faces", []))
    return len(quads)


def _fix_zero_area(bm, scope):
    verts_before = len(bm.verts)
    faces_before = len(bm.faces)

    edges = scope.iter_edges()
    if edges:
        bmesh.ops.dissolve_degenerate(bm, dist=_DEGEN_DIST, edges=edges)
        _ensure_tables(bm)

    leftover = [face for face in scope.iter_faces() if face.calc_area() < _AREA_EPS]
    if leftover:
        bmesh.ops.delete(bm, geom=leftover, context="FACES")
        _ensure_tables(bm)

    return (verts_before - len(bm.verts)) + (faces_before - len(bm.faces))


def _fix_issues(obj, bm, scope, settings):
    """Run the fixes in an order where each one sees the previous one's output."""
    totals = dict.fromkeys(
        ("ngons", "quads", "loose", "degenerate", "lamina", "interior"), 0
    )
    steps = (
        ("ngons", settings.cleanup_ngons, _fix_ngons),
        ("quads", settings.cleanup_quads, _fix_quads),
        ("loose", settings.cleanup_loose, _fix_loose),
        ("degenerate", settings.cleanup_zero_area, _fix_zero_area),
        ("lamina", settings.cleanup_lamina, _fix_lamina),
        ("interior", settings.cleanup_interior, _fix_interior),
    )
    try:
        for key, enabled, fn in steps:
            if not enabled:
                continue
            totals[key] = fn(bm, scope)
            _ensure_tables(bm)
    finally:
        bm.normal_update()
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
        _scope_memo.pop(obj.data.name, None)

    return totals


def _apply_select_mode(context, kinds):
    if kinds:
        context.tool_settings.mesh_select_mode = (
            "VERT" in kinds,
            "EDGE" in kinds,
            "FACE" in kinds,
        )


def _scope_warning(scope, settings):
    if scope.restricted and _wants_faces(settings) and not scope.has_faces():
        return "The selection doesn't enclose whole faces"
    return None


class MODTOOLS_OT_cleanup_select(Operator):
    bl_idname = "modtools.cleanup_select"
    bl_label = "Select Issues"
    bl_description = (
        "Select geometry matching the cleanup checkboxes. "
        "Edit Mode with a selection: only that selection. Otherwise the whole mesh"
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

        restrict = context.mode == "EDIT_MESH"
        # Stays in Edit Mode on purpose: the result is a component selection.
        meshes, _entered = prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        total = 0
        kinds = set()
        warning = None
        for obj in meshes:
            bm = bmesh.from_edit_mesh(obj.data)
            _ensure_tables(bm)
            scope, source = _resolve_scope(obj, bm, restrict)
            warning = warning or _scope_warning(scope, settings)
            found, marked = _mark_issues(obj, bm, scope, settings, source)
            total += found
            kinds |= marked

        _apply_select_mode(context, kinds)

        if total:
            self.report({"INFO"}, f"Selected {total} issue(s) on {len(meshes)} mesh(es)")
        elif warning:
            self.report({"WARNING"}, warning)
        else:
            self.report({"INFO"}, "No issues found")
        return {"FINISHED"}


class MODTOOLS_OT_cleanup_fix(Operator):
    bl_idname = "modtools.cleanup_fix"
    bl_label = "Fix Issues"
    bl_description = (
        "Fix checked issues in the current selection if anything is selected, "
        "otherwise the whole mesh. Tris and non-manifold are selected only"
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

        restrict = context.mode == "EDIT_MESH"
        meshes, entered = prepare_edit(context)
        if not meshes:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        totals = dict.fromkeys(
            ("ngons", "quads", "loose", "degenerate", "lamina", "interior"), 0
        )
        warning = None
        if _any_fixable(settings):
            for obj in meshes:
                bm = bmesh.from_edit_mesh(obj.data)
                _ensure_tables(bm)
                scope, _source = _resolve_scope(obj, bm, restrict)
                warning = warning or _scope_warning(scope, settings)
                for key, value in _fix_issues(obj, bm, scope, settings).items():
                    totals[key] += value

        # Whole-mesh runs finish by showing whatever could not be repaired.
        leftover = 0
        kinds = set()
        if not restrict:
            for obj in meshes:
                bm = bmesh.from_edit_mesh(obj.data)
                _ensure_tables(bm)
                found, marked = _mark_issues(obj, bm, _Scope(bm), settings, None)
                leftover += found
                kinds |= marked
            _apply_select_mode(context, kinds)

        if entered and not leftover:
            leave_edit(context, True)

        self.report(*self._summary(settings, totals, leftover, restrict, warning))
        return {"FINISHED"}

    @staticmethod
    def _summary(settings, totals, leftover, restrict, warning):
        parts = [f"{name} {count}" for name, count in totals.items() if count]

        skipped = _select_only_names(settings)
        if skipped:
            label = ", ".join(skipped)
            if restrict:
                parts.append(f"{label} has no auto-fix")
            else:
                parts.append(f"selected {label} (no auto-fix)")
        elif leftover:
            parts.append(f"{leftover} left selected")

        if not parts:
            if warning:
                return {"WARNING"}, warning
            return {"INFO"}, "Nothing to fix"
        return {"INFO"}, "Fix: " + "; ".join(parts)


classes = (
    MODTOOLS_OT_cleanup_select,
    MODTOOLS_OT_cleanup_fix,
)

KEYMAP_ITEMS = (
    keymap_item("modtools.cleanup_select", section="Cleanup"),
    keymap_item("modtools.cleanup_fix", section="Cleanup"),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    _scope_memo.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
