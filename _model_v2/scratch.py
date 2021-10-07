import pandas as pd
import glob

input_dfs = {}


filepaths = glob.glob(f'C:\\Users\\vdesai\\Git\\bootstrapper-og\\model_scenarios\\z_test\\2021-10-06_16_22\\drivers\\*.xlsx')

print(filepaths)

for fp in filepaths:
    k = fp.partition('drivers\\')[2].partition('.xlsx')[0]
    input_dfs[k] = pd.read_excel(fp)
    print(input_dfs)

