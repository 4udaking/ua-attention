"""Зіставлення шарів для сторінки. Вихід: analysis/out/compare.json.

Пошук (тренди Google) проти читання (топ-1000 uk.wikipedia) на спільному відрізку
28.11.2024–17.05.2026 (архів) + живий ряд.
  Сплеск читання: стаття в топ-100 доби, а за попередні 7 діб у топ-1000 була щонайбільше раз.
  Збіг: токени назви статті (без по батькові й уточнень у дужках) усі є в одному з запитів
  тренду, стартом у межах доби до/після. Порівнюємо основи слів (перші n−2 літер, мін. 4),
  щоб «навроцького» ловило «навроцький».
Мова: сценарій запиту — укр (і ї є ґ), рос (ы э ъ ё), інакше невизначено.
"""
import collections
import datetime as dt
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = ROOT / "analysis" / "out"
OUT.mkdir(parents=True, exist_ok=True)

UK, RU = set("іїєґ"), set("ыэъё")
PATRON = re.compile(r"(ович|евич|йович|івна|ївна|овна|ич)$")
STOP = {"україна", "україни", "київ", "список", "року", "рік", "день"}


def script(s):
    s = s.lower()
    if set(s) & UK:
        return "uk"
    if set(s) & RU:
        return "ru"
    return "?"


def norm(s):
    s = s.lower().replace("_", " ").replace("’", "'").replace("ʼ", "'").replace("ё", "е")
    return re.sub(r"\s*\(.*?\)", "", s).strip()


def toks(s):
    return [t for t in re.findall(r"[a-zа-яіїєґ0-9']+", norm(s)) if len(t) >= 3 or t.isdigit()]


def stem(t):
    return t[:max(4, len(t) - 2)] if len(t) > 4 and not t.isdigit() else t


def article_key(title):
    t = toks(title)
    if len(t) == 3 and PATRON.search(t[2]):
        t = t[:2]
    return [stem(x) for x in t if x not in STOP]


# ---------- тренди ----------
trends = []
for l in open(D / "archive" / "googletrendarchive_UA.ndjson", encoding="utf-8"):
    r = json.loads(l)
    trends.append({"src": "archive", "title": r["trends"], "start": r["start_time"][:16],
                   "day": r["start_time"][:10], "vol": int(r["search_volume_lower"]),
                   "queries": [q.strip() for q in (r["trend_breakdown"] or r["trends"]).split(",")], "cats": None})
live_first = None
seen = {}
for p in sorted((D / "trending").glob("*.ndjson")):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        seen[r["key"]] = r  # остання версія епізоду
for r in seen.values():
    day = dt.datetime.utcfromtimestamp(r["start"]).strftime("%Y-%m-%d")
    trends.append({"src": "live", "title": r["title"], "start": dt.datetime.utcfromtimestamp(r["start"]).strftime("%Y-%m-%dT%H:%M"),
                   "day": day, "vol": r["vol"], "queries": r["queries"] or [r["title"]], "cats": r["cats"]})
    live_first = min(live_first or day, day)
for t in trends:
    t["script"] = script(" ".join(t["queries"]))
    t["qtoks"] = [set(toks(q)) for q in t["queries"]]  # слова запиту цілі: обрізана основа «укрнет» → «укрн» ловила «Укрнафту»

print("тренди", len(trends), flush=True)
# ---------- Вікіпедія ----------
wiki = {}
for p in sorted((D / "wiki" / "uk").glob("*.json")):
    rows = json.loads(p.read_text(encoding="utf-8"))
    wiki[p.stem] = [(a, v) for a, v in rows if ":" not in a and a != "Головна_сторінка"]
days = sorted(wiki)
in_top = collections.defaultdict(set)  # стаття -> доби в топ-1000
for d in days:
    for a, _ in wiki[d]:
        in_top[a].add(d)


