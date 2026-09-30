# -*- coding: utf-8 -*-
"""
测试高德 Key 是否能用
运行方式：右键 -> Run 'test_amap'
"""
import requests

KEY = ""

# 测一发：在武汉江汉路附近 1km 内找 POI
r = requests.get(
    "https://restapi.amap.com/v3/place/around",
    params={
        "key": KEY,
        "location": "114.30,30.59",   # 武汉江汉广场附近
        "radius": 1000,
        "offset": 5,
        "extensions": "all",
    },
    timeout=10,
).json()

print("status:", r.get("status"))       # 1=成功  0=失败
print("count:", r.get("count"))         # 命中总数
print("info:", r.get("info"))           # 失败原因会写在这里

if r.get("pois"):
    print("\n前 5 个 POI：")
    for p in r["pois"]:
        print(f"  - {p['name']}  ({p['location']})  [{p['typecode']}]")
else:
    print("\n没有返回 POI")
