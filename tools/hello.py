"""Template tool. Duplicate this file, rename the class/idname, then add it to MODULES."""

import bpy
from bpy.types import Operator


class MODTOOLS_OT_hello(Operator):
    bl_idname = "modtools.hello"
    bl_label = "Hello ModTools"
    bl_description = "Sanity check that ModTools is loaded"
    bl_options = {"REGISTER"}

    def execute(self, context):
        self.report({"INFO"}, "ModTools is loaded")
        return {"FINISHED"}


classes = (MODTOOLS_OT_hello,)

# Leave unbound for the scaffold. Example:
# KEYMAP_ITEMS = [
#     {
#         "idname": "modtools.hello",
#         "type": "F5",
#         "value": "PRESS",
#         "shift": True,
#         "keymap": "3D View",
#         "space_type": "VIEW_3D",
#     },
# ]
KEYMAP_ITEMS = ()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
