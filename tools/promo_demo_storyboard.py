"""BlenderShelf promo-video storyboard, driven live via Blender's own
bpy.app.timers so it plays out at a locked tempo while you screen-record --
no manual clicking, no MCP round-trip jitter.

HOW TO RUN: paste this whole file's contents into a single
mcp__blender__execute_blender_code call (or `exec(open(path).read())` from
Blender's own Python console/Text Editor). It registers one timer and
returns immediately; the sequence itself plays out on its own.

HOW TO EDIT: everything you'd plausibly want to tweak lives in the CONFIG
section below -- BPM, the button list/order, the color palettes, the
bounce/scale tuning. The state machine after it should rarely need to
change. See project_blendershelf_promo_video.md (Claude's memory) for the
full narrated storyboard and the lessons learned building this.

IMPORTANT -- recapture ORIG before running on a different shelf/session:
run this first and copy the printed values into ORIG below:

    import bpy
    p = bpy.context.preferences.addons['BlenderShelf'].preferences
    print(p.shelf_scale, p.top_margin, p.left_margin_pct, p.orientation,
          p.label_placement, list(p.label_color), list(p.btn_color),
          list(p.bg_color), list(p.separator_color))

Also recapture the live viewport width (VP_W below) if the recording
window/monitor changed:

    for a in bpy.context.window.screen.areas:
        if a.type == 'VIEW_3D':
            print([r.width for r in a.regions if r.type == 'WINDOW'])
"""
import bpy, os
import BlenderShelf as mod

prefs = bpy.context.preferences.addons['BlenderShelf'].preferences
ICON = mod.BLENDER_ICON_DIR

# ============================== CONFIG ======================================

BPM = 100.0  # measured from untitled.wav via librosa beat-tracking: steady 0.601s
             # quarter-note interval (std ~8ms) = ~99.83 BPM, rounded to a clean 100 --
             # the track loops, so this constant tempo holds indefinitely.
BEAT8 = 60.0 / BPM / 2.0  # eighth note -- the base cadence for every discrete step

HOLD_SECONDS = 5.0  # empty shelf held on screen before anything happens

# the shelf's own baseline, captured live before this take (see docstring) --
# everything reverts to this at the end of the sequence.
ORIG = {
    'shelf_scale': 1.2,
    'top_margin': 300,
    'left_margin_pct': 0.3784516751766205,
    'orientation': 'HORIZONTAL',
    'label_placement': 'INSIDE',
    'label_color': (0.8713645935058594, 0.672469973564148, 0.11010005325078964, 0.8999999761581421),
    'btn_color': (0.0, 0.0, 0.0, 0.6457144021987915),
    'bg_color': (0.32777780294418335, 0.32777780294418335, 0.32777780294418335, 0.5685714483261108),
    'separator_color': (1.0, 1.0, 1.0, 1.0),
}

# 12 buttons, in 3 thematic groups of 4 -- separators land at index 4 and 9,
# splitting exactly on the group boundaries.
BUTTONS = [
    ('Cube', 'MESH_CUBE.png', 'bpy.ops.mesh.primitive_cube_add()'),
    ('Sphere', 'MESH_UVSPHERE.png', 'bpy.ops.mesh.primitive_uv_sphere_add()'),
    ('Cylinder', 'MESH_CYLINDER.png', 'bpy.ops.mesh.primitive_cylinder_add()'),
    ('Cone', 'MESH_CONE.png', 'bpy.ops.mesh.primitive_cone_add()'),
    ('Camera', 'OUTLINER_OB_CAMERA.png', 'bpy.ops.object.camera_add()'),
    ('Sun', 'LIGHT_SUN.png', "bpy.ops.object.light_add(type='SUN')"),
    ('Point Light', 'LIGHT_POINT.png', "bpy.ops.object.light_add(type='POINT')"),
    ('Force Field', 'OUTLINER_OB_FORCE_FIELD.png', 'bpy.ops.object.effector_add()'),
    ('Mirror', 'MOD_MIRROR.png', "bpy.ops.object.modifier_add(type='MIRROR')"),
    ('Subsurf', 'MOD_SUBSURF.png', "bpy.ops.object.modifier_add(type='SUBSURF')"),
    ('Wave', 'MOD_WAVE.png', "bpy.ops.object.modifier_add(type='WAVE')"),
    ('Particles', 'PARTICLES.png', "bpy.ops.object.modifier_add(type='PARTICLE_SYSTEM')"),
]
SEPARATOR_POSITIONS = (4, 9)  # insert-and-move targets, in the order they're placed

HORIZ_LABEL_SEQ = ['ABOVE', 'INSIDE', 'BELOW', 'INSIDE']
VERT_LABEL_SEQ = ['LEFT', 'INSIDE', 'RIGHT', 'INSIDE']

