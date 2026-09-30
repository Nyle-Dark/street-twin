import os
import osmnx as ox
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

# 开缓存：第二次起不用重新下载 OSM 数据
ox.settings.use_cache = True
ox.settings.cache_folder = r'D:\PythonPRO\PyCharmProjects\PythonProject\load\cache'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1) 三环线围合区（近似多边形，逆时针描点，根据三环线走向）
#    北/西/南各外扩约 1.5 km（北 +0.0135°、南 -0.0135°、西 -0.0156°），
#    确保整条三环线都在 AOI 内；东侧不动（光谷 box 负责东边）
third_ring = Polygon([
    (114.170, 30.610),  # 西：西移到长丰桥以西
    (114.200, 30.645),  # 西北：北延到额头湾以北
    (114.280, 30.675),  # 北：北延过三金潭
    (114.360, 30.665),  # 东北：北延过天兴洲大桥南岸
    (114.400, 30.630),
    (114.425, 30.580),
    (114.430, 30.525),
    (114.330, 30.460),  # 南：南延到白沙洲大桥以南
    (114.230, 30.480),
    (114.175, 30.550),
])


# 2) 光谷中心城矩形飞地
guanggu = box(114.42, 30.465, 114.56, 30.555)

# 3) 合并成 AOI
aoi = unary_union([third_ring, guanggu])

# 4) 拉路网（Overpass 偶发超时/限流：自动切换端点并重试）
# 注意：osmnx 2.1 的设置项是 overpass_url（基础地址，不带 /interpreter）和 requests_timeout
OVERPASS_BASES = [
    'https://overpass-api.de/api',                 # 官方（当前首选）
    'https://overpass.openstreetmap.fr/api',       # 法国镜像（已测可达）
    'https://overpass.osm.ch/api',                 # 瑞士镜像（已测可达）
]

def _download_network(aoi):
    last_err = None
    for attempt in range(3):                      # 最多 3 轮
        for base in OVERPASS_BASES:               # 每轮按顺序换端点
            ox.settings.overpass_url = base
            try:
                print('尝试 Overpass 端点:', base)
                return ox.graph_from_polygon(
                    aoi, network_type='drive', simplify=True, truncate_by_edge=True
                )
            except Exception as e:
                last_err = e
                print('  失败:', type(e).__name__, '，换下一个...')
    raise last_err

G = _download_network(aoi)
gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

# ---- 查看结果 ----

# 1) 打印规模统计
print('节点数:', len(G.nodes))
print('边数:', len(G.edges))
print(gdf_nodes.head())   # 节点表前 5 行
print(gdf_edges.head())   # 边表前 5 行

# ---- 新增：导出必需属性（等级/单双向/长度 + 桥隧/名称/限速）到 CSV ----

# OSM 道路等级 → 中文对照（用于通行阻抗权重）
HIGHWAY_CN = {
    'motorway': '高速公路', 'motorway_link': '高速匝道',
    'trunk': '快速路', 'trunk_link': '快速路匝道',
    'primary': '主干道', 'primary_link': '主干道连接线',
    'secondary': '次干道', 'secondary_link': '次干道连接线',
    'tertiary': '一般道路', 'tertiary_link': '一般道路连接线',
    'unclassified': '未分级道路',
    'residential': '支路（居住区）',
    'living_street': '生活性街道',
    'service': '服务性道路',
    'busway': '公交专用道',
}

def _hw(x):
    return x[0] if isinstance(x, (list, tuple)) else x

edges = gdf_edges.reset_index()                     # u/v/key 从索引变成正式列
edges['highway'] = edges['highway'].map(_hw)        # 等级：列表取第一个值
edges['road_class'] = edges['highway'].map(HIGHWAY_CN).fillna(edges['highway'])
edges['oneway'] = edges['oneway'].map({True: '单向', False: '双向'}).fillna('未知')

attr = edges[['u', 'v', 'key', 'highway', 'oneway', 'length', 'road_class',
              'bridge', 'tunnel', 'name', 'maxspeed']].copy()
