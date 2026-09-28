"""План Києва під сцену метро: 10 районів + русло Дніпра → data/metro/city.json.

Разовий скрипт, як і collect_metro.py: межі районів не рухаються. Два джерела, обидва
віддає raw.githubusercontent, тож працює й там, де решта мережі закрита.

  райони — OpenStreetMap (ODbL), через kyiv-air-map, де вони вже спрощені до 394 точок;
  Дніпро — Natural Earth 10m, суспільне надбання. Це осьова лінія масштабу 1:10 млн:
  на місті вона схематична (похибка до кілометра), тому на сторінці підписана як схема.

Перевірено на кількох точках: русло NE проходить західніше Гідропарку — і це правильно,
Гідропарк стоїть на Венеціанському острові, головне річище йде повз нього із заходу.
"""
import json
import sys
from lib import DATA, fetch, log, write_json

RAIONS = ("https://raw.githubusercontent.com/zheniaslius/kyiv-air-map/"
          "master/public/data/raions.geojson")
RIVERS = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          "master/geojson/ne_10m_rivers_lake_centerlines.geojson")
BOX = (30.1, 50.15, 30.95, 50.65)   # Київ із запасом: за ним річку обрізаємо


def rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def round_ring(ring):
    """П'ять знаків — це ~1 м. Більше не має сенсу: джерело й так спрощене."""
    return [[round(c[0], 5), round(c[1], 5)] for c in ring]


def main(argv):
    src = {p.split("=")[0]: p.split("=", 1)[1] for p in argv if "=" in p}
    raw = (open(src["raions"], encoding="utf-8").read() if "raions" in src
           else fetch(RAIONS, waits=(5, 20)))
    districts = []
    for f in json.loads(raw)["features"]:
        if f["properties"].get("oblast") != "UA80":
            continue
        districts.append({"name": f["properties"]["name"].replace(" район", ""),
                          "rings": [round_ring(r) for r in rings(f["geometry"])]})
    districts.sort(key=lambda d: d["name"])

    raw = (open(src["rivers"], encoding="utf-8").read() if "rivers" in src
           else fetch(RIVERS, waits=(5, 20)))
    inbox = lambda c: BOX[0] <= c[0] <= BOX[2] and BOX[1] <= c[1] <= BOX[3]
    river = []
    for f in json.loads(raw)["features"]:
        if f["properties"].get("name") != "Dnipro":
            continue
        g = f["geometry"]
        for ln in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]):
            seg = [c for c in ln if inbox(c)]
            if len(seg) > len(river):
                river = seg
    river = round_ring(sorted(river, key=lambda c: -c[1]))   # з півночі на південь

    out = {
        "source": {
            "districts": "OpenStreetMap (ODbL), спрощені у zheniaslius/kyiv-air-map",
            "river": "Natural Earth 10m rivers (public domain), схематична осьова",
        },
        "districts": districts,
        "river": river,
    }
    write_json(DATA / "metro" / "city.json", out)
    log("metro_map", "ok" if len(districts) == 10 and len(river) > 10 else "partial",
        districts=len(districts), points=sum(len(r) for d in districts for r in d["rings"]),
        river=len(river))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
