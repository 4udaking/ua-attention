"""Поденна історія пошуку Telegram (і якоря YouTube) на весь період архіву трендів.
Google дає поденні точки лише для вікон ≤ ~269 діб, тож три вікна з перекриттям 10 діб —
зшиваються через якір. Разовий збір для сторінки зіставлення, не щоденний шар."""
import json, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import DATA, google_warmup, write_json
from collect_explore import explore, widget, pause

ITEMS = ["/m/09jcvs", "/m/0zwk75g"]  # YouTube (якір), Telegram
WINDOWS = ["2024-11-20 2025-07-31", "2025-07-20 2026-03-31", "2026-03-20 2026-09-10"]
out = DATA / "history" / "telegram_daily.json"
have = json.loads(out.read_text()) if out.exists() else {"items": ITEMS, "windows": {}}
print("cookie:", google_warmup())
for w in WINDOWS:
    if w in have["windows"]:
        continue
    pause()
    ws = explore(ITEMS, 0, w)
    ts = next(x for x in ws if x["id"] == "TIMESERIES")
    tl = widget(ts, "multiline")["default"]["timelineData"]
    have["windows"][w] = [[r["formattedAxisTime"] if "formattedAxisTime" in r else r["time"], int(r["time"]), r["value"]] for r in tl]
    write_json(out, have)
    print(w, len(tl), "точок")
