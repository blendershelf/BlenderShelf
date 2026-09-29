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
        # real PropertyGroup entries come with their declared defaults
        item = NS(name="", top_margin=bs.DEFAULT_TOP_MARGIN,
                  left_margin_pct=bs.DEFAULT_LEFT_MARGIN_PCT, orientation='HORIZONTAL')
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
    assert len(p.placements) == len(bs._CONTEXTS) - 1  # lazily ensured all non-Object targets


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


def test_ui_context_selector():
    import inspect
    assert "ui_context" in bs.BlenderShelfPreferences.__annotations__
    assert list(inspect.signature(bs._draw_button_list).parameters) == ["layout", "prefs", "target"]


for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
    fn()
print("check_contexts OK")
