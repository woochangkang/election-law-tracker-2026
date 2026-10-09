# election-law-tracker-2026

2026 미국 중간선거(상원·하원·주지사)의 선거 법·제도 분쟁 트래커 — 행정명령·연방 규칙·우편투표·유권자 명부·재획정·선거자금·후보 자격 소송의 현재 상태.

- 공개 사이트: https://woochangkang.github.io/election-law-tracker-2026/
- 배포: `main` push → `.github/workflows/publish.yml` → build.py(병합) → gen_pages.py(페이지 생성) → Quarto render → GitHub Pages

## 일일 파이프라인
1. 수집: 클라우드 루틴이 `prompts/legal_daily.md`를 따라 웹 조사 → `inbox/YYYY-MM-DD.json` + `briefings/YYYY-MM-DD.md`
2. 병합: `python3 scripts/build.py` — 항목 단위 검증(출처 URL 필수·category/status/tier enum) → `data/cases.json`. 거부 항목은 `inbox/YYYY-MM-DD.rejected.json`. 처리한 inbox는 내용 해시로 `data/build_state.json`에 기록(고친 파일만 재적용, 사람이 직접 고친 cases.json을 옛 inbox가 되돌리지 않음).
3. 커밋·push → Actions 배포

## 데이터
- `data/cases.json` 사건 목록. 사건 = 소송·행정명령·규칙·법안 하나. 필드: id, category, title_kr, name_en, court, states, status(pending·active·enjoined·ruled·closed), status_kr, next_date, next_kr, summary_kr, impact_kr, events[{date,text,url,outlet,tier}], sources, last_date(자동), last_checked, status_updated
- 2026-09-25~10-09 자료는 us-elections-2026.github.io 의 `data/legal_tracker.json`에서 이관(14건). URL 없는 이벤트는 당시 _NIS 상원·전국 일일 브리핑 기록이 근거.
- 사람이 고칠 때는 `data/cases.json`을 직접 편집하고 push.

로컬 확인: `python3 scripts/build.py && python3 scripts/gen_pages.py && quarto render && python3 -m http.server -d _site`

## 접속 차단 도메인 알림
- 클라우드 루틴 환경은 Network access = Custom. 허용 목록은 `data/allowed_domains.txt`(환경 설정과 같이 유지).
- 배포 때 `scripts/blocked_report.py`가 inbox의 audit에서 막힌 사이트를 모아 `docs/blocked_domains.md`를 갱신하고, 최근 실행에 허용 목록 밖 도메인이 있으면 이슈 「네트워크 차단 도메인 — 허용 목록 추가 필요」에 날짜별 댓글(붙여넣기용 목록)을 단다.
