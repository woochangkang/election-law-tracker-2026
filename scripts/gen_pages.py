#!/usr/bin/env python3
"""data/cases.json → 렌더용 마크다운 생성(생성물은 git 밖, 배포 때마다 다시 만든다).

산출: _gen/overview.md(index.qmd 포함) · _gen/table.md(cases.qmd 포함) · _gen/log.md(log.qmd 포함)
      cases/<id>.qmd — 사건별 상세 페이지
사용: python3 scripts/gen_pages.py   (배포 때 추가로 --briefings: 일일 브리핑에 용어 풀이, 커밋 금지)
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
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


class Glossary:
    """data/glossary.json 의 용어를 페이지에서 처음 나오는 곳에 풀이(툴팁)로 감싼다.
    머리말(YAML)·제목 줄·링크 주소·HTML 태그·이미 감싼 용어 안은 건드리지 않는다. 영문 용어는 단어 경계에서만 맞춘다."""
    PROTECT = re.compile(r'<span class="term".*?</span>|<[^>]+>|\]\([^)]*\)|https?://\S+|`[^`]*`|\{[^}]*\}')

    def __init__(self):
        p = REPO / "data" / "glossary.json"
        self.items = json.loads(p.read_text())["items"] if p.exists() else []
        pats = []
        for it in self.items:
            for m in it.get("match") or [it["term"]]:
                rx = re.escape(m)
                if re.fullmatch(r"[A-Za-z][A-Za-z .\-]*", m):
                    rx = rf"(?<![A-Za-z]){rx}(?![A-Za-z])"
                pats.append((len(m), re.compile(rx), it))
        self.pats = sorted(pats, key=lambda z: -z[0])

    def _wrap_first(self, text, rx, it):
        pos, out = 0, []
        for m in list(self.PROTECT.finditer(text)) + [None]:
            end = m.start() if m else len(text)
            seg = text[pos:end]
            hit = rx.search(seg)
            if hit:
                tip = html.escape(it["explain_kr"], quote=True)
                seg = seg[:hit.start()] + f'<span class="term" tabindex="0" data-tip="{tip}">{hit.group()}</span>' + seg[hit.end():]
                return "".join(out) + seg + text[end:], True
            out.append(seg + (m.group() if m else ""))
            pos = m.end() if m else end
        return text, False

    def page(self, md, box=True, root=""):
        """md 전체에 첫 등장 풀이를 달고, box=True면 끝에 「용어 풀이」 상자를 붙인다."""
        lines, body_from = md.split("\n"), 0
        if lines and lines[0].strip() == "---":
            body_from = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0) + 1
        idx = [i for i in range(body_from, len(lines)) if not lines[i].lstrip().startswith(("#", ":::", "|---"))]
        used = []
        for _, rx, it in self.pats:
            if it in used:
                continue
            for i in idx:
                lines[i], ok = self._wrap_first(lines[i], rx, it)
                if ok:
                    used.append(it); break
        out = "\n".join(lines)
        if box and used:
            rows = "\n".join(f"- **{it['term']}** — {it['explain_kr']}" for it in used)
            out += f'\n\n::: {{.glossary-box .fold}}\n**용어 풀이**\n\n{rows}\n\n[전체 용어 풀이]({root}glossary.qmd)\n:::\n'
        return out

    def glossary_md(self):
        out = []
        for cat in dict.fromkeys(it["category"] for it in self.items):
            out.append(f"\n## {cat}\n")
            out += [f"- **{it['term']}** — {it['explain_kr']}" for it in self.items if it["category"] == cat]
        return "\n".join(out) + "\n"


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


def opinion_line(label, o):
    if not o or not o.get("summary_kr"):
        return ""
    who = o.get("author") or "서명 없음(per curiam)"
    if o.get("joined_by"):
        who += f" (동참: {'·'.join(o['joined_by'])})"
    return f"- **{label} — {who}**: {o['summary_kr']}"


def fold(md):
    """긴 덩어리를 접기 상자로 감싼다(assets/fold.js 가 첫 4줄만 보이게 하고 「더 보기」 단추를 단다)."""
    return ["::: {.fold}", md, ":::", ""]


def glance_md(c):
    """사건 페이지 맨 위 「한눈에 보기」: 상태 · 다음 기일 · 최근 판결(없으면 최근 움직임) · 선거 영향."""
    rows = [f"- **상태** {badge(c['status'])} {c.get('status_kr') or ''}"]
    if c.get("next_kr") or c.get("next_date"):
        rows.append(f"- **다음** {c.get('next_kr') or ''}" + (f" ({c['next_date']})" if c.get("next_date") else ""))
    rs = sorted(c.get("rulings") or [], key=lambda r: r["date"])
    if rs:
        r = rs[-1]
        vote = f" · {r['vote']}" if r.get("vote") else ""
        rows.append(f"- **최근 판결** {r['date']} · {r.get('court') or ''}{vote} — {r.get('decision_kr') or ''}")
    elif c.get("events"):
        e = c["events"][-1]
        rows.append(f"- **최근 움직임** {e['date']} — {e['text']}")
    if c.get("impact_kr"):
        rows.append(f"- **선거 영향** {c['impact_kr']}")
    rows.append(f'- **확인** <span class="mu">최근 확인 {c.get("last_checked") or "—"} · 상태 갱신 {c.get("status_updated") or "—"}</span>')
    return "\n".join(["::: {.glance}", "**한눈에 보기**", ""] + rows + [":::"])


RESULT_CLS = {"원고 승": "win", "원고 패": "lose", "일부": "mixed"}


def litigation_md(L):
    """소송별 카드: 맨 위 요약표 → 사건마다 쟁점 한 줄, 원고|피고 주장 나란히, 법원 판단(결과 배지)."""
    def badge_r(r):
        return f'<span class="res res-{RESULT_CLS.get(r.get("result"), "mixed")}">{r.get("result") or "—"}</span>'
    rows = ["| 사건 | 쟁점 | 최종 결과 |", "|---|---|---|"]
    for l in L:
        last = l["rulings"][-1] if l.get("rulings") else {}
        rows.append(f"| {cell(l['name'])} | {cell(l['issue_kr'])} | {badge_r(last)} {cell(last.get('court'))} |")
    out = ["## 소송별 쟁점과 주장", "", '<p class="mu">원고·피고의 주장을 나란히 두고, 그 아래에 법원 판단을 시간순으로 적었습니다.</p>', "",
           "\n".join(rows), "", ": {.lit-table}", ""]
    for l in L:
        out += ["::: {.lit-card}", f"### {l['name']}", "",
                f'<p class="mu">{l.get("court") or ""}</p>', "",
                f"**쟁점** — {l['issue_kr']}", "",
                "::: {.fold}",
                ":::: {.claims}", "::::: {.claim-p}", f"**원고** · {l.get('plaintiffs') or ''}", ""]
        out += [f"- {x}" for x in l.get("plaintiff_claims") or []] or ["- (주장 요지 미확인)"]
        out += ["", ":::::", "::::: {.claim-d}", f"**피고** · {l.get('defendants') or ''}", ""]
        out += [f"- {x}" for x in l.get("defendant_claims") or []] or ['- <span class="mu">별도로 확인한 주장 없음</span>']
        out += ["", ":::::", "::::", "", "**법원 판단**", ""]
        for r in l.get("rulings") or []:
            vote = f" · {r['vote']}" if r.get("vote") else ""
            out.append(f"- {badge_r(r)} <b class=\"d\">{r.get('date') or '날짜 미확인'}</b> {r.get('court') or ''}{vote} — {r.get('summary_kr') or ''}")
            out += [f"    - {p}" for p in r.get("points") or []]
            if r.get("note_kr"):
                out.append(f"    - *{r['note_kr']}*")
        out += ["", ":::", ":::", ""]
    return "\n".join(out)


def ruling_md(r):
    head = f"### {r['date']} · {r.get('court') or ''}" + (f" · {r['vote']}" if r.get("vote") else "")
    lines = [head, "", "::: {.fold}", f"**결론** — {r.get('decision_kr') or '미확인'}", ""]
    ops = [opinion_line("다수의견", r.get("majority"))]
    ops += [opinion_line("보충의견", o) for o in r.get("concurrences") or []]
    ops += [opinion_line("반대의견", o) for o in r.get("dissents") or []]
    ops = [x for x in ops if x]
    if ops:
        lines += ops + [""]
    tail = []
    if r.get("url"):
        tail.append(f"[{'판결문·명령' if r.get('verified') == 'primary' else '보도'}]({r['url']})")
    if r.get("verified") == "secondary":
        tail.append("2차 출처 기준(판결문 미열람)")
    if r.get("note_kr"):
        tail.append(r["note_kr"])
    if tail:
        lines.append(f'<p class="mu">{" · ".join(tail)}</p>')
    lines += ["", ":::"]
    return "\n".join(lines) + "\n"


def main():
    doc = json.loads((REPO / "data" / "cases.json").read_text())
    items = doc["items"]
    G = Glossary()
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    shutil.rmtree(GEN, ignore_errors=True); GEN.mkdir()
    shutil.rmtree(CASES, ignore_errors=True); CASES.mkdir()

    # 개요: 상태별 건수 · 다가오는 기일 · 최근 2주 움직임
    cnt = Counter(c["status"] for c in items)
    # 상태 상자 = 필터 버튼(assets/filter.js). 아래 목록의 data-status 로 보이기/숨기기.
    o = [f'<div class="kpis" role="group" aria-label="상태로 거르기">' + "".join(
        f'<button type="button" class="kpi" data-filter="{s}" aria-pressed="false"><div class="n">{cnt.get(s, 0)}</div>'
        f'<div class="l">{badge(s)}</div></button>' for s in STATUS_ORDER)
        + f'<button type="button" class="kpi" data-filter="all" aria-pressed="true"><div class="n">{len(items)}</div>'
          f'<div class="l">전체 사건</div></button></div>\n',
        f'<p class="mu">기준 {doc.get("as_of")} · 상자를 누르면 그 상태의 사건만 보입니다 · 상태 정의는 [자료와 방법](about.qmd)</p>\n',
        '<ul class="case-filter">'] + [
        f'<li data-status="{c["status"]}">{badge(c["status"])} <a href="cases/{c["id"]}.html">{c["title_kr"]}</a>'
        f' <span class="mu">— {c.get("status_kr") or ""}</span></li>'
        for c in sorted(sorted(items, key=lambda c: c.get("last_date") or "", reverse=True), key=lambda c: STATUS_ORDER.index(c["status"]))] + ['</ul>\n']
    up = sorted((c for c in items if c.get("next_date") and dt.date.fromisoformat(c["next_date"]) >= today - dt.timedelta(days=3)),
                key=lambda c: c["next_date"])
    o.append("\n## 다가오는 기일\n")
    o += [f"- <b class=\"d\">{c['next_date']}</b> [{c['title_kr']}](cases/{c['id']}.qmd) — {c.get('next_kr') or ''}" for c in up] \
        or ["- 날짜가 정해진 다음 기일이 없습니다. 각 사건의 「다음」 칸에 날짜 미정 절차가 적혀 있습니다."]
    recent = sorted(((e, c) for c in items for e in c.get("events", [])
                     if dt.date.fromisoformat(e["date"]) >= today - dt.timedelta(days=14)), key=lambda z: z[0]["date"], reverse=True)
    o.append("\n\n## 최근 2주 움직임\n")
    o += [ev_line(e, c) for e, c in recent] or ["- 최근 2주 안에 기록된 움직임이 없습니다."]
    (GEN / "overview.md").write_text(G.page("\n".join(o) + "\n", box=False))

    # 사건표
    rows = sorted(items, key=lambda c: (c.get("last_date") or ""), reverse=True)
    t = ["| 분류 | 사건 | 지역 | 상태 | 현재 상태 | 최근 | 다음 |", "|---|---|---|---|---|---|---|"]
    t += [f"| {cell(c['category'])} | [{cell(c['title_kr'])}](cases/{c['id']}.qmd) | {states_kr(c)} | {badge(c['status'])} | "
          f"{cell(c.get('status_kr'))} | {cell(c.get('last_date'))} | {cell(c.get('next_kr'))} |" for c in rows]
    (GEN / "table.md").write_text(f'<p class="mu">기준 {doc.get("as_of")} · {len(items)}건 · 최근 움직임 순</p>\n\n'
                                  + "\n".join(t) + "\n\n: {.cases-table}\n")

    # 날짜별 기록
    allev = sorted(((e, c) for c in items for e in c.get("events", [])), key=lambda z: z[0]["date"], reverse=True)
    (GEN / "log.md").write_text(G.page("\n".join(ev_line(e, c) for e, c in allev) + "\n", box=False))
    (GEN / "glossary.md").write_text(G.glossary_md())

    # 사건 상세
    for c in items:
        src = " · ".join(f"[{s['label']}]({s['url']})" for s in c.get("sources") or [])
        body = [
            "---", f'title: "{c["title_kr"].replace(chr(34), chr(39))}"',
            f'subtitle: "{c["category"]} · {states_kr(c)}"', "---", "",
            glance_md(c), "",
            f'<p class="mu">{c.get("name_en") or ""} · {c.get("court") or ""}</p>', "",
            "## 쟁점", "", c.get("summary_kr") or "", "",
        ]
        lit_done = False
        for d in c.get("detail") or []:   # 쟁점 상세(선택): [{"heading", "md"}] — 지도 비교·배경 등
            if d["heading"] in ("앞으로", "확인하지 못한 것") and c.get("litigation") and not lit_done:
                body += [litigation_md(c["litigation"]), "## 앞으로와 미확인 사항", ""]
                lit_done = True
            md = d["md"]
            lead = ""
            if md.startswith("!["):            # 그림은 접지 않고 위에 둔다
                cut = md.find("\n\n")
                lead, md = (md, "") if cut < 0 else (md[:cut], md[cut + 2:])
            body += [f"### {d['heading']}", "", lead, ""] + (fold(md) if md.strip() else [])
        if c.get("litigation") and not lit_done:
            body += [litigation_md(c["litigation"])]
        if c.get("rulings"):
            body += ["## 판결 내용", ""] + [ruling_md(r) for r in sorted(c["rulings"], key=lambda r: r["date"], reverse=True)]
        body += ["## 시간순 기록", ""] + fold("\n".join(["::: {.timeline}"] + [ev_line(e) for e in reversed(c.get("events", []))] + [":::"]))
        if src:
            body += ["## 주요 출처", ""] + fold(src)
        body.append(f'<p class="mu">최근 확인 {c.get("last_checked") or "—"} · 상태 갱신 {c.get("status_updated") or "—"} · [사건표로](../cases.qmd)</p>')
        (CASES / f"{c['id']}.qmd").write_text(G.page("\n".join(body) + "\n", root="../"))
    print(f"gen_pages: 사건 {len(items)}쪽 · 다가오는 기일 {len(up)} · 최근 2주 이벤트 {len(recent)} · 전체 이벤트 {len(allev)}")


def annotate_briefings():
    """배포 작업 공간에서만 쓴다(Actions): briefings/*.md 에 용어 풀이를 달아 덮어쓴다. 커밋하지 않는다."""
    G = Glossary()
    for p in sorted((REPO / "briefings").glob("20??-??-??.md")):
        p.write_text(G.page(p.read_text(), root="../"))
    print("annotate_briefings: 완료")


if __name__ == "__main__":
    import sys
    annotate_briefings() if "--briefings" in sys.argv else main()
