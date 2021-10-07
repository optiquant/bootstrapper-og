import pandas as pd
import model_control

pd.set_option('display.max_columns', None)

local_scenario_filepath, network_scenario_filepath = model_control.initialize()
print(local_scenario_filepath, network_scenario_filepath)

# using scenario ID: 2021-10-06_16_22

drilling_schedule = pd.read_excel(network_scenario_filepath + f'drivers/live_ds_2.xlsx', na_values=['nan'])
print(drilling_schedule.head())

# calculate NRI production
