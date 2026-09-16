import pandas as pd
import io
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from scipy import stats

# ─────────────────────────────────────────────────────────────
# Load & prepare data
# ─────────────────────────────────────────────────────────────
sample_data = """
Estrous	Virgin	Exp	Fem	Male	FTU	PS
0	0	041301L	3-2	2-7	1	-83.7
1	0	041301R	3-3	2-6	1	311.3
1	0	041302L	3-1	2-3	1	276.7
1	0	041302R	4-1	2-2	1	22.3
1	0	041303L	4-2	2-4	1	-23.2
0	0	041303R	6-1	2-6	1	-164.3
0	0	041304L	6-2	2-7	1	28.1
0	0	041304R	6-3	2-6	1	-107.9
1	0	041401L	3-1	2-4	2	-50.6
0	0	041401R	3-2	2-2	2	16.3
1	0	041402L	3-3	2-2	2	-17.8
1	0	041402R	4-1	2-4	2	122.8
0	0	042001L	3-1	2-7	3	-72
0	0	042001R	4-1	2-6	3	106.6
1	0	042701L	3-1	2-6	4	-85.3
0	0	042701R	3-3	2-7	3	-210.3
1	0	042702L	2-3	2-2	1	-29.6
0	0	042702R	4-1	2-3	4	209
1	0	042703L	2-1	3-2	1	7.9
1	0	042703R	2-2	3-1	1	411.5
0	0	042704L	6-1	2-6	2	-126
0	0	042704R	6-2	2-4	2	75.4
0	1	042705L	V8-2	2-7	1	-49.4
0	1	042705R	V8-3	2-3	1	154
0	0	050101L	5-1	3-1	1	-131.5
0	0	050101R	5-3	3-2	1	3.1
1	0	050102L	6-1	2-3	3	-41.8
0	0	050102R	6-2	2-2	3	151.3
0	0	051101L	3-1	2-2	5	-145.8
1	0	051101R	3-3	3-1	4	54.6
0	1	051401L	V8-1	3-1	1	181.4
0	1	051401R	V8-2	3-4	2	177.1
0	0	051402L	1-2	3-4	1	-41.6
1	0	051402R	7-3	3-1	1	131.6
1	0	051501L	7-2	3-1	1	-9.6
0	1	051501R	V9-2	3-4	1	287
1	1	051502L	V9-1	3-4	1	120.2
1	1	051502R	V9-3	3-1	1	-241.4
0	0	051503L	1-11	3-4	1	-144.3
1	0	051503R	3-3	3-1	5	113
0	1	051801L	V8-3	3-4	2	-23.7
1	1	051801R	V9-2	3-1	2	194.3


"""

df = pd.read_csv(io.StringIO(sample_data), sep='\t')
df['MTU'] = df['FTU'] - 1  # 0-indexed female reuse count

# Create group labels
df['Group'] = df['Virgin'].astype(str) + '_' + df['Estrous'].astype(str)
df['Group'] = df['Group'].replace({
    '0_0': 'SE-NE', '0_1': 'SE-E',
    '1_0': 'VG-NE', '1_1': 'VG-E',
})

# ─────────────────────────────────────────────────────────────
# Plot: One subplot per group with LINEAR trends
# ─────────────────────────────────────────────────────────────
sns.set_style("whitegrid")
sns.set_context("talk", font_scale=1.0)

# Define groups and layout
groups = sorted(df['Group'].unique())
valid_groups = [g for g in groups if len(df[df['Group']==g]) >= 2]
n_groups = len(valid_groups)

# Dynamic layout: try to make it roughly square
n_cols = int(np.ceil(np.sqrt(n_groups)))
n_rows = int(np.ceil(n_groups / n_cols))

fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows), sharex=True, sharey=True)
axes = np.atleast_1d(axes).flatten()  # Flatten for easy indexing

palette = {
    'SE-NE': '#d62728', 'SE-E': '#2ca02c',
    'VG-NE': '#1f77b4', 'VG-E': '#9467bd',
}

for idx, group in enumerate(valid_groups):
    ax = axes[idx]
    subset = df[df['Group'] == group].copy()
    base_color = palette.get(group, 'gray')
    
    # Fit LINEAR model: PS ~ MTU
    try:
        lin_model = smf.ols('PS ~ MTU', data=subset).fit()
        
        # Generate smooth line for plotting
        x_smooth = np.linspace(subset['MTU'].min(), subset['MTU'].max(), 100)
        y_smooth = (lin_model.params['Intercept'] + 
                   lin_model.params['MTU'] * x_smooth)
        
        # Plot line
        ax.plot(x_smooth, y_smooth, 
                color=base_color, linewidth=2.5, label='Linear fit')
                
    except Exception as e:
        print(f"Could not fit line for {group}: {e}")
    
    # 🔥 Plot raw data points: SOLID, no opacity shading
    ax.scatter(subset['MTU'], subset['PS'],
               color=base_color, alpha=0.8,  # 🔥 Fixed alpha, no FTU mapping
               s=60, edgecolor='white', linewidth=0.8, zorder=4, label='Data')
    
    # Subplot formatting
    ax.set_title(f'{group}\n(n={len(subset)})', fontsize=20, fontweight='bold')
    ax.axhline(0, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.set_xticks([0,1,2,3,4])
    
    
    if idx in (0,2):
        ax.set_ylabel('Sniffing Time Diff [Seconds]\n (Dominant - Subordinate)', fontsize=20)

    if idx > 1:
        ax.set_xlabel('Female Reuse Count', fontsize=20)


# Hide unused subplots
for idx in range(n_groups, len(axes)):
    axes[idx].set_visible(False)

# Overall figure formatting
fig.suptitle('Preference vs. Female Reuse by Group\n(Linear Fits; FTU=1+ included)', 
             fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('group_linear_trends_faceted.png', dpi=300, bbox_inches='tight')
plt.show()

# ─────────────────────────────────────────────────────────────
# Bonus: Print linear coefficients summary
# ─────────────────────────────────────────────────────────────
print("\n📊 Linear Fit Coefficients (PS ~ MTU):")
print("-" * 80)
for group in valid_groups:
    subset = df[df['Group'] == group].copy()
    try:
        model = smf.ols('PS ~ MTU', data=subset).fit()
        slope = model.params['MTU']
        direction = "↗" if slope > 0 else "↘" if slope < 0 else "→"
        print(f"{group:8} | Slope β={slope:6.3f} {direction} | Intercept={model.params['Intercept']:6.3f} | n={len(subset)}")
    except Exception as e:
        print(f"{group:8} | Fit failed: {e}")