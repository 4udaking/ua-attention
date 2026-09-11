"""analysis/page_template.html + out/page_data.json → analysis/index.html"""
import json, pathlib
A = pathlib.Path(__file__).resolve().parent
tpl = (A / "page_template.html").read_text(encoding="utf-8")
data = (A / "out" / "page_data.json").read_text(encoding="utf-8")
assert "/*__DATA__*/null" in tpl
(A / "index.html").write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")
print("index.html", (A / "index.html").stat().st_size, "байт")
