"""
验证Z轴穿透是否真的解决：
1. 找一个之前锚定在高架上的POI
2. 看它现在锚定在哪
3. 从这个POI节点出发，能不能走地面路
"""
import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph.graphml'))
G.graph['crs'] = 'epsg:4326'
for u,v,k,d in G.edges(keys=True, data=True):
    d['impedance'] = float(d.get('impedance', 0))

# 读修复后的投影
pa = pd.read_csv(os.path.join(POI, 'poi_anchored.csv'))

# 找之前锚定在高架上的POI（现在应该不在高架上了）
print("="*60)
print("验证1：现在还有多少POI锚定在高架桥上？")
print("="*60)

bridge_now = 0
for idx, row in pa.iterrows():
    u, v = row['nearest_u'], row['nearest_v']
    if G.has_edge(u, v):
        ed = G.get_edge_data(u, v)
        d = ed[list(ed.keys())[0]]
        if d.get('bridge') and d.get('highway') in ('trunk','trunk_link','motorway','motorway_link'):
            bridge_now += 1

print(f"锚定在高架桥上的POI: {bridge_now} / {len(pa)} ({bridge_now/len(pa)*100:.1f}%)")

print("\n" + "="*60)
print("验证2：抽一个之前有问题的POI，看它现在的连通性")
print("="*60)

# 找一个住宅类POI，看它锚定的边是什么类型
sample = pa[pa['category']=='住宅'].iloc[0]
u, v = sample['nearest_u'], sample['nearest_v']
ed = G.get_edge_data(u, v)
d = ed[list(ed.keys())[0]]
print(f"POI: {sample.get('name', '')}")
print(f"锚定边: {u} -> {v}")
print(f"  highway: {d.get('highway')}")
print(f"  bridge: {d.get('bridge', '无')}")
print(f"  length: {d.get('length', 0):.0f}m")

# 从这个POI节点出发，看它的出边
print(f"\n从节点 {u} 出发的出边:")
for _, v2, k2, d2 in G.out_edges(u, keys=True, data=True):
    print(f"  -> {v2} [{d2.get('highway')}, bridge={d2.get('bridge', '无')}, {d2.get('length',0):.0f}m]")

print(f"\n从节点 {v} 出发的出边:")
for _, v2, k2, d2 in G.out_edges(v, keys=True, data=True):
    print(f"  -> {v2} [{d2.get('highway')}, bridge={d2.get('bridge', '无')}, {d2.get('length',0):.0f}m]")

print("\n" + "="*60)
print("验证3：从POI出发，能走到附近地面路吗？")
print("="*60)

# 从u出发，走100m内能不能到非bridge的路
lengths = nx.single_source_dijkstra_path_length(G, u, cutoff=200, weight='impedance')
ground_reachable = False
for node, dist in lengths.items():
    for _, v2, k2, d2 in G.out_edges(node, keys=True, data=True):
        hw = d2.get('highway', '')
        br = d2.get('bridge', None)
        if not br and hw in ('residential','tertiary','secondary','unclassified','living_street'):
            ground_reachable = True
            break
    if ground_reachable:
        break

print(f"从POI出发200m内能到达地面路: {ground_reachable}")
print(f"200m内可达节点数: {len(lengths)}")
