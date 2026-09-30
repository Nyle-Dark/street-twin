# 脚本流程说明

## 目录结构

### 底座：数据获取（已完成）

| 脚本 | 作用 |
|---|---|
| `test_amap.py` | 测试高德API Key是否可用 |
| `fetch_pois.py` | 分网格抓高德POI（住宅/写字楼/商圈/枢纽/真实网点） |
| `fill_type_labels.py` | typecode反查高德一二三级类目名称 |
| `network.py` | osmnx拉武汉OSM路网，导出road_attrs.csv + nodes.csv |
| `跨江通道核对.py` | 验证关键跨江桥隧是否在路网中 |
| `check_bidir.py` | 检查双向边是否有成对反向边 |
| `clip_wuhan_ghsl.py` | 从全球GHSL栅格裁剪武汉区域 |
| `view_pop.py` | 查看人口栅格基本信息 |

---

### 第一步：路网阻抗矩阵

| 脚本 | 作用 | 状态 |
|---|---|---|
| `build_graph.py` | 从road_attrs.csv+nodes.csv重建MultiDiGraph，按PDF公式算每条边impedance = Length × Class_Penalty × 1.1（桥隧），存graphml | ✅ 已完成 |

**输出**：wuhan_graph.graphml（15MB，35217边全带阻抗）

---

### 第二步：POI需求当量与空间锚定

| 脚本 | 作用 | 状态 |
|---|---|---|
| `anchor_pois.py` | POI坐标GCJ-02→WGS-84转换，投影到最近边，需求权重分摊到两端节点，仓打is_generator标签 | ✅ 已完成 |
| `add_population.py` | 采样GHSL人口栅格，需求当量 = 类别权重 × (1 + 0.5 × 人口因子)，重新跑Dijkstra | ✅ 已完成 |

**输出**：wuhan_graph_pop.graphml, poi_with_pop.csv, facility_load_v2.csv

---

### 第三步：网络泰森多边形

| 脚本 | 作用 | 状态 |
|---|---|---|
| `network_voronoi.py` | 75个仓多源Dijkstra，每个节点找最近仓，检测边界边 | ✅ 已完成 |
| `three_scenarios.py` | 三仓场景对比：盒马单独/中百仓储单独/罗森单独 | ✅ 已完成 |
| `compare_methods.py` | 网络泰森多边形 vs 传统欧氏缓冲圆对比 |  未完成 |

**输出**：facility_load.csv, boundary_edges.csv, node_assign.csv, three_scenario_compare.csv, network_vs_euclidean.csv

---

## 运行顺序

```
底座（一次性）:
  test_amap.py → fetch_pois.py → fill_type_labels.py
  network.py → 跨江通道核对.py → check_bidir.py
  clip_wuhan_ghsl.py

第一步:
  build_graph.py

第二步:
  anchor_pois.py
  add_population.py

第三步:
  network_voronoi.py
  three_scenarios.py
```

