"""
从 road_attrs.csv + nodes.csv 重建路网图，计算阻抗，存 graphml。
不用再拉 OSM 数据。
"""
import os
import pandas as pd
import networkx as nx
import osmnx as ox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1) 读节点坐标
print("=== 1. 读节点 ===")
nodes_df = pd.read_csv(os.path.join(BASE_DIR, 'nodes.csv'))
print(f"节点数: {len(nodes_df)}")
print(nodes_df.head())

# 2) 读边表
print("\n=== 2. 读边表 ===")
edges_df = pd.read_csv(os.path.join(BASE_DIR, 'road_attrs.csv'))
print(f"边数: {len(edges_df)}")
print(edges_df.columns.tolist())

# 3) 建 MultiDiGraph
print("\n=== 3. 建图 ===")
G = nx.MultiDiGraph()

# 加节点
for _, row in nodes_df.iterrows():
    nid = int(row['node_id'])
    G.add_node(nid, x=row['lon'], y=row['lat'])

# 加边
for _, row in edges_df.iterrows():
    u = int(row['u'])
    v = int(row['v'])
    k = int(row['key']) if pd.notna(row['key']) else 0
    length = row['length'] if pd.notna(row['length']) else 0

    # highway 可能是字符串
    hw = row['highway'] if pd.notna(row['highway']) else 'residential'

    G.add_edge(u, v, key=k,
               length=length,
               highway=hw,
               oneway=row['oneway'] if pd.notna(row['oneway']) else '双向',
               bridge=row['bridge'] if pd.notna(row['bridge']) else None,
               tunnel=row['tunnel'] if pd.notna(row['tunnel']) else None,
               name=row['name'] if pd.notna(row['name']) else None)

print(f"图节点数: {G.number_of_nodes()}")
print(f"图边数: {G.number_of_edges()}")

# 4) 算阻抗（PDF 方法3：Length × Class_Penalty × Environment_Penalty）
print("\n=== 4. 计算阻抗 ===")

CLASS_PENALTY = {
    'motorway': 0.9,
    'trunk': 1.0, 'primary': 1.0,
    'trunk_link': 1.1, 'primary_link': 1.1,
    'secondary': 1.2, 'secondary_link': 1.2,
    'tertiary': 1.5, 'tertiary_link': 1.5,
    'busway': 1.5,
    'unclassified': 1.8,
    'residential': 2.0,
    'living_street': 2.5,
}

impedances = []
for u, v, k, data in G.edges(keys=True, data=True):
    hw = data.get('highway', 'residential')
    cp = CLASS_PENALTY.get(hw, 2.0)
    has_bridge = bool(data.get('bridge'))
    has_tunnel = bool(data.get('tunnel'))
    ep = 1.1 if (has_bridge or has_tunnel) else 1.0
    length = data.get('length', 0)
    data['impedance'] = round(length * cp * ep, 3)
    data['class_penalty'] = cp
    data['env_penalty'] = ep
    impedances.append(data['impedance'])

print(f"阻抗统计: 最短 {min(impedances):.1f}m, 最长 {max(impedances):.1f}m, 平均 {sum(impedances)/len(impedances):.1f}m")

# 按 highway 分组统计
print("\n按道路等级阻抗统计:")
hw_groups = {}
for u, v, k, data in G.edges(keys=True, data=True):
    hw = data.get('highway', 'residential')
    if hw not in hw_groups:
        hw_groups[hw] = []
    hw_groups[hw].append(data['impedance'])

for hw in sorted(hw_groups.keys(), key=lambda x: -len(hw_groups[x])):
    vals = hw_groups[hw]
    print(f"  {hw:20s}: {len(vals):5d} 条, 平均阻抗 {sum(vals)/len(vals):8.1f}m")

# 5) 存 graphml
print("\n=== 5. 保存 graphml ===")
graphml_path = os.path.join(BASE_DIR, 'wuhan_graph.graphml')
ox.save_graphml(G, graphml_path)
print(f"已保存: {graphml_path}")
print(f"文件大小: {os.path.getsize(graphml_path)/1024/1024:.1f} MB")

print("\n=== 完成 ===")
