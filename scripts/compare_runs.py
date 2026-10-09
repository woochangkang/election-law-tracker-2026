#!/usr/bin/env python3
"""모델 비교: 같은 날 main(Sonnet 루틴)과 eval/opus-<날짜> 브랜치(Opus 시험 루틴)의 inbox를 대조한다.

비교 항목: 자기 보고 검색 횟수(audit) · 후속 확인 대상/확인 수 · 움직임·확인·새 사건 건수 · 거부 건수
          · 한쪽만 찾은 움직임(사건 id + 날짜 + URL 기준)과 새 사건 — 품질 검토는 이 목록을 사람이 출처로 확인한다.
주의: audit 검색 횟수는 에이전트의 자기 보고다. 실제 도구 호출 수는 루틴 실행 로그(get_run_log)로 따로 센다.
사용: git fetch origin && python3 scripts/compare_runs.py 2026-10-10 [2026-10-11 ...] > evals/<마지막 날짜>.md
"""
from __future__ import annotations

import json
import subprocess
import sys


def show(ref: str, path: str):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def audit_sum(d, key):
    runs = [d.get("audit") or {}] + list(d.get("audit_runs") or [])
    return sum(int(a.get(key) or 0) for a in runs)


def ev_keys(d):
    out = {}
    for u in d.get("updates") or []:
        out[(u.get("case_id"), u.get("date"), u.get("url"))] = u
    for n in d.get("new_cases") or []:
        for e in n.get("events") or []:
            out[(n.get("id"), e.get("date"), e.get("url"))] = e
    return out


def summary(d, rej):
    return {
        "검색(공화 측)": audit_sum(d, "searches_R_side"), "검색(민주 측)": audit_sum(d, "searches_D_side"),
        "검색(주제)": audit_sum(d, "searches_topic"),
        "후속 확인 대상": audit_sum(d, "followups_due"), "후속 확인 수행": audit_sum(d, "followups_checked"),
        "움직임(updates)": len(d.get("updates") or []), "확인만(checks)": len(d.get("checks") or []),
        "새 사건": len(d.get("new_cases") or []), "거부": len(rej or []),
        "대법원 페이지 열람": sum(len(((a or {}).get("scotus") or {}).get("pages_opened") or []) for a in [d.get("audit")] + list(d.get("audit_runs") or [])),
        "대법원 docket 확인": sum(len(((a or {}).get("scotus") or {}).get("dockets_checked") or []) for a in [d.get("audit")] + list(d.get("audit_runs") or [])),
        "새 용어": len(d.get("glossary") or []),
        "상태 변경 제안": sum(1 for u in d.get("updates") or [] if "status" in u),
        "court 출처 비율": "{:.0%}".format(
            (lambda xs: sum(1 for x in xs if x.get("tier") == "court") / len(xs) if xs else 0)(list(ev_keys(d).values()))),
    }


def one(date):
    refs = {"Sonnet(main)": "origin/main", "Opus(eval)": f"origin/eval/opus-{date}"}
    ds = {k: show(r, f"inbox/{date}.json") for k, r in refs.items()}
    rj = {k: show(r, f"inbox/{date}.rejected.json") for k, r in refs.items()}
    out = [f"## {date}\n"]
    miss = [k for k, v in ds.items() if v is None]
    if miss:
        return "\n".join(out + [f"- 비교 불가: {', '.join(miss)} 산출물 없음\n"]), None
    s = {k: summary(ds[k], rj[k]) for k in ds}
    a, b = list(ds)
    out += [f"| 항목 | {a} | {b} |", "|---|---|---|"] + [f"| {m} | {s[a][m]} | {s[b][m]} |" for m in s[a]]
    ka, kb = ev_keys(ds[a]), ev_keys(ds[b])
    for name, only, src in ((a, ka.keys() - kb.keys(), ka), (b, kb.keys() - ka.keys(), kb)):
        out.append(f"\n**{name}만 찾은 움직임 {len(only)}건**")
        out += [f"- `{c}` {dte} — {src[(c, dte, u)].get('text', '')[:90]} ([출처]({u}))" for c, dte, u in sorted(only, key=str)]
    na = {n["id"] for n in ds[a].get("new_cases") or []}
    nb = {n["id"] for n in ds[b].get("new_cases") or []}
    out.append(f"\n새 사건 — 공통 {sorted(na & nb)} · {a}만 {sorted(na - nb)} · {b}만 {sorted(nb - na)}\n")
    return "\n".join(out), s


def main():
    dates = sys.argv[1:]
    if not dates:
        sys.exit(__doc__)
    print("# 모델 비교 — Sonnet 5.5(운영) vs Opus 5.5(시험)\n")
    totals = {}
    for d in dates:
        text, s = one(d)
        print(text)
        if s:
            for k, v in s.items():
                for m, x in v.items():
                    if isinstance(x, int):
                        totals.setdefault(k, {}).setdefault(m, 0)
                        totals[k][m] += x
    if len(totals) == 2:
        a, b = list(totals)
        print(f"## 합계 ({len(dates)}일)\n\n| 항목 | {a} | {b} |\n|---|---|---|")
        for m in totals[a]:
            print(f"| {m} | {totals[a][m]} | {totals[b][m]} |")


if __name__ == "__main__":
    main()
