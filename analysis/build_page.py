"""analysis/page_template.html + out/page_data.json → analysis/index.html"""
import json, pathlib
A = pathlib.Path(__file__).resolve().parent
tpl = (A / "page_template.html").read_text(encoding="utf-8")
data = (A / "out" / "page_data.json").read_text(encoding="utf-8")
assert "/*__DATA__*/null" in tpl
html = tpl.replace("/*__DATA__*/null", data)
(A / "index.html").write_text(html, encoding="utf-8")
# для GitHub Pages: повний документ (артефакт додає обгортку сам, Pages — ні)
site = A.parent / "site"
site.mkdir(exist_ok=True)
(site / "index.html").write_text('<!doctype html><html lang="uk"><head><meta charset="utf-8">\n' + html.replace("</style>", "</style>\n</head><body>", 1) + "\n</body></html>", encoding="utf-8")
print("index.html", (A / "index.html").stat().st_size, "байт; site/index.html готовий")
