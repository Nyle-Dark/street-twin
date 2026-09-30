# -*- coding: utf-8 -*-
"""
不重抓API，根据已有typecode反查一二三级类目
输入: 现有5个POI CSV（有typecode字段）
输出: 补了 type_l1/l2/l3 的新CSV（覆盖原文件）
"""

import os
import pandas as pd

POI_DIR = r"C:\Users\temp\Desktop\静态数字\POI"

# typecode -> (一级类目, 二级类目, 三级类目)
# 基于高德POI分类规则 + 我们实际抓到的编码
TYPE_MAP = {
    # 12 商务住宅
    "120302": ("商务住宅", "住宅区", "住宅小区"),
    "120300": ("商务住宅", "住宅区", ""),
    "120201": ("商务住宅", "楼宇", "商务写字楼"),
    "120200": ("商务住宅", "楼宇", ""),
    "120000": ("商务住宅", "", ""),

    # 06 购物服务（已用API实测验证）
    "060100": ("购物服务", "商场", "购物中心"),      # 实测：万象城、万汇MALL
    "060101": ("购物服务", "商场", "购物中心"),
    "060102": ("购物服务", "商场", "普通商场"),
    "060400": ("购物服务", "超级市场", ""),
    "060401": ("购物服务", "超级市场", "超市"),
    "060706": ("购物服务", "专营店", ""),
    "060000": ("购物服务", "", ""),

    # 15 交通设施服务
    "150000": ("交通设施服务", "", ""),
    "150100": ("交通设施服务", "机场", ""),
    "150200": ("交通设施服务", "火车站", ""),
    "150300": ("交通设施服务", "港口码头", ""),

    # 07 生活服务
    "070000": ("生活服务", "", ""),
    "070100": ("生活服务", "便民服务", ""),

    # 05 餐饮服务
    "050000": ("餐饮服务", "", ""),
    "050100": ("餐饮服务", "中餐厅", ""),
    "050118": ("餐饮服务", "中餐厅", "地方风味餐厅"),
    "050112": ("餐饮服务", "中餐厅", "家常菜"),
    "050201": ("餐饮服务", "外国餐厅", ""),

    # 17 公司企业
    "170000": ("公司企业", "", ""),
    "170200": ("公司企业", "公司", ""),

    # 16 金融保险服务
    "160000": ("金融保险服务", "", ""),

    # 10 住宿服务
    "100000": ("住宿服务", "", ""),
    "100100": ("住宿服务", "酒店宾馆", ""),
}


def fill_type(row):
    """根据typecode填一二三级类目"""
    tc = str(row.get("typecode", "")).strip()
    # 多类别用|分隔，取第一个
    if "|" in tc:
        tc = tc.split("|")[0]

    if tc in TYPE_MAP:
        l1, l2, l3 = TYPE_MAP[tc]
    else:
        # 尝试前4位匹配（中类）
        tc4 = tc[:4] if len(tc) >= 4 else tc
        found = False
        for code, (a, b, c) in TYPE_MAP.items():
            if code.startswith(tc4) and len(tc4) >= 4:
                l1, l2, l3 = a, b, ""
                found = True
                break
        if not found:
            # 尝试前2位匹配（大类）
            tc2 = tc[:2] if len(tc) >= 2 else tc
            big_map = {
                "12": "商务住宅", "06": "购物服务", "15": "交通设施服务",
                "07": "生活服务", "05": "餐饮服务", "17": "公司企业",
                "16": "金融保险服务", "10": "住宿服务",
            }
            l1 = big_map.get(tc2, "")
            l2, l3 = "", ""
    return pd.Series([l1, l2, l3])


def process_file(fn):
    path = os.path.join(POI_DIR, fn)
    if not os.path.exists(path):
        print(f"  [跳过] {fn} 不存在")
        return

    df = pd.read_csv(path)
    print(f"\n处理 {fn}: {len(df)} 条")

    # 检查是否已有type_l1列，有就删掉重填
    if "type_l1" in df.columns:
        df = df.drop(columns=["type_l1", "type_l2", "type_l3"])
        print(f"  检测到已有类目列，删除后重新填充")

    # 按文件名给兜底类别（抓这个CSV时用的主typecode）
    fallback = {
        "POI_住宅.csv": ("商务住宅", "住宅区", "住宅小区"),
        "POI_写字楼.csv": ("商务住宅", "楼宇", "商务写字楼"),
        "POI_商圈.csv": ("购物服务", "商场", "购物中心"),
        "POI_交通枢纽.csv": ("交通设施服务", "交通枢纽", ""),
        "POI_真实网点.csv": ("购物服务", "零售", ""),
    }
    fb = fallback.get(fn, ("", "", ""))

    # 填一二三级类目
    df[["type_l1", "type_l2", "type_l3"]] = df.apply(fill_type, axis=1)

    # 填充失败的用文件名兜底
    mask = df["type_l1"] == ""
    df.loc[mask, ["type_l1", "type_l2", "type_l3"]] = fb
    filled = len(df) - mask.sum()
    print(f"  填充成功: {filled}/{len(df)} ({filled/len(df)*100:.1f}%)")
    if mask.sum() > 0:
        print(f"  {mask.sum()} 条用文件名兜底: {fb[0]};{fb[1]};{fb[2]}")

    # 覆盖保存
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  已保存: {path}")


if __name__ == "__main__":
    files = [
        "POI_住宅.csv",
        "POI_写字楼.csv",
        "POI_商圈.csv",
        "POI_交通枢纽.csv",
        "POI_真实网点.csv",
    ]
    print("=" * 50)
    print("根据typecode反查一二三级类目（不调API）")
    print("=" * 50)
    for fn in files:
        process_file(fn)
    print("\n完成！")