def dshift(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


# Календарні статті («21 лютого», «2025») сплескують щодня за визначенням — це не події.
CAL = re.compile(r"^(\d{1,2}_(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)|\d{3,4}(_рік)?|.*_\d{4}_року)$")
surges = []
for d in days:
    prev = {dshift(d, -i) for i in range(1, 8)}
    if len(prev & set(days)) < 5:  # мало історії — не вирішуємо
        continue
    for rank, (a, v) in enumerate(wiki[d][:100], 1):
        if len(in_top[a] & prev) <= 1 and not CAL.match(a):
            surges.append({"day": d, "article": a, "views": v, "rank": rank, "key": article_key(a)})

print("сплесків читання", len(surges), flush=True)
# ---------- збіги ----------
by_day = collections.defaultdict(list)
for i, t in enumerate(trends):
    by_day[t["day"]].append(i)


def match(key, t):
    """Повертає сам запит із кластера тренду, у якому знайшлась назва статті (або None).
    Кластер Google буває строкатим, тож показувати треба запит, а не назву тренду."""
    if not key:
        return None
    # Слово запиту може бути довшим за основу назви (відмінок) або коротшим лише на закінчення.
    # 12.09.2026: без обмеження «укр» ловило «Укрнафту».
    ok = lambda k, q: (k == q) if k.isdigit() else (q.startswith(k) or (k.startswith(q) and len(q) >= max(4, len(k) - 3)))
    for qs, qtext in zip(t["qtoks"], t["queries"]):
        if qs and all(any(ok(k, q) for q in qs) for k in key):
            return qtext
    return None


period = (days[0], "2026-05-17")
covered = lambda d: (period[0] <= d <= period[1]) or (live_first and d >= live_first and d <= days[-1])
for s in surges:
    s["hits"] = [(i, q) for n in (-1, 0, 1) for i in by_day.get(dshift(s["day"], n), []) for q in [match(s["key"], trends[i])] if q]
    s["trends"] = [i for i, _ in s["hits"]]
matched_trends = collections.defaultdict(list)
for si, s in enumerate(surges):
    for i in s["trends"]:
        matched_trends[i].append(si)

print("збіги пораховано", flush=True)
S = [s for s in surges if covered(s["day"])]
T = [i for i, t in enumerate(trends) if covered(t["day"]) and t["day"] in wiki]

# частка трендів з відлунням у Вікіпедії — за обсягом і сценарієм
by_vol = collections.defaultdict(lambda: [0, 0])
for i in T:
    t = trends[i]
    if t["script"] == "ru":
        continue
    b = by_vol[t["vol"]]
    b[0] += 1
    b[1] += bool(matched_trends.get(i))
script_share = collections.Counter(trends[i]["script"] for i in T)

res = {
    "period": list(period), "live_from": live_first, "wiki_last": days[-1],
    "n_trends": len(T), "n_surges": len(S),
    "surges_with_trend": sum(bool(s["trends"]) for s in S),
    "trend_script": dict(script_share),
    "echo_by_volume": [[v, n, m] for v, (n, m) in sorted(by_vol.items())],
}

# приклади: у обох, лише читання, лише пошук
def tr(i):
    t = trends[i]
    return {"title": t["title"], "day": t["day"], "vol": t["vol"]}

both = sorted([s for s in S if s["trends"]], key=lambda s: -s["views"])
seen_a = set(); res["both"] = []
for s in both:
    if s["article"] in seen_a:
        continue
    seen_a.add(s["article"])
    bi, bq = max(s["hits"], key=lambda h: trends[h[0]]["vol"])
    res["both"].append({"article": s["article"].replace("_", " "), "day": s["day"], "views": s["views"], "trend": dict(tr(bi), title=bq)})
    if len(res["both"]) == 25:
        break
only_read = sorted([s for s in S if not s["trends"]], key=lambda s: -s["views"])
seen_a = set(); res["only_read"] = []
for s in only_read:
    if s["article"] in seen_a:
        continue
    seen_a.add(s["article"])
    res["only_read"].append({"article": s["article"].replace("_", " "), "day": s["day"], "views": s["views"]})
    if len(res["only_read"]) == 25:
        break
# повторювані «утиліти» (погода, хвилина мовчання…) трендують десятки разів — окремо від подій
title_n = collections.Counter(norm(trends[i]["title"]) for i in T)
res["recurring"] = [[t, n] for t, n in title_n.most_common(15) if n >= 10]
rec = {t for t, n in title_n.items() if n >= 10}  # відсіваємо всі повторювані, а не лише показані
only_search = sorted([i for i in T if not matched_trends.get(i) and trends[i]["script"] != "ru" and norm(trends[i]["title"]) not in rec],
                     key=lambda i: -trends[i]["vol"])
seen_t = set(); res["only_search"] = []
for i in only_search:
    k = norm(trends[i]["title"])
    if k in seen_t:
        continue
    seen_t.add(k); res["only_search"].append(tr(i))
    if len(res["only_search"]) == 25:
        break
import random
random.seed(7)
res["_sample_matches"] = [[s["day"], s["article"], [trends[i]["title"] for i in s["trends"]][:3]] for s in random.sample([s for s in S if s["trends"]], 20)]
# ---------- доба для блоку «Вчора» ----------
DAY = days[-1]
dT = sorted([i for i, t in enumerate(trends) if t["day"] == DAY], key=lambda i: -trends[i]["vol"])
seen_t = set(); day_trends = []
for i in dT:
    k = norm(trends[i]["title"])
    if k in seen_t:
        continue
    seen_t.add(k)
    day_trends.append({"title": trends[i]["title"], "vol": trends[i]["vol"], "cats": trends[i]["cats"],
                       "echo": [surges[si]["article"].replace("_", " ") for si in matched_trends.get(i, [])][:2]})
day_surges = sorted([s for s in surges if s["day"] == DAY], key=lambda s: -s["views"])
res["day"] = {"date": DAY, "n_trends": len(dT), "has_live": bool(live_first and DAY >= live_first),
              "trends": day_trends[:20],
              "surges": [{"article": s["article"].replace("_", " "), "day": DAY, "views": s["views"], "rank": s["rank"],
                          "trends": [q for _, q in s["hits"]][:2]} for s in day_surges[:20]],
              "n_surges": len(day_surges), "n_match": sum(bool(s["trends"]) for s in day_surges)}
# Автоматичний трафік: стаття, яку за добу дивляться майже лише з десктопу, — підозріла.
import time, urllib.parse, sys
sys.path.insert(0, str(ROOT))
from lib import fetch, WIKI_UA
cache_p = D / "cache" / "wiki_access.json"  # у git: хмара не перепитує вже перевірене
cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
def access(article, day):
    k = f"{article}|{day}"
    if k not in cache:
        v = {}
        for acc in ("desktop", "mobile-web", "mobile-app"):
            u = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/uk.wikipedia/%s/user/%s/daily/%s/%s"
                 % (acc, urllib.parse.quote(article.replace(" ", "_"), safe=""), day.replace("-", ""), day.replace("-", "")))
            try:
                v[acc] = json.loads(fetch(u, ua=WIKI_UA, waits=(5,), timeout=20))["items"][0]["views"]
            except Exception:
                v[acc] = 0
            time.sleep(0.1)
        cache[k] = v
    v = cache[k]; tot = sum(v.values()) or 1
    return round(v["desktop"] / tot, 3)
for lst in (res["both"], res["only_read"], res["day"]["surges"]):
    for x in lst:
        x["desktop_share"] = access(x["article"], x["day"])
cache_p.write_text(json.dumps(cache, ensure_ascii=False))
(OUT / "search_vs_read.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("both", "only_read", "only_search")}, ensure_ascii=False))
print("\nУ ОБОХ:"); [print(" ", x["day"], x["views"], x["article"], "←", x["trend"]["title"], x["trend"]["vol"]) for x in res["both"][:15]]
print("\nЛИШЕ ЧИТАННЯ:"); [print(" ", x["day"], x["views"], x["article"], "десктоп", x["desktop_share"]) for x in res["only_read"][:25]]
print("\nПОВТОРЮВАНІ:", res["recurring"])
print("\nВИБІРКА ЗБІГІВ:"); [print(" ", x) for x in res["_sample_matches"]]
print("\nЛИШЕ ПОШУК:"); [print(" ", x["day"], x["vol"], x["title"]) for x in res["only_search"][:15]]
