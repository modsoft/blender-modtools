"""Maya / Ninja Dojo style mesh selection tools."""

from math import radians
import random
import re

import bmesh
import bpy
from bpy.types import Operator

from . import settings as mesh_settings
from .ops_util import (
    edit_meshes,
    ensure_object_mode,
    keymap_item,
    select_only,
    selected_meshes,
)

_MAX_ANGLE_REFS = 256

_MODE_ORDER = ("VERT", "EDGE", "FACE")
_MODE_LABEL = {"VERT": "vertex", "EDGE": "edge", "FACE": "face"}
_SELECT_COUNTER = {
    "VERT": "total_vert_sel",
    "EDGE": "total_edge_sel",
    "FACE": "total_face_sel",
}


def _active_modes(context):
    flags = context.tool_settings.mesh_select_mode
    return {name for name, on in zip(_MODE_ORDER, flags) if on}


def _selection_count(context, kinds):
    """Live counters Blender maintains, so this is safe to call from poll()."""
    total = 0
    for obj in context.objects_in_mode:
        if obj.type != "MESH":
            continue
        for kind in kinds:
            total += getattr(obj.data, _SELECT_COUNTER[kind])
    return total


def _next_loop_edge(edge, vert):
    if vert is None:
        return None
    linked = vert.link_edges
    if len(linked) == 2:
        for other in linked:
            if other is not edge:
                return other
        return None
    if len(linked) != 4:
        return None
    shared = set(edge.link_faces)
    opposite = [
        other
        for other in linked
        if other is not edge and not shared.intersection(other.link_faces)
    ]
    if len(opposite) == 1:
        return opposite[0]
    return None


def _walk_loop_dir(edge, vert):
    """Edges continuing the loop from `edge` through `vert`.

    Second value is True when the walk came back around to the seed, which
    means the loop is closed and the opposite direction would repeat it.
    """
    path = []
    prev_edge = edge
    curr_vert = vert
    seen = {edge}
    while True:
        nxt = _next_loop_edge(prev_edge, curr_vert)
        if nxt is edge:
            return path, True
        if nxt is None or nxt in seen:
            return path, False
        seen.add(nxt)
        path.append(nxt)
        curr_vert = nxt.other_vert(curr_vert)
        prev_edge = nxt


def _ordered_loop_closed(edge):
    """Ordered loop through `edge`, plus whether it closes back on itself.

    A closed loop always starts at the seed, so the seed sits at index 0.
    """
    v0, v1 = edge.verts[:]
    forward, closed = _walk_loop_dir(edge, v1)
    if closed:
        return [edge] + forward, True
    backward, _ = _walk_loop_dir(edge, v0)
    return list(reversed(backward)) + [edge] + forward, False


def _ordered_loop(edge):
    return _ordered_loop_closed(edge)[0]


def _next_ring_edge(edge, face):
    if face is None or len(face.verts) != 4:
        return None
    loops = list(face.loops)
    for i, loop in enumerate(loops):
        if loop.edge is edge:
            return loops[(i + 2) % 4].edge
    return None


def _walk_ring_dir(edge, face):
    """Edges continuing the ring from `edge` across `face`. See _walk_loop_dir."""
    path = []
    curr_edge = edge
    curr_face = face
    seen = {edge}
    while curr_face is not None:
        nxt = _next_ring_edge(curr_edge, curr_face)
        if nxt is edge:
            return path, True
        if nxt is None or nxt in seen:
            return path, False
        seen.add(nxt)
        path.append(nxt)
        others = [other for other in nxt.link_faces if other is not curr_face]
        curr_face = others[0] if others else None
        curr_edge = nxt
    return path, False


def _ordered_ring_closed(edge):
    """Ordered ring through `edge`, plus whether it closes. See _ordered_loop_closed."""
    faces = list(edge.link_faces)
    if not faces:
        return [edge], False
    forward, closed = _walk_ring_dir(edge, faces[0])
    if closed:
        return [edge] + forward, True
    backward = []
    if len(faces) > 1:
        backward, _ = _walk_ring_dir(edge, faces[1])
    return list(reversed(backward)) + [edge] + forward, False


def _ordered_ring(edge):
    return _ordered_ring_closed(edge)[0]


def _subsample(ordered, seed, skip_amount):
    period = skip_amount + 1
    try:
        origin = ordered.index(seed)
    except ValueError:
        origin = 0
    return {edge for i, edge in enumerate(ordered) if (i - origin) % period == 0}


