"""Шар 4 — читання: топ української Вікіпедії і топ статей, які читають з України.

Вікімедіа віддає доби заднім числом без обмежень, тож щоразу добираємо всі
відсутні доби за останні 14 днів (самозаліковування). Дані за добу UTC
з'являються через кілька годин після її кінця — 404 для вчора це норма.

Файли: data/wiki/uk/ДД.json (≈1000 статей, точні перегляди),
       data/wiki/country_UA/ДД.json (≈20–30 статей усіх мовних розділів, округлено вгору до 100).
Бекфіл: python3 collect_wiki.py 2024-11-28 2026-01-03
"""
import datetime as dt
import json
import sys
import time
import urllib.error
from lib import DATA, WIKI_UA, fetch, log, write_json

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
SOURCES = {
    "uk": API + "/top/uk.wikipedia/all-access/{y}/{m:02d}/{d:02d}",
    "country_UA": API + "/top-per-country/UA/all-access/{y}/{m:02d}/{d:02d}",
}
FIRST = {"uk": dt.date(2015, 7, 1), "country_UA": dt.date(2021, 2, 9)}


def get_day(src, day):
    url = SOURCES[src].format(y=day.year, m=day.month, d=day.day)
    try:
        d = json.loads(fetch(url, ua=WIKI_UA, waits=(5, 20)))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    arts = d["items"][0]["articles"]
    if src == "uk":
        return [[a["article"], a["views"]] for a in arts]
    return [[a["project"].split(".")[0], a["article"], a["views_ceil"]] for a in arts]


def main(argv):
    if len(argv) == 2:
        a, b = (dt.date.fromisoformat(x) for x in argv)
    else:
        b = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
        a = b - dt.timedelta(days=13)
    got, missing = 0, []
    for src in SOURCES:
        day = max(a, FIRST[src])
        while day <= b:
            p = DATA / "wiki" / src / f"{day}.json"
            if not p.exists():
                rows = get_day(src, day)
                if rows is None:
                    missing.append(f"{src}:{day}")
                else:
                    write_json(p, rows)
                    got += 1
                time.sleep(0.2)
            day += dt.timedelta(days=1)
    log("wiki", "ok", fetched=got, not_yet=missing[-4:], range=f"{a}..{b}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
