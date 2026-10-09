// 개요의 상태 상자를 필터로: 누른 상태의 사건만 목록에 남긴다("전체 사건"은 모두).
document.addEventListener("DOMContentLoaded", () => {
  const btns = document.querySelectorAll(".kpis .kpi[data-filter]");
  const rows = document.querySelectorAll(".case-filter li[data-status]");
  btns.forEach(b => b.addEventListener("click", () => {
    const f = b.dataset.filter;
    btns.forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    rows.forEach(r => { r.hidden = !(f === "all" || r.dataset.status === f); });
  }));
});