def _anchor_pair(bm, picks):
    """Order the two picks so the one clicked first anchors the pattern.

    Blender drops the select history on box select and after most operators, so
    the click order is a nicety rather than something to rely on.
    """
    for element in bm.select_history:
        if isinstance(element, bmesh.types.BMEdge) and element in picks:
            other = picks[1] if picks[0] == element else picks[0]
            return element, other
    return picks[0], picks[1]


def _pattern_from_pair(anchor, other, kind):
    """Find the run holding both picks and the spacing between them.

    Returns (ordered, seed, gap), or None when the picks share no loop or ring.
    On a closed run the walk direction is arbitrary, so two edges three apart
    read as a gap of three one way and len-3 the other. Re-seeding from the
    second pick when it gives the shorter gap keeps both picks in the result and
    matches what the spacing looks like on screen.
    """
    walker = _ordered_loop_closed if kind == "loop" else _ordered_ring_closed
    ordered, closed = walker(anchor)
    if other not in ordered:
        return None
    gap = abs(ordered.index(other) - ordered.index(anchor))
    if not gap:
        return None
    if closed and gap > len(ordered) - gap:
        # Rotating is still a valid traversal, and unlike re-walking from the
        # other pick it cannot flip to the opposite direction around the run.
        ordered = ordered[gap:] + ordered[:gap]
        anchor = other
        gap = len(ordered) - gap
    return ordered, anchor, gap


def _selected_edges(bm):
    return [edge for edge in bm.edges if edge.select]


def _clear_selection(bm):
    for face in bm.faces:
        face.select = False
    for edge in bm.edges:
        edge.select = False
    for vert in bm.verts:
        vert.select = False


def _apply_edges(obj, bm, keep, modes):
    keep = [edge for edge in keep if edge.is_valid]
    _clear_selection(bm)
    for edge in keep:
        edge.select = True
    bm.select_history.clear()
    for edge in keep:
        bm.select_history.add(edge)
    bm.select_mode = modes
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return len(set(keep))


