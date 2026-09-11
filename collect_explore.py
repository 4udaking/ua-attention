"""Шари 2 і 3 — обсяг: Google Trends Explore по Україні.

Шар 2 (top): найбільші й найшвидші запити тижня за категоріями. Тут живе те,
що ніколи не трендує: погода, ютуб, телеграм, олх. Шкала відносна —
перший запит категорії = 100.
Шар 3 (panel): фіксовані платформи й сервіси, поденно за 90 діб,
пачками по 5 з якорем (panel.json). Кожен запуск перезнімає все вікно,
тож ряди зшиваються через перекриття.

Explore швидко віддає 429. Тому: пауза між запитами, раз на київську добу,
а недобране того ж дня добирає наступний запуск (хмара або ноутбук).
Файли: data/explore_top/ДД.json, data/panel/ДД.json.
"""
import json
import random
import sys
import time
import urllib.parse
from lib import DATA, ROOT, fetch, kyiv_now, log, write_json, Throttled

GEO, HL, TZ = "UA", "uk", "-180"
CFG = json.loads((ROOT / "panel.json").read_text(encoding="utf-8"))


def pause():
    time.sleep(random.uniform(4, 8))


def api(path, params):
    raw = fetch(f"https://trends.google.com/trends/api/{path}?" + urllib.parse.urlencode(params))
    return json.loads(raw.split("\n", 1)[1])


def explore(items, cat, tf):
    req = {"comparisonItem": [{"keyword": k, "geo": GEO, "time": tf} for k in items],
           "category": int(cat), "property": ""}
    return api("explore", {"hl": HL, "tz": TZ, "req": json.dumps(req)})["widgets"]


def widget(w, path):
    pause()
    return api(f"widgetdata/{path}", {"hl": HL, "tz": TZ, "req": json.dumps(w["request"]), "token": w["token"]})


def collect_top(day):
    p = DATA / "explore_top" / f"{day}.json"
    have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    jobs = [(c, "now 7-d") for c in CFG["top_categories"]] + [("0", "now 1-d")]
    done = 0
    for cat, tf in jobs:
        k = f"{cat}|{tf}"
        if k in have:
            continue
        pause()
        ws = explore([""], cat, tf)
        w = next(x for x in ws if x["id"] == "RELATED_QUERIES")
        L = widget(w, "relatedsearches")["default"]["rankedList"]
        pick = lambda i: [[q["query"], q["value"], q.get("formattedValue")] for q in (L[i]["rankedKeyword"] if len(L) > i else [])]
        have[k] = {"top": pick(0), "rising": pick(1)}
        write_json(p, have)  # після кожної категорії: обрив не губить зроблене
        done += 1
    return done, len(jobs) - len(have)


def collect_panel(day):
    p = DATA / "panel" / f"{day}.json"
    have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"anchor": CFG["anchor"]["id"], "batches": {}}
    terms = CFG["terms"]
    batches = [terms[i:i + 4] for i in range(0, len(terms), 4)]
    done = 0
    for b in batches:
        ids = [CFG["anchor"]["id"]] + [t["id"] for t in b]
        k = ",".join(ids)
        if k in have["batches"]:
            continue
        pause()
        ws = explore(ids, 0, "today 3-m")
        w = next(x for x in ws if x["id"] == "TIMESERIES")
        tl = widget(w, "multiline")["default"]["timelineData"]
        have["batches"][k] = [[int(r["time"]), r["value"], bool(r.get("isPartial"))] for r in tl]
        write_json(p, have)
        done += 1
    return done, len(batches) - len(have["batches"])


def main():
    day = kyiv_now().date()
    rc = 0
    for layer, fn in (("explore_top", collect_top), ("panel", collect_panel)):
        try:
            done, left = fn(day)
            log(layer, "ok" if left == 0 else "partial", fetched=done, left=left)
        except Throttled:
            log(layer, "throttled")
            rc = 2
            break  # далі в цьому запуску все одно 429
        except Exception as e:
            log(layer, "error", error=f"{type(e).__name__}: {e}"[:300])
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
