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
from lib import DATA, ROOT, fetch, google_warmup, kyiv_now, log, reset_cookies, write_json, Throttled

GEO, HL, TZ = "UA", "uk", "-180"
CFG = json.loads((ROOT / "panel.json").read_text(encoding="utf-8"))


def pause():
    # 11.09.2026: при 4–8 с Google різав після ~14 запитів поспіль.
    time.sleep(random.uniform(12, 20))


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
        w = next((x for x in ws if x["id"] == "RELATED_QUERIES"), None)
        if w is None:  # Google не дає блоку, коли даних замало (буває для now 1-d) — фіксуємо як порожнє
            have[k] = {"top": [], "rising": [], "note": "no RELATED_QUERIES widget"}
            write_json(p, have)
            continue
        L = widget(w, "relatedsearches")["default"]["rankedList"]
        pick = lambda i: [[q["query"], q["value"], q.get("formattedValue")] for q in (L[i]["rankedKeyword"] if len(L) > i else [])]
        have[k] = {"top": pick(0), "rising": pick(1)}
        write_json(p, have)  # після кожної категорії: обрив не губить зроблене
        done += 1
    return done, sum(f"{c}|{tf}" not in have for c, tf in jobs)


def collect_panel(day):
    p = DATA / "panel" / f"{day}.json"
    have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"anchor": CFG["anchor"]["id"], "batches": {}}
    # solo — терми, що значно більші за якір: у спільній пачці вони стискають решту до цілих 0–3
    solo = [[t] for t in CFG["terms"] if t.get("solo")]
    rest = [t for t in CFG["terms"] if not t.get("solo")]
    batches = [rest[i:i + 4] for i in range(0, len(rest), 4)] + solo
    done = 0
    need = [",".join([CFG["anchor"]["id"]] + [t["id"] for t in b]) for b in batches]
    for b, k in zip(batches, need):
        ids = k.split(",")
        if k in have["batches"]:
            continue
        pause()
        ws = explore(ids, 0, "today 3-m")
        w = next(x for x in ws if x["id"] == "TIMESERIES")
        tl = widget(w, "multiline")["default"]["timelineData"]
        have["batches"][k] = [[int(r["time"]), r["value"], bool(r.get("isPartial"))] for r in tl]
        write_json(p, have)
        done += 1
    # у файлі дня можуть лежати й пачки старої конфігурації — рахуємо лише потрібні
    return done, sum(k not in have["batches"] for k in need)


def main():
    day = kyiv_now().date()
    rc = 0
    print("cookie:", google_warmup())
    retried = False
    for layer, fn in (("explore_top", collect_top), ("panel", collect_panel)):
        while True:
            try:
                done, left = fn(day)
                log(layer, "ok" if left == 0 else "partial", fetched=done, left=left)
                break
            except Throttled:
                if retried:
                    log(layer, "throttled")
                    return 2  # далі в цьому запуску все одно 429; зроблене вже на диску
                # один раз на запуск: свіжі cookie і хвилина тиші
                retried = True
                log(layer, "throttled_retry")
                reset_cookies()
                time.sleep(90)
                google_warmup()
            except Exception as e:
                log(layer, "error", error=f"{type(e).__name__}: {e}"[:300])
                rc = 1
                break
    return rc


if __name__ == "__main__":
    sys.exit(main())
