"""Package the Extensions Platform (extensions.blender.org) submission zip.

Separate from build_release.py on purpose: this build's files -- most of
all blender_manifest.toml -- must NEVER end up in the legacy BlenderShelf.zip
that existing users update through, because a manifest's mere presence makes
Blender treat the folder as an Extension and, on install, wipe out an
existing legacy scripts/addons/BlenderShelf install (config included). See
the comment on EXCLUDE_NAMES in build_release.py for how that was confirmed.

Source is BlenderShelf-releases/addon/ (the repo copy), not the live
Blender addons folder -- that one deliberately never carries the manifest.

Run: python build_extension.py
Output: dist/blender_shelf-<version>.zip -- upload this one to
extensions.blender.org, never BlenderShelf.zip.
"""
import os
import shutil
import tomllib
import zipfile

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_SRC = os.path.join(REPO_DIR, "addon")
OUT_DIR = os.path.join(REPO_DIR, "dist")

# Extension zips are flat: manifest + __init__.py + assets sit at the zip
# root, with no wrapping folder (unlike the legacy install zip).
EXCLUDE_NAMES = {"__pycache__", "shelf_config.json", "backups"}


def _ignore(_dir, names):
    return [n for n in names if n in EXCLUDE_NAMES or n.endswith(".pyc")]


def main():
    manifest_path = os.path.join(ADDON_SRC, "blender_manifest.toml")
    if not os.path.isfile(manifest_path):
        raise SystemExit(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "rb") as f:
        manifest = tomllib.load(f)

    zip_name = f"{manifest['id']}-{manifest['version']}.zip"
    zip_path = os.path.join(OUT_DIR, zip_name)

    stage_dir = os.path.join(OUT_DIR, "_extension_stage")
    shutil.rmtree(stage_dir, ignore_errors=True)
    shutil.copytree(ADDON_SRC, stage_dir, ignore=_ignore)

    os.makedirs(OUT_DIR, exist_ok=True)
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
