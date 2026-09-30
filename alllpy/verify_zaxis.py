"""
验证Z轴穿透修复效果：
1. 确认路网里高架还在
2. 确认POI已经锚定到地面路
3. 从一个仓出发，看最短路径是否经过高架
"""
import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph_pop.graphml'))
G.graph['crs'] = 'epsg:4326'
for u,v,k,d in G.edges(keys=True, data=True):
    d['impedance'] = float(d.get('impedance', 0))

print("="*60)
print("验证1：路网里高架还在吗？")
print("="*60)

bridge_edges = 0
trunk_edges = 0
for u,v,k,d in G.edges(keys=True, data=True):
    if d.get('bridge'):
        bridge_edges += 1
    if d.get('highway') in ('trunk', 'trunk_link', 'motorway', 'motorway_link'):
        trunk_edges += 1

print(f"桥边: {bridge_edges} 条")
print(f"快速路边: {trunk_edges} 条")
print(f"路网完整: {G.number_of_edges()} 条边")

print("\n" + "="*60)
print("验证2：修复后POI还在高架上吗？")
print("="*60)

pa = pd.read_csv(os.path.join(POI, 'poi_anchored_fixed.csv'))
print(f"总POI: {len(pa)}")

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

print(f"修复后仍在高架桥上的POI: {bridge_after} ({bridge_after/len(pa)*100:.1f}%)")

print("\n" + "="*60)
print("验证3：从仓出发，最短路径走高架吗？")
print("="*60)

# 取一个仓
gen_df = pd.read_csv(os.path.join(POI, 'generators.csv'))
gen_node = gen_df.iloc[0]['node']
print(f"仓节点: {gen_node}")

# 找一个远处的需求点
target = None
for node in G.nodes:
    dw = float(G.nodes[node].get('demand_weight', 0))
    if node != gen_node and dw > 0:
        target = node
        break

# 算最短路径
path = nx.shortest_path(G, gen_node, target, weight='impedance')
path_len = nx.shortest_path_length(G, gen_node, target, weight='impedance')

# 检查路径上有没有高架
has_bridge = False
for i in range(len(path)-1):
    u, v = path[i], path[i+1]
    if G.has_edge(u, v):
        edge_dict = G.get_edge_data(u, v)
        first_key = list(edge_dict.keys())[0]
        d = edge_dict[first_key]
        if d.get('bridge') and d.get('highway') in ('trunk', 'trunk_link', 'motorway', 'motorway_link'):
            has_bridge = True
            break

print(f"路径长度: {path_len:.0f}m")
print(f"路径经过高架桥: {has_bridge}")
print(f"结论: {'配送车可以走高架' if has_bridge else '配送车走地面路'}")