# 5 variations (hue + alpha both vary) then a revert to ORIG's own scheme.
PALETTES = [
    {'label_color': (0.15, 0.95, 0.90, 1.0), 'btn_color': (0.02, 0.10, 0.10, 0.55),
     'bg_color': (0.05, 0.18, 0.18, 0.35), 'separator_color': (0.15, 0.95, 0.90, 0.6)},
    {'label_color': (1.0, 0.25, 0.55, 1.0), 'btn_color': (0.12, 0.02, 0.08, 0.85),
     'bg_color': (0.20, 0.05, 0.12, 0.55), 'separator_color': (1.0, 0.25, 0.55, 0.5)},
    {'label_color': (0.65, 0.45, 1.0, 0.85), 'btn_color': (0.10, 0.06, 0.18, 0.4),
     'bg_color': (0.14, 0.10, 0.24, 0.25), 'separator_color': (0.65, 0.45, 1.0, 0.35)},
    {'label_color': (0.70, 1.0, 0.20, 1.0), 'btn_color': (0.04, 0.10, 0.02, 0.65),
     'bg_color': (0.10, 0.20, 0.05, 0.45), 'separator_color': (0.70, 1.0, 0.20, 0.45)},
    {'label_color': (1.0, 0.60, 0.10, 1.0), 'btn_color': (0.14, 0.06, 0.0, 0.9),
     'bg_color': (0.24, 0.13, 0.02, 0.65), 'separator_color': (1.0, 0.60, 0.10, 0.6)},
    {'label_color': ORIG['label_color'], 'btn_color': ORIG['btn_color'],
     'bg_color': ORIG['bg_color'], 'separator_color': ORIG['separator_color']},
]

REMOVE_TO_COUNT = 4  # keep only the first N items when the teardown phase runs

# smooth shelf_scale pulse -- total leg duration is locked to whole beats
# (so the peak and the return-to-baseline land on-beat) even though the
# motion itself is a smooth many-substep tween, not a stepped one.
SCALE_LO, SCALE_HI = 1.2, 1.4
SCALE_BEATS = 2
SCALE_SUBSTEPS = 20

# "screensaver" diamond bounce of the panel's own position, sized off the
# shelf's REAL geometry (not the viewport) -- see _panel_size below.
VP_W = 2115  # live viewport region width; recapture per docstring if it changed
BOUNCE_BUTTON_COUNT = REMOVE_TO_COUNT  # panel size is measured at this many buttons
LEFT_WIDTH_MULT = 2.2   # how many panel-widths either side of center the left/right points sit
TOP_HEIGHT_MULT = 1.6   # how many panel-heights below the start the bottom point sits
BOUNCE_BEATS = 2
BOUNCE_SUBSTEPS = 24

# ============================ END CONFIG ====================================

PANEL_W, PANEL_H = mod._panel_size(BOUNCE_BUTTON_COUNT, True)
LEFT_DELTA = (PANEL_W * LEFT_WIDTH_MULT) / VP_W
TOP_DELTA = PANEL_H * TOP_HEIGHT_MULT
START_TOP, START_LEFT = ORIG['top_margin'], ORIG['left_margin_pct']
WAYPOINTS = [
    (START_TOP + TOP_DELTA * 0.5, START_LEFT - LEFT_DELTA),  # left, mid-height
    (START_TOP + TOP_DELTA, START_LEFT),                     # bottom, center
    (START_TOP + TOP_DELTA * 0.5, START_LEFT + LEFT_DELTA),  # right, mid-height
    (START_TOP, START_LEFT),                                 # back to start
]
BOUNCE_DT = (BOUNCE_BEATS * BEAT8) / BOUNCE_SUBSTEPS
SCALE_DT = (SCALE_BEATS * BEAT8) / SCALE_SUBSTEPS
SCALE_DELTA = (SCALE_HI - SCALE_LO) / SCALE_SUBSTEPS

# --- reset to a clean, known starting state ---
mod._loading_config = True
try:
    prefs.buttons.clear()
finally:
    mod._loading_config = False
prefs.orientation = ORIG['orientation']
prefs.label_placement = ORIG['label_placement']
prefs.shelf_scale = ORIG['shelf_scale']
prefs.top_margin = ORIG['top_margin']
prefs.left_margin_pct = ORIG['left_margin_pct']
prefs.label_color = ORIG['label_color']
prefs.btn_color = ORIG['btn_color']
prefs.bg_color = ORIG['bg_color']
prefs.separator_color = ORIG['separator_color']
prefs.active_index = 0
mod._save_prefs()

state = {'phase': 'hold', 'i': 0}


def _remove_bottom_any():
    if len(prefs.buttons) <= REMOVE_TO_COUNT:
        return False
    prefs.buttons.remove(len(prefs.buttons) - 1)
    mod._tag_viewports_redraw()
    return True


