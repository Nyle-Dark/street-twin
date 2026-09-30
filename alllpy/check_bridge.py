import os, osmnx as ox
ROAD = r'C:\Users\temp\Desktop\静态数字孪生\静态数字数据\路网'
G = ox.load_graphml(os.path.join(ROAD, 'wuhan_graph.graphml'))
for i, (u,v,k,d) in enumerate(G.edges(keys=True, data=True)):
    if i >= 10: break
    b = d.get('bridge')
    t = d.get('tunnel')
    print('bridge=%r type=%s, tunnel=%r' % (b, type(b).__name__, t))
