"""Telegram: чи збігаються тренди Google зі стрибками поденного рівня пошуку.
Рівень = Telegram / YouTube того самого дня (у межах одного вікна Explore — вікна не треба зшивати).
Стрибок = рівень ≥ 1,5 × медіани попередніх 28 діб."""
import json, pathlib, statistics, datetime as dt, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"
h = json.loads((D / "history" / "telegram_daily.json").read_text())
ratio = {}
for w, rows in h["windows"].items():
    for _, t, v in rows:
        day = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        if v[0] > 0 and day not in ratio:   # у перекритті беремо раннє вікно
            ratio[day] = v[1] / v[0]
days = sorted(ratio)
base = {}
for i, d in enumerate(days):
    prev = [ratio[x] for x in days[max(0, i - 28):i]]
    if len(prev) >= 20:
        base[d] = statistics.median(prev)
pat = re.compile(r"(телеграм|telegram|дуров)", re.I)
eps = []
for l in open(D / "archive" / "googletrendarchive_UA.ndjson", encoding="utf-8"):
    r = json.loads(l)
    if pat.search(r["trend_breakdown"] or r["trends"]):
        eps.append({"day": r["start_time"][:10], "title": r["trends"], "vol": int(r["search_volume_lower"]), "src": "archive"})
for p in sorted((D / "trending").glob("*.ndjson")):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if pat.search(" ".join(r["queries"]) + r["title"]):
            eps.append({"day": dt.datetime.utcfromtimestamp(r["start"]).strftime("%Y-%m-%d"), "title": r["title"], "vol": r["vol"], "src": "live"})
eps = [e for e in eps if "техник" not in e["title"] and "шабунін" not in e["title"]]  # «паша техник», «шабунін фото телеграм» — не про платформу
for e in eps:
    d = e["day"]
    e["lift"] = round(max(ratio.get(x, 0) for x in (d, (dt.date.fromisoformat(d) + dt.timedelta(1)).isoformat())) / base[d], 2) if d in base else None
spikes = [d for d in days if d in base and ratio[d] >= 1.5 * base[d]]
ep_days = {e["day"] for e in eps} | {(dt.date.fromisoformat(e["day"]) + dt.timedelta(n)).isoformat() for e in eps for n in (-1, 1)}
arch = lambda d: "2024-11-28" <= d <= "2026-05-17" or d >= "2026-09-04"
res = {"series": [[d, round(ratio[d], 4), round(base.get(d, 0), 4)] for d in days], "episodes": sorted(eps, key=lambda e: e["day"]),
       "spikes": [[d, round(ratio[d] / base[d], 2), d in ep_days, arch(d)] for d in spikes]}
(ROOT / "analysis" / "out" / "telegram.json").write_text(json.dumps(res, ensure_ascii=False))
print("діб", len(days), days[0], days[-1], "медіана рівня", round(statistics.median(ratio.values()), 3))
print("епізоди:"); [print(" ", e["day"], e["vol"], e["title"], "підйом", e["lift"]) for e in res["episodes"]]
print("стрибки ≥1,5×:"); [print(" ", s) for s in res["spikes"]]