def _redraw_view3d(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _skip_on_mesh(obj, skip_amount, kind, modes):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    seeds = _selected_edges(bm)
    if not seeds:
        return 0

    keep = set()
    used = set()
    walker = _ordered_loop if kind == "loop" else _ordered_ring
    for seed in seeds:
        if seed in used:
            continue
        ordered = walker(seed)
        used.update(ordered)
        keep.update(_subsample(ordered, seed, skip_amount))

    if kind == "ring_loop":
        looped = set()
        used_loops = set()
        for edge in keep:
            if edge in used_loops:
                continue
            loop = _ordered_loop(edge)
            used_loops.update(loop)
            looped.update(loop)
        keep = looped

    return _apply_edges(obj, bm, keep, modes)


def _grow_shrink_loop(obj, grow, modes):
    bm = bmesh.from_edit_mesh(obj.data)
    selected = _selected_edges(bm)
    if not selected:
        return 0
    selected_set = set(selected)
    if grow:
        add = []
        for edge in selected:
            for vert in edge.verts:
                nxt = _next_loop_edge(edge, vert)
                if nxt is not None and nxt not in selected_set:
                    add.append(nxt)
        keep = selected_set.union(add)
    else:
        tips = []
        for edge in selected:
            neighbors = 0
            for vert in edge.verts:
                nxt = _next_loop_edge(edge, vert)
                if nxt is not None and nxt in selected_set:
                    neighbors += 1
            if neighbors < 2:
                tips.append(edge)
        keep = selected_set.difference(tips)
    return _apply_edges(obj, bm, keep, modes)


def _active_components(bm, modes):
    """Selected elements of the finest component type the user has enabled."""
    for kind, source in (("FACE", bm.faces), ("EDGE", bm.edges), ("VERT", bm.verts)):
        if kind not in modes:
            continue
        items = [element for element in source if element.select]
        if items:
            return items
    return []


def _select_only_components(obj, bm, keep, modes):
    _clear_selection(bm)
    for element in keep:
        element.select = True
    bm.select_mode = modes
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def _seed_faces(bm):
    """Faces to seed from. Callers poll on face mode, so this is the selection."""
    return [face for face in bm.faces if face.select]


def _base_name(name):
    stripped = re.sub(r"\.\d+$", "", name)
    stripped = re.sub(r"\d+$", "", stripped)
    return stripped


def _normal_key(normal, step=1e-3):
    return (
        round(normal.x / step),
        round(normal.y / step),
        round(normal.z / step),
    )


def _reference_normals(faces):
    """One normal per distinct direction, so a big seed selection stays cheap."""
    refs = {}
    for face in faces:
        normal = face.normal
        if normal.length < 1e-8:
            continue
        refs.setdefault(_normal_key(normal), normal.copy())
    return list(refs.values())


def _grow_by_angle(seeds, thresh):
    keep = set(seeds)
    stack = list(seeds)
    while stack:
        face = stack.pop()
        if face.normal.length < 1e-8:
            continue
        for edge in face.edges:
            for other in edge.link_faces:
                if other in keep or other.normal.length < 1e-8:
                    continue
                if face.normal.angle(other.normal) <= thresh:
                    keep.add(other)
                    stack.append(other)
    return keep


class _EditSelectOp(Operator):
    """Base for selection tools that read the current component selection.

    `component` is the mode the tool reads from. The tool greys out unless that
    mode is active, which means it never has to switch modes behind your back.
    """

    bl_options = {"REGISTER", "UNDO"}
    component = None
    needs_selection = True

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH" or not edit_meshes(context):
            return False
        modes = _active_modes(context)
        if cls.component is not None and cls.component not in modes:
            cls.poll_message_set(
                f"Switch to {_MODE_LABEL[cls.component]} select mode"
            )
            return False
        if cls.needs_selection:
            kinds = (cls.component,) if cls.component else tuple(modes)
            if not _selection_count(context, kinds):
                cls.poll_message_set("Select something first")
                return False
        return True


class MODTOOLS_OT_select_shrink(_EditSelectOp):
    bl_idname = "modtools.select_shrink"
    bl_label = "Shrink"
    bl_description = "Shrink component selection"

    def execute(self, context):
        bpy.ops.mesh.select_less()
        return {"FINISHED"}


class MODTOOLS_OT_select_grow(_EditSelectOp):
    bl_idname = "modtools.select_grow"
    bl_label = "Grow"
    bl_description = "Grow component selection"

    def execute(self, context):
        bpy.ops.mesh.select_more()
        return {"FINISHED"}


class MODTOOLS_OT_select_invert(_EditSelectOp):
    bl_idname = "modtools.select_invert"
    bl_label = "Invert"
    bl_description = "Invert component selection"
    needs_selection = False

    def execute(self, context):
        bpy.ops.mesh.select_all(action="INVERT")
        return {"FINISHED"}


class _EdgeOp(_EditSelectOp):
    component = "EDGE"


class MODTOOLS_OT_pattern_select(_EdgeOp):
    bl_idname = "modtools.pattern_select"
    bl_label = "Smart Pattern Select"
    bl_description = (
        "Pick two edges on the same loop or ring, then repeat that spacing "
        "along the topology"
    )

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        if _selection_count(context, ("EDGE",)) != 2:
            cls.poll_message_set("Select exactly two edges")
            return False
        return True

    def execute(self, context):
        modes = _active_modes(context)
        for obj in edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            picks = _selected_edges(bm)
            if len(picks) != 2:
                continue

            anchor, other = _anchor_pair(bm, picks)
            for kind in ("loop", "ring"):
                found = _pattern_from_pair(anchor, other, kind)
                if found is not None:
                    break
            if found is None:
                self.report({"WARNING"}, "Those two edges share no loop or ring")
                return {"CANCELLED"}

            ordered, seed, gap = found
            total = _apply_edges(obj, bm, _subsample(ordered, seed, gap - 1), modes)
            _redraw_view3d(context)
            self.report({"INFO"}, f"Every {gap} along the {kind}: {total} edge(s)")
            return {"FINISHED"}

        self.report({"WARNING"}, "Select two edges on the same mesh")
        return {"CANCELLED"}


class MODTOOLS_OT_edge_loop_shrink(_EdgeOp):
    bl_idname = "modtools.edge_loop_shrink"
    bl_label = "Edge Loop Shrink"
    bl_description = "Shrink the edge loop selection by 1"

    def execute(self, context):
        modes = _active_modes(context)
        total = sum(
            _grow_shrink_loop(obj, False, modes) for obj in edit_meshes(context)
        )
        _redraw_view3d(context)
        self.report({"INFO"}, f"Loop shrink: {total} edge(s)")
        return {"FINISHED"}


class MODTOOLS_OT_edge_loop_grow(_EdgeOp):
    bl_idname = "modtools.edge_loop_grow"
    bl_label = "Edge Loop Grow"
    bl_description = "Grow the edge loop selection by 1"

    def execute(self, context):
        modes = _active_modes(context)
        total = sum(
            _grow_shrink_loop(obj, True, modes) for obj in edit_meshes(context)
        )
        _redraw_view3d(context)
        self.report({"INFO"}, f"Loop grow: {total} edge(s)")
        return {"FINISHED"}


class MODTOOLS_OT_edge_loop(_EdgeOp):
    bl_idname = "modtools.edge_loop"
    bl_label = "Edge Loop"
    bl_description = "Select edge loop"

    def execute(self, context):
        bpy.ops.mesh.select_edge_loop_multi()
        return {"FINISHED"}


class MODTOOLS_OT_edge_ring(_EdgeOp):
    bl_idname = "modtools.edge_ring"
    bl_label = "Edge Ring"
    bl_description = "Select edge ring"

    def execute(self, context):
        bpy.ops.mesh.select_edge_ring_multi()
        return {"FINISHED"}


class _SkipOp(_EdgeOp):
    skip_kind = "loop"

    def execute(self, context):
        settings = mesh_settings.get(context)
        if settings is None:
            self.report({"WARNING"}, "Reload ModTools to finish enabling")
            return {"CANCELLED"}
        modes = _active_modes(context)
        total = 0
        for obj in edit_meshes(context):
            total += _skip_on_mesh(obj, settings.skip_amount, self.skip_kind, modes)
        if not total:
            self.report({"WARNING"}, "Select at least one edge")
            return {"CANCELLED"}
        _redraw_view3d(context)
        self.report({"INFO"}, f"Selected {total} edge(s)")
        return {"FINISHED"}


class MODTOOLS_OT_skip_edge_loop(_SkipOp):
    bl_idname = "modtools.skip_edge_loop"
    bl_label = "Skip Edge Loop"
    bl_description = "Select every (skip+1)th edge along the edge loop"
    skip_kind = "loop"


class MODTOOLS_OT_skip_edge_ring(_SkipOp):
    bl_idname = "modtools.skip_edge_ring"
    bl_label = "Skip Edge Ring"
    bl_description = "Select every (skip+1)th edge along the edge ring"
    skip_kind = "ring"


class MODTOOLS_OT_skip_ring_loop(_SkipOp):
    bl_idname = "modtools.skip_ring_loop"
    bl_label = "Skip Ring Loop"
    bl_description = (
        "Skip along the edge ring, then select the edge loop through each kept edge"
    )
    skip_kind = "ring_loop"


class _RandomOp(_EditSelectOp):
    use_percent = True

    def execute(self, context):
        settings = mesh_settings.get(context)
        if settings is None:
            self.report({"WARNING"}, "Reload ModTools to finish enabling")
            return {"CANCELLED"}
        modes = _active_modes(context)
        total = 0
        for obj in edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            items = _active_components(bm, modes)
            if not items:
                continue
            if self.use_percent:
                pct = min(100, settings.random_value)
                count = max(1, round(len(items) * pct / 100.0))
            else:
                count = settings.random_value
            keep = random.sample(items, min(count, len(items)))
            _select_only_components(obj, bm, keep, modes)
            total += len(keep)
        if not total:
            self.report({"WARNING"}, "Select components first")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Random: {total}")
        return {"FINISHED"}


class MODTOOLS_OT_select_random_percent(_RandomOp):
    bl_idname = "modtools.select_random_percent"
    bl_label = "Select Random %"
    bl_description = "Keep a random percent of the current selection"
    use_percent = True


class MODTOOLS_OT_select_random_count(_RandomOp):
    bl_idname = "modtools.select_random_count"
    bl_label = "Select Random #"
    bl_description = "Keep a random number of items from the current selection"
    use_percent = False


class _FaceOp(_EditSelectOp):
    component = "FACE"


class _FaceAngleOp(_FaceOp):
    contiguous = False

    def execute(self, context):
        settings = mesh_settings.get(context)
        if settings is None:
            self.report({"WARNING"}, "Reload ModTools to finish enabling")
            return {"CANCELLED"}
        thresh = max(radians(settings.select_face_angle), 1e-5)

        # Read the seeds before touching the select mode, which would flush the
        # selection away from whatever component mode the user is in.
        pending = []
        for obj in edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            bm.normal_update()
            seeds = _seed_faces(bm)
            if seeds:
                pending.append((obj, bm, seeds))
        if not pending:
            self.report({"WARNING"}, "Select a face first")
            return {"CANCELLED"}

        modes = _active_modes(context)
        total = 0
        for obj, bm, seeds in pending:
            if self.contiguous:
                keep = _grow_by_angle(seeds, thresh)
            else:
                refs = _reference_normals(seeds)
                if len(refs) > _MAX_ANGLE_REFS:
                    self.report(
                        {"WARNING"},
                        f"{len(refs)} distinct normals in the selection. "
                        "Seed with fewer faces, or use Contiguous",
                    )
                    return {"CANCELLED"}
                keep = set(seeds)
                for face in bm.faces:
                    if face.normal.length < 1e-8:
                        continue
                    if any(face.normal.angle(ref) <= thresh for ref in refs):
                        keep.add(face)
            _select_only_components(obj, bm, keep, modes)
            total += len(keep)
        self.report({"INFO"}, f"Selected {total} face(s)")
        return {"FINISHED"}


class MODTOOLS_OT_select_by_face_angle(_FaceAngleOp):
    bl_idname = "modtools.select_by_face_angle"
    bl_label = "Select By Face Angle"
    bl_description = "Select faces whose normals are within the angle of the selection"
    contiguous = False


class MODTOOLS_OT_select_contiguous(_FaceAngleOp):
    bl_idname = "modtools.select_contiguous"
    bl_label = "Select Contiguous"
    bl_description = "Grow through connected faces within the angle tolerance"
    contiguous = True


class MODTOOLS_OT_select_same_shader(_FaceOp):
    bl_idname = "modtools.select_same_shader"
    bl_label = "Select by same Shader"
    bl_description = "Select faces that use the same material as the selection"

    def execute(self, context):
        pending = []
        for obj in edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            seeds = _seed_faces(bm)
            if seeds:
                pending.append((obj, bm, {face.material_index for face in seeds}))
        if not pending:
            self.report({"WARNING"}, "Select a face first")
            return {"CANCELLED"}

        modes = _active_modes(context)
        total = 0
        for obj, bm, slots in pending:
            keep = [face for face in bm.faces if face.material_index in slots]
            _select_only_components(obj, bm, keep, modes)
            total += len(keep)
        self.report({"INFO"}, f"Selected {total} face(s)")
        return {"FINISHED"}


class MODTOOLS_OT_select_same_name(Operator):
    bl_idname = "modtools.select_same_name"
    bl_label = "Select by same Name"
    bl_description = "Select objects that share a name, ignoring trailing numbers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        sources = selected_meshes(context)
        active = context.active_object
        if active is not None and active.type == "MESH" and active not in sources:
            sources = [active] + sources
        if not sources:
            self.report({"WARNING"}, "Select a mesh")
            return {"CANCELLED"}

        bases = {_base_name(obj.name) for obj in sources}
        bases.discard("")
        if not bases:
            self.report({"WARNING"}, "No matching name pattern")
            return {"CANCELLED"}

        matches = [
            obj
            for obj in context.view_layer.objects
            if obj.type == "MESH" and _base_name(obj.name) in bases
        ]
        ensure_object_mode(context)
        select_only(context, matches, active=active if active in matches else None)
        self.report({"INFO"}, f"Selected {len(matches)} object(s)")
        return {"FINISHED"}


classes = (
    MODTOOLS_OT_pattern_select,
    MODTOOLS_OT_select_shrink,
    MODTOOLS_OT_select_grow,
    MODTOOLS_OT_select_invert,
    MODTOOLS_OT_edge_loop_shrink,
    MODTOOLS_OT_edge_loop_grow,
    MODTOOLS_OT_edge_loop,
    MODTOOLS_OT_edge_ring,
    MODTOOLS_OT_skip_edge_loop,
    MODTOOLS_OT_skip_edge_ring,
    MODTOOLS_OT_skip_ring_loop,
    MODTOOLS_OT_select_random_percent,
    MODTOOLS_OT_select_random_count,
    MODTOOLS_OT_select_by_face_angle,
    MODTOOLS_OT_select_contiguous,
    MODTOOLS_OT_select_same_shader,
    MODTOOLS_OT_select_same_name,
)

KEYMAP_ITEMS = (
    keymap_item(
        "modtools.pattern_select",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_shrink",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_grow",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_invert",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.edge_loop_shrink",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.edge_loop_grow",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.edge_loop",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.edge_ring",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.skip_edge_loop",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.skip_edge_ring",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.skip_ring_loop",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_random_percent",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_random_count",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_by_face_angle",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_contiguous",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_same_shader",
        keymap="Mesh",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
    keymap_item(
        "modtools.select_same_name",
        keymap="Object Mode",
        space_type="EMPTY",
        section="Mesh Selections",
    ),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
