"""Builds the EasyShelf site (easyshelf/site/) from the BlenderShelf site (site/): same pages and look, no "BlenderShelf"
anywhere in text, URLs, file names or the release asset name -- the Extensions listing links to this site, and the
extensions.blender.org ToS forbid "Blender" in an extension's name.

  python easyshelf/build_site.py --owner <github-user-or-org> [--repo EasyShelf]
  -> easyshelf/site/   (publish as the root of GitHub Pages of <owner>/<repo>; URL https://<owner>.github.io/<repo>/)

What differs from the BlenderShelf site (all flagged in easyshelf/docs/site-todo.md):
  * brand text, logo/favicon ("E" badge from easyshelf/logo), lang storage key
  * download -> <owner>/<repo> releases, asset EasyShelf.zip (upload the extension zip under that name)
  * video guide + PDF guides removed (they show the old name) -- bring back once re-made
  * feedback form kept; it still posts to the existing Cloudflare Worker (WORKER_HOST), which files issues into the old repo
    (the Worker must allow this site's origin -- see worker/src/index.js ALLOWED_ORIGINS, deployed by the owner with wrangler)
  * GoatCounter snippet removed (the existing counter is named blendershelf)
"""
import argparse
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent / "site"
OUT = HERE / "site"
OLD_PAGES = "https://blendershelf.github.io/BlenderShelf/"
OLD_REPO = "https://github.com/blendershelf/BlenderShelf"
WORKER_HOST = "blendershelf-feedback.denis-ghome.workers.dev"   # deliberately kept: reports go through the old handler for now


def sub_once(text, pattern, repl, flags=re.S):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    assert n == 1, f"pattern not found: {pattern[:60]}"
    return new


def rebrand(text, pages, repo_url):
    text = text.replace(OLD_PAGES, pages).replace(OLD_REPO, repo_url)
    text = text.replace("BlenderShelf.zip", "EasyShelf.zip")
    text = text.replace("blendershelf-icon-", "easyshelf-icon-").replace("blendershelf-lang", "easyshelf-lang")
    text = text.replace('Blender<span class="brand-accent">Shelf</span>', 'Easy<span class="brand-accent">Shelf</span>')   # header wordmark is split by a tag
    return text.replace("BlenderShelf", "EasyShelf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", default="EasyShelf")
    a = ap.parse_args()
    pages = f"https://{a.owner}.github.io/{a.repo}/"
    repo_url = f"https://github.com/{a.owner}/{a.repo}"

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("guide", "blendershelf-icon-*", "favicon.ico"))
    logo_dir = OUT / "assets" / "logo"
    logo_dir.mkdir(parents=True, exist_ok=True)
    for f in (HERE / "logo").iterdir():
        shutil.copy(f, logo_dir / f.name)

    html = (SRC / "index.html").read_text(encoding="utf-8")
    html = sub_once(html, r'\s*<section id="guide".*?</section>\n', "\n")            # video guide + PDF
    html = sub_once(html, r'<script data-goatcounter=[^>]*></script>\n', "")           # old analytics counter
    html = rebrand(html, pages, repo_url)
    assert "blendershelf" not in html.lower() and not re.search(r"Blender\W*(<[^>]+>\s*)*Shelf", html), "old name left in index.html"
    (OUT / "index.html").write_text(html, encoding="utf-8", newline="\n")

    js = rebrand((SRC / "assets" / "main.js").read_text(encoding="utf-8"), pages, repo_url)
    js = js.replace("https://github.com/blendershelf/EasyShelf/releases/latest", f"{repo_url}/releases/latest")
    (OUT / "assets" / "main.js").write_text(js, encoding="utf-8", newline="\n")

    versions = [{"addon_version": "0.3.0", "blender_min": "4.2.0", "blender_max": None,
                 "url": f"{repo_url}/releases/download/v0.3.0/EasyShelf.zip"}]
    (OUT / "versions.json").write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    (OUT / "sitemap.xml").write_text(rebrand((SRC / "sitemap.xml").read_text(encoding="utf-8"), pages, repo_url), encoding="utf-8")
    (OUT / "robots.txt").write_text(rebrand((SRC / "robots.txt").read_text(encoding="utf-8"), pages, repo_url), encoding="utf-8")

    left = [str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file() and "blendershelf" in
            (p.read_text(encoding="utf-8", errors="ignore").lower().replace(WORKER_HOST, "") if p.suffix in (".html", ".js", ".json", ".xml", ".txt", ".css") else "") + p.name.lower()]
    assert not left, f"old name still present in: {left}"
    print(f"EasyShelf site: {OUT}\n  url: {pages}\n  repo: {repo_url}")


if __name__ == "__main__":
    main()
