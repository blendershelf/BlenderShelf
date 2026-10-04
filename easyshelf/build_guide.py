"""Builds the EasyShelf PDF guides (RU + EN) from the BlenderShelf guide sources in guide/: same text, same screenshots,
the name BlenderShelf replaced by EasyShelf everywhere it appears in the text (title, header strip, footer, captions, PDF author).
Images are NOT changed (the pie-menu screenshot still carries the old name -- accepted by the owner).

  python easyshelf/build_guide.py   ->  easyshelf/guide/EasyShelf_Guide_RU.pdf, EasyShelf_Guide_EN.pdf
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
GUIDE = HERE.parent / "guide"
sys.path.insert(0, str(GUIDE))
import build_guide  # noqa: E402  (guide/build_guide.py)


def rebrand(node):
    if isinstance(node, str):
        return node.replace("BlenderShelf", "EasyShelf")
    if isinstance(node, list):
        return [rebrand(x) for x in node]
    if isinstance(node, dict):
        return {k: rebrand(v) for k, v in node.items()}
    return node


def main():
    out_dir = HERE / "guide"
    out_dir.mkdir(exist_ok=True)
    for lang in ("ru", "en"):
        content = rebrand(json.loads((GUIDE / f"content_{lang}.json").read_text(encoding="utf-8")))
        content["brand"] = "EasyShelf"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8", dir=GUIDE) as f:
            json.dump(content, f, ensure_ascii=False)
            tmp = Path(f.name)
        try:
            # screenshots/ are resolved relative to the content file, so the temp file sits next to the originals
            build_guide.build(str(tmp), str(out_dir / f"EasyShelf_Guide_{lang.upper()}.pdf"))
        finally:
            tmp.unlink()


if __name__ == "__main__":
    main()
