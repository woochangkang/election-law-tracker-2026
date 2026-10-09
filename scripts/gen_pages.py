#!/usr/bin/env python3
"""data/cases.json → 렌더용 마크다운 생성(생성물은 git 밖, 배포 때마다 다시 만든다).

산출: _gen/overview.md(index.qmd 포함) · _gen/table.md(cases.qmd 포함) · _gen/log.md(log.qmd 포함)
      cases/<id>.qmd — 사건별 상세 페이지
사용: python3 scripts/gen_pages.py
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GEN, CASES = REPO / "_gen", REPO / "cases"
STATUS_KR = {"pending": "계류", "active": "진행", "ruled": "판결", "closed": "종결", "enjoined": "집행정지"}
STATUS_ORDER = ["enjoined", "pending", "active", "ruled", "closed"]
STATE_KR = {"US": "연방", "AL": "앨라배마", "AK": "알래스카", "AZ": "애리조나", "AR": "아칸소", "CA": "캘리포니아",
            "CO": "콜로라도", "CT": "코네티컷", "DE": "델라웨어", "FL": "플로리다", "GA": "조지아", "HI": "하와이",
            "ID": "아이다호", "IL": "일리노이", "IN": "인디애나", "IA": "아이오와", "KS": "캔자스", "KY": "켄터키",
            "LA": "루이지애나", "ME": "메인", "MD": "메릴랜드", "MA": "매사추세츠", "MI": "미시간", "MN": "미네소타",
            "MS": "미시시피", "MO": "미주리", "MT": "몬태나", "NE": "네브래스카", "NV": "네바다", "NH": "뉴햄프셔",
            "NJ": "뉴저지", "NM": "뉴멕시코", "NY": "뉴욕", "NC": "노스캐롤라이나", "ND": "노스다코타", "OH": "오하이오",
            "OK": "오클라호마", "OR": "오리건", "PA": "펜실베이니아", "RI": "로드아일랜드", "SC": "사우스캐롤라이나",
            "SD": "사우스다코타", "TN": "테네시", "TX": "텍사스", "UT": "유타", "VT": "버몬트", "VA": "버지니아",
            "WA": "워싱턴", "WV": "웨스트버지니아", "WI": "위스콘신", "WY": "와이오밍", "DC": "워싱턴 DC"}


def cell(s):
    return (s or "—").replace("|", "／").replace("\n", " ")


def states_kr(c):
    return "·".join(STATE_KR.get(s, s) for s in c.get("states") or []) or "—"


def badge(st):
    return f'<span class="st st-{st}">{STATUS_KR.get(st, st)}</span>'


def ev_line(e, case=None):
    src = f" ([{e.get('outlet') or '출처'}]({e['url']}))" if e.get("url") else " <span class=\"mu\">(브리핑 기록, URL 없음)</span>"
    who = f"[{case['title_kr']}](cases/{case['id']}.qmd) — " if case else ""
    return f"- <b class=\"d\">{e['date']}</b> {who}{e['text']}{src}"


def main():
    doc = json.loads((REPO / "data" / "cases.json").read_text())
    items = doc["items"]
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    shutil.rmtree(GEN, ignore_errors=True); GEN.mkdir()
    shutil.rmtree(CASES, ignore_errors=True); CASES.mkdir()

    # 개요: 상태별 건수 · 다가오는 기일 · 최근 2주 움직임
    cnt = Counter(c["status"] for c in items)
    o = [f'<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="n">{cnt.get(s, 0)}</div><div class="l">{badge(s)}</div></div>' for s in STATUS_ORDER)
        + f'<div class="kpi"><div class="n">{len(items)}</div><div class="l">전체 사건</div></div></div>\n',
        f'<p class="mu">기준 {doc.get("as_of")} · 상태 정의는 [자료와 방법](about.qmd)</p>\n']
    up = sorted((c for c in items if c.get("next_date") and dt.date.fromisoformat(c["next_date"]) >= today - dt.timedelta(days=3)),
                key=lambda c: c["next_date"])
    o.append("\n## 다가오는 기일\n")
    o += [f"- <b class=\"d\">{c['next_date']}</b> [{c['title_kr']}](cases/{c['id']}.qmd) — {c.get('next_kr') or ''}" for c in up] \
        or ["- 날짜가 정해진 다음 기일이 없습니다. 각 사건의 「다음」 칸에 날짜 미정 절차가 적혀 있습니다."]
    recent = sorted(((e, c) for c in items for e in c.get("events", [])
                     if dt.date.fromisoformat(e["date"]) >= today - dt.timedelta(days=14)), key=lambda z: z[0]["date"], reverse=True)
    o.append("\n\n## 최근 2주 움직임\n")
    o += [ev_line(e, c) for e, c in recent] or ["- 최근 2주 안에 기록된 움직임이 없습니다."]
    (GEN / "overview.md").write_text("\n".join(o) + "\n")

    # 사건표
    rows = sorted(items, key=lambda c: (c.get("last_date") or ""), reverse=True)
    t = ["| 분류 | 사건 | 지역 | 상태 | 현재 상태 | 최근 | 다음 |", "|---|---|---|---|---|---|---|"]
    t += [f"| {cell(c['category'])} | [{cell(c['title_kr'])}](cases/{c['id']}.qmd) | {states_kr(c)} | {badge(c['status'])} | "
          f"{cell(c.get('status_kr'))} | {cell(c.get('last_date'))} | {cell(c.get('next_kr'))} |" for c in rows]
    (GEN / "table.md").write_text(f'<p class="mu">기준 {doc.get("as_of")} · {len(items)}건 · 최근 움직임 순</p>\n\n'
                                  + "\n".join(t) + "\n\n: {.cases-table}\n")

    # 날짜별 기록
    allev = sorted(((e, c) for c in items for e in c.get("events", [])), key=lambda z: z[0]["date"], reverse=True)
    (GEN / "log.md").write_text("\n".join(ev_line(e, c) for e, c in allev) + "\n")

    # 사건 상세
    for c in items:
        src = " · ".join(f"[{s['label']}]({s['url']})" for s in c.get("sources") or [])
        nxt = f" · 다음: {c['next_kr']}" + (f" ({c['next_date']})" if c.get("next_date") else "") if c.get("next_kr") else ""
        body = [
            "---", f'title: "{c["title_kr"].replace(chr(34), chr(39))}"',
            f'subtitle: "{c["category"]} · {states_kr(c)}"', "---", "",
            f'<p class="mu">{c.get("name_en") or ""} · {c.get("court") or ""}</p>',
            f'<p>{badge(c["status"])} {c.get("status_kr") or ""}{nxt}</p>', "",
            "## 쟁점", "", c.get("summary_kr") or "", "",
        ]
        if c.get("impact_kr"):
            body += ["## 선거 영향", "", c["impact_kr"], ""]
        body += ["## 시간순 기록", "", "::: {.timeline}"] + [ev_line(e) for e in c.get("events", [])] + [":::", ""]
        if src:
            body += ["## 주요 출처", "", src, ""]
        body.append(f'<p class="mu">최근 확인 {c.get("last_checked") or "—"} · 상태 갱신 {c.get("status_updated") or "—"} · [사건표로](../cases.qmd)</p>')
        (CASES / f"{c['id']}.qmd").write_text("\n".join(body) + "\n")
    print(f"gen_pages: 사건 {len(items)}쪽 · 다가오는 기일 {len(up)} · 최근 2주 이벤트 {len(recent)} · 전체 이벤트 {len(allev)}")


if __name__ == "__main__":
    main()
