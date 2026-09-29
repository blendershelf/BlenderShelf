# Contextual Shelves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One BlenderShelf shelf per mode/editor (Object, Edit, Sculpt, UV, Shader, Geometry Nodes), each with its own buttons and position; Add to Shelf gets a context picker; the pie menu mirrors the current context's shelf.

**Architecture:** Reuse the existing per-context button collections (`pie_buttons_*` + `pie_context_*` flags) as the contextual shelf lists. A `_CONTEXTS` table + `_context_target()` resolver picks the list; a module global `_active_target` (set at the top of every draw and modal event) lets existing geometry/hit-test helpers stay parameterless. The same `draw_shelf` is registered on the Image and Node editor spaces. The single modal operator finds the area under the cursor from absolute window coordinates (its own `context.area` is the *invoke* area) and runs commands inside `context.temp_override`.

**Tech Stack:** Python / Blender 4.4 `bpy` (GPU draw handlers, modal operator, AddonPreferences). Checks run inside Blender via the Blender MCP `execute_blender_code`.

**Spec:** `docs/superpowers/specs/2026-09-29-contextual-shelves-design.md`

## Global Constraints

- Source of truth is the repo file `addon/__init__.py`. After edits, sync to the live addon by copying **only** `__init__.py` to `%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons\BlenderShelf\__init__.py`. **Never copy `blender_manifest.toml` or `LICENSE` there** (Blender then converts the install to an extension and deletes the folder + config).
- Do not reload/enable/disable the addon in the user's live Blender from scripts, and do not fire rapid enable→disable cycles. Tasks 1–5 verify with `py_compile` and `tests/check_contexts.py` (which loads the repo file as a *separate* module); only Task 6 asks the user to reload.
- No screenshots (`get_viewport_screenshot`) — the user checks visuals; verify by read-backs.
- No config migration code. Old configs may load with defaults; unknown JSON keys are ignored.
- No renaming of legacy `pie_*` names. No version bump, tag, release, or `build_*.py` run.
- Any value computed for `IntProperty` margins must be wrapped in `round()`.
- `bpy.utils.register_class` errors: catch `(RuntimeError, ValueError)`, never only `RuntimeError`.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Work on branch `contextual-shelves` (create in Task 1).

## Review Focus

1. Two shelved editors open at once (3D Viewport + UV): hovering/pressing in one must not highlight or show a tooltip in the other. → Task 3 manual checklist.
2. Cursor leaves the area mid-drag of the drag handle: shelf keeps following; the new position is saved to the *dragged* context, not the area the cursor ended in. → Task 3 (`_drag_target`), manual checklist.
3. Clicks on empty space in the Node/UV editors (box select, pan, click-drag) must pass through untouched. → Task 3 manual checklist.
4. An old `shelf_config.json` (has `pie_mode`, `pie_buttons_object`, no `placements`) loads without exception and yields default placements. → Task 1 `test_old_config_loads`.
5. Reset Position / enabling a context whose editor is not open must warn, not raise; Add to Shelf right-clicked from a non-shelf editor (Properties) defaults to Object. → Task 2 (`_find_region` returns `None` path), Task 5.

---

### Task 1: Context table, resolver, placement model, config

**Files:**
- Modify: `addon/__init__.py` (constants near `_PIE_TARGETS` ~line 598; `BLENDERSHELF_button_item`/`command_param` ~561-582; `BlenderShelfPreferences` props ~1670-1705; `_config_to_dict` ~784; `_load_config_from_path` ~871; `classes` ~3270; `register()` ~3316)
- Create: `tests/check_contexts.py`

**Interfaces:**
- Produces: `_CONTEXTS` (`target -> (label, flag_attr | None, area_type)`), `_CONTEXT_ITEMS`, `_SHELF_AREA_TYPES`, `_enabled_targets(prefs) -> [target]`, `_context_target(area, mode, prefs) -> target | None`, `BLENDERSHELF_placement` PropertyGroup, `prefs.placements`, `prefs.pie_context_edit`, `_ensure_placements(prefs)`, `_placement(prefs, target)`.

- [ ] **Step 1: Create branch**

```bash
cd /c/Users/denis/BlenderShelf-releases && git switch -c contextual-shelves
```

- [ ] **Step 2: Write the failing check** — create `tests/check_contexts.py`:

```python
"""Run inside Blender (Blender MCP execute_blender_code, or `blender -b --python`):
    exec(open(r"C:\\Users\\denis\\BlenderShelf-releases\\tests\\check_contexts.py").read())
Loads the repo addon file as a SEPARATE module (does not touch the live addon)."""
import importlib.util, json, os, sys, tempfile
from types import SimpleNamespace as NS

ADDON = r"C:\Users\denis\BlenderShelf-releases\addon\__init__.py"
spec = importlib.util.spec_from_file_location("bs_under_test", ADDON)
bs = importlib.util.module_from_spec(spec)
sys.modules["bs_under_test"] = bs
spec.loader.exec_module(bs)


class FakeColl(list):
    def add(self):
        item = NS(name="")
        self.append(item)
        return item

    def clear(self):
        del self[:]

    def get(self, key):
        return next((i for i in self if i.name == key), None)


class FakePrefs:
    """Attribute bag: collections appear on first access, flags default False."""
    def __getattr__(self, name):
        if name == "buttons" or name == "placements" or name.startswith("pie_buttons_"):
            coll = FakeColl()
            setattr(self, name, coll)
            return coll
        if name.startswith("pie_context_"):
            return False
        raise AttributeError(name)


def prefs(**flags):
    p = FakePrefs()
    for k, v in flags.items():
        setattr(p, k, v)
    return p


def area(kind, ui_type="", tree_type=""):
    return NS(type=kind, ui_type=ui_type, spaces=NS(active=NS(tree_type=tree_type)))


def test_resolver():
    t = bs._context_target
    assert t(area('VIEW_3D'), 'OBJECT', prefs()) == 'SHELF'
    assert t(area('VIEW_3D'), 'EDIT_MESH', prefs()) == 'SHELF'  # Edit shelf off -> Object shelf
    assert t(area('VIEW_3D'), 'EDIT_MESH', prefs(pie_context_edit=True)) == 'PIE_EDIT'
    assert t(area('VIEW_3D'), 'SCULPT', prefs(pie_context_sculpt=True)) == 'PIE_SCULPT'
    assert t(area('IMAGE_EDITOR', ui_type='UV'), 'OBJECT', prefs()) is None
    assert t(area('IMAGE_EDITOR', ui_type='UV'), 'OBJECT', prefs(pie_context_uv=True)) == 'PIE_UV'
    assert t(area('IMAGE_EDITOR', ui_type='IMAGE_EDITOR'), 'OBJECT', prefs(pie_context_uv=True)) is None
    shader = area('NODE_EDITOR', tree_type='ShaderNodeTree')
    geo = area('NODE_EDITOR', tree_type='GeometryNodeTree')
    assert t(shader, 'OBJECT', prefs(pie_context_node_shader=True)) == 'PIE_NODE_SHADER'
    assert t(geo, 'OBJECT', prefs(pie_context_node_shader=True)) is None
    assert t(geo, 'OBJECT', prefs(pie_context_node_geo=True)) == 'PIE_NODE_GEO'
    assert t(area('PROPERTIES'), 'OBJECT', prefs()) is None
    assert t(None, 'OBJECT', prefs()) is None


def test_table_consistent():
    for target, (label, flag, area_type) in bs._CONTEXTS.items():
        assert target in bs._PIE_TARGETS, target
        assert area_type in bs._SHELF_AREA_TYPES
        if flag:
            assert flag in bs.BlenderShelfPreferences.__annotations__, flag
    assert bs._enabled_targets(prefs()) == ['SHELF']
    assert bs._enabled_targets(prefs(pie_context_uv=True)) == ['SHELF', 'PIE_UV']


def test_placement():
    p = prefs()
    assert bs._placement(p, 'SHELF') is p
    entry = bs._placement(p, 'PIE_UV')
    assert entry.name == 'PIE_UV' and bs._placement(p, 'PIE_UV') is entry
    assert len(p.placements) == 1


def test_old_config_loads():
    old = {"version": [0, 1, 6], "top_margin": 55, "pie_mode": "SPLIT",
           "pie_buttons_object": [{"label": "X", "command": "1"}],
           "buttons": [{"label": "Cube", "command": "bpy.ops.mesh.primitive_cube_add()"}]}
    path = os.path.join(tempfile.gettempdir(), "bs_old_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old, f)
    p = prefs()
    assert bs._load_config_from_path(p, path)
    assert p.top_margin == 55 and len(p.buttons) == 1
    assert p.pie_context_edit is False
    d = bs._config_to_dict(p)
    assert set(d["placements"]) == {t for t in bs._CONTEXTS if t != 'SHELF'}
    for entry in d["placements"].values():
        assert entry["top_margin"] == bs.DEFAULT_TOP_MARGIN


for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
    fn()
print("check_contexts OK")
```

