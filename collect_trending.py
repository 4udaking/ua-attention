"""Шар 1 — сплески: Google Trending Now по Україні.

Google показує тренди лише за 7 діб, тож беремо все вікно (168 год) щоразу.
Пропуск до 6 діб самозаліковується. На диск пишемо лише нове або змінене
(обсяг росте, поки тренд активний; з'являється кінець), тобто дельти до
останнього відомого стану за 9 діб.

Файли: data/trending/ДД.ndjson за київською датою збору, один рядок = одна версія епізоду.
Окремо data/trending_rss/ — 10 пунктів офіційної стрічки з заголовками й посиланнями новин.
"""
import json
import re
import sys
import datetime as dt
import html
from lib import DATA, fetch, kyiv_now, log, Throttled

GEO, LANG, HOURS = "UA", "uk", 168
CATS = {1: "Авто", 2: "Краса і мода", 3: "Бізнес і фінанси", 4: "Розваги", 5: "Їжа і напої",
        6: "Ігри", 7: "Здоров'я", 8: "Хобі і дозвілля", 9: "Робота і освіта", 10: "Право і держава",
        11: "Інше", 13: "Тварини", 14: "Політика", 15: "Наука", 16: "Покупки", 17: "Спорт",
        18: "Технології", 19: "Подорожі і транспорт", 20: "Клімат"}
OUT = DATA / "trending"


def fetch_items():
    req = json.dumps([[["i0OFE", json.dumps([None, None, GEO, 0, LANG, HOURS, 1]), None, "generic"]]])
    raw = fetch("https://trends.google.com/_/TrendsUi/data/batchexecute",
                data={"f.req": req},
                headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8"})
    line = next(l for l in raw.splitlines() if l.startswith('[["wrb.fr"'))
    inner = json.loads(json.loads(line)[0][2])
    items = inner[1] or []
    if not items:
        raise ValueError("порожня відповідь i0OFE — схема могла змінитись")
    recs = []
    for it in items:
        if len(it) < 13 or not isinstance(it[3], list):
            raise ValueError(f"незнайома форма пункту: {str(it)[:200]}")
        recs.append({
            "key": f"{it[0]}|{it[3][0]}",
            "title": it[0],
            "start": it[3][0],
            "end": it[4][0] if it[4] else None,
            "vol": it[6],
            "inc": it[8],
            "queries": it[9] or [],
            "cats": it[10] or [],
            "news_n": len(it[11] or []),
            "explore": it[12],
        })
    return recs


def sig(r):
    return (r["vol"], r["end"], r["inc"], tuple(r["queries"]), tuple(r["cats"]))


def known_state(days=9):
    """Останній відомий стан кожного епізоду з дельт за останні дні."""
    state = {}
    today = kyiv_now().date()
    for i in range(days, -1, -1):
        p = OUT / f"{today - dt.timedelta(days=i)}.ndjson"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                state[r["key"]] = r
    return state


def fetch_rss():
    raw = fetch(f"https://trends.google.com/trending/rss?geo={GEO}")
    out = []
    for item in re.findall(r"<item>(.*?)</item>", raw, re.S):
        g = lambda tag, s=item: [html.unescape(x) for x in re.findall(rf"<{tag}>(.*?)</{tag}>", s, re.S)]
        out.append({"title": g("title")[0], "traffic": (g("ht:approx_traffic") or [None])[0],
                    "pub": (g("pubDate") or [None])[0],
                    "news": [{"title": t, "url": u, "source": s} for t, u, s in
                             zip(g("ht:news_item_title"), g("ht:news_item_url"), g("ht:news_item_source"))]})
    return out


def main():
    now = kyiv_now()
    seen = now.isoformat(timespec="seconds")
    try:
        recs = fetch_items()
    except Throttled:
        log("trending", "throttled")
        return 2
    state = known_state()
    fresh = [r for r in recs if r["key"] not in state or sig(r) != sig(state[r["key"]])]
    new = sum(1 for r in fresh if r["key"] not in state)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{now.date()}.ndjson", "a", encoding="utf-8") as f:
        for r in fresh:
            f.write(json.dumps(dict(r, seen=seen), ensure_ascii=False) + "\n")
    rss_n = 0
    try:
        rss = fetch_rss()
        rss_n = len(rss)
        p = DATA / "trending_rss" / f"{now.date()}.ndjson"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"seen": seen, "items": rss}, ensure_ascii=False) + "\n")
    except Exception as e:  # стрічка — додаток, її збій не валить шар
        print("rss:", e, file=sys.stderr)
    active = sum(1 for r in recs if r["end"] is None)
    log("trending", "ok", window=len(recs), active=active, written=len(fresh), new=new, rss=rss_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
