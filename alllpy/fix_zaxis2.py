"""
Z轴穿透真正修复：
删掉高架桥边，用纯地面图重新投影POI
"""
import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox
from shapely.geometry import Point

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

print("加载图...")
G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph_pop.graphml'))
G.graph['crs'] = 'epsg:4326'

# 复制一个地面图，删掉高架桥边
G_ground = G.copy()
removed = 0
edges_to_remove = []
for u, v, k, d in G_ground.edges(keys=True, data=True):
    hw = d.get('highway', '')
    br = d.get('bridge', None)
    if br and hw in ('trunk', 'trunk_link', 'motorway', 'motorway_link'):
        edges_to_remove.append((u, v, k))
        removed += 1

for u, v, k in edges_to_remove:
    G_ground.remove_edge(u, v, k)

print(f"删掉高架桥边: {removed} 条")
print(f"地面图剩余: {G_ground.number_of_edges()} 条边")

# 读poi_anchored
pa = pd.read_csv(os.path.join(POI, 'poi_anchored.csv'))
print(f"总POI: {len(pa)}")

# 找出锚定在高架桥上的POI
needs_fix = []
for idx, row in pa.iterrows():
    u, v = row['nearest_u'], row['nearest_v']
    if G.has_edge(u, v):
        edge_dict = G.get_edge_data(u, v)
        first_key = list(edge_dict.keys())[0]
        edge_data = edge_dict[first_key]
        hw = edge_data.get('highway', '')
        br = edge_data.get('bridge', None)
        if br and hw in ('trunk', 'trunk_link', 'motorway', 'motorway_link'):
            needs_fix.append(idx)

print(f"需要修复的POI: {len(needs_fix)}")

# 用地面图重新投影这些POI
fixed = 0
for idx in needs_fix:
    row = pa.loc[idx]
    lon, lat = row['lon'], row['lat']
    
    # 在地面图上找最近边
    try:
        nearest = ox.distance.nearest_edges(G_ground, X=[lon], Y=[lat], return_dist=True)
        u_new, v_new, k_new = nearest[0][0]
        dist_new = nearest[1][0]
        
        # 如果新边距离在150m内，接受
        if dist_new < 150:
            pa.at[idx, 'nearest_u'] = u_new
            pa.at[idx, 'nearest_v'] = v_new
            fixed += 1
    except:
        pass

print(f"\n修复结果:")
print(f"  成功重新锚定到地面路: {fixed} / {len(needs_fix)}")
print(f"  失败（地面图上找不到）: {len(needs_fix) - fixed}")

# 统计修复后还有多少在高架上
bridge_after = 0
for idx, row in pa.iterrows():
    u, v = row['nearest_u'], row['nearest_v']
    if G.has_edge(u, v):
        edge_dict = G.get_edge_data(u, v)
        first_key = list(edge_dict.keys())[0]
        edge_data = edge_dict[first_key]
        br = edge_data.get('bridge', None)
        hw = edge_data.get('highway', '')
        if br and hw in ('trunk', 'trunk_link', 'motorway', 'motorway_link'):
            bridge_after += 1

print(f"\n修复后仍在高架桥上的POI: {bridge_after} ({bridge_after/len(pa)*100:.1f}%)")

# 保存
pa.to_csv(os.path.join(POI, 'poi_anchored_fixed.csv'), index=False, encoding='utf-8-sig')
print(f"已存 poi_anchored_fixed.csv")
