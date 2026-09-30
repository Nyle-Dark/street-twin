import os, pandas as pd, numpy as np, networkx as nx, osmnx as ox

ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
POI = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\POI'

print('='*60)
print('第一步：路网拓扑抽象与阻抗矩阵')
print('='*60)

G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph.graphml'))
G.graph['crs'] = 'epsg:4326'
print('节点数: %d' % G.number_of_nodes())
print('边数: %d' % G.number_of_edges())

imps = []
for u,v,k,d in G.edges(keys=True, data=True):
    d['impedance'] = float(d.get('impedance', 0))
    d['length'] = float(d.get('length', 0))
    imps.append(d['impedance'])
print('impedance: %d条, 范围 %.1f-%.1fm, 均值 %.1fm' % (len(imps), min(imps), max(imps), np.mean(imps)))

bridge_cnt = sum(1 for _,_,_,d in G.edges(keys=True,data=True) if d.get('bridge'))
tunnel_cnt = sum(1 for _,_,_,d in G.edges(keys=True,data=True) if d.get('tunnel'))
print('桥边: %d, 隧道边: %d' % (bridge_cnt, tunnel_cnt))

print()
print('='*60)
print('第二步：POI需求当量与空间锚定')
print('='*60)

pop = pd.read_csv(os.path.join(POI, 'poi_with_pop.csv'))
print('总POI: %d' % len(pop))
print('类别分布:')
print(pop.groupby('category').size())
zero = (pop['pop']==0).sum()
print('pop=0: %d (%.1f%%)' % (zero, zero/len(pop)*100))
print('final_weight: %.2f - %.2f' % (pop.final_weight.min(), pop.final_weight.max()))

gen = pd.read_csv(os.path.join(POI, 'generators.csv'))
print('\n仓(generator): %d' % len(gen))
print(gen.groupby('brand').size())

print()
print('='*60)
print('第三步：网络泰森多边形')
print('='*60)

na = pd.read_csv(os.path.join(POI, 'node_assign.csv'))
print('节点分配: %d' % len(na))
covered = (na.nearest_gen > 0).sum()
print('有归属: %d (%.1f%%)' % (covered, covered/len(na)*100))
print('各仓覆盖Top5:')
print(na.nearest_gen.value_counts().head())

be = pd.read_csv(os.path.join(POI, 'boundary_edges.csv'))
print('\n边界边: %d' % len(be))

fl = pd.read_csv(os.path.join(POI, 'facility_load_v2.csv'))
print('\n仓负荷: %d个仓' % len(fl))
print('总需求: %.1f' % fl.demand.sum())
print('最高: %.1f, 最低: %.1f' % (fl.demand.max(), fl.demand.min()))