csv_path = os.path.join(BASE_DIR, 'road_attrs.csv')
attr.to_csv(csv_path, index=False, encoding='utf-8-sig')
print('属性 CSV 已保存:', csv_path)
print(attr.head())
print('非空统计 -> bridge:', int(attr['bridge'].notna().sum()),
      '| tunnel:', int(attr['tunnel'].notna().sum()),
      '| name:', int(attr['name'].notna().sum()),
      '| maxspeed:', int(attr['maxspeed'].notna().sum()))

# ---- 新增：双向边成对校验（反向边必须在） ----

bidir = attr[attr['oneway'] == '双向']
pairs = set(map(tuple, bidir[['u', 'v']].values))
missing = sum(1 for u, v in pairs if (v, u) not in pairs)
sample = bidir.iloc[0]
rev_cnt = len(attr[(attr['u'] == sample['v']) & (attr['v'] == sample['u'])])
print('双向边总数:', len(bidir))
print('抽样一条 (u=%s, v=%s) 的反向边条数: %d (应为 1)' % (sample['u'], sample['v'], rev_cnt))
print('全量校验: 双向边缺失反向边的条数 =', missing, '(应为 0)')

# ---- 新增：节点表（ID + 经纬度）单独导出 ----

nodes = gdf_nodes[['x', 'y']].copy()
nodes.index.name = 'node_id'                        # 索引就是 OSM 节点 id
nodes = nodes.reset_index().rename(columns={'x': 'lon', 'y': 'lat'})
nodes_path = os.path.join(BASE_DIR, 'nodes.csv')
nodes.to_csv(nodes_path, index=False, encoding='utf-8-sig')
print('节点 CSV 已保存:', nodes_path, '| 节点数:', len(nodes))
print(nodes.head())

# 2) 路网图保存为 PNG（不弹窗，直接存文件）
ox.plot_graph(
    G, node_size=0, edge_linewidth=0.3,
    figsize=(12, 12), dpi=150,
    save=True, show=False, close=True,
    filepath=os.path.join(BASE_DIR, 'network_map.png')
)
print('路网图已保存:', os.path.join(BASE_DIR, 'network_map.png'))

# 3) 存成文件，之后用 QGIS / ArcGIS 打开
gdf_nodes.to_file(os.path.join(BASE_DIR, 'wuhan_nodes.geojson'), driver='GeoJSON')
gdf_edges.to_file(os.path.join(BASE_DIR, 'wuhan_edges.geojson'), driver='GeoJSON')

# ---- 新增：计算阻抗属性并保存 graphml（后面直接加载，不用重拉 OSM） ----

# Class_Penalty（PDF 方法3：Length × Class_Penalty × Environment_Penalty）
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

def _hw(x):
    return x[0] if isinstance(x, (list, tuple)) else x

# 给每条边算 impedance
for u, v, k, data in G.edges(keys=True, data=True):
    hw = _hw(data.get('highway', 'residential'))
    cp = CLASS_PENALTY.get(hw, 2.0)
    # Environment_Penalty：bridge 或 tunnel 非空 → 1.1
    has_bridge = bool(data.get('bridge'))
    has_tunnel = bool(data.get('tunnel'))
    ep = 1.1 if (has_bridge or has_tunnel) else 1.0
    length = data.get('length', 0)
    data['impedance'] = round(length * cp * ep, 3)
    data['class_penalty'] = cp
    data['env_penalty'] = ep

# 存 graphml（后面直接 ox.load_graphml 加载）
graphml_path = os.path.join(BASE_DIR, 'wuhan_graph.graphml')
ox.save_graphml(G, graphml_path)
print('graphml 已保存:', graphml_path)

# 统计阻抗分布
impedances = [d['impedance'] for _, _, _, d in G.edges(keys=True, data=True)]
print('阻抗统计: 最短 %.1f 米, 最长 %.1f 米, 平均 %.1f 米' % (
    min(impedances), max(impedances), sum(impedances)/len(impedances)))
