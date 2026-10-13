#!/usr/bin/env python3
"""수집 자기보고를 검증한다. 기본은 경고·공개 표시, --strict는 게시 전 최소 3/3/5 하드 게이트.
접근 차단과 검색 요약은 원문 확인 성공으로 바꾸지 않는다. 재실행은 마지막 audit_runs만 검사한다.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path

MINIMUM = {"searches_R_side": 3, "searches_D_side": 3, "searches_topic": 5}
LABELS = {"searches_R_side": "공화 측", "searches_D_side": "민주 측", "searches_topic": "주제"}
REPO = Path(__file__).resolve().parent.parent


def audit_summary(raw):
    runs = raw.get("audit_runs")
    audit = runs[-1] if isinstance(runs, list) and runs else raw.get("audit")
    audit = audit if isinstance(audit, dict) else {}
    problems, counts = [], {}
    for key, minimum in MINIMUM.items():
        value = audit.get(key)
        counts[key] = value if type(value) is int and value >= 0 else None
        if counts[key] is None:
            problems.append(f"{LABELS[key]} 검색 횟수 미확인(최소 {minimum}회)")
        elif value < minimum:
            problems.append(f"{LABELS[key]} {value}회 < 최소 {minimum}회")
    due, checked = audit.get("followups_due"), audit.get("followups_checked")
    if type(due) is int and type(checked) is int and checked < due:
        problems.append(f"후속 확인 {checked}/{due}건 미완료")
    scotus = audit.get("scotus") or {}
    blocked = list(audit.get("blocked_sites") or []) + list(scotus.get("blocked") or [])
    return {"run_date": raw.get("run_date"), "counts": counts, "problems": problems,
            "blocked": list(dict.fromkeys(blocked)), "notes": audit.get("notes") or "",
            "status": "미완료" if problems else ("접근 제한 있음" if blocked else "최소 검색 기준 충족"),
            "rerun": bool(runs)}


def latest_inbox(folder):
    paths = sorted(folder.glob("20??-??-??.json"))
    return paths[-1] if paths else None


def collection_notice(folder):
    path = latest_inbox(folder)
    if path is None:
        return '\n::: {.callout-warning}\n## 수집 점검 미확인\n수집 점검 기록이 없습니다.\n:::\n'
    result = audit_summary(json.loads(path.read_text()))
    counts = " · ".join(f"{LABELS[k]} {result['counts'][k] if result['counts'][k] is not None else '미확인'}/{v}회" for k, v in MINIMUM.items())
    lines = ['\n::: {.callout-warning}' if result['problems'] or result['blocked'] else '\n::: {.callout-note}',
             f"## 수집 점검 — {result['status']}", "",
             f"{html.escape(str(result['run_date']))} {'마지막 재실행' if result['rerun'] else '실행'} · {counts}", "",
             "검색 횟수는 자기보고입니다. 최소 기준 충족은 원문 열람이나 사실 검증 완료를 뜻하지 않습니다."]
    lines += [f"- {html.escape(p)}" for p in result['problems']]
    if result['blocked']:
        lines.append("- 접근 차단: " + html.escape(" · ".join(result['blocked'])))
    if result['notes']:
        lines.append("- 수집 메모: " + html.escape(result['notes']))
    return "\n".join(lines + [":::", ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    path = args.path or latest_inbox(REPO / "inbox")
    if path is None:
        print("수집 점검 기록 없음"); return 1 if args.strict else 0
    result = audit_summary(json.loads(path.read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.strict and result['problems'] else 0


if __name__ == "__main__":
    raise SystemExit(main())
