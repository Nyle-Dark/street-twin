# -*- coding: utf-8 -*-
"""
双向边成对校验（独立测试脚本）
用法：在 PyCharm 里直接运行本文件，或在终端执行：
    py D:/PythonPRO/PyCharmProjects/PythonProject/load/check_bidir.py
依赖：osmnx 已安装；OSM 数据有缓存（首次运行会自动下载，稍慢）
"""
import os
import osmnx as ox
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ox.settings.use_cache = True
ox.settings.cache_folder = r'D:\PythonPRO\PyCharmProjects\PythonProject\load\cache'

# 与 network.py 保持同一几何：北/西/南各外扩约 1.5 km
third_ring = Polygon([
    (114.169, 30.605), (114.200, 30.630), (114.280, 30.674), (114.360, 30.655),
    (114.400, 30.630), (114.425, 30.580), (114.430, 30.525), (114.330, 30.461),
    (114.230, 30.490), (114.169, 30.550),
])
guanggu = box(114.42, 30.465, 114.56, 30.555)
aoi = unary_union([third_ring, guanggu])

G = ox.graph_from_polygon(
    aoi, network_type="drive", simplify=True, truncate_by_edge=True
)
gdf_edges = ox.graph_to_gdfs(G, nodes=False)

# 2) 构造边表：u/v/key 变成正式列，oneway 转成 单向/双向
edges = gdf_edges.reset_index()
edges['oneway'] = edges['oneway'].map({True: '单向', False: '双向'}).fillna('未知')

# 3) 成对校验：双向边 (u,v) 必须存在反向边 (v,u)
bidir = edges[edges['oneway'] == '双向'].copy()
pairs = set(zip(bidir['u'], bidir['v']))
bidir['has_rev'] = [(v, u) in pairs for u, v in zip(bidir['u'], bidir['v'])]
missing = bidir[~bidir['has_rev']]

print('=' * 60)
print('① 总量核对')
print('  双向边:', len(bidir), '| 单向边:', (edges['oneway'] == '单向').sum(),
      '| 总边数:', len(edges))
print('  双向 + 单向 =', len(bidir) + (edges['oneway'] == '单向').sum(), '(应等于总边数)')
print('=' * 60)

print('② 成对校验')
print('  双向边总数:', len(bidir))
print('  缺失反向边的条数:', len(missing), '（应为 0）')
print('=' * 60)

# 4) 抽一条双向边，正反两条都打印出来
sample = bidir.iloc[0]
su, sv = int(sample['u']), int(sample['v'])
print('③ 抽样展示 (u=%d, v=%d)：' % (su, sv))
forward = edges[(edges['u'] == su) & (edges['v'] == sv)]
reverse = edges[(edges['u'] == sv) & (edges['v'] == su)]
print('  正向边:')
print(forward[['u', 'v', 'key', 'oneway', 'highway', 'length']].to_string(index=False))
print('  反向边:')
print(reverse[['u', 'v', 'key', 'oneway', 'highway', 'length']].to_string(index=False))
print('=' * 60)

# 5) 如果存在缺失，打印完整清单；否则给出结论
if len(missing):
    print('④ 缺失反向边的双向边清单（异常，需处理）:')
    print(missing[['u', 'v', 'key', 'highway', 'length']].to_string(index=False))
else:
    print('④ 结论: 所有双向边都有反向边，有向图方向完整，最短路可以放心按边方向算。')
