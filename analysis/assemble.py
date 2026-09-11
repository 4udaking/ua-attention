"""Збирає дані сторінки зіставлення: analysis/out/page_data.json.
Бере готові telegram.json і search_vs_read.json, дораховує мову, категорії тижня й панель."""
import collections, datetime as dt, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
D, OUT = ROOT / "data", ROOT / "analysis" / "out"
sys.path.insert(0, str(ROOT))
from lib import kyiv_now
UK, RU = set("іїєґ"), set("ыэъё")
CATS = {1: "Авто", 2: "Краса і мода", 3: "Бізнес і фінанси", 4: "Розваги", 5: "Їжа і напої", 6: "Ігри",
        7: "Здоров'я", 8: "Хобі і дозвілля", 9: "Робота і освіта", 10: "Право і держава", 11: "Інше",
        13: "Тварини", 14: "Політика", 15: "Наука", 16: "Покупки", 17: "Спорт", 18: "Технології",
        19: "Подорожі і транспорт", 20: "Клімат"}


def script(s):
    s = s.lower()
    return "uk" if set(s) & UK else "ru" if set(s) & RU else "?"


# ---- мова: тренди Google (архів + живий) проти Вікіпедії, яку читають з України ----
g = collections.defaultdict(collections.Counter)
for l in open(D / "archive" / "googletrendarchive_UA.ndjson", encoding="utf-8"):
    r = json.loads(l)
    g[r["start_time"][:7]][script(r["trend_breakdown"] or r["trends"])] += 1
live = {}
for p in sorted((D / "trending").glob("*.ndjson")):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l); live[r["key"]] = r
for r in live.values():
    m = dt.datetime.utcfromtimestamp(r["start"]).strftime("%Y-%m")
    g[m][script(" ".join(r["queries"]) + " " + r["title"])] += 1
SKIP = re.compile(r"(Заглавная_страница|Головна_сторінка|Main_Page|^Служебная:|^Спеціальна:|^Special:|^Especial:|^Speciale:|^Đặc_biệt:|:)")
w = collections.defaultdict(collections.Counter)
for p in sorted((D / "wiki" / "country_UA").glob("*.json")):
    for proj, art, v in json.loads(p.read_text(encoding="utf-8")):
        if proj in ("uk", "ru") and not SKIP.search(art):
            w[p.stem[:7]][proj] += v
lang = []
for m in sorted(set(g) | set(w)):
    gu, gr = g[m]["uk"], g[m]["ru"]
    wu, wr = w[m]["uk"], w[m]["ru"]
    lang.append({"m": m, "g_ru": round(gr / (gu + gr), 3) if gu + gr >= 50 else None, "g_n": gu + gr, "g_und": g[m]["?"],
                 "w_ru": round(wr / (wu + wr), 3) if wu + wr >= 1000 else None, "w_n": wu + wr})

# ---- категорії тижня (лише живий ряд) ----
cat_n, cat_v = collections.Counter(), collections.Counter()
t_last = max(r["start"] for r in live.values())
week_eps = [r for r in live.values() if r["start"] > t_last - 7 * 86400]  # ковзний тиждень
starts = [r["start"] for r in week_eps]
for r in week_eps:
    for c in (r["cats"] or [11]):
        cat_n[c] += 1
        cat_v[c] += r["vol"]
top_by_cat = collections.defaultdict(list)
for r in sorted(week_eps, key=lambda r: -r["vol"]):
    for c in (r["cats"] or [11]):
        if len(top_by_cat[c]) < 4:
            top_by_cat[c].append(r["title"])
cats = [{"id": c, "name": CATS.get(c, str(c)), "n": cat_n[c], "vol": cat_v[c], "top": top_by_cat[c]} for c in cat_n]
cats.sort(key=lambda x: -x["vol"])
week = [dt.datetime.utcfromtimestamp(min(starts)).strftime("%Y-%m-%d"), dt.datetime.utcfromtimestamp(max(starts)).strftime("%Y-%m-%d")]

# ---- панель: остання повна знімка, частка від YouTube, поденно ----
cfg = json.loads((ROOT / "panel.json").read_text(encoding="utf-8"))
lab = {t["id"]: t["label"] for t in cfg["terms"]}
lab["монобанк"] = "Монобанк"; lab["/g/11ghn_v832"] = "Монобанк (стара тема)"
snap = sorted((D / "panel").glob("*.json"))[-1]
pd = json.loads(snap.read_text(encoding="utf-8"))
panel = {}
for k, rows in pd["batches"].items():
    ids = k.split(",")
    for j, i in enumerate(ids[1:], 1):
        if i == "/g/11ghn_v832":
            continue  # хибна тема, лише нулі
        panel[lab.get(i, i)] = [[dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), round(v[j] / v[0], 3) if v[0] else None, part]
                                for t, v, part in rows]

# ---- «Вчора»: що росте в топі тижня і хто з платформ відхилився від звичного ----
tops = sorted((D / "explore_top").glob("*.json"))
et = json.loads(tops[-1].read_text(encoding="utf-8")) if tops else {}
rising = {name: [[q, fv] for q, v, fv in et.get(f"{c}|now 7-d", {}).get("rising", [])[:10]]
          for c, name in (("0", "Усе"), ("16", "Новини"))}
movers = []
for k, s in panel.items():
    f = [r for r in s if not r[2] and r[1] is not None]
    if len(f) < 30:
        continue
    # тижневий цикл сильний — база: медіана тих самих днів тижня за 4 попередні тижні
    prev = sorted(f[-1 - 7 * w][1] for w in range(1, 5))
    med = (prev[1] + prev[2]) / 2
    if med > 0:
        movers.append({"k": k, "day": f[-1][0], "v": f[-1][1], "lift": round(f[-1][1] / med, 2)})
movers.sort(key=lambda m: -m["lift"])

page = {
    "built": kyiv_now().strftime("%Y-%m-%d %H:%M"),  # київський: хмара живе в UTC
    "telegram": json.loads((OUT / "telegram.json").read_text()),
    "svr": json.loads((OUT / "search_vs_read.json").read_text()),
    "lang": lang, "cats": cats, "week": week,
    "panel": panel, "panel_snapshot": snap.stem,
    "top_snapshot": tops[-1].stem if tops else None, "rising": rising, "movers": movers,
}
page["svr"].pop("_sample_matches", None)
(OUT / "page_data.json").write_text(json.dumps(page, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("мова:"); [print(" ", x) for x in lang]
print("категорії", week, [(c["name"], c["n"], c["vol"]) for c in cats])
print("панель", snap.stem, list(panel))
print("розмір", (OUT / "page_data.json").stat().st_size)
