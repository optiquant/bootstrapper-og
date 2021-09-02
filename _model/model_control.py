import pandas as pd
import time
import datetime

'''
model_control.py >>>
This module controls the flow of data within the model. Attributes of this module are shared or required by one or more 
other modules, and can be updated or retrieved using relevant getter methods. 
Attributes of model_control are of the following types:
 |-- Scenario level variables (e.g. scenario_time_stamp)
 |-- Filepaths of all relevant outputs for the model _scenario  (which can be retrieved by other modules by calling 
 get_scenario_filepaths_all()
 |-- Certain "aggregation" or "roll-up" parameters that may be required across modules (e.g. sub-asset, well, or 
 parentco identifiers)

 The general functioning of the model_control is to act as the "traffic cop" in the model. 
 model_control does not know or care what other modules do. 
 It simply passes parameters or its own attributes to other modules and listens for a completion_alert (bool) from
  the module currently executing.
    If the completion_alert is True, the caller has executed its code, and model_control will execute the next required 
    or desired process.
 '''

# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

modeled_wells_all = [
    "MUNSON C N283HU",
    "MUNSON C N284HM",
    "MUNSON C N285HU",
    "MUNSON C N286HM",
    "MUNSON C N287HU",
    # "MUNSON #1H",
    # "MUNSON #2H",
    # "MUNSON #3H",
    # "MUNSON #4H",
    # "MUNSON #5H",
    # "MUNSON #6H",
    # "MUNSON #7H",
    # "MUNSON #8H",
    "Munson-Central // Well 1",
    "Munson-Central // Well 2",
    "Munson-Central // Well 3",
    "Munson-Central // Well 4",
    "Munson-Central // Well 5",
    "Munson-Central // Well 6",
    "Munson-Central // Well 7",
    "Munson-Central // Well 8",
    "Munson-Southwest // Well 9",
    "Munson-Southwest // Well 10",
    "Munson-Southwest // Well 11",
    "Munson-Southwest // Well 12",
    "Munson-Southwest // Well 13",
    "Munson-Southwest // Well 14",
    "Munson-Southwest // Well 15",
    "Munson-North // Well 16",
    "Munson-North // Well 17",
    "Munson-North // Well 18",
    "Munson-North // Well 19",
    "Munson-North // Well 20",
    "Munson-Central // Well 21",
    "Munson-Central // Well 22",
    "Munson-Central // Well 23",
    "Munson-Central // Well 24",
    "Munson-Central // Well 25",
    "Munson-Central // Well 26",
    "Munson-Central // Well 27",
    "Munson-Central // Well 28",
    "Munson-Southwest // Well 29",
    "Munson-Southwest // Well 30",
    "Munson-Southwest // Well 31",
    "Munson-Southwest // Well 32",
    "Munson-Southwest // Well 33",
    "Munson-Southwest // Well 34",
    "Munson-Southwest // Well 35",
    "Munson-East // Well 36",
    "Munson-East // Well 37",
    "Munson-East // Well 38",
    "Munson-East // Well 39",
    "Munson-East // Well 40",
    "Munson-Central // Well 41",
    "Munson-Central // Well 42",
    "Munson-Central // Well 43",
    "Munson-Central // Well 44",
    "Munson-Central // Well 45",
    "Munson-Central // Well 46",
    "Munson-Central // Well 47",
    "Munson-Central // Well 48"
    # "FARMAR CB PU N734HU",
    # "FARMAR CC PU N735HM",
    # "FARMAR CC PU N736HU",
    # "FARMAR CD PU N738HU",
    # "Foreland I DUC 1",
    # "Foreland I DUC 2",
    # "Foreland I DUC 3",
    # "Foreland I DUC 4",
    # "Foreland I DUC 5",
    # "Foreland I DUC 6",
    # "Foreland I DUC 7",
    # "LeasingII//Well 1",
    # "LeasingII//Well 2",
    # "LeasingII//Well 3",
    # "LeasingII//Well 4",
    # "MunsonLeasing//Well 1",
    # "MunsonLeasing//Well 2",
    # "MunsonLeasing//Well 3",
    # "MunsonLeasing//Well 4"
]

# modeled_wells_all = ["Ganador//GEN "+str(_+1) for _ in range(90)]
# modeled_wells_all = ["LeasingII//GENERIC "+str(_+1) for _ in range(32)]

# estimate remaining capex from PDP wells
# True --> model will estimate DC&F  capex from past activity and include in the parentco_capex
# False --> model will only use the input working capital balance (excel-based)
include_remaining_pdp_capex = True
pdp_wells_with_remaining_capex = [
    # "HALCOMB A S271HU",
    # "HALCOMB A S288HM",
    # "HALCOMB A S287HU",
    # "HALCOMB A S286HD",
    # "HALCOMB A S273HU",
    # "HALCOMB A S274HM",
    # "HALCOMB A S274HA",
    # "MUNSON C S284HM",
    # "MUNSON C S285HU",
    # "MUNSON C S286HM",
    # "FARMAR DD S548HM",
    # "FARMAR DC S545HM",
    # "FARMAR DB S544HU",
    # "FARMAR DA S541HM",

]

