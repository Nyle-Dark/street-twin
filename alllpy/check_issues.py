"""
核查两个问题：
1. Z轴穿透：POI被锚定到bridge/motorway高架上
2. 单向限行：Dijkstra是否沿出边方向
"""
import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

print("="*60)
print("核查1：Z轴穿透——POI锚定在bridge/motorway上")
print("="*60)

G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph_pop.graphml'))
G.graph['crs'] = 'epsg:4326'

# 读poi_anchored
pa = pd.read_csv(os.path.join(POI, 'poi_anchored.csv'))
print(f"总POI: {len(pa)}")

# 检查每个POI锚定的边的highway和bridge属性
bridge_count = 0
motorway_count = 0
bridge_pois = []

for _, row in pa.iterrows():
    u, v = row['nearest_u'], row['nearest_v']
    if G.has_edge(u, v):
        # 取第一条边
        edge_dict = G.get_edge_data(u, v)
        if edge_dict:
            first_key = list(edge_dict.keys())[0]
            edge_data = edge_dict[first_key]
        hw = edge_data.get('highway', '')
        br = edge_data.get('bridge', None)
        
        if br:
            bridge_count += 1
            if len(bridge_pois) < 20:
                bridge_pois.append({
                    'name': row.get('name', ''),
                    'category': row.get('category', ''),
                    'highway': hw,
                    'bridge': br,
                    'u': u, 'v': v
                })
        
        if hw in ('motorway', 'motorway_link', 'trunk', 'trunk_link'):
            motorway_count += 1

print(f"\n锚定在bridge=yes边上的POI: {bridge_count} ({bridge_count/len(pa)*100:.1f}%)")
print(f"锚定在motorway/trunk边上的POI: {motorway_count} ({motorway_count/len(pa)*100:.1f}%)")

print("\n锚定在bridge上的POI样例（前20个）:")
bp = pd.DataFrame(bridge_pois)
if len(bp) > 0:
    print(bp[['name', 'category', 'highway', 'bridge']].to_string(index=False))

print("\n" + "="*60)
print("核查2：单向限行兼容")
print("="*60)

# 检查图是否有向
print(f"图类型: {'有向图' if G.is_directed() else '无向图'}")

# 数单向边
oneway_count = sum(1 for _,_,_,d in G.edges(keys=True,data=True) if d.get('oneway'))
print(f"单向边数: {oneway_count} / {G.number_of_edges()} ({oneway_count/G.number_of_edges()*100:.1f}%)")

# 验证：Dijkstra是否沿出边方向
# 取一个generator节点，看它的出边和入边
gen_df = pd.read_csv(os.path.join(POI, 'generators.csv'))
sample_gen = gen_df.iloc[0]['node']
out_edges = list(G.out_edges(sample_gen, keys=True, data=True))
in_edges = list(G.in_edges(sample_gen, keys=True, data=True))
print(f"\n样例仓节点 {sample_gen}:")
print(f"  出边: {len(out_edges)} 条")
print(f"  入边: {len(in_edges)} 条")

# 验证Dijkstra从这个节点出发，能否到达单向对面
# 如果是单向道，从A到B能走，但B到A不能
print("\n验证单向道：")
for u, v, k, d in out_edges[:3]:
    hw = d.get('highway', '')
    ow = d.get('oneway', False)
    length = d.get('length', 0)
    # 检查反向是否存在
    reverse_exists = G.has_edge(v, u)
    print(f"  {u} -> {v} [{hw}, oneway={ow}, {length:.0f}m], 反向存在={reverse_exists}")
