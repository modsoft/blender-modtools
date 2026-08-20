"""Check GitHub for a newer ModTools version.

This only ever reads. Replacing a package Python has already imported needs a
restart, backup and rollback to survive a half-finished download, and here it
would write through the junction into a git working tree. So the button reports
what is published and leaves installing to you.
"""

import os
import re
import sys
import threading
import urllib.request

import bpy
from bpy.types import Operator

REPO_URL = "https://github.com/modsoft/blender-modtools"
_MANIFEST_URL = (
    "https://raw.githubusercontent.com/modsoft/blender-modtools"
    "/master/blender_manifest.toml"
)
_TIMEOUT = 8.0

# Handed from the worker thread to the timer. Plain Python values only, since
# bpy is not safe to touch off the main thread.
_fetched = None
_checking = False

_status = {"text": "", "behind": False}


def _format(version):
    return ".".join(str(part) for part in version)


def _version_from_manifest(text):
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        return None
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        return None


def _current_version():
    """bl_info when it exists, else the manifest an extension install ships with."""
    package = sys.modules.get(__package__)
    info = getattr(package, "bl_info", None)
    if info and info.get("version"):
        return tuple(info["version"])

    path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _version_from_manifest(handle.read())
    except OSError:
        return None


def _worker():
    global _fetched
    try:
        request = urllib.request.Request(
            _MANIFEST_URL, headers={"User-Agent": "ModTools"}
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            _fetched = (True, response.read().decode("utf-8", "replace"))
    except Exception as exc:
        # Offline, DNS, TLS, 404. All of it is just something to report.
        _fetched = (False, f"{type(exc).__name__}: {exc}")


def _redraw_preferences():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "PREFERENCES":
                area.tag_redraw()


def _finish(text, behind=False):
    _status["text"] = text
    _status["behind"] = behind


def _poll_result():
    global _fetched, _checking
    if _fetched is None:
        return 0.2

    ok, payload = _fetched
    _fetched = None
    _checking = False

    if not ok:
        _finish(f"Could not reach GitHub. {payload}")
    else:
        latest = _version_from_manifest(payload)
        current = _current_version()
        if latest is None or current is None:
            _finish("Could not read the published version")
        elif latest > current:
            _finish(f"Version {_format(latest)} is available", behind=True)
        else:
            _finish(f"Up to date, running {_format(current)}")

    _redraw_preferences()
    return None


class MODTOOLS_OT_check_for_updates(Operator):
    bl_idname = "modtools.check_for_updates"
    bl_label = "Check for Updates"
    bl_description = "Ask GitHub which version is published. Nothing is downloaded"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if _checking:
            cls.poll_message_set("Already checking")
            return False
        return True

    def execute(self, context):
        global _checking, _fetched
        _checking = True
        _fetched = None
        _finish("Checking...")
        threading.Thread(target=_worker, daemon=True).start()
        if not bpy.app.timers.is_registered(_poll_result):
            bpy.app.timers.register(_poll_result, first_interval=0.2)
        return {"FINISHED"}


def draw(layout):
    current = _current_version()
    row = layout.row(align=True)
    row.operator("modtools.check_for_updates", icon="FILE_REFRESH")
    if current is not None:
        row.label(text=f"Installed {_format(current)}")

    if not _status["text"]:
        return
    row = layout.row(align=True)
    if _status["behind"]:
        row.label(text=_status["text"], icon="IMPORT")
        row.operator("wm.url_open", text="Open on GitHub").url = REPO_URL
    else:
        row.label(text=_status["text"])


classes = (MODTOOLS_OT_check_for_updates,)


def register():
    global _checking, _fetched
    _checking = False
    _fetched = None
    _finish("")
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if bpy.app.timers.is_registered(_poll_result):
        bpy.app.timers.unregister(_poll_result)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
