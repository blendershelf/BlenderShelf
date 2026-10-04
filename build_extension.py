"""Package the Extensions Platform (extensions.blender.org) submission zip.

Separate from build_release.py on purpose: this build's files -- most of
all blender_manifest.toml -- must NEVER end up in the legacy BlenderShelf.zip
that existing users update through, because a manifest's mere presence makes
Blender treat the folder as an Extension and, on install, wipe out an
existing legacy scripts/addons/BlenderShelf install (config included). See
the comment on EXCLUDE_NAMES in build_release.py for how that was confirmed.

Source is BlenderShelf-releases/addon/ (the repo copy), not the live
Blender addons folder -- that one deliberately never carries the manifest.

Run: python build_extension.py                      -> dist/blender_shelf-<version>.zip (legacy-named build)
     python build_extension.py --edition easyshelf  -> easyshelf/dist/easy_shelf-<version>.zip (the one for extensions.blender.org)

The extensions.blender.org ToS forbid "Blender" in an extension's name, tampering with Blender
internals / other add-ons, and promoting updates from inside Blender's UI. So the easyshelf
edition is the same source with: everything between `# EDITION-STRIP begin/end` (update checker,
FBX-exporter patch) and lines tagged `# EDITION-STRIP-LINE` removed, names rewritten
(BlenderShelf -> EasyShelf; lines tagged `# EDITION-KEEP` are left alone), no network permission,
and a first-run import of the user's BlenderShelf settings.
"""
import argparse
import os
import re
import shutil
import tomllib
import zipfile

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_SRC = os.path.join(REPO_DIR, "addon")
OUT_DIR = os.path.join(REPO_DIR, "dist")

# Extension zips are flat: manifest + __init__.py + assets sit at the zip
# root, with no wrapping folder (unlike the legacy install zip).
EXCLUDE_NAMES = {"__pycache__", "shelf_config.json", "backups"}

EASY_MANIFEST = '''schema_version = "1.0.0"

id = "easy_shelf"
version = "{version}"
name = "EasyShelf"
tagline = "Customizable quick-access button shelf for any workflow"
maintainer = "DenisZakharov"
type = "add-on"

website = "https://easyshelf-addon.github.io/EasyShelf/"

tags = ["3D View", "User Interface"]

license = [
  "SPDX:GPL-3.0-or-later",
]

blender_version_min = "4.2.0"

[permissions]
files = "Export and import settings and scripts"
'''

URL_MASK = ("blendershelf.github.io/BlenderShelf", "\0SITEURL\0")


def _ignore(_dir, names):
    return [n for n in names if n in EXCLUDE_NAMES or n.endswith(".pyc")]


def to_easyshelf(src, version):
    """Source text of the legacy-named add-on -> the Extensions Platform edition."""
    # the manual: extensions drop bl_info (the manifest replaces it); only ADDON_VERSION read it
    src = re.sub(r"^bl_info = \{.*?^\}\n", "", src, count=1, flags=re.S | re.M)
    src = src.replace('ADDON_VERSION = tuple(bl_info["version"])', f"ADDON_VERSION = {tuple(int(x) for x in version.split('.'))}", 1)
    src = re.sub(r"[ \t]*# EDITION-STRIP begin\n.*?[ \t]*# EDITION-STRIP end\n", "", src, flags=re.S)
    src = "".join(l for l in src.splitlines(keepends=True) if "EDITION-STRIP-LINE" not in l)
    src = src.replace('EDITION = "blendershelf"', 'EDITION = "easyshelf"', 1)
    out = []
    for line in src.splitlines(keepends=True):
        if "EDITION-KEEP" not in line:
            line = line.replace(*URL_MASK)
            line = line.replace("BLENDERSHELF_", "EASYSHELF_").replace("BlenderShelf", "EasyShelf")
            line = line.replace("blender_shelf", "easy_shelf")
            line = re.sub(r"blendershelf", "easyshelf", line)
            line = line.replace(URL_MASK[1], URL_MASK[0])
        out.append(line)
    return "".join(out)


def check_easyshelf(src, manifest_text):
    """Fail the build rather than ship something the ToS would reject."""
    for bad in ("bl_info = {", "urllib", "io_scene_fbx", "check_update", "VERSIONS_JSON_URL", "boosty", "donat", "dalink"):
        assert bad not in src, f"easyshelf edition still contains {bad!r}"
    for n, line in enumerate(src.splitlines(), 1):
        if re.search(r"blender_shelf|BlenderShelf|BLENDERSHELF|blendershelf(?!\.github)", line.replace(URL_MASK[0], "")):
            assert "EDITION-KEEP" in line, f"old name left at line {n}: {line.strip()[:80]}"
    m = tomllib.loads(manifest_text)
    assert "blender" not in m["name"].lower() and "blender" not in m["id"].lower(), "ToS 2.1: no 'Blender' in the name"
    assert len(m["tagline"]) <= 64 and m["tagline"][-1] not in ".!?,;:", "tagline: <=64 chars, no end punctuation"
    for k, v in m.get("permissions", {}).items():
        assert len(v) <= 64 and not v.endswith("."), f"permission {k!r}: <=64 chars, no period"
    assert "network" not in m.get("permissions", {}), "no network permission expected in this edition"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", choices=("blendershelf", "easyshelf"), default="blendershelf")
    edition = ap.parse_args().edition
    out_dir = os.path.join(REPO_DIR, "easyshelf", "dist") if edition == "easyshelf" else OUT_DIR

    manifest_path = os.path.join(ADDON_SRC, "blender_manifest.toml")
    if not os.path.isfile(manifest_path):
        raise SystemExit(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "rb") as f:
        manifest = tomllib.load(f)

    stage_dir = os.path.join(out_dir, "_extension_stage")
    shutil.rmtree(stage_dir, ignore_errors=True)
    shutil.copytree(ADDON_SRC, stage_dir, ignore=_ignore)

    if edition == "easyshelf":
        init_path = os.path.join(stage_dir, "__init__.py")
        with open(init_path, encoding="utf-8") as f:
            src = to_easyshelf(f.read(), manifest["version"])
        manifest_text = EASY_MANIFEST.format(version=manifest["version"])
        check_easyshelf(src, manifest_text)
        with open(init_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
        with open(os.path.join(stage_dir, "blender_manifest.toml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(manifest_text)
        manifest = tomllib.loads(manifest_text)

    zip_name = f"{manifest['id']}-{manifest['version']}.zip"
    zip_path = os.path.join(out_dir, zip_name)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(stage_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, stage_dir)  # flat, no wrapping folder
                zf.write(full, rel)
    shutil.rmtree(stage_dir, ignore_errors=True)

    print(f"Extension build ready: {zip_path}")
    print(f"id={manifest['id']} version={manifest['version']}")
    print("Upload this file at https://extensions.blender.org -- "
          "never distribute it as the update path for existing users.")


if __name__ == "__main__":
    main()
