import pandas as pd

df = pd.read_csv(r"C:\Users\temp\Desktop\静态数字\路网\road_attrs.csv")

print("=== 1. 桥/隧道边数 ===")
print("bridge=yes 边数:", (df["bridge"]=="yes").sum())
print("tunnel=yes 边数:", (df["tunnel"]=="yes").sum())

print("\n=== 2. 名字里带'桥/隧道/长江/汉江'的边（去重路名） ===")
mask = df["name"].astype(str).str.contains("桥|隧道|长江|汉江|大桥", na=False)
names = (df[mask]["name"].dropna().unique())
for n in sorted(names):
    print(" -", n)

print("\n=== 3. 关键跨江通道命中检查 ===")
key_bridges = ["长江大桥","长江二桥","二七","鹦鹉洲","杨泗港","天兴洲","白沙洲",
               "长江隧道","江汉桥","知音桥","月湖桥","晴川桥","长丰桥","二七长江"]
all_names = " | ".join(df["name"].dropna().astype(str).unique())
for k in key_bridges:
    hit = "✅" if k in all_names else "❌ 缺失"
    print(f"  {hit}  {k}")
