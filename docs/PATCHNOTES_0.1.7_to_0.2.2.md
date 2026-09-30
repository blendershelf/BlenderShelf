# BlenderShelf — patch notes 0.1.7 → 0.2.2

For the extensions.blender.org review. Package: `blender_shelf-0.2.2.zip`. Minimum Blender 4.2.0.

## New
- **Contextual shelves.** Each editor has its own shelf: Object, Edit, Sculpt, UV, Shader and Geometry Nodes. Every shelf has its own buttons, its own Shelf/Pie mode and its own pie hotkey.
- **UV and node editors.** The shelf now draws in the UV and node editors, not only the 3D Viewport. The modal finds the area under the cursor.
- **Pie menu follows the context.** The pie shows the buttons of the current context's shelf. The separate "Pie Menu" page and the "Split pie" mode are gone.
- **Add to Shelf** asks which context's shelf the button goes to.
- **Position.** Each context keeps its own shelf position. Edit and Sculpt can share the Object shelf position. Position settings sit in a collapsed panel with a single Reset button.
- **Icons.** New icons for common UV tools (Unwrap, Pack, Stitch, Gridify, Straighten, Export Layout, ...) and sculpt brushes (Draw, Clay Strips, Grab, Smooth, Inflate, ...).
- **Label placement per orientation (0.2.2).** The label position (above / below / left / right / inside) is stored separately for the horizontal and vertical layouts. Switching layout switches the label position with it. Configs without the new field use the horizontal value for both.

## Fixed
- Buttons that run operators opening a file dialog (for example Export UV Layout) now work: shelf buttons invoke such operators instead of executing them without user interaction.

## Compatibility
- Settings from 0.1.x are **not** migrated. The shelf starts with the stock buttons and default colors.
- No new permissions. The add-on still only checks blendershelf.github.io for the latest version number (`network` permission is declared in the manifest).
- No new dependencies and no bundled binaries beyond PNG icons.
