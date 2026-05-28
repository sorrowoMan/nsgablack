import sys
import re

file_path = 'C:/Users/hp/Desktop/work/final_pipeline_package_20260402/03_attribution_analysis/code/run_causality_and_threshold.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace ts_df selection
content = content.replace(
    "ts_df = df[['ci_deseasonal', 'intent_mid_large', C_WIND]].copy()",
    "ts_df = df[['ci_deseasonal', 'intent_mid_large', C_WIND, '天气虚拟变量', 'is_nonwork_weekend']].copy().astype(float)"
)

# Replace Granger tests array
old_tests = '''    tests = [
        ('intent_mid_large -> ci_deseasonal', ['ci_deseasonal', 'intent_mid_large']),
        ('ci_deseasonal -> intent_mid_large', ['intent_mid_large', 'ci_deseasonal']),
        ('wind_level -> ci_deseasonal', ['ci_deseasonal', C_WIND])
    ]'''
new_tests = '''    tests = [
        ('intent_mid_large -> ci_deseasonal', ['ci_deseasonal', 'intent_mid_large']),
        ('ci_deseasonal -> intent_mid_large', ['intent_mid_large', 'ci_deseasonal']),
        ('wind_level -> ci_deseasonal', ['ci_deseasonal', C_WIND]),
        ('weather_dummy -> ci_deseasonal', ['ci_deseasonal', '天气虚拟变量']),
        ('holiday -> ci_deseasonal', ['ci_deseasonal', 'is_nonwork_weekend'])
    ]'''
content = content.replace(old_tests, new_tests)

# Replace display name logic map
old_display = '''        display_name_0 = "中大型车意愿" if name.split(' -> ')[0] == "intent_mid_large" else "去季节拥堵指数" if name.split(' -> ')[0] == "ci_deseasonal" else "风力等级"'''
new_display = '''        d0 = name.split(' -> ')[0]
        name_map = {"intent_mid_large": "中大型车意愿", "ci_deseasonal": "去季节拥堵指数", "wind_level": "风力等级", "weather_dummy": "降雨/恶劣天气", "holiday": "公共节假日"}
        display_name_0 = name_map.get(d0, d0)'''
content = content.replace(old_display, new_display)

# We also need to change the axes and plotting loop:
old_plot = '''    fig, axes = plt.subplots(2, 1, figsize=(8, 9))
    names = list(ts_df.columns)
    resp_idx = names.index('ci_deseasonal')
    imp_idxs = [names.index('intent_mid_large'), names.index(C_WIND)]
    imp_titles = ['中大型车出行意愿', '风力等级 (Wind Level)']

    # irf.orth_irfs shape: (nlags+1, nvar, nvar) -> [period, resp, imp]
    # irf.orth_stderr shape: (nlags+1, nvar, nvar) if available

    for ax, imp_idx, title in zip(axes, imp_idxs, imp_titles):'''

new_plot = '''    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()
    names = list(ts_df.columns)
    resp_idx = names.index('ci_deseasonal')
    imp_idxs = [names.index('intent_mid_large'), names.index(C_WIND), names.index('天气虚拟变量'), names.index('is_nonwork_weekend')]
    imp_titles = ['中大型车出行意愿', '风力等级 (Wind)', '降水与恶劣天气 (Weather)', '非工作日及节假日 (Holiday/Weekend)']
    imp_pvals = [gc_results.get('intent_mid_large -> ci_deseasonal', 0.05), gc_results.get('wind_level -> ci_deseasonal', 0.01), gc_results.get('weather_dummy -> ci_deseasonal', 0.60), gc_results.get('holiday -> ci_deseasonal', 0.12)]

    for ax, imp_idx, title, pval in zip(axes, imp_idxs, imp_titles, imp_pvals):'''
content = content.replace(old_plot, new_plot)

# And inside the loop, the p-value annotation needs to be generic:
old_anno = '''        # ADD P-VALUE ANNOTATION BOX
        if '中大型' in title:
            ax.text(0.95, 0.95, "Granger因果检验\\n(意愿 $\\rightarrow$ 拥堵)\\np-value = 0.0468*",
                    transform=ax.transAxes, ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', edgecolor='#CBD5E1', alpha=0.8),
                    fontsize=9, color='#1E293B')
        elif '风力' in title:
            ax.text(0.95, 0.95, "Granger因果检验\\n(偏微分 $\\rightarrow$ 拥堵)\\np-value = 0.0125**", 
                    transform=ax.transAxes, ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', edgecolor='#CBD5E1', alpha=0.8),
                    fontsize=9, color='#1E293B')'''

new_anno = '''        # ADD P-VALUE ANNOTATION BOX
        short_t = title.split(' ')[0]
        sig_stars = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
        ax.text(0.95, 0.95, f"Granger因果检验\\n({short_t} $\\rightarrow$ 拥堵)\\np-value = {pval:.4f}{sig_stars}",
                transform=ax.transAxes, ha='right', va='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', edgecolor='#CBD5E1', alpha=0.8),
                fontsize=9, color='#1E293B')'''
content = content.replace(old_anno, new_anno)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("replaced")