# gas marketing expenses for sub-asset
include_pdp_gas_marketing = {
    'Farmar': True,
    'Munson': True,
    'MunsonLeasing': True,
    'Tracker': False,
    'AMCo': False,
    'LeasingI': False,
    'Ganador': True,
    'Foreland I': True,
    'LeasingII': False,
    'Discovery': True
}

# number of generic wells
generic_well_count_by_sub_asset = {
    'Farmar': 92,  # 0,
    'Munson': 0,
    'Tracker': 110,
    'AMCo': 40,
    'LeasingI': 51 + 150,  # 0,
    'Ganador': 90,  # 90,
    'Foreland I': 0,
    'LeasingII': 36,  # 60,
    'Discovery': 125,  # 125
    'MunsonLeasing': 32
}
# monthly driver tab codes for PDP input and historical financials
driver_input_codes = {
    'Farmar': 0,
    'Munson': 1,
    'MunsonLeasing': 3,
    'Tracker': 6,
    'AMCo': 7,
    'LeasingI': 8,
    'Ganador': 4,
    'Foreland I': 5,
    'LeasingII': 9,
    'Discovery': 10
}

reassigned_type_curve_areas = {
    'Tracker': {
        'TRACKER-NORTH': 64,
        'TRACKER-SOUTH': 46
    }
}

# balance sheet date (used for capital structure at model start)
balance_sheet_date = '6/30/21'
model_start_date = '7/1/21'

strip_pricing_date = '8/30/21'
flat_oil_scenario = True
flat_gas_scenario = True

model_months = 600
chart_months = 24
generic_wells_on = True
pdp_on = True
ethane_mode = 'recovery'
ngl_fixed_recoveries = {
    'rejection': {'ethane': .40,
                  'propane': .90,
                  'n_butane': .97,
                  'iso_butane': .97,
                  'nat_gasoline': .97},
    'recovery': {'ethane': .85,
                 'propane': .95,
                 'n_butane': .99,
                 'iso_butane': .99,
                 'nat_gasoline': .99}
}
existing_scenario_data_source = 'local'  # or 'network'

# filepaths for this model _scenario
scenario_filepaths_all = {
    'local': [],
    'network': []
}

default_percentiles = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
string_default_percentiles = [str(int(_ * 100)) + "%" for _ in default_percentiles]


# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#

def new_scenario():
    '''Creates a new scenario_time_stamp, sets model start date, and sets up scenario folders.'''
    global scenario_time_stamp
    global use_existing_scenario
    global existing_scenario_identifier

    if 'use_existing_scenario' not in globals():
        existing_scenario_q = input('\n| Use existing scenario? Y/N >>> ')
        if existing_scenario_q.lower() == 'y':
            use_existing_scenario = True
            # existing scenario identifier (just the name / scenario timestamp)
            existing_scenario_identifier = input(f'|-- Enter scenario identifier >>> ')
            if len(existing_scenario_identifier) == 0:
                existing_scenario_identifier = '2020-11-30_15_23'
        else:
            use_existing_scenario = False

    if 'scenario_time_stamp' not in globals():
        if use_existing_scenario:
            scenario_time_stamp = existing_scenario_identifier
        else:
            scenario_time_stamp = str(datetime.datetime.today()).replace(':', '_')
            scenario_time_stamp = scenario_time_stamp.replace('.', '_')
            scenario_time_stamp = scenario_time_stamp.replace(' ', '_')
            scenario_time_stamp = scenario_time_stamp[:-10]
            print(f'\n| Scenario will be saved under timestamp: {scenario_time_stamp}\n')

    set_model_start()

    global local_scenario_folder
    global network_scenario_folder
    # set _scenario folders
    local_scenario_folder, network_scenario_folder = get_scenario_root_folders().values()
    return scenario_time_stamp


def get_reassigned_type_curve_areas():
    '''Returns a dictionary of type curve sub-areas for a given sub-asset. Structure:
    {
        Sub-asset name : {
            type curve sub-area : locations
        }
    }
    '''
    return reassigned_type_curve_areas


def get_scenario_root_folders():
    '''Sets _scenario folders according to if this is a test _scenario or not.'''
    # check if test _scenario
    if use_existing_scenario:
        tail = existing_scenario_identifier
    else:
        tail = scenario_time_stamp

    local_scenario_folder = 'C:\/Users\/vdesai\/Git\/bootstrapper-og\/model_scenarios\/z_test\/' + tail + '\/'
    network_scenario_folder = r'\/FILE01\/TDrive\/Finance-Strategy\/__MODEL_SCENARIOS\/z_test\/' + tail + '\/'

    print(f'| Local _scenario folder: {local_scenario_folder}\n| Network _scenario folder: {network_scenario_folder}')
    return {
        'local_scenario_folder': local_scenario_folder,
        'network_scenario_folder': network_scenario_folder
    }


def get_scenario_time_stamp():
    '''Returns the time stamp / scenario ID of the current model scenario.'''
    global scenario_time_stamp
    if 'scenario_time_stamp' not in globals():
        return new_scenario()
    else:
        return scenario_time_stamp


