import bpy
from bpy.types import AddonPreferences


class ModToolsPreferences(AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout

        from . import update

        update.draw(layout)
        layout.separator()

        layout.label(text="Assign shortcuts here. Panel buttons stay grey when they don't apply.")
        layout.label(text="Group is Ctrl+G, Ungroup is Ctrl+Shift+G (Object Mode).")
        layout.separator()

        from . import keymaps

        keymaps.draw_preferences(layout, context)


classes = (ModToolsPreferences,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
