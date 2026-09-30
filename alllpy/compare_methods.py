"""
对比实验：网络泰森多边形 vs 传统欧氏缓冲圆
"""
import os
import math
import pandas as pd
import numpy as np
import networkx as nx
import osmnx as ox

ROAD_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

G = ox.load_graphml(os.path.join(ROAD_DIR, 'wuhan_graph_pop.graphml'))
G.graph['crs'] = 'epsg:4326'

# 修复类型
for n in G.nodes:
    G.nodes[n]['is_generator'] = (G.nodes[n].get('is_generator') == True or
                                   G.nodes[n].get('is_generator') == 'True')
    dw = G.nodes[n].get('demand_weight', 0)
    try: dw = float(dw)
    except: dw = 0.0
    if np.isnan(dw): dw = 0.0
    G.nodes[n]['demand_weight'] = dw
for u, v, k, data in G.edges(keys=True, data=True):
    data['impedance'] = float(data.get('impedance', 0))

gen_df = pd.read_csv(os.path.join(POI_DIR, 'generators.csv'))
gen_nodes = gen_df['node'].tolist()

# === 方法1：网络泰森多边形（已有结果）===
print("=== 方法1：网络泰森多边形 ===")
nearest_gen_net = {}
min_dist_net = {}
for gen in gen_nodes:
    lengths = nx.single_source_dijkstra_path_length(G, gen, weight='impedance')
    for node, d in lengths.items():
        if node not in min_dist_net or d < min_dist_net[node]:
            min_dist_net[node] = d
            nearest_gen_net[node] = gen

# === 方法2：欧氏缓冲圆（直线距离）===
print("\n=== 方法2：欧氏缓冲圆 ===")
# 每个仓坐标
gen_coords = {}
for gen in gen_nodes:
    gen_coords[gen] = (G.nodes[gen]['x'], G.nodes[gen]['y'])

# 每个节点算到所有仓的直线距离
nearest_gen_euc = {}
min_dist_euc = {}
for node in G.nodes:
    nlon = G.nodes[node]['x']
    nlat = G.nodes[node]['y']
    best_gen = None
    best_d = float('inf')
    for gen, (glon, glat) in gen_coords.items():
        # 直线距离（米）
        d = math.sqrt((nlon-glon)**2 + (nlat-glat)**2) * 111000
        if d < best_d:
            best_d = d
            best_gen = gen
    nearest_gen_euc[node] = best_gen
    min_dist_euc[node] = best_d

# === 对比差异 ===
print("\n=== 对比结果 ===")
diff_nodes = 0
for node in G.nodes:
    if nearest_gen_net.get(node) != nearest_gen_euc.get(node):
        diff_nodes += 1

print(f"总节点: {G.number_of_nodes()}")
print(f"两种方法归属不同的节点: {diff_nodes} ({diff_nodes/G.number_of_nodes()*100:.1f}%)")

# 距离差异对比
diffs = []
for node in G.nodes:
    if node in min_dist_net and node in min_dist_euc:
        diffs.append(min_dist_euc[node] - min_dist_net[node])

print(f"欧氏距离 vs 网络阻抗:")
print(f"  欧氏平均: {np.mean([min_dist_euc[n] for n in G.nodes if n in min_dist_euc]):.0f}m")
print(f"  网络平均: {np.mean([min_dist_net[n] for n in G.nodes if n in min_dist_net]):.0f}m")
print(f"  差异: 欧氏比网络近 {np.mean(diffs):.0f}m ({np.mean(diffs)/np.mean([min_dist_net[n] for n in G.nodes if n in min_dist_net])*100:.0f}%)")

# === 保存对比结果 ===
df = pd.DataFrame([
    {
        'method': '网络泰森多边形',
        'covered': len(nearest_gen_net),
        'avg_dist': round(np.mean([min_dist_net[n] for n in G.nodes if n in min_dist_net]), 0),
    },
    {
        'method': '欧氏缓冲圆',
        'covered': len(nearest_gen_euc),
        'avg_dist': round(np.mean([min_dist_euc[n] for n in G.nodes]), 0),
    },
])
df.to_csv(os.path.join(POI_DIR, 'network_vs_euclidean.csv'),
          index=False, encoding='utf-8-sig')
print("\n已存 network_vs_euclidean.csv")
print("\n=== 完成 ===")
