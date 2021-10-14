import pandas as pd
import model_control
import type_curves

pd.set_option('display.max_columns', None)

modeled_wells_all = model_control.modeled_wells_all
local_scenario_filepath, network_scenario_filepath = model_control.initialize()
print(local_scenario_filepath, network_scenario_filepath)

# using scenario ID: vdd test

drilling_schedule = pd.read_excel(network_scenario_filepath + f'drivers\\/live_ds_2.xlsx', na_values=['nan'])
# filter down to the modeled wells only
drilling_schedule = drilling_schedule[drilling_schedule['WELL'].isin(modeled_wells_all)]
print(drilling_schedule.head())

# calculate NRI production
# get type curves
TypeCurves = type_curves.load_gross_type_curves()
print(TypeCurves)



