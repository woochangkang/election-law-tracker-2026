#!/usr/bin/env python3
"""미주리 하원 선거구 2022년 지도 vs 2025년 지도 비교 그림 → assets/figures/missouri_maps.png

위: 주 전체(왼쪽 2022, 오른쪽 2025) · 아래: 캔자스시티 확대. 색은 예상 우세 정당(2022년 6–2, 2025년 공화당 기대 7–1)이고,
5선거구는 굵은 테두리로 강조한다. 경계 출처는 data/geo/README.md.
로컬 실행 전용(geopandas 필요, 배포 작업에서는 돌지 않음): python3 scripts/fig_missouri_maps.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False

REPO = Path(__file__).resolve().parent.parent
D_DISTRICTS = {"2022": {1, 5}, "2025": {1}}          # 예상 민주 우세 선거구
BLUE = ["#2f6db3", "#6f9fd8"]
REDS = ["#c0392b", "#d9534f", "#e57368", "#ef9488", "#c45a4a", "#d97a6c", "#b03a2e"]
CITIES = {"캔자스시티": (-94.58, 39.10), "세인트루이스": (-90.20, 38.63), "제퍼슨시티": (-92.17, 38.58), "스프링필드": (-93.29, 37.21)}
CITY_OFF = {"캔자스시티": (-0.05, 0.12, "right"), "세인트루이스": (0.08, -0.13, "left"), "제퍼슨시티": (-0.08, -0.05, "right"), "스프링필드": (0.08, -0.13, "left")}
EXTRA_ZOOM_LABELS = {"2025": [(4, -94.59, 39.02)]}   # 2025년 4구는 Troost 서쪽의 폭 2km 띠(경도 -94.60~-94.58)와 남동쪽이 이어진 모양 → 서쪽 띠를 화살표로 표시
KC_BOX = (-94.78, 38.78, -94.10, 39.40)              # 캔자스시티 확대 범위(경도·위도)


def colors(g, year):
    out, bi, ri = [], 0, 0
    for d in g.district:
        if d in D_DISTRICTS[year]:
            out.append(BLUE[bi % 2]); bi += 1
        else:
            out.append(REDS[ri % len(REDS)]); ri += 1
    return out


def draw(ax, g, year, zoom=False):
    g = g.sort_values("district")
    g.plot(ax=ax, color=colors(g, year), edgecolor="white", linewidth=0.8 if not zoom else 1.4)
    g[g.district == 5].boundary.plot(ax=ax, color="#111", linewidth=2.2 if not zoom else 3)
    if zoom:
        ax.set_xlim(KC_BOX[0], KC_BOX[2]); ax.set_ylim(KC_BOX[1], KC_BOX[3])
        clip = g.clip(KC_BOX)
        for _, r in clip.iterrows():
            if r.geometry.is_empty or r.geometry.area < 0.004:
                continue
            p = r.geometry.representative_point()
            ax.text(p.x, p.y, f"{r.district}구", ha="center", va="center", fontsize=13, weight="bold", color="white")
        for d, x, y in EXTRA_ZOOM_LABELS.get(year, []):
            ax.annotate(f"{d}구\n(Troost 서쪽 띠)", xy=(x, y), xytext=(x - 0.12, y - 0.06), fontsize=11, weight="bold",
                        ha="center", color="#222", arrowprops=dict(arrowstyle="->", color="#222", lw=1.3))
        ax.plot(*CITIES["캔자스시티"], "o", color="#111", ms=4)
        ax.text(CITIES["캔자스시티"][0] - 0.02, CITIES["캔자스시티"][1] + 0.02, "캔자스시티 도심", fontsize=10, ha="right",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    else:
        for _, r in g.iterrows():
            p = r.geometry.representative_point()
            ax.text(p.x, p.y, str(r.district), ha="center", va="center", fontsize=15, weight="bold", color="white")
        for n, (x, y) in CITIES.items():
            dx, dy, ha = CITY_OFF[n]
            ax.plot(x, y, "o", color="#111", ms=3)
            ax.text(x + dx, y + dy, n, fontsize=9, color="#222", ha=ha,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
        x0, y0, x1, y1 = KC_BOX
        ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color="#111", lw=0.8, ls="--")
    ax.set_aspect(1 / 0.78)   # 위도 38.5° 근처 경위도 비율 보정
    ax.set_axis_off()


def main():
    g22 = gpd.read_file(REPO / "data/geo/mo_cd_2022.geojson")
    g25 = gpd.read_file(REPO / "data/geo/mo_cd_2025.geojson")
    fig, axes = plt.subplots(2, 2, figsize=(13, 12.5), gridspec_kw={"height_ratios": [1.15, 1]})
    draw(axes[0, 0], g22, "2022"); draw(axes[0, 1], g25, "2025")
    draw(axes[1, 0], g22, "2022", zoom=True); draw(axes[1, 1], g25, "2025", zoom=True)
    axes[0, 0].set_title("2022년 지도 (HB 2909) — 공화 6 : 민주 2\n2022·2024년 선거, 2026년 11월 선거에 사용", fontsize=13)
    axes[0, 1].set_title("2025년 지도 (HB 1) — 공화당 기대 7 : 1\n2026년 8월 예비선거에만 사용, 법원이 11월 사용 막음", fontsize=13)
    axes[1, 0].set_title("캔자스시티 확대 — 2022년: 도심 전체가 5구", fontsize=12)
    axes[1, 1].set_title("캔자스시티 확대 — 2025년: Troost Ave. 서쪽은 4구, 동쪽은 5구", fontsize=12)
    fig.suptitle("미주리 연방 하원 선거구: 2022년 지도와 2025년 지도", fontsize=17, weight="bold", y=0.995)
    fig.text(0.5, 0.012,
             "파랑 = 민주 우세 예상 · 빨강 = 공화 우세 예상(선거구 구분을 위해 명도를 달리함) · 굵은 테두리 = 5선거구(Cleaver 의원 지역구) · 점선 = 아래 확대 범위\n"
             "경계: 2022년 미국 인구조사국(제119대 의회 선거구), 2025년 미주리 행정청 재획정실 GIS. 우세 정당은 보도된 예상 의석(6–2, 7–1) 기준.",
             ha="center", fontsize=9.5, color="#444")
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    out = REPO / "assets/figures/missouri_maps.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, facecolor="white")
    print("저장:", out)


if __name__ == "__main__":
    main()
