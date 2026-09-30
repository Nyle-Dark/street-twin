import rasterio
import matplotlib.pyplot as plt
import numpy as np

with rasterio.open("wuhan_ghsl_pop_100m_2025.tif") as src:
    data = src.read(1)
    # 把水域(-200)和0设为透明
    data_masked = np.ma.masked_where(data <= 0, data)

    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    im = ax.imshow(data_masked, cmap='YlOrRd', vmin=0, vmax=200)
    ax.set_title('Wuhan Population Density (100m, GHSL 2025)')
    ax.axis('off')
    plt.colorbar(im, label='People per 100m pixel', shrink=0.7)
    plt.tight_layout()
    plt.savefig("wuhan_pop_map.png", dpi=150, bbox_inches='tight')
    plt.show()
