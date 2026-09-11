"""Спільне для збирачів: HTTP з відступом на 429, київський час, журнал запусків."""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
# Вікімедіа вимагає впізнаваний UA з контактом, браузерний їй не підходить.
WIKI_UA = "ua-attention/0.1 (daily attention tracker; boykojunior@gmail.com)"
RUNNER = os.environ.get("UA_ATT_RUNNER", "laptop")


class Throttled(Exception):
    """Google відповідає 429 і після всіх відступів — шар пропускаємо, решту збираємо."""


def kyiv_now():
    # Без zoneinfo: на ноутбуці python 3.9 без tzdata не гарантований.
    # Україна: UTC+3 з останньої неділі березня до останньої неділі жовтня, інакше UTC+2.
    now = dt.datetime.now(dt.timezone.utc)
    y = now.year
    def last_sunday(month):
        d = dt.datetime(y, month, 31 if month in (3, 10) else 30, 1, tzinfo=dt.timezone.utc)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    off = 3 if last_sunday(3) <= now < last_sunday(10) else 2
    return now.astimezone(dt.timezone(dt.timedelta(hours=off)))


def fetch(url, data=None, headers=None, ua=BROWSER_UA, waits=(20, 60, 150), timeout=40):
    """GET/POST з повторами. 429 → чекаємо й повторюємо; після останнього відступу — Throttled."""
    hdr = {"User-Agent": ua}
    hdr.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    for attempt in range(len(waits) + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < len(waits):
                time.sleep(waits[attempt])
                continue
            if e.code == 429:
                raise Throttled(url)
            if e.code >= 500 and attempt < len(waits):
                time.sleep(10)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < len(waits):
                time.sleep(10)
                continue
            raise


def log(layer, status, **kw):
    DATA.mkdir(exist_ok=True)
    rec = {"ts": kyiv_now().isoformat(timespec="seconds"), "runner": RUNNER, "layer": layer, "status": status}
    rec.update(kw)
    with open(DATA / "log.ndjson", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False))


def write_json(path, obj):
    """Атомарний запис: спершу тимчасовий файл, потім заміна."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
