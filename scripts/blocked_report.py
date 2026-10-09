#!/usr/bin/env python3
"""수집 루틴이 접속하지 못한 사이트 집계 → docs/blocked_domains.md, 그리고 최근 실행의 '허용 목록에 없는' 도메인 출력.

입력: inbox/*.json 의 audit·audit_runs 안 blocked_sites, scotus.blocked (도메인 또는 URL, 뒤에 설명이 붙어도 됨)
      data/allowed_domains.txt (클라우드 환경에 이미 허용한 도메인)
출력: docs/blocked_domains.md (전체 집계 + 붙여넣기용 목록)
      표준출력 — 가장 최근 실행일에 막힌 '허용 목록 밖' 도메인(한 줄에 하나). 없으면 아무것도 출력하지 않는다.
사용: python3 scripts/blocked_report.py
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOST = re.compile(r"(?:https?://)?([a-z0-9.-]+\.[a-z]{2,})", re.I)


def allowed():
    p = REPO / "data/allowed_domains.txt"
    rules = [l.strip().lower() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []
    return lambda h: any(h == r or (r.startswith("*.") and h.endswith(r[1:])) for r in rules)


def hosts(items):
    for s in items or []:
        m = HOST.search(str(s))
        if m:
            yield m.group(1).lower()


def main():
    ok = allowed()
    seen = {}   # host -> {"count", "first", "last"}
    last_run, last_hosts = None, set()
    for p in sorted((REPO / "inbox").glob("20??-??-??.json")):
        d = json.loads(p.read_text())
        runs = [d.get("audit") or {}] + list(d.get("audit_runs") or [])
        hs = set()
        for a in runs:
            hs |= set(hosts(a.get("blocked_sites"))) | set(hosts((a.get("scotus") or {}).get("blocked")))
        for h in hs:
            s = seen.setdefault(h, {"count": 0, "first": p.stem, "last": p.stem})
            s["count"] += 1; s["last"] = p.stem
        last_run, last_hosts = p.stem, hs
    rows = sorted(seen.items(), key=lambda kv: (ok(kv[0]), -kv[1]["count"], kv[0]))
    todo = [h for h, _ in rows if not ok(h)]
    md = ["# 수집 루틴 접속 차단 도메인", "",
          "클라우드 루틴이 원문을 열지 못한 사이트입니다(`scripts/blocked_report.py`가 배포 때마다 갱신).",
          "환경 설정(claude.ai/code → 클라우드 → 환경 ⚙️ → Network access = Custom → Allowed domains)에 추가하고, "
          "`data/allowed_domains.txt`에도 같은 줄을 넣으면 이 목록에서 빠집니다.", "",
          f"## 추가할 도메인 ({len(todo)}개) — 그대로 붙여넣기", "", "```", *todo, "```", "",
          "## 전체 집계", "", "| 도메인 | 상태 | 막힌 날 수 | 처음 | 마지막 |", "|---|---|---|---|---|"]
    md += [f"| {h} | {'허용함(설정 반영 확인 필요)' if ok(h) else '**추가 필요**'} | {s['count']} | {s['first']} | {s['last']} |" for h, s in rows]
    (REPO / "docs/blocked_domains.md").write_text("\n".join(md) + "\n")
    if last_run:
        new = sorted(h for h in last_hosts if not ok(h))
        if new:
            print("\n".join(new))


if __name__ == "__main__":
    main()
