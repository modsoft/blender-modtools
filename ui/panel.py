import bpy
from bpy.types import Panel


def _mesh_settings(context):
    return getattr(context.scene, "modtools_mesh", None)


def _pivot_settings(context):
    return getattr(context.scene, "modtools_pivot", None)


class _Subpanel(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ModTools"
    bl_parent_id = "MODTOOLS_PT_main"


class MODTOOLS_PT_main(Panel):
    bl_label = "ModTools"
    bl_idname = "MODTOOLS_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ModTools"

    def draw(self, context):
        layout = self.layout
        mesh = _mesh_settings(context)
        if mesh is None or _pivot_settings(context) is None:
            layout.label(text="Reload ModTools to finish enabling.")
            return

        box = layout.box()
        box.label(text="Group")
        row = box.row(align=True)
        row.operator("modtools.group", text="Group", icon="OUTLINER_OB_EMPTY")
        row.operator("modtools.ungroup", text="Ungroup", icon="UNLINKED")
        box.prop(mesh, "group_locator", text="Locator")
        # Blender's own Affect Only > Parents. Sticky and scene-wide, so it gets a
        # toggle that reads as on rather than a button you press and forget.
        box.prop(
            context.scene.tool_settings,
            "use_transform_skip_children",
            text="Edit Locator(s)",
            icon="ORIENTATION_PARENT",
            toggle=True,
        )

        box = layout.box()
        box.label(text="Mesh")
        row = box.row(align=True)
        row.operator("modtools.combine", text="Combine")
        row.operator("modtools.separate", text="Separate")
        row.operator("modtools.extract", text="Extract")


class MODTOOLS_PT_selections(_Subpanel):
    bl_label = "Mesh Selections"
    bl_idname = "MODTOOLS_PT_selections"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        mesh = _mesh_settings(context)
        if mesh is None:
            return
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "modtools.pattern_select", text="Smart Pattern Select", icon="MOD_ARRAY"
        )
        layout.separator()
        row = layout.row(align=True)
        row.operator("modtools.select_shrink", text="Shrink")
        row.operator("modtools.select_grow", text="Grow")
        row.operator("modtools.select_invert", text="Invert")
        row = layout.row(align=True)
        row.operator("modtools.edge_loop_shrink", text="Edge Loop Shrink")
        row.operator("modtools.edge_loop_grow", text="Edge Loop Grow")
        row = layout.row(align=True)
        row.operator("modtools.edge_loop", text="Edge Loop")
        row.operator("modtools.edge_ring", text="Edge Ring")
        row = layout.row(align=True)
        row.prop(mesh, "skip_amount", text="")
        row.label(text="Skip Amount")
        row = layout.row(align=True)
        row.operator("modtools.skip_edge_loop", text="Skip Edge Loop")
        row.operator("modtools.skip_edge_ring", text="Skip Edge Ring")
        row.operator("modtools.skip_ring_loop", text="Skip Ring Loop")
        row = layout.row(align=True)
        row.prop(mesh, "random_value", text="")
        row.operator("modtools.select_random_percent", text="Random %")
        row.operator("modtools.select_random_count", text="Random #")
        row = layout.row(align=True)
        row.prop(mesh, "select_face_angle", text="")
        row.operator("modtools.select_by_face_angle", text="Face Angle")
        row.operator("modtools.select_contiguous", text="Contiguous")
        row = layout.row(align=True)
        row.operator("modtools.select_same_shader", text="Same Shader")
        row.operator("modtools.select_same_name", text="Same Name")


class MODTOOLS_PT_normals(_Subpanel):
    bl_label = "Normals"
    bl_idname = "MODTOOLS_PT_normals"

    def draw(self, context):
        mesh = _mesh_settings(context)
        if mesh is None:
            return
        layout = self.layout
        row = layout.row(align=True)
        row.operator("modtools.soften_edge", text="Soften Edge", icon="NORMALS_VERTEX")
        row.operator("modtools.harden_edge", text="Harden Edge", icon="NORMALS_FACE")
        row = layout.row(align=True)
        row.operator("modtools.smooth_by_angle", text="Smooth by Angle")
        row.prop(mesh, "smooth_angle", text="")
        row = layout.row(align=True)
        row.operator("modtools.unlock_normals", text="Unlock")
        row.operator("modtools.reverse_normals", text="Reverse")
        row.operator("modtools.recalculate_normals", text="Recalculate")