def _step():
    # Loops through pure bookkeeping transitions (no visible change) without
    # consuming a beat -- only returns once a phase performs a real, visible
    # mutation, so no phase boundary ever eats a silent "dead" tick.
    while True:
        ph = state['phase']

        if ph == 'hold':
            state['phase'] = 'fill'
            state['i'] = 0
            continue

        if ph == 'fill':
            i = state['i']
            if i >= len(BUTTONS):
                state['phase'] = 'sep'
                state['i'] = 0
                continue
            label, icon, cmd = BUTTONS[i]
            item = prefs.buttons.add()
            item.label = label
            item.icon_path = os.path.join(ICON, icon)
            item.command = cmd
            item.enabled = True
            prefs.active_index = len(prefs.buttons) - 1
            state['i'] += 1
            return BEAT8

        if ph == 'sep':
            i = state['i']
            if i >= len(SEPARATOR_POSITIONS):
                state['phase'] = 'horiz_label_cycle'
                state['i'] = 0
                continue
            item = prefs.buttons.add()
            item.label = "Separator"
            item.is_separator = True
            item.enabled = True
            prefs.buttons.move(len(prefs.buttons) - 1, SEPARATOR_POSITIONS[i])
            prefs.active_index = SEPARATOR_POSITIONS[i]
            state['i'] += 1
            return BEAT8

        if ph == 'horiz_label_cycle':
            i = state['i']
            if i >= len(HORIZ_LABEL_SEQ):
                state['phase'] = 'rotate'
                continue
            prefs.label_placement = HORIZ_LABEL_SEQ[i]
            state['i'] += 1
            return BEAT8

        if ph == 'rotate':
            prefs.orientation = 'VERTICAL'
            state['phase'] = 'vert_label_cycle'
            state['i'] = 0
            return BEAT8

        if ph == 'vert_label_cycle':
            i = state['i']
            if i >= len(VERT_LABEL_SEQ):
                state['phase'] = 'color_cycle'
                state['i'] = 0
                continue
            prefs.label_placement = VERT_LABEL_SEQ[i]
            state['i'] += 1
            return BEAT8

        if ph == 'color_cycle':
            i = state['i']
            if i >= len(PALETTES):
                state['phase'] = 'remove_all'
                continue
            pal = PALETTES[i]
            prefs.label_color = pal['label_color']
            prefs.btn_color = pal['btn_color']
            prefs.bg_color = pal['bg_color']
            prefs.separator_color = pal['separator_color']
            state['i'] += 1
            return BEAT8

        if ph == 'remove_all':
            if not _remove_bottom_any():
                state['phase'] = 'scale_up'
                state['i'] = 0
                continue
            return BEAT8

        if ph == 'scale_up':
            i = state['i']
            if i >= SCALE_SUBSTEPS:
                prefs.shelf_scale = SCALE_HI
                state['phase'] = 'scale_down'
                state['i'] = 0
                return SCALE_DT
            prefs.shelf_scale = SCALE_LO + SCALE_DELTA * i
            state['i'] += 1
            return SCALE_DT

        if ph == 'scale_down':
            i = state['i']
            if i >= SCALE_SUBSTEPS:
                prefs.shelf_scale = SCALE_LO
                state['phase'] = 'bounce_setup'
                return SCALE_DT
            prefs.shelf_scale = SCALE_HI - SCALE_DELTA * i
            state['i'] += 1
            return SCALE_DT

        if ph == 'bounce_setup':
            state['leg'] = 0
            state['sub'] = 0
            state['from'] = (START_TOP, START_LEFT)
            state['phase'] = 'bounce_leg'
            continue

        if ph == 'bounce_leg':
            leg = state['leg']
            if leg >= len(WAYPOINTS):
                print("full storyboard sequence done")
                return None
            sub = state['sub']
            frm = state['from']
            to = WAYPOINTS[leg]
            if sub >= BOUNCE_SUBSTEPS:
                prefs.top_margin = round(to[0])
                prefs.left_margin_pct = to[1]
                state['from'] = to
                state['leg'] += 1
                state['sub'] = 0
                return BOUNCE_DT
            t = sub / BOUNCE_SUBSTEPS
            prefs.top_margin = round(frm[0] + (to[0] - frm[0]) * t)
            prefs.left_margin_pct = frm[1] + (to[1] - frm[1]) * t
            state['sub'] += 1
            return BOUNCE_DT

        return None


mod._demo_step = _step  # module attribute so a later script could unregister/inspect it
bpy.app.timers.register(_step, first_interval=HOLD_SECONDS)
print("armed: BlenderShelf promo storyboard at %d BPM" % int(BPM))
