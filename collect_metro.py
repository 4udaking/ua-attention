"""Глибини київського метро: 52 станції з uk.wikipedia → data/metro/stations.json.

Не шар щоденного збору: глибина й координати станції не змінюються. Запускати вручну
або коли Вікіпедія доповнилася — напр. після відкриття станції на Виноградар.

Порядок станцій уздовж ліній і пересадки задані тут (у Вікіпедії вони розкидані),
глибина, координати, тип і дата відкриття — з Вікіпедії. Чого немає в джерелі,
лишається null: вигадана глибина зіпсувала б усю карту.
"""
import datetime as dt
import json
import re
import sys
import urllib.parse
from lib import DATA, WIKI_UA, fetch, log, write_json

API = "https://uk.wikipedia.org/w/api.php"
RU_API = "https://ru.wikipedia.org/w/api.php"

LINES = [
    {"id": "m1", "num": 1, "name": "Святошинсько-Броварська", "color": "#d3232f"},
    {"id": "m2", "num": 2, "name": "Оболонсько-Теремківська", "color": "#0072bc"},
    {"id": "m3", "num": 3, "name": "Сирецько-Печерська", "color": "#00a04a"},
]

# Назва станції → стаття в uk.wikipedia. Де назва статті збігається з назвою станції
# плюс «(станція метро)», пишемо None: збирач добудує сам.
STATIONS = {
    "m1": [
        "Академмістечко", "Житомирська", "Святошин", "Нивки", "Берестейська", "Шулявська",
        "Політехнічний інститут", "Вокзальна", "Університет", "Театральна", "Хрещатик",
        "Арсенальна", "Дніпро", "Гідропарк", "Лівобережна", "Дарниця", "Чернігівська", "Лісова",
    ],
    "m2": [
        "Героїв Дніпра", "Мінська", "Оболонь", "Почайна", "Тараса Шевченка", "Контрактова площа",
        "Поштова площа", "Майдан Незалежності", "Площа Українських Героїв", "Олімпійська",
        "Палац «Україна»", "Либідська", "Деміївська", "Голосіївська", "Васильківська",
        "Виставковий центр", "Іподром", "Теремки",
    ],
    "m3": [
        "Сирець", "Дорогожичі", "Лук'янівська", "Золоті ворота", "Палац спорту", "Кловська",
        "Печерська", "Звіринецька", "Видубичі", "Славутич", "Осокорки", "Позняки", "Харківська",
        "Вирлиця", "Бориспільська", "Червоний хутір",
    ],
}

# Пересадкові вузли: станції однієї пари з'єднані переходом.
TRANSFERS = [
    ("Театральна", "Золоті ворота"),
    ("Хрещатик", "Майдан Незалежності"),
    ("Палац спорту", "Площа Українських Героїв"),
]

# Назви полів — з інфобоксу «Станція метро» в uk.wikipedia, перевірені на живих статтях.
# Обережно: |відкриття| — це година початку роботи станції (06:31), а не дата; дата в |дата|.
FIELDS = {
    "depth": ("глибина закладення", "глибина"),
    "type": ("тип", "тип станції", "конструкція"),
    "opened": ("дата", "дата відкриття", "відкрита"),
}


def api(**params):
    params.update(format="json", formatversion="2")
    return json.loads(fetch(API + "?" + urllib.parse.urlencode(params), ua=WIKI_UA, waits=(5, 20)))


def clean(v):
    """Значення поля інфобоксу → простий текст: без посилань, шаблонів, приміток, тегів."""
    v = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", v, flags=re.S)
    v = re.sub(r"\{\{[^{}]*\}\}", " ", v)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]", r"\1", v)
    v = re.sub(r"<[^>]+>", " ", v)
    return re.sub(r"\s+", " ", v).replace("'''", "").strip(" .,")


def field_raw(text, names):
    """Сире значення поля інфобоксу |ім'я = значення, з шаблонами й посиланнями."""
    for n in names:
        m = re.search(r"\n\s*\|\s*" + re.escape(n) + r"\s*=([^\n]*(?:\n(?!\s*[|}])[^\n]*)*)",
                      text, flags=re.I)
        if m and m.group(1).strip():
            return m.group(1)
    return None


def field(text, names):
    """Те саме, очищене до простого тексту. Вікіпедія пише поля і з великої, і з малої."""
    raw = field_raw(text, names)
    return clean(raw) or None if raw else None


MONTHS = ("січня лютого березня квітня травня червня липня серпня вересня жовтня "
          "листопада грудня").split()


