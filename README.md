# Blender modtools

Various Maya inspired functions and hotkeys in Blender, with a modeling kit toolbar.

Blender 5.2

<img width="242" height="866" alt="image" src="https://github.com/user-attachments/assets/56be42dd-f6ef-463c-936f-93dcbb27be34" />

## Install

Zip this repo and install from **Edit → Preferences → Add-ons → Install from Disk**. Enable **ModTools**.

Or clone it into your add-ons folder as `modtools`:

```
git clone https://github.com/modsoft/blender-modtools.git modtools
```

## Tools

N-panel → ModTools.

- **Group / Ungroup** — Ctrl+G / Ctrl+Shift+G (Object Mode)
- **Mesh** — Combine, Separate, Extract
- **Normals** — Soften/Harden Edge, Smooth by Angle, Unlock, Reverse, Recalculate
- **Modifiers** — Apply All, Focus Stack
- **Cleanup** — select or fix n-gons, non-manifold, loose, zero-area, and related issues
- **Topology** — Select Planar Edges, then dissolve (Ctrl+X) to un-triangulate. Quadrangulate joins tris into quads.
- **Pivot** — zero local values, snap origin to base/center/world, align to bounding box

Right-click a button to assign a shortcut.

## Changelog

### v0.1.0

Initial commit.

## License

GPL-3.0. See [LICENSE](LICENSE).
