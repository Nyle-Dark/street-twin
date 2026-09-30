"""
add_population.py
人口栅格采样 + 需求当量分摊 + Z轴穿透修复后投影
"""
import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox
from collections import defaultdict

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

print("=== 1. 加载路网 ===")
G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph.graphml'))
G.graph['crs'] = 'epsg:4326'
for u,v,k,d in G.edges(keys=True, data=True):
    d['impedance'] = float(d.get('impedance', 0))
print(f"节点: {G.number_of_nodes()}, 边: {G.number_of_edges()}")

print("\n=== 2. 读修复后的POI投影（Z轴穿透已修复） ===")
pa = pd.read_csv(os.path.join(POI, 'poi_anchored.csv'))
print(f"POI: {len(pa)}")

# 重置节点需求
for n in G.nodes:
    G.nodes[n]['demand_weight'] = 0.0

print("\n=== 3. 分摊需求到节点 ===")
CLASS_WEIGHT = {
    '住宅': 1.0,
    '写字楼': 0.8,
    '商圈': 2.5,
    '交通枢纽': 3.0,
    '中百罗森': 0.5,
}

for _, row in pa.iterrows():
    cat = row.get('category', '')
    w = CLASS_WEIGHT.get(cat, 0.5)
    pop = float(row.get('pop', 0))
    pop_factor = min(pop / 5000, 1.0) if pop > 0 else 0
    final_w = w * (1 + 0.5 * pop_factor)
    
    u, v = row['nearest_u'], row['nearest_v']
    G.nodes[u]['demand_weight'] += final_w / 2
    G.nodes[v]['demand_weight'] += final_w / 2

total = sum(G.nodes[n]['demand_weight'] for n in G.nodes)
print(f"总需求: {total:.1f}")

print("\n=== 4. 读仓 ===")
gen_df = pd.read_csv(os.path.join(POI, 'generators.csv'))
gen_nodes = gen_df['node'].tolist()
print(f"仓: {len(gen_nodes)}")

print("\n=== 5. 多源Dijkstra ===")
nearest_gen = {}
min_dist = {}
for gen in gen_nodes:
    lengths = nx.single_source_dijkstra_path_length(G, gen, weight='impedance')
    for node, d in lengths.items():
        if node not in min_dist or d < min_dist[node]:
            min_dist[node] = d
            nearest_gen[node] = gen

covered = len(nearest_gen)
print(f"覆盖: {covered}/{G.number_of_nodes()} ({covered/G.number_of_nodes()*100:.1f}%)")

print("\n=== 6. 各仓负荷 ===")
load = defaultdict(float)
nodes_cov = defaultdict(int)
maxd = defaultdict(float)
for node in nearest_gen:
    g = nearest_gen[node]
    load[g] += G.nodes[node]['demand_weight']
    nodes_cov[g] += 1
    if min_dist[node] > maxd[g]:
        maxd[g] = min_dist[node]

results = []
for g in gen_nodes:
    results.append({
        'node': g,
        'brand': gen_df[gen_df['node']==g]['brand'].iloc[0] if g in gen_df['node'].values else '',
        'nodes': nodes_cov[g],
        'demand': load[g],
        'max_dist': maxd[g]
    })
rdf = pd.DataFrame(results).sort_values('demand', ascending=False)
print(rdf.head(10).to_string(index=False))

print("\n=== 7. 保存 ===")
rdf.to_csv(os.path.join(POI, 'facility_load_v3.csv'), index=False, encoding='utf-8-sig')

print("\n=== 8. 三场景对比 ===")
hema = gen_df[gen_df['brand']=='盒马鲜生']['node'].tolist()
zhongbai = gen_df[gen_df['brand']=='中百仓储']['node'].tolist()
luosen = pa[pa['category']=='中百罗森']
luosen_nodes = list(set(luosen['nearest_u'].tolist()))
luosen_nodes = [n for n in luosen_nodes if n in G.nodes]

def run_scenario(gen_list, label):
    ng = {}
    md = {}
    for gen in gen_list:
        lengths = nx.single_source_dijkstra_path_length(G, gen, weight='impedance')
        for node, d in lengths.items():
            if node not in md or d < md[node]:
                md[node] = d
                ng[node] = gen
    ld = defaultdict(float)
    md_max = defaultdict(float)
    for node in ng:
        g = ng[node]
        ld[g] += G.nodes[node]['demand_weight']
        if md[node] > md_max[g]:
            md_max[g] = md[node]
    total_d = sum(ld.values())
    avg_maxd = np.mean(list(md_max.values())) if md_max else 0
    overload = sum(1 for g in ld if ld[g] > total_d/len(ld)*1.5) if ld else 0
    idle = sum(1 for g in ld if ld[g] < total_d/len(ld)*0.5) if ld else 0
    return {'label': label, 'n_gen': len(gen_list), 'covered': len(ng),
            'total_demand': total_d, 'avg_max_dist': avg_maxd,
            'overload': overload, 'idle': idle}

a = run_scenario(hema, "场景A：盒马鲜生(31仓)")
b = run_scenario(zhongbai, "场景B：中百仓储(49仓)")
c = run_scenario(luosen_nodes, "场景C：中百罗森便利店(%d仓)" % len(luosen_nodes))

sc = pd.DataFrame([a, b, c])
print(sc.to_string(index=False))
sc.to_csv(os.path.join(POI, 'three_scenario_compare_v2.csv'), index=False, encoding='utf-8-sig')

print("\n完成！")