def parse_date(raw):
    """Дата відкриття → ISO. У полі буває {{дата|6|11|1960}}, «6 листопада 1960» або лише рік."""
    if not raw:
        return None
    m = re.search(r"\{\{\s*дата\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\|\s*(\d{4})", raw, flags=re.I)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    txt = clean(raw)
    m = re.search(r"(\d{1,2})\s+([а-яіїєґ']+)\s+(\d{4})", txt, flags=re.I)
    if m and m.group(2).lower() in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", txt)
    return m.group(1) if m else None


def number(s):
    """«105,5 м», «близько 20», «5—7 м» → число. Діапазон — його середина."""
    if not s:
        return None
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", s)]
    nums = [x for x in nums if x < 200]  # роки й номери проєктів у це поле теж потрапляють
    if not nums:
        return None
    if len(nums) >= 2 and re.search(r"\d\s*(?:—|–|-|…|\.\.)\s*\d", s):
        return round((nums[0] + nums[1]) / 2, 1)
    return nums[0]


def depth_from_prose(text):
    """Глибина в тексті статті, коли інфобокс її не має: «глибина закладення — 105,5 м»."""
    m = re.search(r"глибин[аи][^.\n]{0,60}?(\d+(?:[.,]\d+)?)\s*(?:м\b|метр)", text, flags=re.I)
    return number(m.group(1)) if m else None


def surface(text):
    """Наземна чи естакадна станція: глибини в метрах у неї немає, і це не пропуск даних."""
    m = re.search(r"\n\s*\|\s*тип\s*=([^\n]*)", text, flags=re.I)
    t = clean(m.group(1)).lower() if m else ""
    for w in ("наземн", "естакадн", "відкрит"):
        if w in t:
            return True
    return bool(re.search(r"(наземна|естакадна)\s+станц", text[:4000], flags=re.I))


def pages(titles):
    """Вікітекст і координати пачкою. API бере до 50 назв за раз, редиректи йдуть слідом."""
    out = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        d = api(action="query", titles="|".join(chunk), redirects=1,
                prop="revisions|coordinates", rvprop="content", rvslots="main", colimit="max")
        q = d.get("query", {})
        back = {r["to"]: r["from"] for r in q.get("redirects", [])}
        for p in q.get("pages", []):
            asked = back.get(p["title"], p["title"])
            if p.get("missing"):
                out[asked] = None
                continue
            co = (p.get("coordinates") or [{}])[0]
            out[asked] = {
                "title": p["title"],
                "text": p["revisions"][0]["slots"]["main"]["content"],
                "lat": co.get("lat"), "lon": co.get("lon"),
            }
    return out


def is_station(p):
    """Чи це стаття про станцію, а не сторінка-неоднозначність.

    «Університет (станція метро)» — саме така: список однойменних станцій у п'яти містах,
    без інфобоксу. Київська стаття називається «Університет (станція метро, Київ)».
    """
    t = p["text"]
    return "{{disambig" not in t.lower() and re.search(r"\n\s*\|\s*лінія\s*=", t, flags=re.I) is not None


def find_title(name):
    """Запасний шлях, якщо назва статті не вгадана: пошук у Вікіпедії."""
    d = api(action="query", list="search", srsearch=f'"{name}" станція метро Київ', srlimit=3)
    for hit in d.get("query", {}).get("search", []):
        if "станція метро" in hit["title"] or name in hit["title"]:
            return hit["title"]
    return None


