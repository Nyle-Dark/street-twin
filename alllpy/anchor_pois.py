"""
第二步：POI 需求当量估算与空间锚定
1. 加载 graphml 路网图
2. 读所有 POI CSV
3. 仓分层：盒马+中百仓储=generator，中百罗森=demand
4. POI 投影到最近边（osmnx nearest_edges）
5. 算需求当量（类别权重 × 人口因子）
6. 分摊到两端节点
7. 打 generator 标签
"""
import os
import math
import pandas as pd
import networkx as nx
import osmnx as ox

# === GCJ-02(高德火星坐标) → WGS-84(OSM/GHSL坐标) 转换 ===
def gcj02_to_wgs84(lon, lat):
    """高德GCJ-02坐标转WGS-84坐标"""
    a = 6378245.0
    ee = 0.00669342162296594323

    def _transform_lat(x, y):
        ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
        ret += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
        return ret

    def _transform_lon(x, y):
        ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
        ret += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
        return ret

    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee*magic*magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglon = lon + dlon
    # 近似逆变换（迭代一次足够）
    return lon * 2 - mglon, lat * 2 - mglat

# === 路径 ===
ROAD_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI_DIR = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

# === 加载图 ===
print("=== 1. 加载路网图 ===")
G = ox.load_graphml(os.path.join(ROAD_DIR, 'wuhan_graph.graphml'))
G.graph['crs'] = 'epsg:4326'  # WGS-84
print(f"节点: {G.number_of_nodes()}, 边: {G.number_of_edges()}")

# === POI 类别基础权重（PDF：住宅1.0、写字楼0.8、枢纽0.5）===
BASE_WEIGHT = {
    '住宅': 1.0,
    '写字楼': 0.8,
    '商圈': 1.5,
    '交通枢纽': 0.5,
    '中百罗森': 0.5,  # 便利店本身需供货
}

# === 读所有 POI ===
print("\n=== 2. 读 POI ===")
all_pois = []

# 住宅
df = pd.read_csv(os.path.join(POI_DIR, 'POI_住宅.csv'))
df['category'] = '住宅'
all_pois.append(df)
print(f"住宅: {len(df)}")

# 写字楼
df = pd.read_csv(os.path.join(POI_DIR, 'POI_写字楼.csv'))
df['category'] = '写字楼'
all_pois.append(df)
print(f"写字楼: {len(df)}")

# 商圈
df = pd.read_csv(os.path.join(POI_DIR, 'POI_商圈.csv'))
df['category'] = '商圈'
all_pois.append(df)
print(f"商圈: {len(df)}")

# 交通枢纽
df = pd.read_csv(os.path.join(POI_DIR, 'POI_交通枢纽.csv'))
df['category'] = '交通枢纽'
all_pois.append(df)
print(f"交通枢纽: {len(df)}")

# 真实网点
df = pd.read_csv(os.path.join(POI_DIR, 'POI_真实网点.csv'))
print(f"\n真实网点: {len(df)}")

# 按品牌分层
hema = df[df['brand'] == '盒马鲜生'].copy()
zb_cangchu = df[df['brand'] == '中百仓储'].copy()
luosen = df[df['brand'] == '中百罗森'].copy()

print(f"  盒马鲜生: {len(hema)}")
print(f"  中百仓储: {len(zb_cangchu)}")
print(f"  中百罗森: {len(luosen)}")

# 清洗盒马：剔除烘焙/网络科技
hema = hema[~hema['name'].str.contains('烘焙|网络科技', na=False)]
# 过滤 bbox 外
hema = hema[(hema['lon'] >= 114.17) & (hema['lon'] <= 114.56) &
            (hema['lat'] >= 30.46) & (hema['lat'] <= 30.68)]
zb_cangchu = zb_cangchu[(zb_cangchu['lon'] >= 114.17) & (zb_cangchu['lon'] <= 114.56) &
                        (zb_cangchu['lat'] >= 30.46) & (zb_cangchu['lat'] <= 30.68)]
print(f"\n清洗后盒马: {len(hema)}")
print(f"清洗后中百仓储: {len(zb_cangchu)}")

# 中百罗森作为需求点
luosen['category'] = '中百罗森'
all_pois.append(luosen)

# 合并所有需求 POI
demand_pois = pd.concat(all_pois, ignore_index=True)

# === GCJ-02 → WGS-84 坐标转换（高德坐标转OSM/GHSL坐标）===
print("\n=== 坐标转换: GCJ-02 → WGS-84 ===")
converted = demand_pois.apply(lambda r: gcj02_to_wgs84(r['lon'], r['lat']), axis=1)
demand_pois['lon_wgs84'] = [c[0] for c in converted]
demand_pois['lat_wgs84'] = [c[1] for c in converted]
print(f"转换完成, 样例: ({demand_pois.iloc[0]['lon']:.6f},{demand_pois.iloc[0]['lat']:.6f}) → ({demand_pois.iloc[0]['lon_wgs84']:.6f},{demand_pois.iloc[0]['lat_wgs84']:.6f})")

# 后续用 WGS-84 坐标投影
demand_pois['lon_orig'] = demand_pois['lon']
demand_pois['lat_orig'] = demand_pois['lat']
demand_pois['lon'] = demand_pois['lon_wgs84']
demand_pois['lat'] = demand_pois['lat_wgs84']

