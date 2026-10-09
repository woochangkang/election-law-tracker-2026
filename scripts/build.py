#!/usr/bin/env python3
"""일일 수집 받은편지함(inbox/YYYY-MM-DD.json) → 검증 → data/cases.json 병합.

입력: inbox/*.json (수집 루틴이 매일 1개 작성, 스키마는 prompts/legal_daily.md §5)
산출: data/cases.json 갱신 · data/build_state.json(처리한 inbox 파일의 해시)
      inbox/YYYY-MM-DD.rejected.json — 검증에서 떨어진 항목과 사유(병합하지 않음)

규칙
  - 항목 단위로 검증한다. 한 항목이 틀려도 나머지는 병합한다. 파일 자체가 JSON이 아니면 종료코드 1.
  - 새 사건·새 이벤트·상태 변경은 출처 URL이 최소 1개 있어야 한다. 날짜를 추정해 채우지 않는다.
  - 같은 사건의 같은 이벤트(날짜 + URL, URL이 같지 않으면 날짜 + 본문)는 한 번만 싣는다.
  - inbox 파일은 내용 해시로 처리 여부를 기록한다. 같은 파일을 고쳐 다시 내면 그 파일만 다시 적용한다
    (이벤트는 중복 제거되므로 안전). 사람이 data/cases.json 을 직접 고친 것을 옛 inbox가 되돌리지 않는다.
  - last_date 는 이벤트 날짜의 최댓값으로 다시 계산한다.
  - 판결(rulings)은 날짜 + 법원이 키. 같은 판결이 다시 오면 새 내용으로 교체한다(반대의견 요지 보강 등).
사용: python3 scripts/build.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA, INBOX = REPO / "data", REPO / "inbox"

STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
          "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
          "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "US"}
CATEGORIES = ["우편투표", "행정명령·연방 규칙", "유권자 등록·명부", "투표 절차·접근", "선거구 재획정·투표권법",
              "선거자금", "후보 자격·투표용지", "선거 관리·개표·인증", "기타"]
STATUS = {"pending", "active", "ruled", "closed", "enjoined"}
TIERS = {"court", "government", "news", "advocacy", "party"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
DOCKET = re.compile(r"^\d{2}(A\d{1,4}|-\d{1,5})$")   # 대법원 사건번호: 26A305(긴급신청) · 25-1017(상고)


def load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def save(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def is_date(v):
    return isinstance(v, str) and bool(DATE.match(v))


def check_event(e, errs, where="event"):
    if not isinstance(e, dict):
        errs.append(f"{where} 형식 오류"); return
    if not is_date(e.get("date")):
        errs.append(f"{where} date 형식 오류: {e.get('date')!r}")
    if not str(e.get("text") or "").strip():
        errs.append(f"{where} text 없음")
    if not str(e.get("url") or "").startswith("http"):
        errs.append(f"{where} 출처 URL 없음")
    if e.get("tier") not in TIERS:
        errs.append(f"{where} tier 오류: {e.get('tier')!r}")


def check_status_fields(x, errs):
    if "status" in x and x["status"] not in STATUS:
        errs.append(f"status 값 오류: {x['status']!r}")
    if x.get("next_date") is not None and not is_date(x["next_date"]):
        errs.append(f"next_date 형식 오류: {x['next_date']!r}")


def check_litigation(x, errs):
    L = x.get("litigation")
    if L is None:
        return
    ok = isinstance(L, list) and all(isinstance(l, dict) and l.get("name") and l.get("issue_kr")
                                     and isinstance(l.get("rulings", []), list) for l in L)
    if not ok:
        errs.append("litigation 형식 오류: [{name, issue_kr, plaintiffs, defendants, plaintiff_claims, defendant_claims, rulings}] 배열")
        return
    for l in L:
        for r in l.get("rulings") or []:
            if r.get("result") not in ("원고 승", "원고 패", "일부"):
                errs.append(f"litigation {l['name']}: result 는 원고 승|원고 패|일부")


def check_detail(x, errs):
    d = x.get("detail")
    if d is None:
        return
    if not isinstance(d, list) or not all(isinstance(s, dict) and s.get("heading") and s.get("md") for s in d):
        errs.append("detail 형식 오류: [{heading, md}] 배열이어야 함")


def check_ruling(r, errs, where="ruling"):
    if not isinstance(r, dict):
        errs.append(f"{where} 형식 오류"); return
    if not is_date(r.get("date")):
        errs.append(f"{where} date 형식 오류: {r.get('date')!r}")
    for k in ("court", "decision_kr"):
        if not str(r.get(k) or "").strip():
            errs.append(f"{where} {k} 없음")
    if not str(r.get("url") or "").startswith("http"):
        errs.append(f"{where} 판결문·명령 URL 없음")
    for k in ("concurrences", "dissents"):
        if not isinstance(r.get(k, []), list):
            errs.append(f"{where} {k} 는 배열")


def add_ruling(case, r):
    """같은 날짜·같은 법원의 판결은 하나 — 다시 오면 새 내용으로 교체(반대의견 보강 등)."""
    rs = case.setdefault("rulings", [])
    for i, o in enumerate(rs):
        if o.get("date") == r["date"] and o.get("court") == r["court"]:
            changed = o != r
            rs[i] = r
            return changed
    rs.append(r)
    rs.sort(key=lambda z: z["date"])
    return True


def add_dockets(case, ds):
    cur = case.setdefault("scotus_dockets", [])
    new = [d for d in ds if d not in cur]
    cur += new
    return bool(new)


def merge_glossary(raw, rejected, stats):
    """inbox 의 glossary 배열 → data/glossary.json. 새 용어만 추가(기존 풀이는 사람이 고친다)."""
    if not raw.get("glossary"):
        return
    p = DATA / "glossary.json"
    g = load(p, {"items": []})
    known = {m for it in g["items"] for m in [it["term"], *(it.get("match") or [])]}
    for t in raw["glossary"]:
        errs = [f"{k} 없음" for k in ("term", "explain_kr", "category") if not str(t.get(k) or "").strip()]
        if errs:
            rejected.append({"section": "glossary", "item": t, "reasons": errs}); continue
        match = [m for m in (t.get("match") or [t["term"]]) if m not in known]
        if t["term"] in known or not match:
            continue
        g["items"].append({"category": t["category"], "term": t["term"], "match": match, "explain_kr": t["explain_kr"]})
        known.update(match + [t["term"]])
        stats["glossary"] += 1
    save(p, g)


def add_event(case, e):
    ev = {k: e.get(k) for k in ("date", "text", "url", "outlet", "tier") if e.get(k) is not None}
    for o in case.setdefault("events", []):
        if o.get("date") == ev["date"] and (o.get("url") == ev.get("url") or o.get("text") == ev["text"]):
            return False
    case["events"].append(ev)
    case["events"].sort(key=lambda z: z["date"])
    return True


def apply_status(case, x, run):
    changed = False
    for k in ("detail", "litigation"):   # 쟁점 상세·소송별 카드는 통째로 교체
        if x.get(k) and case.get(k) != x[k]:
            case[k] = x[k]; changed = True
    for k in ("status", "status_kr", "next_date", "next_kr", "plain_kr", "impact_kr", "summary_kr"):
        if k in x and case.get(k) != x[k]:
            case[k] = x[k]; changed = True
    if changed:
        case["status_updated"] = run
    return changed


def process(path: Path, cases: dict, stats: dict):
    run = path.stem
    raw = json.loads(path.read_text())
    rejected = []

    for n in raw.get("new_cases", []):
        errs = []
        for k in ("id", "title_kr", "name_en", "category", "court", "status", "summary_kr", "states", "events"):
            if not n.get(k):
                errs.append(f"필수 키 없음: {k}")
        if n.get("id") and not ID.match(n["id"]):
            errs.append(f"id 형식 오류: {n['id']!r}")
        if n.get("category") and n["category"] not in CATEGORIES:
            errs.append(f"category 값 오류: {n['category']!r}")
        if isinstance(n.get("states"), list) and set(n["states"]) - STATES:
            errs.append(f"states 오류: {sorted(set(n['states']) - STATES)}")
        check_status_fields(n, errs)
        check_detail(n, errs)
        check_litigation(n, errs)
        for d in n.get("scotus_dockets") or []:
            if not DOCKET.match(str(d)):
                errs.append(f"scotus_dockets 형식 오류: {d!r}")
        for i, e in enumerate(n.get("events") or []):
            check_event(e, errs, f"events[{i}]")
        for i, r in enumerate(n.get("rulings") or []):
            check_ruling(r, errs, f"rulings[{i}]")
        if errs:
            rejected.append({"section": "new_cases", "item": n, "reasons": errs}); continue
        if n["id"] in cases:  # 이미 있는 사건이면 갱신으로 처리
            c = cases[n["id"]]
            for e in n["events"]:
                stats["events"] += add_event(c, e)
            add_dockets(c, n.get("scotus_dockets") or [])
            for r in n.get("rulings") or []:
                stats["rulings"] += add_ruling(c, r)
            stats["status"] += apply_status(c, n, run)
        else:
            c = {k: n.get(k) for k in ("id", "category", "title_kr", "name_en", "court", "status", "status_kr",
                                       "summary_kr", "impact_kr", "states", "next_date", "next_kr", "scotus_dockets", "detail", "litigation", "plain_kr")}
            c.update(events=[], sources=n.get("sources") or [], first_seen=run, last_checked=run, status_updated=run)
            for e in n["events"]:
                add_event(c, e)
            for r in n.get("rulings") or []:
                stats["rulings"] += add_ruling(c, r)
            cases[c["id"]] = c
            stats["new"] += 1

    for u in raw.get("updates", []):
        errs = []
        c = cases.get(u.get("case_id"))
        if c is None:
            errs.append(f"없는 case_id: {u.get('case_id')!r}")
        check_event(u, errs, "update")
        check_status_fields(u, errs)
        check_detail(u, errs)
        check_litigation(u, errs)
        if u.get("ruling") is not None:
            check_ruling(u["ruling"], errs, "update.ruling")
        for d in u.get("scotus_dockets") or []:
            if not DOCKET.match(str(d)):
                errs.append(f"scotus_dockets 형식 오류: {d!r}")
        if errs:
            rejected.append({"section": "updates", "item": u, "reasons": errs}); continue
        stats["events"] += add_event(c, u)
        if u.get("ruling"):
            stats["rulings"] += add_ruling(c, u["ruling"])
        add_dockets(c, u.get("scotus_dockets") or [])
        stats["status"] += apply_status(c, u, run)
        c["last_checked"] = max(c.get("last_checked") or run, run)

    for ck in raw.get("checks", []):
        c = cases.get(ck.get("case_id"))
        if c is None:
            rejected.append({"section": "checks", "item": ck, "reasons": [f"없는 case_id: {ck.get('case_id')!r}"]}); continue
        c["last_checked"] = max(c.get("last_checked") or run, run)
        stats["checks"] += 1

    merge_glossary(raw, rejected, stats)

    rej = path.with_suffix(".rejected.json")
    if rejected:
        save(rej, rejected)
    elif rej.exists():
        rej.unlink()
    stats["rejected"] += len(rejected)


def main():
    cases_p, state_p = DATA / "cases.json", DATA / "build_state.json"
    doc = load(cases_p, {"as_of": None, "items": []})
    cases = {x["id"]: x for x in doc["items"]}
    state = load(state_p, {"processed": {}})
    stats = dict(files=0, new=0, events=0, rulings=0, status=0, checks=0, glossary=0, rejected=0)
    for p in sorted(INBOX.glob("20??-??-??.json")):
        h = hashlib.sha1(p.read_bytes()).hexdigest()
        if state["processed"].get(p.name) == h:
            continue
        try:
            process(p, cases, stats)
        except json.JSONDecodeError as e:
            print(f"✗ {p.name}: JSON 아님 — {e}", file=sys.stderr); sys.exit(1)
        state["processed"][p.name] = h
        stats["files"] += 1
        doc["as_of"] = max(doc.get("as_of") or p.stem, p.stem)
    for c in cases.values():
        ds = [e["date"] for e in c.get("events", []) if is_date(e.get("date"))]
        c["last_date"] = max(ds) if ds else None
    doc["items"] = list(cases.values())
    save(cases_p, doc)
    save(state_p, state)
    print("build: inbox {files} · 새 사건 {new} · 새 이벤트 {events} · 판결 {rulings} · 상태 변경 {status} · 확인만 {checks} · 새 용어 {glossary} · 거부 {rejected}".format(**stats))
    print(f"cases.json: {len(cases)}건 · as_of {doc['as_of']} · 오늘(KST) {dt.datetime.now(dt.timezone(dt.timedelta(hours=9))):%Y-%m-%d}")


if __name__ == "__main__":
    main()
