#!/bin/bash
# Підстраховка на ноутбуці (launchd, 10:30 і 22:30; якщо Mac спав — одразу після пробудження).
# Хмара — основний збирач. Ноутбук збирає те, чого хмара не взяла: сплески, якщо їх не було
# понад 10 год, Вікіпедію (ідемпотентно) і Explore, якщо сьогоднішні файли неповні.
# 11.09.2026: хмара й ноутбук зібрали ту саму панель — злиття застрягло на JSON. Тепер при
# конфлікті ноутбук скидається на версію хмари і добирає лише відсутнє (збирачі продовжують з місця).
set -u
cd "$(dirname "$0")"
export UA_ATT_RUNNER=laptop
PY=/usr/bin/python3
has_remote=$(git remote | head -1)

sync_remote() {
  [ -z "$has_remote" ] && return 0
  # це й робоча копія для правок коду: з незакоміченими змінами поза data/ git не чіпаємо взагалі
  if [ -n "$(git status --porcelain -- . ':!data')" ]; then
    echo "незакомічені зміни коду — синхронізацію пропускаю, дані лишаються локально"
    return 3
  fi
  git fetch -q origin || return 1
  if [ -n "$(git status --porcelain data)" ] || [ "$(git rev-list --count origin/main..HEAD)" != "0" ]; then
    git add data && git commit -q -m "збір (ноутбук) $(date '+%Y-%m-%d %H:%M')" 2>/dev/null
    if ! git rebase -q origin/main 2>/dev/null; then
      git rebase --abort 2>/dev/null
      echo "конфлікт із хмарою — беру її версію і добираю відсутнє"
      git reset -q --hard origin/main
      return 2
    fi
  else
    git merge -q --ff-only origin/main
  fi
  return 0
}

collect() {
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
}

sync_remote
collect
sync_remote; rc=$?
[ "$rc" = "2" ] && { collect; sync_remote; rc=$?; }
[ "$rc" = "0" ] && [ -n "$has_remote" ] && git push -q origin HEAD:main 2>&1 | tail -1
tail -3 data/log.ndjson
