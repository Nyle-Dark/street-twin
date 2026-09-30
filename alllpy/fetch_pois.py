# -*- coding: utf-8 -*-
"""
武汉三环内 + 光谷中心城 POI 分网格抓取脚本
- 数据源：高德 Web 服务 API
- 研究区：三环线围合区（细网格 0.015°）+ 光谷中心城（粗网格 0.02°）
- 输出：5 个 CSV（住宅/写字楼/商圈/交通枢纽/真实网点）
"""

import requests
import time
import os
import pandas as pd
from datetime import datetime

# ============ 配置区 ============
KEY = ""
AROUND_URL = "https://restapi.amap.com/v3/place/around"

# 研究区网格（经纬度范围 + 步长）
# 三环内主城：密网格
RING3 = dict(lon_min=114.18, lon_max=114.43,
             lat_min=30.46, lat_max=30.67, step=0.015)
# 光谷中心城：疏网格
GUANGGU = dict(lon_min=114.42, lon_max=114.56,
               lat_min=30.465, lat_max=30.555, step=0.02)

# 要抓的 POI 类别：(关键词, typecode, 输出文件名)
# typecode 已用 API 实测验证（2026-09-25）
#   120302 住宅小区 / 120201 商务写字楼 / 060100 商业街
#   150200 火车站 / 150300 港口码头（武汉轮渡）
POI_TYPES = [
    ("住宅小区",   "120302",                "POI_住宅.csv"),
    ("商务写字楼", "120201",                "POI_写字楼.csv"),
    ("商业街",     "060100",                "POI_商圈.csv"),
    ("火车站",     "150200",                "POI_交通枢纽.csv"),
    ("港口码头",   "150300",                "POI_交通枢纽.csv"),
]

# 真实连锁网点（用关键词搜，不按 typecode）
STORE_KEYWORDS = ["盒马鲜生", "中百仓储", "中百罗森"]

OUTPUT_DIR = r"C:\Users\temp\Desktop\静态数字\POI"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 限流参数
SLEEP_BETWEEN = 0.25   # 每次请求间隔（秒），高德 QPS 限制 50，留余量
RETRY_TIMES = 3
RADIUS = 1500         # 每个网格周边搜索半径（米）
PAGE_SIZE = 25        # 高德 around API 每页最多 25 条
# ================================


def build_grid(bbox: dict) -> list:
    """根据 bbox 生成网格中心点坐标列表"""
    pts = []
    lat = bbox["lat_min"]
    while lat <= bbox["lat_max"]:
        lon = bbox["lon_min"]
        while lon <= bbox["lon_max"]:
            pts.append((round(lon, 5), round(lat, 5)))
            lon += bbox["step"]
        lat += bbox["step"]
    return pts


# 两个片区的网格合并成一个列表
GRID_POINTS = build_grid(RING3) + build_grid(GUANGGU)
print(f"[初始化] 三环内网格 {len(build_grid(RING3))} 个，"
      f"光谷网格 {len(build_grid(GUANGGU))} 个，合计 {len(GRID_POINTS)} 个")


def amap_around(lon: float, lat: float, keywords: str = "",
                types: str = "", page: int = 1) -> dict:
    """调用高德周边搜索 API，带重试"""
    params = {
        "key": KEY,
        "location": f"{lon},{lat}",
        "keywords": keywords,
        "types": types,
        "radius": RADIUS,
        "offset": PAGE_SIZE,
        "page": page,
        "extensions": "all",
        "output": "json",
    }
    for attempt in range(RETRY_TIMES):
        try:
            r = requests.get(AROUND_URL, params=params, timeout=10)
            data = r.json()
            if data.get("status") == "1":
                return data
            else:
                print(f"  [高德报错] {data.get('info')} "
                      f"(等待 2s 后重试 {attempt+1}/{RETRY_TIMES})")
                time.sleep(2)
        except Exception as e:
            print(f"  [请求异常] {e} (重试 {attempt+1}/{RETRY_TIMES})")
            time.sleep(2)
    return {"pois": [], "count": "0"}


