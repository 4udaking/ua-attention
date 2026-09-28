"""analysis/metro_template.html + data/metro/stations.json → analysis/metro.html, site/metro.html

Сторінка — ES-модуль і тягне three.js сусіднім файлом, тож vendor/ їде в site/ разом з нею.
З file:// модуль не завантажиться (CORS): дивитися через Pages або `python3 -m http.server`.
"""
import pathlib, shutil, sys
A = pathlib.Path(__file__).resolve().parent
src = A.parent / "data" / "metro" / "stations.json"
if not src.exists():
    print(f"немає {src} — спершу python3 collect_metro.py", file=sys.stderr)
    sys.exit(1)
tpl = (A / "metro_template.html").read_text(encoding="utf-8")
data = src.read_text(encoding="utf-8")
city = A.parent / "data" / "metro" / "city.json"
assert "/*__DATA__*/null" in tpl and "/*__CITY__*/null" in tpl
html = tpl.replace("/*__DATA__*/null", data)
# План міста необов'язковий: без нього сцена просто лишається без підкладки.
html = html.replace("/*__CITY__*/null", city.read_text(encoding="utf-8") if city.exists() else "null")
(A / "metro.html").write_text(html, encoding="utf-8")
# для GitHub Pages: повний документ (артефакт додає обгортку сам, Pages — ні)
site = A.parent / "site"
site.mkdir(exist_ok=True)
(site / "metro.html").write_text('<!doctype html><html lang="uk"><head><meta charset="utf-8">\n'
                                 + html.replace("</style>", "</style>\n</head><body>", 1)
                                 + "\n</body></html>", encoding="utf-8")
shutil.copytree(A / "vendor", site / "vendor", dirs_exist_ok=True)
print("metro.html", (A / "metro.html").stat().st_size, "байт; site/metro.html і site/vendor готові")
