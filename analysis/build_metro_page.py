"""analysis/metro_template.html + data/metro/stations.json → analysis/metro.html, site/metro.html"""
import json, pathlib, sys
A = pathlib.Path(__file__).resolve().parent
src = A.parent / "data" / "metro" / "stations.json"
if not src.exists():
    print(f"немає {src} — спершу python3 collect_metro.py", file=sys.stderr)
    sys.exit(1)
tpl = (A / "metro_template.html").read_text(encoding="utf-8")
data = src.read_text(encoding="utf-8")
assert "/*__DATA__*/null" in tpl
html = tpl.replace("/*__DATA__*/null", data)
(A / "metro.html").write_text(html, encoding="utf-8")
# для GitHub Pages: повний документ (артефакт додає обгортку сам, Pages — ні)
site = A.parent / "site"
site.mkdir(exist_ok=True)
(site / "metro.html").write_text('<!doctype html><html lang="uk"><head><meta charset="utf-8">\n'
                                 + html.replace("</style>", "</style>\n</head><body>", 1)
                                 + "\n</body></html>", encoding="utf-8")
print("metro.html", (A / "metro.html").stat().st_size, "байт; site/metro.html готовий")
