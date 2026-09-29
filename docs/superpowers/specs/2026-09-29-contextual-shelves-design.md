# Contextual Shelves — Design

Status: approved in conversation 2026-09-29. No code written yet.

## Goal

Today BlenderShelf draws one floating shelf, only in the 3D Viewport. Make
the shelf **contextual**: every mode/editor gets its own shelf with its own
buttons, position and orientation. Add to Shelf gets a context picker. The pie
menu mirrors the shelf of the current context.

## Decisions

1. **One mode/editor = one shelf. No shared "general" list.** If a context's
   shelf is not enabled, nothing is drawn there. Exception: in the 3D
   Viewport, Edit and Sculpt fall back to the Object shelf until they get
   their own (keeps today's behavior for existing users).
2. **Contexts:** Object (the existing shelf, `prefs.buttons`), Edit (mesh),
   Sculpt, UV Editor, Shader Editor, Geometry Nodes. Object is always on; the
   other five each have an enable checkbox.
3. **Add to Shelf** shows a context picker (dialog) when more than one shelf
   is enabled; with only Object enabled it stays one click. Default choice =
   context under the right-clicked button, else Object.
4. **Pie menu = mirror of the current context's shelf**, falling back to the
   Object shelf where the context has no shelf. Split mode, the separate pie
   lists, and "Add to ShelfPie" are removed. `show_in_pie` stays.
5. **Per-context placement:** each context stores its own `top_margin`,
   `left_margin_pct`, `orientation`. Colors, size, labels, opacity stay global.
6. **FBX export slot** appears only in 3D-Viewport contexts.
7. **No config migration.** Only ~3 users; losing/ignoring an old config is
   acceptable. Old `pie_buttons_*` lists simply become the contextual shelf
   lists (same collections, no rename); `pie_buttons_object` and `pie_mode`
   are dropped. Prefer no migration code over a migration that can add bugs.

## Architecture

- **Reuse existing collections.** `pie_buttons_edit/sculpt/uv/node_shader/
  node_geo` and their `pie_context_*` enable flags become the contextual shelf
  lists/flags. Names stay legacy (renaming buys nothing without migration).
  Only new prop: `pie_context_edit`.
- **`_CONTEXTS` table** maps target key → (label, enable-flag attr, area type).
  One resolver `_context_target(area, mode, prefs)` picks the target for both
  the shelf and the pie.
- **`_active_target` module global**, set at the top of each draw and each
  modal event, so the existing geometry/hit-test helpers need no new
  parameter. `_placement(prefs, target)` returns `prefs` itself for Object
  (no data change) and a `BLENDERSHELF_placement` entry for other contexts —
  same attribute names, so call sites are identical.
- **Same `draw_shelf` registered on** `SpaceView3D`, `SpaceImageEditor`,
  `SpaceNodeEditor`.
- **Single modal operator stays.** Finding from reading the code: a modal
  operator's `context.area/region` is where it was *invoked*, not where the
  mouse is. So the modal finds the area under the cursor itself from absolute
  window coordinates (`event.mouse_x/y` vs `area.x/y/width/height`) and runs
  button commands inside `context.temp_override(area=…, region=…)` so
  `bpy.ops.uv.*` / `node.*` get the right editor context. This works whether
  or not the invoke-area assumption is right.

## Out of scope

- Shelves in a separate (pop-out) window: the modal is bound to the window it
  was invoked in (existing limitation, unchanged).
- Other modes (Pose, paint modes, Grease Pencil, Compositor…): add on request.
- Renaming legacy `pie_*` names.
- Release/tag/extension upload (separate, user-triggered).

## Risks

- Clicks on empty space in node/UV editors must pass through; the modal only
  consumes clicks on shelf rects (same rule as the 3D Viewport today).
- Hover/pressed/tooltip state is global; it must render only in the area the
  mouse is in (`_active_area_ptr`), or two open editors show ghost hovers.
- `_start_modal` lifecycle code is fragile (see project notes); touch only its
  host-area choice.
