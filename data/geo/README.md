# 미주리 하원 선거구 경계 (그림용, 30m 단순화)
- `mo_cd_2022.geojson` — 2022년 지도(HB 2909). 미국 인구조사국 Cartographic Boundary 2024, 제119대 의회 선거구(cb_2024_us_cd119_500k) 중 미주리(STATEFP 29). https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip
- `mo_cd_2025.geojson` — 2025년 지도(HB 1). 미주리 행정청(Office of Administration) 재획정실 GIS, LEGIS/CongressHouseDistricts_2025 MapServer layer 3. https://gis.mo.gov/arcgis/rest/services/LEGIS/CongressHouseDistricts_2025/MapServer/3 (2026-10-10 취득)
- 표시용으로 UTM 15N에서 30m 허용오차로 단순화했다. 면적·인구 계산에는 원본을 쓸 것.
- 그림: `scripts/fig_missouri_maps.py` → `assets/figures/missouri_maps.png`
