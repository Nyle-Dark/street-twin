"""
GHSL GHS-POP 100m 人口数据 - 武汉区域裁剪与统计
数据文件: GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R6_C30.tif
分辨率: 3 arc-second (~100m)
坐标系: WGS84 (EPSG:4326)
年份: 2025

使用方法:
  1. 把 .tif 文件放在本脚本同目录（或修改下方 INPUT_TIF 路径）
  2. pip install rasterio numpy
  3. python clip_wuhan_ghsl.py
"""

import rasterio
from rasterio.mask import mask
import numpy as np
import os

# ==================== 配置区 ====================

# 输入文件（和脚本同目录就直接写文件名，否则写完整路径）
INPUT_TIF = r"C:\Users\temp\Desktop\GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R6_C30.tif"

# 输出文件
OUTPUT_TIF = "wuhan_ghsl_pop_100m_2025.tif"

# 武汉研究范围（经纬度，WGS84）
# 覆盖：三环内 + 光谷中心城
# 如需调整，改这四个数即可
WUHAN_BBOX = {
    "min_lon": 114.05,   # 西边界（汉阳/东西湖）
    "max_lon": 114.70,   # 东边界（光谷中心城以东）
    "min_lat": 30.35,    # 南边界（沌口/江夏北部）
    "max_lat": 30.72,    # 北边界（盘龙城/汉口北）
}

# ================================================


def main():
    # 检查文件
    if not os.path.exists(INPUT_TIF):
        print(f"[错误] 找不到文件: {INPUT_TIF}")
        print("请把tif文件放在脚本同目录，或修改 INPUT_TIF 为完整路径")
        return

    # ========== 1. 读取原始瓦片，打印基本信息 ==========
    print("=" * 60)
    print("1. 读取 GHSL GHS-POP 原始瓦片")
    print("=" * 60)
    with rasterio.open(INPUT_TIF) as src:
        print(f"文件名:     {INPUT_TIF}")
        print(f"尺寸:       {src.width} x {src.height} 像素")
        print(f"坐标系:     {src.crs}")
        print(f"瓦片范围:   经度 {src.bounds.left:.2f}-{src.bounds.right:.2f}, "
              f"纬度 {src.bounds.bottom:.2f}-{src.bounds.top:.2f}")
        print(f"像素大小:   {src.transform[0]:.6f} x {abs(src.transform[4]):.6f} 度 (约100m)")
        print(f"NoData值:   {src.nodata}")

        data_full = src.read(1)
        # GHSL 数据用 -200 表示水域/无数据，但元数据可能没标注
        nodata = -200
        valid = data_full > 0  # 人口数不可能为负或零
        if valid.any():
            print(f"瓦片总人口: {data_full[valid].sum():,.0f} 人")
            print(f"有效像素:   {valid.sum():,}")

    # ========== 2. 构建武汉范围多边形 ==========
    min_lon = WUHAN_BBOX["min_lon"]
    max_lon = WUHAN_BBOX["max_lon"]
    min_lat = WUHAN_BBOX["min_lat"]
    max_lat = WUHAN_BBOX["max_lat"]

    wuhan_geom = {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]]
    }

    # ========== 3. 裁剪武汉区域 ==========
    print("\n" + "=" * 60)
    print("2. 裁剪武汉区域")
    print("=" * 60)
    print(f"裁剪范围: 经度 {min_lon}-{max_lon}, 纬度 {min_lat}-{max_lat}")

    with rasterio.open(INPUT_TIF) as src:
        out_image, out_transform = mask(
            src,
            [wuhan_geom],
            crop=True,
            nodata=-200
        )
        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        })

    # ========== 4. 保存裁剪结果 ==========
    with rasterio.open(OUTPUT_TIF, "w", **out_meta) as dst:
        dst.write(out_image)
    print(f"已保存: {OUTPUT_TIF}")

    # ========== 5. 武汉区域人口统计 ==========
    print("\n" + "=" * 60)
    print("3. 武汉区域人口统计")
    print("=" * 60)

    with rasterio.open(OUTPUT_TIF) as src:
        data = src.read(1)
        valid_mask = data > 0  # 人口数不可能为负，-200是水域NoData

        if not valid_mask.any():
            print("[警告] 裁剪区域内没有有效数据！")
            print("请检查经纬度范围，或确认原始瓦片覆盖该区域")
            return

        valid_data = data[valid_mask]
        total_pop = float(valid_data.sum())
        pixel_count = int(valid_mask.sum())
        # 每个像素约 100m x 100m = 0.01 km^2
        area_km2 = pixel_count * 0.01

        print(f"裁剪后尺寸:   {src.width} x {src.height} 像素")
        print(f"有效像素数:   {pixel_count:,}")
        print(f"覆盖面积:     {area_km2:.1f} km^2")
        print(f"总人口:       {total_pop:,.0f} 人")
        print(f"平均密度:     {total_pop / area_km2:,.0f} 人/km^2")
        print(f"最高密度:     {valid_data.max():.1f} 人/像素 (100m格)")
        print(f"中位数密度:   {np.median(valid_data):.1f} 人/像素")

    # ========== 6. 后续使用提示 ==========
    print("\n" + "=" * 60)
    print("4. 后续使用")
    print("=" * 60)
    print(f"输出文件: {os.path.abspath(OUTPUT_TIF)}")
    print("")
    print("在 POI 需求当量估算中，读取每个 POI 缓冲区的人口：")
    print("""
    import rasterio
    from rasterio.mask import mask

    with rasterio.open("wuhan_ghsl_pop_100m_2025.tif") as src:
        # poi_buffer 是 POI 的缓冲区多边形 (GeoJSON 格式)
        out_img, _ = mask(src, [poi_buffer], crop=True)
        pop = out_img[out_img != src.nodata].sum()
        # pop 就是这个 POI 缓冲区内的估算人口
    """)

    print("完成！")


if __name__ == "__main__":
    main()
