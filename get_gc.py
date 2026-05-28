import pandas as pd
import sys
from pathlib import Path
from statsmodels.tsa.stattools import grangercausalitytests
sys.path.append('C:/Users/hp/Desktop/work/final_pipeline_package_20260402/03_attribution_analysis/code')
from run_causality_and_threshold import build_model_frame
df = build_model_frame(Path('C:/Users/hp/Desktop/work/final_pipeline_package_20260402/00_raw_data/clean_features_with_holidays_alt.xlsx'))

tests = ['intent_mid_large', '风力', '天气虚拟变量', '空气质量指数（AQI）', 'is_holiday_day', 'is_nonwork_weekend', 'dayofweek']
for col in tests:
    try:
        res = grangercausalitytests(df[['ci_deseasonal', col]].dropna(), maxlag=[7], verbose=False)
        pval = res[7][0]['ssr_ftest'][1]
        print(f"{col} -> ci_deseasonal p={pval:.4f}")
    except:
        pass
