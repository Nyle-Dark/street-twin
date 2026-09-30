"""
三仓场景对比
场景A：盒马鲜生单独当仓
场景B：中百仓储单独当仓
场景C：中百仓储当仓，中百罗森转为需求点
"""
import os
import math
import pandas as pd
import numpy as np
import networkx as nx
import osmnx as ox

ROAD_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

# 加载带人口的图
G = ox.load_graphml(os.path.join(ROAD_DIR, 'wuhan_graph_pop.graphml'))
G.graph['crs'] = 'epsg:4326'

# 修复类型
for n in G.nodes:
    G.nodes[n]['is_generator'] = (G.nodes[n].get('is_generator') == True or
                                   G.nodes[n].get('is_generator') == 'True')
    dw = G.nodes[n].get('demand_weight', 0)
    try:
        dw = float(dw)
    except (ValueError, TypeError):
        dw = 0.0
    if np.isnan(dw):
        dw = 0.0
    G.nodes[n]['demand_weight'] = dw
for u, v, k, data in G.edges(keys=True, data=True):
    data['impedance'] = float(data.get('impedance', 0))

# 读 generator 表
gen_df = pd.read_csv(os.path.join(POI_DIR, 'generators.csv'))
hema_nodes = gen_df[gen_df['brand'] == '盒马鲜生']['node'].tolist()
zb_nodes = gen_df[gen_df['brand'] == '中百仓储']['node'].tolist()

# 中百罗森投影成 generator 节点（场景C用）
print("\n投影中百罗森为仓节点...")
luosen_df = pd.read_csv(os.path.join(POI_DIR, 'POI_真实网点.csv'))
luosen_df = luosen_df[luosen_df.brand == '中百罗森'].copy()
# bbox 过滤
luosen_df = luosen_df[(luosen_df.lon>=114.17)&(luosen_df.lon<=114.56)&
                       (luosen_df.lat>=30.46)&(luosen_df.lat<=30.68)]
# GCJ-02 → WGS-84
import math
def gcj02_to_wgs84(lon, lat):
    a = 6378245.0; ee = 0.00669342162296594323
    def _tlat(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
        r+=(20*math.sin(y*math.pi)+40*math.sin(y/3*math.pi))*2/3
        r+=(160*math.sin(y/12*math.pi)+320*math.sin(y*math.pi/30))*2/3
        return r
    def _tlon(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
        r+=(20*math.sin(x*math.pi)+40*math.sin(x/3*math.pi))*2/3
        r+=(150*math.sin(x/12*math.pi)+300*math.sin(x/30*math.pi))*2/3
        return r
    dlat=_tlat(lon-105,lat-35); dlon=_tlon(lon-105,lat-35)
    radlat=lat/180*math.pi; magic=1-ee*math.sin(radlat)**2
    sqrtmagic=math.sqrt(magic)
    dlat=(dlat*180)/((a*(1-ee))/(magic*sqrtmagic)*math.pi)
    dlon=(dlon*180)/(a/sqrtmagic*math.cos(radlat)*math.pi)
    return lon*2-(lon+dlon), lat*2-(lat+dlat)

conv = luosen_df.apply(lambda r: gcj02_to_wgs84(r['lon'], r['lat']), axis=1)
luosen_df['lon_wgs'] = [c[0] for c in conv]
luosen_df['lat_wgs'] = [c[1] for c in conv]

luosen_nodes = []
for _, row in luosen_df.iterrows():
    nn = ox.distance.nearest_nodes(G, X=row['lon_wgs'], Y=row['lat_wgs'])
    luosen_nodes.append(nn)
luosen_nodes = list(set(luosen_nodes))  # 去重

print(f"盒马仓: {len(hema_nodes)} 个节点")
print(f"中百仓储仓: {len(zb_nodes)} 个节点")
print(f"中百罗森仓: {len(luosen_nodes)} 个节点")

def run_voronoi(gen_list, label, demand_filter=None):
    """跑一次多源 Dijkstra
    demand_filter: None=所有节点；'luosen'=只看中百罗森节点
    """
    # 中百罗森节点列表（从 poi_anchored 提取 category=中百罗森 的节点）
    if demand_filter == 'luosen':
        anchored = pd.read_csv(os.path.join(POI_DIR, 'poi_anchored.csv'))
        luosen_u = set(anchored[anchored.category=='中百罗森'].nearest_u.tolist())
        luosen_v = set(anchored[anchored.category=='中百罗森'].nearest_v.tolist())
        target_nodes = luosen_u | luosen_v
    else:
        target_nodes = None

    # 重置节点分配
    nearest_gen = {}
    min_dist = {}
    for gen in gen_list:
        lengths = nx.single_source_dijkstra_path_length(G, gen, weight='impedance')
        for node, d in lengths.items():
            if node not in min_dist or d < min_dist[node]:
                min_dist[node] = d
                nearest_gen[node] = gen

    # 统计
    from collections import defaultdict
    load = defaultdict(float)
    nodes_cov = defaultdict(int)
    maxd = defaultdict(float)
    for node in G.nodes:
        if node in nearest_gen:
            g = nearest_gen[node]
            if target_nodes is None:
                load[g] += G.nodes[node]['demand_weight']
                nodes_cov[g] += 1
            elif node in target_nodes:
                load[g] += G.nodes[node]['demand_weight']
                nodes_cov[g] += 1
            if min_dist[node] > maxd[g]:
                maxd[g] = min_dist[node]

    total_demand = sum(load.values())
    avg_maxd = np.mean(list(maxd.values())) if maxd else 0
    overload = sum(1 for g in load if load[g] > total_demand/len(load)*1.5) if load else 0
    idle = sum(1 for g in load if load[g] < total_demand/len(load)*0.5) if load else 0

    print(f"\n=== {label} ===")
    print(f"  仓数: {len(gen_list)}")
    print(f"  覆盖节点: {len(nearest_gen)}/{G.number_of_nodes()}")
    print(f"  总需求负荷: {total_demand:.1f}")
    print(f"  平均最大到达距离: {avg_maxd:.0f}m")
    print(f"  过载仓: {overload}, 闲置仓: {idle}")

    return {
        'label': label,
        'n_gen': len(gen_list),
        'covered': len(nearest_gen),
        'total_demand': round(total_demand, 1),
        'avg_max_dist': round(avg_maxd, 0),
        'overload': overload,
        'idle': idle,
    }

# 场景A：盒马鲜生当仓
result_a = run_voronoi(hema_nodes, "场景A：盒马鲜生(31仓)")

# 场景B：中百仓储当仓
result_b = run_voronoi(zb_nodes, "场景B：中百仓储(49仓)")

# 场景C：中百罗森当仓
result_c = run_voronoi(luosen_nodes, "场景C：中百罗森便利店(344仓)")

# 汇总
print("\n=== 三场景对比汇总 ===")
df = pd.DataFrame([result_a, result_b, result_c])
print(df.to_string(index=False))
df.to_csv(os.path.join(POI_DIR, 'three_scenario_compare.csv'),
          index=False, encoding='utf-8-sig')
print("\n已存 three_scenario_compare.csv")
