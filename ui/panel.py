import bpy
from bpy.types import Panel


class MODTOOLS_PT_main(Panel):
    bl_label = "ModTools"
    bl_idname = "MODTOOLS_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ModTools"

    def draw(self, context):
        layout = self.layout
        pivot = getattr(context.window_manager, "modtools_pivot", None)
        mesh = getattr(context.window_manager, "modtools_mesh", None)
        if pivot is None or mesh is None:
            layout.label(text="Reload ModTools to finish enabling.")
            return

        box = layout.box()
        box.label(text="Group")
        row = box.row(align=True)
        row.operator("modtools.group", text="Group")
        row.operator("modtools.ungroup", text="Ungroup")

        box = layout.box()
        box.label(text="Mesh")
        row = box.row(align=True)
        row.operator("modtools.combine", text="Combine")
        row.operator("modtools.separate", text="Separate")
        row.operator("modtools.extract", text="Extract")

        box = layout.box()
        box.label(text="Normals")
        row = box.row(align=True)
        row.operator("modtools.soften_edge", text="Soften Edge")
        row.operator("modtools.harden_edge", text="Harden Edge")
        row = box.row(align=True)
        row.operator("modtools.smooth_by_angle", text="Smooth by Angle")
        row.prop(mesh, "smooth_angle", text="")
        row = box.row(align=True)
        row.operator("modtools.unlock_normals", text="Unlock")
        row.operator("modtools.reverse_normals", text="Reverse")
        row.operator("modtools.recalculate_normals", text="Recalculate")

        box = layout.box()
        box.label(text="Modifiers")
        row = box.row(align=True)
        row.operator("modtools.apply_all_modifiers", text="Apply All")
        row.operator("modtools.focus_modifiers", text="Focus Stack")

        box = layout.box()
        box.label(text="Cleanup")
        grid = box.grid_flow(columns=2, even_columns=True, align=True)
        grid.prop(mesh, "cleanup_ngons", toggle=True)
        grid.prop(mesh, "cleanup_nonmanifold", toggle=True)
        grid.prop(mesh, "cleanup_loose", toggle=True)
        grid.prop(mesh, "cleanup_zero_area", toggle=True)
        grid.prop(mesh, "cleanup_lamina", toggle=True)
        grid.prop(mesh, "cleanup_tris", toggle=True)
        grid.prop(mesh, "cleanup_quads", toggle=True)
        grid.prop(mesh, "cleanup_interior", toggle=True)
        row = box.row(align=True)
        row.operator("modtools.cleanup_select", text="Select Issues")
        row.operator("modtools.cleanup_fix", text="Fix Issues")

        box = layout.box()
        box.label(text="Topology")
        row = box.row(align=True)
        row.operator("modtools.select_planar_edges", text="Select Planar Edges")
        row.prop(mesh, "planar_angle", text="")
        box.operator("modtools.quadrangulate", text="Quadrangulate")

        box = layout.box()
        box.label(text="Pivot Tools")
        col = box.column(align=True)
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
        box.separator()
        box.label(text="Align Pivot to Bounding Box")
        box.prop(pivot, "center_first")
        box.prop(pivot, "individual")
        grid = box.column(align=True)
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_x", text="Min X")
        row.operator("modtools.pivot_align_max_x", text="Max X")
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_y", text="Min Y")
        row.operator("modtools.pivot_align_max_y", text="Max Y")
        row = grid.row(align=True)
        row.operator("modtools.pivot_align_min_z", text="Min Z")
        row.operator("modtools.pivot_align_max_z", text="Max Z")


classes = (MODTOOLS_PT_main,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
