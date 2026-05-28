import pandas as pd
import sys
from pathlib import Path
sys.path.append('C:/Users/hp/Desktop/work/final_pipeline_package_20260402/03_attribution_analysis/code')
from run_causality_and_threshold import build_model_frame
df = build_model_frame(Path('C:/Users/hp/Desktop/work/final_pipeline_package_20260402/00_raw_data/clean_features_with_holidays_alt.xlsx'))
print(df.columns)