- [ ] **Step 3: Run it to verify it fails**

Run via Blender MCP `execute_blender_code` with code `exec(open(r"C:\Users\denis\BlenderShelf-releases\tests\check_contexts.py").read())`.
Expected: `AttributeError: module 'bs_under_test' has no attribute '_context_target'` (or `_CONTEXTS`).

- [ ] **Step 4: Add the context table.** In `addon/__init__.py`, directly **above** the line `_TARGET_LABELS = {` add:

```python
# Every list is a per-context shelf; the pie menu mirrors the current
# context's list. The `pie_buttons_*` / `pie_context_*` names are legacy from
# when these were pie-only lists -- kept as-is (renaming would need a config
# migration for no user-visible gain).
# target -> (label, prefs flag that enables it (None = always on), area type)
_CONTEXTS = {
    'SHELF': ("Object Mode", None, 'VIEW_3D'),
    'PIE_EDIT': ("Edit Mode", "pie_context_edit", 'VIEW_3D'),
    'PIE_SCULPT': ("Sculpt Mode", "pie_context_sculpt", 'VIEW_3D'),
    'PIE_UV': ("UV Editor", "pie_context_uv", 'IMAGE_EDITOR'),
    'PIE_NODE_SHADER': ("Shader Editor", "pie_context_node_shader", 'NODE_EDITOR'),
    'PIE_NODE_GEO': ("Geometry Nodes", "pie_context_node_geo", 'NODE_EDITOR'),
}
_CONTEXT_ITEMS = tuple((k, v[0], "") for k, v in _CONTEXTS.items())
_SHELF_AREA_TYPES = ('VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR')
```

Then, after `_target_collection()` add:

```python
def _enabled_targets(prefs):
    return [t for t, (_label, flag, _area) in _CONTEXTS.items() if flag is None or getattr(prefs, flag)]


def _context_target(area, mode, prefs):
    """Which shelf list applies to this area/mode, or None if no shelf lives
    there. In the 3D Viewport Edit/Sculpt fall back to the Object shelf until
    they have their own enabled; UV/Node editors draw nothing until enabled."""
    if area is None or prefs is None:
        return None
    if area.type == 'VIEW_3D':
        if mode == 'SCULPT' and prefs.pie_context_sculpt:
            return 'PIE_SCULPT'
        if mode == 'EDIT_MESH' and prefs.pie_context_edit:
            return 'PIE_EDIT'
        return 'SHELF'
    if area.type == 'IMAGE_EDITOR':
        return 'PIE_UV' if area.ui_type == 'UV' and prefs.pie_context_uv else None
    if area.type == 'NODE_EDITOR':
        tree = getattr(area.spaces.active, "tree_type", "")
        if tree == 'ShaderNodeTree' and prefs.pie_context_node_shader:
            return 'PIE_NODE_SHADER'
        if tree == 'GeometryNodeTree' and prefs.pie_context_node_geo:
            return 'PIE_NODE_GEO'
    return None


def _ensure_placements(prefs):
    for target in _CONTEXTS:
        if target != 'SHELF' and prefs.placements.get(target) is None:
            prefs.placements.add().name = target


def _placement(prefs, target):
    """Object holding top_margin / left_margin_pct / orientation for a
    context. The Object shelf keeps those three directly on prefs (no data
    change for it); every other context has a BLENDERSHELF_placement entry.
    Same attribute names either way, so callers don't branch."""
    if target == 'SHELF':
        return prefs
    entry = prefs.placements.get(target)
    if entry is None:
        _ensure_placements(prefs)
        entry = prefs.placements.get(target)
    return entry
```

- [ ] **Step 5: Add the placement PropertyGroup.** After `class BLENDERSHELF_command_param(...)` add:

```python
class BLENDERSHELF_placement(bpy.types.PropertyGroup):
    # .name = context target key (see _CONTEXTS). Not used for 'SHELF'.
    top_margin: bpy.props.IntProperty(name="Top Margin", default=DEFAULT_TOP_MARGIN, min=0,
                                       update=lambda self, context: _on_prefs_changed())
    left_margin_pct: bpy.props.FloatProperty(
        name="Left Margin", default=DEFAULT_LEFT_MARGIN_PCT, min=0.0, max=1.0, subtype='FACTOR',
        description="Distance from the area's left edge, as a fraction of its width",
        update=lambda self, context: _on_prefs_changed())
    orientation: bpy.props.EnumProperty(
        name="Orientation",
        items=(('HORIZONTAL', "Horizontal", ""), ('VERTICAL', "Vertical", "")),
        default='HORIZONTAL',
        update=lambda self, context: _on_prefs_changed())
```

Register it before prefs: in `classes` insert `BLENDERSHELF_placement,` right after `BLENDERSHELF_command_param,`.

- [ ] **Step 6: Prefs props.** In `BlenderShelfPreferences`, next to `pie_context_sculpt` add:

