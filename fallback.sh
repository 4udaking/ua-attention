#!/bin/bash
# Підстраховка на ноутбуці (launchd, 10:30 і 22:30; якщо Mac спав — одразу після пробудження).
# Хмара — основний збирач. Ноутбук збирає те, чого хмара не взяла: сплески, якщо їх не було
# понад 10 год, Вікіпедію (ідемпотентно) і Explore, якщо сьогоднішні файли неповні
# (з домашньої адреси Google ріже рідше, ніж хмару).
set -u
cd "$(dirname "$0")"
export UA_ATT_RUNNER=laptop
PY=/usr/bin/python3
has_remote=$(git remote | head -1)
[ -n "$has_remote" ] && git pull --rebase -q 2>&1

stale=$($PY - <<'PY'
import json, datetime as dt
from lib import DATA, kyiv_now
last = None
try:
    for l in open(DATA / "log.ndjson", encoding="utf-8"):
        r = json.loads(l)
        if r["layer"] == "trending" and r["status"] == "ok":
            last = dt.datetime.fromisoformat(r["ts"])
except FileNotFoundError:
    pass
print(1 if last is None or (kyiv_now() - last).total_seconds() > 10 * 3600 else 0)
PY
)
[ "$stale" = "1" ] && $PY collect_trending.py
$PY collect_wiki.py
$PY collect_explore.py

git add data
if ! git diff --staged --quiet; then
  git commit -q -m "збір (ноутбук) $(date '+%Y-%m-%d %H:%M')"
  [ -n "$has_remote" ] && { git pull --rebase -q && git push -q; }
fi
tail -3 data/log.ndjson