print(f"\n总需求 POI: {len(demand_pois)}")

# === 初始化节点需求权重 ===
for node in G.nodes():
    G.nodes[node]['demand_weight'] = 0.0
    G.nodes[node]['is_generator'] = False
    G.nodes[node]['brand'] = ''

# === 投影需求 POI 到最近边 ===
print("\n=== 3. 投影需求 POI ===")
lons = demand_pois['lon'].tolist()
lats = demand_pois['lat'].tolist()

# osmnx nearest_edges: return_dist=True 时返回 (edges, distances) tuple
nearest_edges, nearest_dists = ox.distance.nearest_edges(G, X=lons, Y=lats, return_dist=True)
print(f"投影完成, POI数: {len(nearest_edges)}")

# 孤岛剔除：200m（PDF 阈值）
MAX_WALK = 200
skipped = 0
anchored = []

for i in range(len(nearest_edges)):
    u, v, key = int(nearest_edges[i][0]), int(nearest_edges[i][1]), int(nearest_edges[i][2])
    dist = float(nearest_dists[i])
    if dist > MAX_WALK:
        skipped += 1
        continue

    row = demand_pois.iloc[i]
    cat = row['category']
    w = BASE_WEIGHT.get(cat, 1.0)

    # 分摊到两端节点
    edge_len = G[u][v][key]['length']
    # dist 是点到边的最短距离，不是沿边的投影距离
    # osmnx nearest_edges 返回的 dist 是垂直距离
    # 用线性插值近似：投影点在边上的位置
    # 简化：按到两端节点的直线距离比例分摊
    import math
    dx_u = row['lon'] - G.nodes[u]['x']
    dy_u = row['lat'] - G.nodes[u]['y']
    d_u = math.sqrt(dx_u**2 + dy_u**2) * 111000  # 粗略米
    dx_v = row['lon'] - G.nodes[v]['x']
    dy_v = row['lat'] - G.nodes[v]['y']
    d_v = math.sqrt(dx_v**2 + dy_v**2) * 111000

    total = d_u + d_v
    if total > 0:
        frac_u = d_v / total
        frac_v = d_u / total
    else:
        frac_u = 0.5
        frac_v = 0.5

    G.nodes[u]['demand_weight'] += w * frac_u
    G.nodes[v]['demand_weight'] += w * frac_v

    anchored.append({
        'name': row['name'],
        'category': cat,
        'lon': row['lon'],
        'lat': row['lat'],
        'nearest_u': u,
        'nearest_v': v,
        'walk_dist': round(dist, 1),
        'weight': w,
    })

print(f"锚定成功: {len(anchored)}, 孤岛剔除(>{MAX_WALK}m): {skipped}")

# === 投影仓（generator）===
print("\n=== 4. 投影前置仓 ===")
generators = []

# 仓也做 GCJ-02 → WGS-84 转换
for gdf in [hema, zb_cangchu]:
    conv = gdf.apply(lambda r: gcj02_to_wgs84(r['lon'], r['lat']), axis=1)
    gdf['lon'] = [c[0] for c in conv]
    gdf['lat'] = [c[1] for c in conv]

for brand, gdf in [('盒马鲜生', hema), ('中百仓储', zb_cangchu)]:
    lons_g = gdf['lon'].tolist()
    lats_g = gdf['lat'].tolist()
    nearest_g_edges, nearest_g_dists = ox.distance.nearest_edges(G, X=lons_g, Y=lats_g, return_dist=True)

    for i in range(len(nearest_g_edges)):
        dist = float(nearest_g_dists[i])
        if dist > MAX_WALK:
            print(f"  跳过(孤岛): {gdf.iloc[i]['name']} dist={dist:.0f}m")
            continue
        row = gdf.iloc[i]
        # 仓投影到最近节点（不是边）
        nearest_node = ox.distance.nearest_nodes(G, X=row['lon'], Y=row['lat'])
        G.nodes[nearest_node]['is_generator'] = True
        G.nodes[nearest_node]['brand'] = brand
        generators.append({
            'name': row['name'],
            'brand': brand,
            'lon': row['lon'],
            'lat': row['lat'],
            'node': nearest_node,
        })

print(f"仓(generator)总数: {len(generators)}")

# === 统计 ===
print("\n=== 5. 统计 ===")
gen_nodes = [n for n in G.nodes if G.nodes[n]['is_generator']]
total_demand = sum(G.nodes[n]['demand_weight'] for n in G.nodes)
print(f"generator 节点数: {len(gen_nodes)}")
print(f"全网总需求当量: {total_demand:.1f}")

# === 保存 ===
print("\n=== 6. 保存 ===")
# 存更新后的图
ox.save_graphml(G, os.path.join(ROAD_DIR, 'wuhan_graph_anchored.graphml'))
print("已存 wuhan_graph_anchored.graphml")

# 存锚定 POI 表
pd.DataFrame(anchored).to_csv(os.path.join(POI_DIR, 'poi_anchored.csv'),
                              index=False, encoding='utf-8-sig')
print("已存 poi_anchored.csv")

# 存 generator 表
pd.DataFrame(generators).to_csv(os.path.join(POI_DIR, 'generators.csv'),
                                index=False, encoding='utf-8-sig')
print("已存 generators.csv")

print("\n=== 完成 ===")