def parse_pois(data: dict, category: str, brand: str = "") -> list:
    """把高德返回的 JSON 解析成扁平字典列表"""
    rows = []
    for p in data.get("pois", []):
        loc = p.get("location", "0,0")
        lon, lat = loc.split(",") if "," in loc else ("0", "0")
        # type 字段格式: "商务住宅;楼宇;商务写字楼"（大类;中类;小类）
        poi_type = p.get("type", "") or ""
        type_parts = poi_type.split(";") if poi_type else ["", "", ""]
        # 补到3段，防止有的POI只有两级
        while len(type_parts) < 3:
            type_parts.append("")
        rows.append({
            "name": p.get("name", ""),
            "lon": float(lon),
            "lat": float(lat),
            "address": p.get("address", "") or "",
            "category": category,
            "brand": brand,
            "typecode": p.get("typecode", ""),
            "type_l1": type_parts[0],   # 一级类目
            "type_l2": type_parts[1],   # 二级类目
            "type_l3": type_parts[2],   # 三级类目
        })
    return rows


def fetch_category(keywords: str, types: str, out_file: str,
                   category_label: str):
    """抓某一类 POI，分网格遍历，断点续抓"""
    out_path = os.path.join(OUTPUT_DIR, out_file)

    # 断点续抓：如果已有文件，读取旧数据追加；空文件/损坏文件则跳过
    all_rows = []
    if os.path.exists(out_path) and os.path.getsize(out_path) > 50:
        try:
            old = pd.read_csv(out_path, encoding="utf-8-sig")
            if len(old) > 0:
                all_rows = old.to_dict("records")
                print(f"[续抓] 已存在 {out_file}，{len(old)} 条，将在其基础上追加")
        except pd.errors.EmptyDataError:
            print(f"[续抓] {out_file} 是空文件，从头抓")

    total = len(GRID_POINTS)
    for i, (lon, lat) in enumerate(GRID_POINTS, 1):
        # 每个网格最多翻 40 页（1000 条上限），实际一般 1-2 页就空了
        page = 1
        while True:
            data = amap_around(lon, lat, keywords=keywords, types=types, page=page)
            rows = parse_pois(data, category_label)
            all_rows.extend(rows)

            count = int(data.get("count", 0))
            if page * PAGE_SIZE >= count or len(data.get("pois", [])) == 0:
                break
            page += 1
            time.sleep(SLEEP_BETWEEN)

        # 进度打印
        if i % 20 == 0 or i == total:
            print(f"  [{category_label}] 进度 {i}/{total}，累计 {len(all_rows)} 条")

        # 每 20 个网格落一次盘（防崩）
        if i % 20 == 0:
            pd.DataFrame(all_rows).to_csv(out_path, index=False, encoding="utf-8-sig")

        time.sleep(SLEEP_BETWEEN)

    # 最终落盘 + 去重
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["name", "lon", "lat"])
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[完成] {category_label}: {len(df)} 条（去重后） -> {out_path}")


def fetch_stores():
    """抓真实连锁门店（盒马/中百），用关键词搜，不分网格直接城市级搜"""
    out_path = os.path.join(OUTPUT_DIR, "POI_真实网点.csv")
    all_rows = []

    for brand in STORE_KEYWORDS:
        print(f"\n[抓门店] {brand}")
        # 城市级文字搜索 + 翻页（门店数少，远不到 1000 条上限）
        page = 1
        while True:
            params = {
                "key": KEY,
                "keywords": brand,
                "city": "武汉",
                "citylimit": "true",
                "offset": PAGE_SIZE,
                "page": page,
                "extensions": "all",
            }
            for attempt in range(RETRY_TIMES):
                try:
                    r = requests.get("https://restapi.amap.com/v3/place/text",
                                     params=params, timeout=10)
                    data = r.json()
                    if data.get("status") == "1":
                        break
                    time.sleep(2)
                except Exception as e:
                    print(f"  [异常] {e}")
                    time.sleep(2)
            else:
                data = {"pois": [], "count": "0"}

            rows = parse_pois(data, category="连锁网点", brand=brand)
            all_rows.extend(rows)

            count = int(data.get("count", 0))
            if page * PAGE_SIZE >= count or len(data.get("pois", [])) == 0:
                break
            page += 1
            time.sleep(SLEEP_BETWEEN)

        time.sleep(SLEEP_BETWEEN)

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["name", "lon", "lat"])
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[完成] 真实网点: {len(df)} 条 -> {out_path}")


if __name__ == "__main__":
    print(f"\n========== 开始抓取 {datetime.now()} ==========\n")

    # 1. 抓四类 POI
    for keywords, types, out_file in POI_TYPES:
        print(f"\n>>> 抓取类别: {keywords}")
        fetch_category(keywords, types, out_file, category_label=keywords)

    # 2. 抓真实连锁门店
    print("\n>>> 抓取真实连锁门店")
    fetch_stores()

    print(f"\n========== 全部完成 {datetime.now()} ==========")
    print(f"输出目录: {OUTPUT_DIR}")
