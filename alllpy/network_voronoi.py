"""
第三步：网络泰森多边形（多源 Dijkstra）
1. 加载已锚定的图
2. 以所有 generator 为多源起点
3. 对每个节点找最近仓和最短阻抗
4. 检测边界边（两端点属不同仓）
5. 统计各仓负荷
"""
import os
import pandas as pd
import networkx as nx
import osmnx as ox

ROAD_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

# === 加载图 ===
print("=== 1. 加载图 ===")
G = ox.load_graphml(os.path.join(ROAD_DIR, 'wuhan_graph_anchored.graphml'))
G.graph['crs'] = 'epsg:4326'
print(f"节点: {G.number_of_nodes()}, 边: {G.number_of_edges()}")

# 修复 graphml 类型问题
for n in G.nodes:
    # is_generator: graphml 存成了字符串，转回布尔
    v = G.nodes[n].get('is_generator', False)
    G.nodes[n]['is_generator'] = (v == True or v == 'True')
    # demand_weight: 转回 float
    G.nodes[n]['demand_weight'] = float(G.nodes[n].get('demand_weight', 0))

for u, v, k, data in G.edges(keys=True, data=True):
    data['impedance'] = float(data.get('impedance', 0))
    data['length'] = float(data.get('length', 0))

# === 找所有 generator 节点 ===
gen_nodes = [n for n in G.nodes if G.nodes[n]['is_generator']]
print(f"generator 节点: {len(gen_nodes)}")

# === 多源 Dijkstra ===
print("\n=== 2. 多源 Dijkstra ===")

# 对每个 generator 跑 Dijkstra，记录每个节点最近的仓
nearest_gen = {}      # node -> generator node
min_dist = {}         # node -> 最短阻抗

for gen in gen_nodes:
    # single_source_dijkstra_path_length 返回 {node: dist}
    lengths = nx.single_source_dijkstra_path_length(G, gen, weight='impedance')
    for node, d in lengths.items():
        if node not in min_dist or d < min_dist[node]:
            min_dist[node] = d
            nearest_gen[node] = gen

print(f"覆盖节点: {len(nearest_gen)} / {G.number_of_nodes()}")

# === 统计各仓负荷 ===
print("\n=== 3. 各仓负荷统计 ===")
from collections import defaultdict
facility_load = defaultdict(float)
facility_nodes = defaultdict(int)
facility_maxdist = defaultdict(float)

for node in G.nodes:
    if node in nearest_gen:
        gen = nearest_gen[node]
        demand = G.nodes[node].get('demand_weight', 0)
        facility_load[gen] += demand
        facility_nodes[gen] += 1
        d = min_dist.get(node, 0)
        if d > facility_maxdist[gen]:
            facility_maxdist[gen] = d

# 仓名映射
gen_info = pd.read_csv(os.path.join(POI_DIR, 'generators.csv'))

results = []
for gen in sorted(facility_load.keys(), key=lambda x: -facility_load[x]):
    brand = G.nodes[gen].get('brand', '?')
    results.append({
        'node': gen,
        'brand': brand,
        'nodes_covered': facility_nodes[gen],
        'total_demand': round(facility_load[gen], 1),
        'max_dist_m': round(facility_maxdist[gen], 1),
    })

df_result = pd.DataFrame(results)
print(df_result.to_string(index=False))

# === 检测边界边 ===
print("\n=== 4. 检测边界边 ===")
boundary_edges = []
for u, v, k, data in G.edges(keys=True, data=True):
    gen_u = nearest_gen.get(u)
    gen_v = nearest_gen.get(v)
    if gen_u is not None and gen_v is not None and gen_u != gen_v:
        boundary_edges.append({
            'u': u, 'v': v, 'key': k,
            'gen_u': gen_u, 'gen_v': gen_v,
            'impedance': data.get('impedance', 0),
        })

print(f"边界边数: {len(boundary_edges)}")

# === 保存 ===
print("\n=== 5. 保存 ===")
df_result.to_csv(os.path.join(POI_DIR, 'facility_load.csv'),
                 index=False, encoding='utf-8-sig')
pd.DataFrame(boundary_edges).to_csv(os.path.join(POI_DIR, 'boundary_edges.csv'),
                                    index=False, encoding='utf-8-sig')

# 存每个节点的最近仓
node_assign = pd.DataFrame([
    {'node': n, 'nearest_gen': nearest_gen.get(n, -1),
     'dist': round(min_dist.get(n, -1), 1)}
    for n in G.nodes
])
node_assign.to_csv(os.path.join(POI_DIR, 'node_assign.csv'),
                   index=False, encoding='utf-8-sig')

print("已存: facility_load.csv, boundary_edges.csv, node_assign.csv")
print("\n=== 完成 ===")