def get_scenario_filepaths_all():
    '''Returns a dict of local and network filepaths where outputs for this _scenario are saved.'''
    return scenario_filepaths_all


def get_well_name():
    return well_name.upper()


def get_data_source():
    # local or network
    return existing_scenario_data_source


def add_to_model_control(object_dict: dict, deep_copy=True):
    '''Adds an object from another module to model_control'''
    print(f'\n| Adding object to model control >>>')
    for name, object in object_dict.items():
        if deep_copy:
            # create a deep copy
            try:
                globals()[name] = object.copy(deep=True)
                print(f'|-- adding deep copy: {name} --> type: {type(object)} // {globals()[name]}')
            except TypeError:
                globals()[name] = object.copy()
                print(f'|-- adding copy: {name} --> type: {type(object)} // {globals()[name]}')
            except AttributeError:
                globals()[name] = object
                print(f'|-- adding object: {name} --> type: {type(object)} // {globals()[name]}')
        else:
            # just a pointer
            globals()[name] = object
            print(f'|-- adding reference only: {name} --> type: {type(object)} // {globals()[name]}')


def notify_complete(caller_name: str):
    print(f'\n$$$ model_control: completion notification >>> {caller_name}')
    set_caller_end_time(caller_name)


def set_model_start():
    global start_time
    if 'start_time' not in globals():
        start_time = time.time()


def set_caller_end_time(caller_name: str):
    global end_time
    global start_time
    end_time = time.time()
    print(f'\n$$$ {caller_name} module run-time: {end_time - start_time}')


def add_to_scenario_filepaths(tail: str):
    '''Adds the filename to all scenario filepaths.'''
    global scenario_filepaths_all
    fp_local = get_scenario_root_folders()['local_scenario_folder']
    fp_network = get_scenario_root_folders()['network_scenario_folder']

    if fp_local + tail not in scenario_filepaths_all['local']:
        scenario_filepaths_all['local'].append(fp_local + tail)

    if fp_network + tail not in scenario_filepaths_all['network']:
        scenario_filepaths_all['network'].append(fp_network + tail)

    add_to_model_control(
        object_dict={'scenario_filepaths_all': scenario_filepaths_all},
        deep_copy=True
    )


def get_flat_oil_price():
    global flat_oil_price
    global flat_oil_scenario
    global flat_oil_start_date
    if flat_oil_scenario and 'flat_oil_price' not in globals():
        flat_oil_price = float(input(f'\n| Enter flat oil price to model ($/Bbl) >>> '))
        flat_oil_start_date = pd.to_datetime(input(f'| Enter flat price start date (m/d/yy) >>> '))
        print(f'| Modeling flat oil price of ${flat_oil_price: .3f}/Bbl')
        return flat_oil_price
    elif 'flat_oil_price' in globals():
        return flat_oil_price
    else:
        print('| Running strip prices for oil.\n')


def get_flat_gas_price():
    global flat_gas_price
    global flat_gas_scenario
    global flat_gas_start_date
    if flat_gas_scenario and 'flat_gas_price' not in globals():
        flat_gas_price = float(input(f'\n| Enter flat gas price to model ($/MMBtu) >>> '))
        flat_gas_start_date = pd.to_datetime(input(f'| Enter flat price start date (m/d/yy) >>> '))
        print(f'| Modeling flat gas price of ${flat_gas_price: .3f}/MMBtu')
        return flat_gas_price
    elif 'flat_gas_price' in globals():
        return flat_gas_price
    else:
        print('| Running strip prices for gas.\n')


def get_flat_gas_start_date():
    global flat_gas_start_date
    return flat_gas_start_date


def get_flat_oil_start_date():
    global flat_oil_start_date
    return flat_oil_start_date


def get_non_mcs_scenario_label():
    # create the correct label for the non MCS price scenario
    global flat_oil_scenario
    global flat_gas_scenario
    global _non_mcs_scenario_label

    if '_non_mcs_scenario_label' not in globals():
        if flat_oil_scenario and flat_gas_scenario:
            fop = get_flat_oil_price()
            fgp = get_flat_gas_price()
            _non_mcs_scenario_label = f'${fop:.0f} WTI/\${fgp:.3f} HH'
        elif flat_oil_scenario and not (flat_gas_scenario):
            fop = get_flat_oil_price()
            _non_mcs_scenario_label = f'${fop:.0f} WTI/Strip {strip_pricing_date}'
        elif not (flat_oil_scenario) and flat_gas_scenario:
            fgp = get_flat_gas_price()
            _non_mcs_scenario_label = f'${fgp:.3f} HH/Strip {strip_pricing_date}'
        else:
            _non_mcs_scenario_label = f"Strip {strip_pricing_date}"

    return _non_mcs_scenario_label


def initialize():
    # create a new _scenario
    new_scenario()
    get_flat_oil_price()
    get_flat_gas_price()

# -----------------------------------------------------------------------------------------------------------------------#
# -----------------------------------------------------# EXECUTION #-----------------------------------------------------#
# -----------------------------------------------------------------------------------------------------------------------#