```python
    pie_context_edit: bpy.props.BoolProperty(name="Edit Mode", default=False,
                                              update=lambda self, context: _on_prefs_changed())
    placements: bpy.props.CollectionProperty(type=BLENDERSHELF_placement)
```

- [ ] **Step 7: Config save/load.** In `_config_to_dict` add after `"pie_context_sculpt"`:

```python
        "pie_context_edit": prefs.pie_context_edit,
```
and after the `pie_buttons_node_geo` entry (end of dict):

```python
        "placements": {p.name: {"top_margin": p.top_margin, "left_margin_pct": p.left_margin_pct,
                                "orientation": p.orientation} for p in prefs.placements},
```
In `_load_config_from_path`, inside the `_loading_config = True` try-block, after the `pie_context_node_geo` line add:

```python
        prefs.pie_context_edit = data.get("pie_context_edit", False)
        _ensure_placements(prefs)
        for name, d in data.get("placements", {}).items():
            if name in _CONTEXTS and name != 'SHELF':
                p = _placement(prefs, name)
                p.top_margin = d.get("top_margin", DEFAULT_TOP_MARGIN)
                p.left_margin_pct = d.get("left_margin_pct", DEFAULT_LEFT_MARGIN_PCT)
                p.orientation = d.get("orientation", 'HORIZONTAL')
```
In `register()`, immediately after `prefs = get_prefs()` / `if prefs is not None:` add as the first line inside: `_ensure_placements(prefs)`.

- [ ] **Step 8: Run compile + check**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` → no output.
Run the Step 3 MCP command. Expected: `check_contexts OK`.

- [ ] **Step 9: Commit**

```bash
git add addon/__init__.py tests/check_contexts.py docs/superpowers
git commit -m "Add context table, resolver and per-context placement model" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Target-aware state helpers

Makes geometry, item lists, placement, hotkey checks and redraws depend on `_active_target`. Object-shelf behavior in the 3D Viewport is unchanged. The modal still reads whatever target the last draw set (Task 3 replaces that).

**Files:**
- Modify: `addon/__init__.py` (`_tag_viewports_redraw` ~624, `_find_view3d_region` ~631, `_pie_hotkey_assigned`/`_should_draw_shelf`/`_export_button_enabled` ~679-702, `_position`/`_enabled_items` ~941-955, `_center_position_on_first_run` ~1002, `start_move_button`/`add_separator` redraw loops ~1088/1112, `_center_shelf_position` + `pref_preset_position` ~1361-1393, `add_from_context` loop ~2287, `_is_vertical` ~2378, `shelf_geometry` ~2442, `draw_shelf` top ~2719, modal redraw loops)
- Modify: `tests/check_contexts.py`

**Interfaces:**
- Consumes: Task 1 (`_CONTEXTS`, `_placement`, `_target_collection`, `_context_target`).
- Produces: `_active_target` (global), `_sync_active_target(area, mode)`, `_find_region(area_type)`, `_area_of_region(region)`, `_pie_hotkey_assigned(area_type)`, `_center_shelf_position(prefs, region, target)`, operator `blender_shelf.pref_preset_position` with `target` prop.

- [ ] **Step 1: Extend the check** — append to `tests/check_contexts.py` **above** the final `for fn in ...` loop:

```python
def test_active_target_helpers():
    p = prefs(pie_context_uv=True)
    bs.get_prefs = lambda: p
    bs._sync_active_target(area('VIEW_3D'), 'OBJECT')
    assert bs._active_target == 'SHELF'
    p.buttons.extend([NS(enabled=True), NS(enabled=False)])
    p.pie_buttons_uv.extend([NS(enabled=True), NS(enabled=True), NS(enabled=False)])
    assert len(bs._enabled_items()) == 1
    bs._sync_active_target(area('IMAGE_EDITOR', ui_type='UV'), 'OBJECT')
    assert bs._active_target == 'PIE_UV' and len(bs._enabled_items()) == 2
    bs._placement(p, 'PIE_UV').orientation = 'VERTICAL'
    assert bs._is_vertical()
    bs._sync_active_target(area('VIEW_3D'), 'OBJECT')
    p.orientation = 'HORIZONTAL'
    assert not bs._is_vertical()
    bs._sync_active_target(area('NODE_EDITOR', tree_type='ShaderNodeTree'), 'OBJECT')
    assert bs._active_target is None and bs._enabled_items() == [] and not bs._should_draw_shelf()
```

- [ ] **Step 2: Run to verify it fails**

Run the MCP command from Task 1 Step 3. Expected: `AttributeError: ... '_sync_active_target'`.

- [ ] **Step 3: Replace redraw + region finder.** Replace the bodies of `_tag_viewports_redraw` and `_find_view3d_region` with:

```python
def _tag_viewports_redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in _SHELF_AREA_TYPES:
                area.tag_redraw()


def _find_region(area_type='VIEW_3D'):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == area_type:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return region
    return None


def _area_of_region(region):
    """A modal operator's context.area is where it was invoked, so the area a
    region belongs to has to be looked up, not read from the context."""
    ptr = region.as_pointer()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if any(r.as_pointer() == ptr for r in area.regions):
                return area
    return None
```
Update `_center_position_on_first_run`: `region = _find_view3d_region()` → `region = _find_region('VIEW_3D')`, and its call `_center_shelf_position(prefs, region)` → `_center_shelf_position(prefs, region, 'SHELF')`.

Replace every 3-line loop

```python
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
```
(any indentation; found with `grep -n "if area.type == 'VIEW_3D'" addon/__init__.py`, sites in `start_move_button`, `add_separator`, `add_from_context`, and the modal — the modal ones are rewritten in Task 3, leave them) with a single `_tag_viewports_redraw()`.

- [ ] **Step 4: Active target + hotkey + draw gating.** Replace `_pie_hotkey_assigned`, `_should_draw_shelf`, `_export_button_enabled` with:

```python
_KEYMAP_FOR_AREA = {space: name for name, space in _PIE_KEYMAP_SPACES}

# ponytail: module global, set at the top of every draw and modal event so
# geometry/hit-test helpers need no extra parameter. Thread `target`
# explicitly if anything ever runs draws/events concurrently.
_active_target = None


def _sync_active_target(area, mode):
    global _active_target
    prefs = get_prefs()
    _active_target = _context_target(area, mode, prefs) if prefs else None
    return _active_target


def _pie_hotkey_assigned(area_type='VIEW_3D'):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    km = kc.keymaps.get(_KEYMAP_FOR_AREA.get(area_type, '3D View')) if kc else None
    if km is None:
        return False
    for kmi in km.keymap_items:
        if kmi.idname == 'wm.call_menu_pie' and kmi.properties.name == BLENDERSHELF_MT_pie.bl_idname:
            return kmi.active and kmi.type != 'NONE'
    return False


def _should_draw_shelf():
    if _active_target is None:
        return False
    prefs = get_prefs()
    mode = prefs.display_mode if prefs else 'BOTH'
    if mode == 'PIE':
        return not _pie_hotkey_assigned(_CONTEXTS[_active_target][2])
    return True


def _export_button_enabled():
    prefs = get_prefs()
    # FBX export only makes sense next to 3D content, not in UV/Node editors
    return bool(prefs and prefs.show_export_button and _active_target is not None
                and _CONTEXTS[_active_target][2] == 'VIEW_3D')
```
(`_KEYMAP_FOR_AREA` must sit **after** `_PIE_KEYMAP_SPACES`; the block above already follows it in the file.)

