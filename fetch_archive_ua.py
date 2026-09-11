"""Передісторія шару 1: Україна з GoogleTrendArchive (Urman, Hannák, Baumann; CC BY 4.0).

28.11.2024–17.05.2026, ~10 млн рядків світу. Беремо лише location='UA' через
datasets-server Hugging Face (фільтр по parquet), сторінками по 100.
Категорій в архіві немає — їх Google віддає лише в живому збирачі.
Вихід: data/archive/googletrendarchive_UA.ndjson (+ .done з підсумком).
"""
import json
import time
import urllib.parse
import urllib.error
from lib import DATA, fetch, WIKI_UA

BASE = "https://datasets-server.huggingface.co/filter"
Q = {"dataset": "aurman/GoogleTrendArchive", "config": "trending_queries", "split": "train",
     "where": "\"location\"='UA'", "orderby": "\"start_time\""}
out = DATA / "archive" / "googletrendarchive_UA.ndjson"
out.parent.mkdir(parents=True, exist_ok=True)


def page(offset):
    for attempt in range(40):
        try:
            d = json.loads(fetch(BASE + "?" + urllib.parse.urlencode(dict(Q, offset=offset, length=100)),
                                 ua=WIKI_UA, waits=(10, 30), timeout=120))
        except urllib.error.HTTPError as e:
            d = {"error": f"HTTP {e.code}"}
        except Exception as e:  # тайм-аут, поки сервер будує індекс
            d = {"error": f"{type(e).__name__}: {e}"}
        if "rows" in d:
            return d
        print("чекаю:", d.get("error"), flush=True)
        time.sleep(30)
    raise SystemExit("індекс так і не підготувався")


first = page(0)
total = first["num_rows_total"]
print("рядків UA:", total, flush=True)
n = 0
with open(out, "w", encoding="utf-8") as f:
    offset, d = 0, first
    while True:
        for r in d["rows"]:
            f.write(json.dumps(r["row"], ensure_ascii=False) + "\n")
            n += 1
        offset += 100
        if offset >= total:
            break
        if offset % 5000 == 0:
            print(offset, "/", total, flush=True)
        time.sleep(0.3)
        d = page(offset)
(out.with_suffix(".done")).write_text(json.dumps({"rows": n, "total": total}), encoding="utf-8")
print("готово", n, "з", total)