def wikidata_coords(titles):
    """Координати для статей без {{coord}}: P625 у Вікіданих. Назва → (широта, довгота).

    Відповідь індексована Q-кодом, тож назву статті беремо з sitelinks тієї ж сутності.
    """
    out = {}
    for i in range(0, len(titles), 40):
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
            "action": "wbgetentities", "sites": "ukwiki", "titles": "|".join(titles[i:i + 40]),
            "props": "claims|sitelinks", "format": "json", "formatversion": "2"})
        for e in json.loads(fetch(url, ua=WIKI_UA, waits=(5, 20))).get("entities", {}).values():
            title = (e.get("sitelinks") or {}).get("ukwiki", {}).get("title")
            for c in e.get("claims", {}).get("P625", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value") or {}
                if title and "latitude" in v:
                    out[title] = (v["latitude"], v["longitude"])
                    break
    return out


def langlinks(titles, lang):
    """Назва статті в uk → назва тієї самої статті в іншому розділі."""
    out = {}
    for i in range(0, len(titles), 40):
        d = api(action="query", titles="|".join(titles[i:i + 40]), redirects=1,
                prop="langlinks", lllang=lang, lllimit="max")
        back = {r["to"]: r["from"] for r in d.get("query", {}).get("redirects", [])}
        for p in d.get("query", {}).get("pages", []):
            for l in p.get("langlinks", []):
                out[back.get(p["title"], p["title"])] = l["title"]
    return out


def ru_depths(titles):
    """Глибини з ru.wikipedia для станцій, яких не знає українська.

    Та сама CC BY-SA, поле в інфобоксі зветься |глубина|. Береться тільки число
    й тільки туди, де українська мовчить; звідки взялося — видно в depth_src.
    """
    out = {}
    for i in range(0, len(titles), 40):
        url = RU_API + "?" + urllib.parse.urlencode({
            "action": "query", "titles": "|".join(titles[i:i + 40]), "redirects": 1,
            "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "format": "json", "formatversion": "2"})
        for p in json.loads(fetch(url, ua=WIKI_UA, waits=(5, 20))).get("query", {}).get("pages", []):
            if p.get("missing"):
                continue
            text = p["revisions"][0]["slots"]["main"]["content"]
            d = number(field(text, ("глубина заложения", "глубина")))
            if d is None:
                m = re.search(r"глубин[аы][^.\n]{0,70}?(\d+(?:[.,]\d+)?)\s*(?:м\b|метр)", text, flags=re.I)
                d = number(m.group(1)) if m else None
            if d is not None:
                out[p["title"]] = d
    return out


def main():
    order = [(lid, i + 1, name) for lid in STATIONS for i, name in enumerate(STATIONS[lid])]
    guess = {name: f"{name} (станція метро)" for _, _, name in order}
    got = pages(sorted(guess.values()))

    stations, no_page, no_depth = [], [], []
    for lid, i, name in order:
        p = got.get(guess[name])
        if p is not None and not is_station(p):
            # Однойменні станції є в кількох містах, і назва без міста веде на
            # неоднозначність — київську статтю тоді дописуємо містом.
            t = f"{name} (станція метро, Київ)"
            alt = pages([t]).get(t)
            p = alt if alt and is_station(alt) else None
        if p is None:
            t = find_title(name)
            p = pages([t]).get(t) if t else None
        if p is None:
            no_page.append(name)
            stations.append({"line": lid, "order": i, "name": name, "title": None,
                             "lat": None, "lon": None, "depth": None, "depth_src": None,
                             "surface": None, "type": None, "opened": None})
            continue
        text = p["text"]
        d, src = number(field(text, FIELDS["depth"])), "infobox"
        if d is None:
            d, src = depth_from_prose(text), "prose"
        if d is None:
            src = None
            no_depth.append(name)
        stations.append({
            "line": lid, "order": i, "name": name, "title": p["title"],
            "lat": p["lat"], "lon": p["lon"],
            "depth": d, "depth_src": src, "surface": surface(text),
            "type": field(text, FIELDS["type"]),
            "opened": parse_date(field_raw(text, FIELDS["opened"])),
        })

    # Глибини, яких немає в українській, добираємо з російської: там ті самі
    # інфобокси заповнені щільніше. Джерело кожного числа лишається в depth_src.
    gap = [s["title"] for s in stations if s["depth"] is None and s["title"]]
    if gap:
        ru = langlinks(gap, "ru")
        got_ru = ru_depths(sorted(set(ru.values())))
        for s in stations:
            d = got_ru.get(ru.get(s["title"]))
            if s["depth"] is None and d is not None:
                s["depth"], s["depth_src"] = d, "ru.wikipedia"
        no_depth = [s["name"] for s in stations if s["depth"] is None]

    # Частина статей не має {{coord}} — добираємо з Вікіданих.
    need = [s["title"] for s in stations if s["lat"] is None and s["title"]]
    if need:
        wd = wikidata_coords(need)
        for s in stations:
            if s["lat"] is None and s["title"] in wd:
                s["lat"], s["lon"] = wd[s["title"]]
                s["coord_src"] = "wikidata"

    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "uk.wikipedia.org, глибини подекуди з ru.wikipedia.org (обидві CC BY-SA 4.0), координати подекуди з Вікіданих",
        "lines": LINES,
        "transfers": [list(t) for t in TRANSFERS],
        "stations": stations,
    }
    write_json(DATA / "metro" / "stations.json", out)
    log("metro", "ok" if not no_page else "partial", stations=len(stations),
        no_page=no_page, no_depth=no_depth,
        no_coords=[s["name"] for s in stations if s["lat"] is None])
    return 0


if __name__ == "__main__":
    sys.exit(main())