- [ ] **Step 5: Position/items/orientation.** Replace `_position`, `_enabled_items`, `_is_vertical`:

```python
def _position(region):
    if _drag_live_margins is not None and _active_target == _drag_target:
        return _drag_live_margins
    prefs = get_prefs()
    if prefs is None or _active_target is None:
        return DEFAULT_TOP_MARGIN, DEFAULT_LEFT_MARGIN_PCT * region.width
    p = _placement(prefs, _active_target)
    return p.top_margin, p.left_margin_pct * region.width


def _enabled_items():
    prefs = get_prefs()
    if prefs is None or _active_target is None:
        return []
    coll, _ = _target_collection(prefs, _active_target)
    return [b for b in coll if b.enabled]
```
```python
def _is_vertical():
    prefs = get_prefs()
    if prefs is None or _active_target is None:
        return False
    return _placement(prefs, _active_target).orientation == 'VERTICAL'
```
Add `_drag_target = None` to the globals block next to `_drag_live_margins` (~line 2961).

- [ ] **Step 6: Centering + Reset Position.** Replace `_center_shelf_position` and the operator:

```python
def _center_shelf_position(prefs, region, target):
    """Shared by Reset Position and the first-run default -- the two must
    land on the same spot, or a fresh install's shelf shows up somewhere the
    user never asked for and never confirmed via the button."""
    global _active_target
    _active_target = target
    items = _enabled_items()
    total_slots = _total_slots(items)
    vertical = _is_vertical()
    panel_w, panel_h = _panel_size(total_slots, vertical)
    p = _placement(prefs, target)

    center_x = max(0.0, (region.width - panel_w) / 2.0)
    left_px = center_x if vertical else max(0.0, center_x - _aux_reserve())
    p.left_margin_pct = max(0.0, min(1.0, left_px / region.width)) if region.width else 0.0
    p.top_margin = PRESET_EDGE_MARGIN + _min_top_margin()


class BLENDERSHELF_OT_pref_preset_position(bpy.types.Operator):
    """Reset this shelf to its default top-center position"""
    bl_idname = "blender_shelf.pref_preset_position"
    bl_label = "Reset Position"
    target: bpy.props.EnumProperty(items=_CONTEXT_ITEMS, default='SHELF')

    def execute(self, context):
        label, _flag, area_type = _CONTEXTS[self.target]
        region = _find_region(area_type)
        if region is None:
            self.report({'WARNING'}, f"No {label} area is open to measure -- open one and try again")
            return {'CANCELLED'}
        prefs = get_prefs()
        _center_shelf_position(prefs, region, self.target)
        _tag_viewports_redraw()
        _save_prefs()
        return {'FINISHED'}
```

- [ ] **Step 7: Geometry + draw gating.** In `shelf_geometry` replace `_sidebar_bounds(bpy.context.area, region)` with `_sidebar_bounds(_area_of_region(region), region)`. In `draw_shelf`, replace the first lines

```python
    region = bpy.context.region
    if region is None:
        return
    items = _enabled_items()
```
with

```python
    region = bpy.context.region
    if region is None:
        return
    if _sync_active_target(bpy.context.area, bpy.context.mode) is None:
        return  # no shelf lives in this area/mode
    items = _enabled_items()
    prefs = get_prefs()
    coll = _target_collection(prefs, _active_target)[0] if prefs is not None else None
```
then in `draw_shelf` replace `_visible_real_indices(prefs.buttons)` with `_visible_real_indices(coll)`, `moving_btn = prefs.buttons[_moving_index]` with `moving_btn = coll[_moving_index]`, and `show_export_button = prefs.show_export_button if prefs else True` with `show_export_button = _export_button_enabled()`. (The later duplicate `prefs = get_prefs()` line stays; harmless.)

- [ ] **Step 8: Verify**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` → no output.
Run the MCP check. Expected: `check_contexts OK`.

- [ ] **Step 9: Commit**

```bash
git add addon/__init__.py tests/check_contexts.py
git commit -m "Make shelf geometry, items and placement follow the active context" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Draw in Image/Node editors and generalize the modal

**Files:**
- Modify: `addon/__init__.py` (globals block ~2928-2970; `draw_shelf`; `BLENDERSHELF_OT_modal.modal` ~2981-3176; `start_move_button`/`add_separator`; `_start_modal` ~3209; `register`/`unregister` draw handle)
- Modify: `tests/check_contexts.py`

**Interfaces:**
- Consumes: Task 2 (`_active_target`, `_sync_active_target`, `_placement`, `_area_of_region`, `_tag_viewports_redraw`).
- Produces: `_area_under_mouse(context, event) -> (area, region, mx, my)`, globals `_active_area_ptr`, `_drag_start_abs`, `_moving_target`, `_draw_handles`.

- [ ] **Step 1: Failing check** — add above the final loop in `tests/check_contexts.py`:

```python
def test_area_under_mouse():
    def a(kind, x, w):
        return NS(type=kind, x=x, y=0, width=w, height=100,
                  regions=[NS(type='WINDOW', x=x, y=0)])
    ui, view = a('IMAGE_EDITOR', 100, 100), a('VIEW_3D', 0, 100)
    props = a('PROPERTIES', 200, 50)
    ctx = NS(window=NS(screen=NS(areas=[view, ui, props])))
    found, region, mx, my = bs._area_under_mouse(ctx, NS(mouse_x=150, mouse_y=20))
    assert found is ui and (mx, my) == (50, 20)
    assert bs._area_under_mouse(ctx, NS(mouse_x=10, mouse_y=5))[0] is view
    assert bs._area_under_mouse(ctx, NS(mouse_x=210, mouse_y=5))[0] is None  # not a shelf area
    assert bs._area_under_mouse(NS(window=None), NS(mouse_x=0, mouse_y=0))[0] is None
```

Run the MCP check. Expected: `AttributeError: ... '_area_under_mouse'`.

- [ ] **Step 2: Helper + globals.** Add above `class BLENDERSHELF_OT_modal`:

```python
def _area_under_mouse(context, event):
    """(area, WINDOW region, region-local x, y) of the shelf-capable area under
    the cursor, from absolute window coordinates. The modal's own
    context.area/region is where it was *invoked*, not where the mouse is."""
    win = context.window
    if win is None:
        return None, None, 0, 0
    for area in win.screen.areas:
        if area.type not in _SHELF_AREA_TYPES:
            continue
        if area.x <= event.mouse_x < area.x + area.width and area.y <= event.mouse_y < area.y + area.height:
            for region in area.regions:
                if region.type == 'WINDOW':
                    return area, region, event.mouse_x - region.x, event.mouse_y - region.y
    return None, None, 0, 0
```
In the globals block replace `_draw_handle = None` with `_draw_handles = []  # (space class, handle)` and add next to `_drag_target = None`:

