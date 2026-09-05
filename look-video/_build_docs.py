from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "look-video" / "static"
html = (src / "index.html").read_text(encoding="utf-8")
html = html.replace('href="/manifest.webmanifest"', 'href="./manifest.webmanifest"')
html = html.replace('href="/static/icon.svg"', 'href="./icon.svg"')
html = html.replace(
    "<script>\nconst API",
    '<script>window.LOOKV_API = "https://lookv.onrender.com";</script>\n<script>\nconst API',
)
man = (src / "manifest.webmanifest").read_text(encoding="utf-8")
man = man.replace('"start_url": "/"', '"start_url": "./"')
man = man.replace('"src": "/static/icon.svg"', '"src": "./icon.svg"')

for name in ("docs", "lookv"):
    dst = root / name
    dst.mkdir(exist_ok=True)
    (dst / "index.html").write_text(html, encoding="utf-8")
    (dst / "icon.svg").write_bytes((src / "icon.svg").read_bytes())
    (dst / "sw.js").write_text((src / "sw.js").read_text(encoding="utf-8"), encoding="utf-8")
    (dst / "manifest.webmanifest").write_text(man, encoding="utf-8")
    (dst / ".nojekyll").write_text("", encoding="utf-8")
    print(name, "ready")