class MODTOOLS_PT_modifiers(_Subpanel):
    bl_label = "Modifiers"
    bl_idname = "MODTOOLS_PT_modifiers"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("modtools.apply_all_modifiers", text="Apply All", icon="CHECKMARK")
        row.operator("modtools.focus_modifiers", text="Focus Stack", icon="MODIFIER_DATA")


class MODTOOLS_PT_cleanup(_Subpanel):
    bl_label = "Cleanup"
    bl_idname = "MODTOOLS_PT_cleanup"

    def draw(self, context):
        mesh = _mesh_settings(context)
        if mesh is None:
            return
        layout = self.layout
        grid = layout.grid_flow(columns=2, even_columns=True, align=True)
        grid.prop(mesh, "cleanup_ngons")
        grid.prop(mesh, "cleanup_nonmanifold")
        grid.prop(mesh, "cleanup_loose")
        grid.prop(mesh, "cleanup_zero_area")
        grid.prop(mesh, "cleanup_lamina")
        grid.prop(mesh, "cleanup_tris")
        grid.prop(mesh, "cleanup_quads")
        grid.prop(mesh, "cleanup_interior")
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator(
            "modtools.cleanup_select",
            text="Select Issues",
            icon="RESTRICT_SELECT_OFF",
        )
        row.operator(
            "modtools.cleanup_fix",
            text="Fix Issues",
            icon="SHADERFX",
        )


class MODTOOLS_PT_topology(_Subpanel):
    bl_label = "Topology"
    bl_idname = "MODTOOLS_PT_topology"

    def draw(self, context):
        mesh = _mesh_settings(context)
        if mesh is None:
            return
        layout = self.layout
        row = layout.row(align=True)
        row.operator("modtools.select_planar_edges", text="Select Planar Edges")
        row.prop(mesh, "planar_angle", text="")
        layout.operator("modtools.quadrangulate", text="Quadrangulate", icon="MESH_GRID")


class MODTOOLS_PT_pivot(_Subpanel):
    bl_label = "Pivot Tools"
    bl_idname = "MODTOOLS_PT_pivot"

    def draw(self, context):
        pivot = _pivot_settings(context)
        if pivot is None:
            return
        layout = self.layout
        col = layout.column(align=True)
        col.operator(
            "modtools.pivot_keep_offset_zero_local",
            text="Keep Pivot Offset and Zero Local Values",
        )
        col.operator(
            "modtools.pivot_center_zero_local",
            text="Center Pivot and Zero Local Values",
        )
        col.operator(
            "modtools.pivot_base_zero_local",
            text="Move Pivot to Base and Zero Local Values",
        )
        col.operator(
            "modtools.pivot_origin_zero_all",
            text="Move Pivot to Origin and Zero All Values",
        )
        layout.separator()
        layout.label(text="Align Pivot to Bounding Box")
        layout.prop(pivot, "center_first")
        layout.prop(pivot, "individual")
        grid = layout.column(align=True)
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_x", text="Min X")
        row.operator("modtools.pivot_align_max_x", text="Max X")
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_y", text="Min Y")
        row.operator("modtools.pivot_align_max_y", text="Max Y")
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_z", text="Min Z")
        row.operator("modtools.pivot_align_max_z", text="Max Z")


classes = (
    MODTOOLS_PT_main,
    MODTOOLS_PT_selections,
    MODTOOLS_PT_normals,
    MODTOOLS_PT_modifiers,
    MODTOOLS_PT_cleanup,
    MODTOOLS_PT_topology,
    MODTOOLS_PT_pivot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