```python
_drag_start_abs = (0, 0)  # absolute window coords at drag start -- area-independent
_active_area_ptr = None  # as_pointer() of the area the mouse is interacting with; hover/press/tooltip draw only there
_moving_target = None  # context target whose list `_moving_index` indexes
```

- [ ] **Step 3: Draw shows interaction state only in the owning area.** In `draw_shelf`, right after the `prefs = get_prefs()` line that precedes `bg_color = ...`, insert:

```python
    area = bpy.context.area
    here = area is not None and area.as_pointer() == _active_area_ptr
    hover_index = _hover_index if here else None
    pressed_index = _pressed_index if here else None
    export_hover = _export_hover and here
    export_pressed = _export_pressed and here
    orient_hover = _orient_hover and here
    drag_hover = _drag_hover and here
    dragging = _dragging_shelf and here
    moving_here = _moving_index is not None and _moving_target == _active_target
```
Then, **inside `draw_shelf` only**, apply these renames (use `grep -n` on the function's line range to catch all):
- `_hover_index` → `hover_index`; `_pressed_index` → `pressed_index`
- `_export_hover` → `export_hover`; `_export_pressed` → `export_pressed`
- `_orient_hover` → `orient_hover`; `_drag_hover` → `drag_hover`; `_dragging_shelf` → `dragging`
- `if draw_panel and prefs is not None and _moving_index is not None:` → `if draw_panel and prefs is not None and moving_here:`
- `if _moving_index is not None and moving_slot_i is not None:` → `if moving_here and here and moving_slot_i is not None:`
- tooltip `if _moving_index is not None:` → `if moving_here and here:`

- [ ] **Step 4: Rewrite the modal body.** In `BLENDERSHELF_OT_modal.modal`, replace the `global` block and everything from `in_viewport = ...` down to (and including) the final `return {'PASS_THROUGH'}` of `modal` (keep the `_last_alive`/`_modal_stop` block between them as it is) with:

```python
        global _modal_running, _hover_index, _pressed_index, _mouse_x, _mouse_y
        global _export_hover, _export_pressed, _orient_hover, _drag_hover
        global _dragging_shelf, _drag_start_mouse, _drag_start_abs, _drag_start_margins
        global _drag_live_margins, _drag_region_width, _drag_target
        global _last_alive, _restart_requested
        global _moving_index, _move_insert_gap
        global _pending_export_selection, _active_target, _active_area_ptr
        _last_alive = time.time()  # proof of life, independent of _modal_running
        if _modal_stop or _restart_requested:
            _modal_running = False
            _restart_requested = False
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            return {'CANCELLED'}

        area, region, mx, my = _area_under_mouse(context, event)
        if not _dragging_shelf:  # a drag keeps owning its area/target wherever the cursor goes
            if area is not None:
                _sync_active_target(area, context.mode)
                _active_area_ptr = area.as_pointer()
            else:
                _active_target = None
                _active_area_ptr = None

        if _moving_index is not None and event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            _moving_index = None
            _move_insert_gap = None
            _tag_viewports_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            if _moving_index is not None:
                if area is not None:
                    _mouse_x, _mouse_y = mx, my
                    if _active_target == _moving_target and _should_draw_shelf():
                        _, _, _, _, rects = shelf_geometry(region)
                        _move_insert_gap = _gap_under_mouse(rects, mx, my, _is_vertical())
                _tag_viewports_redraw()
                return {'RUNNING_MODAL'}  # consume it -- don't hover/orbit while moving

            if _dragging_shelf:
                dx = event.mouse_x - _drag_start_abs[0]
                dy = event.mouse_y - _drag_start_abs[1]
                _mouse_x, _mouse_y = _drag_start_mouse[0] + dx, _drag_start_mouse[1] + dy
                start_top, start_left = _drag_start_margins
                _drag_live_margins = (max(0.0, start_top - dy), max(0.0, start_left + dx))
                _tag_viewports_redraw()
                return {'RUNNING_MODAL'}  # consume the drag, don't also orbit/pan the viewport

            new_hover = None
            new_export_hover = False
            new_orient_hover = False
            new_drag_hover = False
            if area is not None:
                _mouse_x, _mouse_y = mx, my
                if _should_draw_shelf():
                    _, _, _, _, rects = shelf_geometry(region)
                    for i, (x0, y0, x1, y1) in enumerate(rects):
                        if x0 <= mx <= x1 and y0 <= my <= y1:
                            new_hover = i
                            break
                    if _export_button_enabled():
                        ex0, ey0, ex1, ey1 = fbx_button_rect(region)
                        new_export_hover = ex0 <= mx <= ex1 and ey0 <= my <= ey1
                    ox0, oy0, ox1, oy1 = orientation_button_rect(region)
                    new_orient_hover = ox0 <= mx <= ox1 and oy0 <= my <= oy1
                    gx0, gy0, gx1, gy1 = drag_handle_rect(region)
                    new_drag_hover = gx0 <= mx <= gx1 and gy0 <= my <= gy1
            # redraw on any state change, and continuously while hovering so
            # the tooltip box tracks the cursor
            should_redraw = (new_hover != _hover_index or new_export_hover != _export_hover
                              or new_orient_hover != _orient_hover or new_drag_hover != _drag_hover
                              or new_hover is not None or new_export_hover or new_orient_hover or new_drag_hover)
            _hover_index = new_hover
            _export_hover = new_export_hover
            _orient_hover = new_orient_hover
            _drag_hover = new_drag_hover
            if should_redraw:
                _tag_viewports_redraw()  # all shelf areas: the previously-hovered one must clear too
            return {'PASS_THROUGH'}

        if _moving_index is not None and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            prefs = get_prefs()
            if prefs is not None and _move_insert_gap is not None:
                coll, idx_attr = _target_collection(prefs, _moving_target)
                real_indices = _visible_real_indices(coll)
                target = _gap_target_real_index(real_indices, _move_insert_gap, len(coll))
                if target != _moving_index:
                    coll.move(_moving_index, target)
                    setattr(prefs, idx_attr, target)
                    _save_prefs()
            _moving_index = None
            _move_insert_gap = None
            _tag_viewports_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS' and area is not None:
            if _should_draw_shelf():
                _, _, _, _, rects = shelf_geometry(region)
                for i, (x0, y0, x1, y1) in enumerate(rects):
                    if x0 <= mx <= x1 and y0 <= my <= y1:
                        prefs = get_prefs()
                        coll, idx_attr = _target_collection(prefs, _active_target)
                        real_indices = _visible_real_indices(coll)
                        if i < len(real_indices):
                            setattr(prefs, idx_attr, real_indices[i])
                            # explicit INVOKE_DEFAULT -- called from a script/
                            # modal context (not a real UI button click), so
                            # without it every operator drawn inside the menu
                            # (Delete's own invoke_confirm included) silently
                            # runs EXEC-only and skips its invoke()/dialog.
                            with context.temp_override(window=context.window, area=area, region=region):
                                bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="BLENDERSHELF_MT_shelf_button_context")
                        return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and area is not None:
            if _should_draw_shelf():
                items = _enabled_items()
                _, _, _, _, rects = shelf_geometry(region)
                for i, (x0, y0, x1, y1) in enumerate(rects):
                    if x0 <= mx <= x1 and y0 <= my <= y1:
                        _pressed_index = i
                        btn = items[i]
                        if btn.command:
                            try:
                                # the command must run in the editor it was clicked in
                                # (bpy.ops.uv.* / node.* poll on the area type)
                                with context.temp_override(window=context.window, area=area, region=region):
                                    _exec_shelf_command(btn.command)
                            except Exception as e:
                                self.report({'ERROR'}, f"Shelf button {i + 1} ({btn.label}) failed: {e}")
                        _tag_viewports_redraw()
                        return {'RUNNING_MODAL'}

                if _export_button_enabled():
                    ex0, ey0, ex1, ey1 = fbx_button_rect(region)
                    if ex0 <= mx <= ex1 and ey0 <= my <= ey1:
                        _export_pressed = True
                        try:
                            _pending_export_selection = [o.name for o in context.selected_objects]
                            with context.temp_override(window=context.window, area=area, region=region):
                                bpy.ops.export_scene.fbx('INVOKE_DEFAULT', use_selection=True)
                        except Exception as e:
                            self.report({'ERROR'}, f"Export FBX failed: {e}")
                        _tag_viewports_redraw()
                        return {'RUNNING_MODAL'}

                ox0, oy0, ox1, oy1 = orientation_button_rect(region)
                if ox0 <= mx <= ox1 and oy0 <= my <= oy1:
                    prefs = get_prefs()
                    if prefs is not None:
                        p = _placement(prefs, _active_target)
                        p.orientation = 'HORIZONTAL' if p.orientation == 'VERTICAL' else 'VERTICAL'
                    _tag_viewports_redraw()
                    return {'RUNNING_MODAL'}

                gx0, gy0, gx1, gy1 = drag_handle_rect(region)
                if gx0 <= mx <= gx1 and gy0 <= my <= gy1:
                    _dragging_shelf = True
                    _drag_target = _active_target
                    _drag_start_mouse = (mx, my)
                    _drag_start_abs = (event.mouse_x, event.mouse_y)
                    _drag_region_width = region.width
                    _drag_start_margins = _position(region)
                    _drag_live_margins = _drag_start_margins
                    _tag_viewports_redraw()
                    return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and _dragging_shelf:
            _dragging_shelf = False
            prefs = get_prefs()
            if prefs is not None and _drag_live_margins is not None and _drag_target is not None:
                top, left_px = _drag_live_margins
                p = _placement(prefs, _drag_target)
                p.top_margin = round(top)  # IntProperty -- rejects a bare float
                if _drag_region_width:
                    p.left_margin_pct = max(0.0, min(1.0, left_px / _drag_region_width))
            _drag_live_margins = None
            _tag_viewports_redraw()
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and (
                _pressed_index is not None or _export_pressed):
            _pressed_index = None
            _export_pressed = False
            _tag_viewports_redraw()
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}
```

- [ ] **Step 5: Moving is per-target.** In `BLENDERSHELF_OT_start_move_button.execute` and `BLENDERSHELF_OT_add_separator.execute`: change `global _moving_index, _move_insert_gap` to `global _moving_index, _move_insert_gap, _moving_target` and add `_moving_target = self.target` next to each `_moving_index = ...` assignment.

- [ ] **Step 6: `_start_modal` host area.** In `_start_modal`, replace the block starting `win = bpy.context.window` / `if win is None: return 0.5` / `for area in win.screen.areas:` … through the final `return 0.5` with:

```python
    win = bpy.context.window
    if win is None:
        return 0.5
    # Any area can host the modal now (it finds the area under the cursor
    # itself); prefer a 3D Viewport so behavior is identical to before
    # whenever one exists.
    for area in sorted(win.screen.areas, key=lambda a: a.type != 'VIEW_3D'):
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            continue
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.blender_shelf.modal('INVOKE_DEFAULT')
        except Exception:
            pass
        return 0.5
    return 0.5
```

- [ ] **Step 7: Draw handlers on all three spaces.** In `register()` replace the `_draw_handle = bpy.types.SpaceView3D.draw_handler_add(...)` line with:

```python
    for space in (bpy.types.SpaceView3D, bpy.types.SpaceImageEditor, bpy.types.SpaceNodeEditor):
        _draw_handles.append((space, space.draw_handler_add(draw_shelf, (), 'WINDOW', 'POST_PIXEL')))
```
and remove `_draw_handle` from `register()`'s `global` line. In `unregister()` remove `_draw_handle` from the `global` line and replace the `if _draw_handle is not None: ...` block with:

```python
    for space, handle in _draw_handles:
        try:
            space.draw_handler_remove(handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
    _draw_handles.clear()
```
Also add `_drag_target = None` and `_active_area_ptr = None` to `unregister()`'s reset list (declare them `global`).

- [ ] **Step 8: Verify statically**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` → no output.
Run: `grep -n "_draw_handle\b\|in_viewport\|_find_view3d_region\|prefs.buttons\[" addon/__init__.py` → only `_draw_handles`/legit uses (no `in_viewport`, no `_find_view3d_region`, no `prefs.buttons[` inside `draw_shelf`/modal).
Run the MCP check. Expected: `check_contexts OK`.

- [ ] **Step 9: Commit**

```bash
git add addon/__init__.py tests/check_contexts.py
git commit -m "Draw shelves in UV/Node editors; modal finds the area under the cursor" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(Manual in-Blender behavior is checked in Task 6, after the UI exists to enable contexts.)

---

### Task 4: Preferences UI — context selector, per-context position

**Files:**
- Modify: `addon/__init__.py` (`BlenderShelfPreferences` props + `draw()` ~1743-1890; `_draw_button_list` ~1908)

**Interfaces:**
- Consumes: `_CONTEXTS`, `_CONTEXT_ITEMS`, `_placement`.
- Produces: `prefs.ui_context` (session-only nav enum). `_draw_button_list(layout, prefs, target)` — always shows the `show_in_pie` checkbox; `show_pie_flag` param removed.

- [ ] **Step 1: Prop.** Next to `prefs_tab` add (no `update=`, not persisted — same as `prefs_tab`):

```python
    ui_context: bpy.props.EnumProperty(items=_CONTEXT_ITEMS, default='SHELF')
```

- [ ] **Step 2: Shelf tab.** In `draw()`, in the `Appearance & Position` panel: rename the header text to `"Appearance"`; delete the lines `panel.row().operator("blender_shelf.pref_preset_position")`, the `row.prop(self, "top_margin")` / `row.prop(self, "left_margin_pct", slider=True)` pair (and their `row = panel.row()`), and `panel.row().prop(self, "orientation", expand=True)`. Replace the two lines

```python
            layout.label(text="Shelf buttons -- order determines button 1..N in the viewport:")
            _draw_button_list(layout, self, 'SHELF', show_pie_flag=True)
```
with:

```python
            layout.row().prop(self, "ui_context", expand=True)
            target = self.ui_context
            label, flag, _area = _CONTEXTS[target]
            if flag:
                layout.prop(self, flag, text=f"Enable the {label} shelf")
            if flag and not getattr(self, flag):
                layout.label(text=f"No shelf is drawn in {label} until enabled.", icon='INFO')
            else:
                pos_box = layout.box()
                pos_box.label(text=f"{label} shelf position")
                pl = _placement(self, target)
                row = pos_box.row()
                row.prop(pl, "top_margin")
                row.prop(pl, "left_margin_pct", slider=True)
                pos_box.row().prop(pl, "orientation", expand=True)
                pos_box.operator("blender_shelf.pref_preset_position").target = target
                layout.label(text=f"{label} buttons -- order determines button 1..N:")
                _draw_button_list(layout, self, target)
```

- [ ] **Step 3: Pie tab.** Replace the whole `elif self.prefs_tab == 'PIE':` body with:

```python
        elif self.prefs_tab == 'PIE':
            layout.prop(self, "display_mode")
            if self.display_mode == 'PIE':
                layout.label(text="(falls back to the shelf if no key is assigned below)", icon='INFO')
            layout.label(text="The pie menu shows the shelf of the context it is opened in.", icon='INFO')
            box = layout.box()
            box.label(text="Pie Menu Hotkey (3D Viewport):")
            _draw_pie_hotkey(box, context, '3D View')
            if self.pie_context_uv:
                box = layout.box()
                box.label(text="Pie Menu Hotkey (UV Editor):")
                _draw_pie_hotkey(box, context, 'Image')
            if self.pie_context_node_shader or self.pie_context_node_geo:
                box = layout.box()
                box.label(text="Pie Menu Hotkey (Node Editor):")
                _draw_pie_hotkey(box, context, 'Node Editor')
```
(Leave the `pie_mode` prop itself for Task 5; nothing in the UI shows it now.)

- [ ] **Step 4: `_draw_button_list`.** Change the signature to `def _draw_button_list(layout, prefs, target):`, replace

```python
        if show_pie_flag:
            box.prop(item, "show_in_pie")
```
with `box.prop(item, "show_in_pie")`, and replace the `if prefs.pie_mode == 'SPLIT':` guard before `Copy To...` with an unconditional call (dedent the operator line and update the comment to `# copy this button into another enabled context's shelf`).

- [ ] **Step 5: Verify**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` → no output.
Run: `grep -n "show_pie_flag\|_draw_button_list(" addon/__init__.py` → only the new definition and the single new call.
Run the MCP check → `check_contexts OK`.

- [ ] **Step 6: Commit**

```bash
git add addon/__init__.py
git commit -m "Preferences: per-context shelf selector, enable flags and position" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pie mirrors the context; Add to Shelf picks the context; remove Split/ShelfPie

**Files:**
- Modify: `addon/__init__.py` (`_PIE_TARGETS`/`_TARGET_LABELS` ~598-616; `BLENDERSHELF_MT_shelf_button_context` ~1118; `_copy_destination_items`/`copy_button` ~1140-1189; `_split_pie_target`, `BLENDERSHELF_MT_pie` ~1576-1654; prefs props ~1672-1698; config to/from; `add_from_context`, `_pie_category_items`, `add_to_pie`, `_shelf_context_menu_draw` ~2266-2371; `classes`)
- Modify: `tests/check_contexts.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `_add_target_items`; `blender_shelf.add_from_context` gains `category` (context picker).

- [ ] **Step 1: Drop the Object pie list and derive labels.** In `_PIE_TARGETS` delete the `'PIE_OBJECT': (...)` entry. Delete the whole `_TARGET_LABELS = {...}` literal and replace with `_TARGET_LABELS = {k: v[0] for k, v in _CONTEXTS.items()}` (keep the `_TARGET_ITEMS = ...` line under it). In `BlenderShelfPreferences` delete `pie_buttons_object`, `pie_active_index_object`, and the `pie_mode` property. In `_config_to_dict` delete the `"pie_mode"` and `"pie_buttons_object"` entries; in `_load_config_from_path` delete the `prefs.pie_mode = ...` and `_deserialize_items(prefs.pie_buttons_object, ...)` lines.

- [ ] **Step 2: Pie mirrors the current context.** Delete `_split_pie_target` entirely and replace `BLENDERSHELF_MT_pie.draw` with:

```python
    def draw(self, context):
        pie = self.layout.menu_pie()
        prefs = get_prefs()
        if prefs is None:
            return
        target = _context_target(context.area, context.mode, prefs) or 'SHELF'
        coll, _ = _target_collection(prefs, target)
        items = [(i, b) for i, b in enumerate(coll) if b.enabled and b.show_in_pie]
        if not items:
            pie.label(text="Not configured yet", icon='INFO')
            return
        _draw_pie_slots(pie, items)
```

- [ ] **Step 3: Shelf-button context menu uses the clicked context.** In `BLENDERSHELF_MT_shelf_button_context.draw`, add `target = _active_target or 'SHELF'` after `layout = self.layout` and replace the three `.target = 'SHELF'` with `.target = target`.

- [ ] **Step 4: Copy To.** Replace `_copy_destination_items` with:

```python
def _copy_destination_items(self, context):
    prefs = get_prefs()
    keys = _enabled_targets(prefs) if prefs else ['SHELF']
    global _copy_destination_items_cache
    _copy_destination_items_cache = [(k, _TARGET_LABELS[k], "") for k in keys if k != self.source]
    return _copy_destination_items_cache
```

- [ ] **Step 5: Add to Shelf with a context picker.** Delete `_pie_category_items`, `_pie_category_items_cache`, and `class BLENDERSHELF_OT_add_to_pie`. Replace `BLENDERSHELF_OT_add_from_context` with:

```python
_add_target_items_cache = []  # kept referenced -- Blender frees dynamic enum strings otherwise


def _add_target_items(self, context):
    prefs = get_prefs()
    global _add_target_items_cache
    _add_target_items_cache = [(t, _TARGET_LABELS[t], "") for t in (_enabled_targets(prefs) if prefs else ['SHELF'])]
    return _add_target_items_cache


class BLENDERSHELF_OT_add_from_context(bpy.types.Operator):
    """Add the right-clicked button's action to one of the enabled shelves"""
    bl_idname = "blender_shelf.add_from_context"
    bl_label = "Add to Shelf"
    bl_options = {'REGISTER'}

    category: bpy.props.EnumProperty(name="Shelf", items=_add_target_items)
    captured_label: bpy.props.StringProperty(options={'HIDDEN'})
    captured_command: bpy.props.StringProperty(options={'HIDDEN'})
    captured_icon_path: bpy.props.StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        # context.button_operator only exists while this runs from the
        # right-click menu itself -- invoke_props_dialog() re-enters via a
        # fresh event loop, so execute() no longer sees it. Capture now and
        # carry the result through as plain string props.
        op_id, label, command, icon_path = _capture_button_command(context)
        if not op_id:
            self.report({'WARNING'}, "No operator found on this button")
            return {'CANCELLED'}
        self.captured_label = label
        self.captured_command = command
        self.captured_icon_path = icon_path or ""
        prefs = get_prefs()
        valid = [item[0] for item in _add_target_items(self, context)]
        target = _context_target(context.area, context.mode, prefs) if prefs else None
        self.category = target if target in valid else 'SHELF'
        if len(valid) == 1:
            return self.execute(context)  # only the Object shelf is on: no dialog, one click
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text=self.captured_label)
        self.layout.prop(self, "category", expand=True)

    def execute(self, context):
        prefs = get_prefs()
        coll, _ = _target_collection(prefs, self.category)
        if any(b.command == self.captured_command for b in coll):
            self.report({'INFO'}, f"'{self.captured_label}' is already on that shelf")
            return {'CANCELLED'}
        item = coll.add()
        item.label = self.captured_label
        item.command = self.captured_command
        item.icon_path = self.captured_icon_path or os.path.join(BLENDER_ICON_DIR, "MESH_MONKEY.png")
        item.enabled = True
        _tag_viewports_redraw()
        _save_prefs()
        self.report({'INFO'}, f"Added '{self.captured_label}' to {_TARGET_LABELS[self.category]}")
        return {'FINISHED'}
```
In `_shelf_context_menu_draw` delete the `prefs`/`pie_mode == 'SPLIT'`/`add_to_pie` lines (keep the separator and the `add_from_context` row). Remove `BLENDERSHELF_OT_add_to_pie,` from `classes`.

- [ ] **Step 6: Extend the check** — add above the final loop in `tests/check_contexts.py`:

```python
def test_dead_code_gone():
    for name in ("_split_pie_target", "BLENDERSHELF_OT_add_to_pie", "_pie_category_items"):
        assert not hasattr(bs, name), name
    assert "PIE_OBJECT" not in bs._PIE_TARGETS
    assert "pie_mode" not in bs.BlenderShelfPreferences.__annotations__
    assert "category" in bs.BLENDERSHELF_OT_add_from_context.__annotations__
    p = prefs(pie_context_uv=True)
    bs.get_prefs = lambda: p
    assert [i[0] for i in bs._add_target_items(None, None)] == ['SHELF', 'PIE_UV']
```

- [ ] **Step 7: Verify**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` → no output.
Run: `grep -n "pie_mode\|PIE_OBJECT\|pie_buttons_object\|add_to_pie\|_split_pie_target\|SPLIT" addon/__init__.py` → no matches.
Run the MCP check → `check_contexts OK` (`test_old_config_loads` still passes: unknown keys ignored).

- [ ] **Step 8: Commit**

```bash
git add addon/__init__.py tests/check_contexts.py
git commit -m "Pie mirrors the current context's shelf; Add to Shelf picks a context; drop Split pie" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Live sync and manual verification

**Files:**
- Modify: `FEEDBACK.md` (append a short "Contextual shelves" decisions note)

- [ ] **Step 1: Final static gate**

Run: `python -m py_compile C:/Users/denis/BlenderShelf-releases/addon/__init__.py` and the MCP check. Expected: no output / `check_contexts OK`.

- [ ] **Step 2: Back up the live file, then sync it.**

```bash
LIVE="$APPDATA/Blender Foundation/Blender/4.4/scripts/addons/BlenderShelf"
ls "$LIVE/__init__.py" && cp "$LIVE/__init__.py" "/c/Users/denis/BlenderShelf-releases/backups/__init___$(date +%Y%m%d_%H%M%S)_before_contextual_shelves.py" \
  && cp /c/Users/denis/BlenderShelf-releases/addon/__init__.py "$LIVE/__init__.py"
```
If `$LIVE` does not exist (the extension install is active instead), **stop and ask the user** — do not recreate the legacy folder next to an enabled extension (see Global Constraints).
Do **not** copy `blender_manifest.toml` / `LICENSE`.

- [ ] **Step 3: Ask the user to reload** (`bpy.ops.script.reload()` or restart Blender) and run this checklist; report results back:
  1. 3D Viewport, Object mode: shelf looks and works as before (drag handle, orientation, FBX slot, buttons).
  2. Preferences → Shelf tab: the context row shows Object / Edit / Sculpt / UV / Shader / Geo; enabling **UV Editor** shows its (empty) list; Add Button works; **Reset Position** with a UV Editor open centers the shelf there, and with none open shows a warning (no exception).
  3. UV Editor: the UV shelf appears; clicking a button runs a `bpy.ops.uv.*` command; hover highlights only in the UV editor while a 3D Viewport is also open and shows its own shelf (Review Focus 1).
  4. Drag the UV shelf's drag handle and move the cursor out over the 3D Viewport before releasing: the UV shelf ends up where the cursor's *offset* says, and the 3D shelf did not move (Review Focus 2).
  5. Node Editor: with Shader and Geometry Nodes enabled, each tree type shows its own shelf; box-select / pan / click on empty node-editor space still work (Review Focus 3).
  6. Edit mode with **Edit Mode** shelf off shows the Object shelf; turn it on → its own (empty) shelf appears; same for Sculpt.
  7. Right-click a Blender button → **Add to Shelf**: with only Object on, one click adds; with UV on, a dialog offers Object / UV Editor.
  8. Pie hotkey in the UV Editor (after assigning one) shows the UV shelf's buttons; in a disabled context it falls back to the Object shelf.

- [ ] **Step 4: Note the decision.** Append to `FEEDBACK.md`:

```markdown
## Contextual shelves (2026-09-29)

Shipped on branch `contextual-shelves`: one shelf per mode/editor (Object, Edit,
Sculpt, UV, Shader, Geometry Nodes), each with its own buttons, position and
orientation. Pie = mirror of the current context's shelf; Split pie and
"Add to ShelfPie" removed. No config migration (old pie lists become the
contextual shelves, disabled until enabled). Not done: pop-out windows,
Pose/paint/Grease Pencil/Compositor contexts, renaming legacy `pie_*` names.
```

- [ ] **Step 5: Commit** (only after the user reports the checklist passes; fix regressions first, one commit per fix)

```bash
git add FEEDBACK.md
git commit -m "Note contextual shelves decisions in FEEDBACK.md" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Merging to `main`, version bump, `build_release.py`/`build_extension.py`, guide update and site changes are **not** part of this plan — separate, user-triggered steps.
