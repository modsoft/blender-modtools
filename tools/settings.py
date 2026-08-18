import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup


class ModToolsMeshSettings(PropertyGroup):
    smooth_angle: FloatProperty(
        name="Angle",
        description="Smooth by Angle threshold in degrees (Maya default is 30)",
        default=30.0,
        min=0.0,
        max=180.0,
        step=10,
        precision=1,
    )
    cleanup_ngons: BoolProperty(
        name="N-gons",
        description="Select n-gons, or tessellate them to quads/tris on Fix",
        default=True,
    )
    cleanup_nonmanifold: BoolProperty(
        name="Non-manifold",
        description="Select non-manifold edges and vertices",
        default=True,
    )
    cleanup_loose: BoolProperty(
        name="Loose",
        description="Select loose vertices and edges with no faces",
        default=True,
    )
    cleanup_zero_area: BoolProperty(
        name="Zero-area",
        description="Select zero-area faces and zero-length edges",
        default=True,
    )
    cleanup_lamina: BoolProperty(
        name="Lamina",
        description="Select overlapping faces that share the same vertices",
        default=False,
    )
    cleanup_tris: BoolProperty(
        name="Tris",
        description="Select triangles",
        default=False,
    )
    cleanup_quads: BoolProperty(
        name="Quads",
        description="Select quads, or triangulate them on Fix",
        default=False,
    )
    cleanup_interior: BoolProperty(
        name="Interior",
        description="Select faces whose edges all have more than two face users",
        default=False,
    )
    planar_angle: FloatProperty(
        name="Planar Angle",
        description="Max angle between faces (degrees) to treat a shared edge as planar",
        default=5.0,
        min=0.0,
        max=90.0,
        step=10,
        precision=1,
    )


def get(context):
    return getattr(context.window_manager, "modtools_mesh", None)


def register():
    bpy.utils.register_class(ModToolsMeshSettings)
    bpy.types.WindowManager.modtools_mesh = PointerProperty(type=ModToolsMeshSettings)


def unregister():
    if hasattr(bpy.types.WindowManager, "modtools_mesh"):
        del bpy.types.WindowManager.modtools_mesh
    bpy.utils.unregister_class(ModToolsMeshSettings)
