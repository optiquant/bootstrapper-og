import model_inputs
import pandas as pd
import prices as pr
from collections import namedtuple
import pprint
import model_control
from useful_functions import *
import type_curves as tc

# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#



# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #-----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

def get_sub_asset(well_name: str, partition_character='//'):
    '''Returns the sub-asset listed for this well in the live drilling schedule.
    If well is not found in the live DS, will return portion of the well_name argument before the partition_character.'''
    global live_ds
    lookup_dict = dict(zip(live_ds['WELL'].values, live_ds['SUB-ASSET'].values))
    try:
        # if well is in live DS, return sub-asset
        return lookup_dict[well_name]
    except KeyError:
        # else well is generic. Extract sub-asset from well name
        return well_name.partition(partition_character)[0]


def save_model_drivers(_model_level_drivers, local_only=False):
    scenario_filepaths_all = model_control.get_scenario_filepaths_all()

    # if _model_level_drivers:
    #     model_level_drivers = _model_level_drivers
    #     save_y_n = input(f'\n| model_level_drivers updated. Save? Y/N ')
    # else:
    #     save_y_n = input(f'\n| Save model_level_drivers? Y/N ')
    #
    # if save_y_n.lower() == 'y':

    # save model level drivers to json and xlsx
    for driver, driver_df in model_level_drivers.items():
        folder = f'{local_scenario_folder}/drivers/'
        network_folder = f'{network_scenario_folder}/drivers/'
        folder_list = [folder, network_folder] if local_only is False else [folder]

        filename_json = f'{driver}.json'
        filename_xlsx = f'{driver}.xlsx'
        for f in folder_list:
            if f == folder:
                scenario_filepaths_all['local'].append(f + filename_xlsx)
            else:
                scenario_filepaths_all['network'].append(f + filename_xlsx)
            # fp = f + filename_json
            # try:
            #     # save the dataframe for this field to _scenario folder json
            #     save_to_json(driver_df,
            #                  folder=f,
            #                  filepath=fp)
            # except (FileNotFoundError, PermissionError, ValueError):
            #     print(f'\n!! {fp} not found or network drive not accessible')
            try:
                # save to excel
                save_to_excel(driver_df,
                              folder=f,
                              filename=filename_xlsx)
            except (FileNotFoundError, PermissionError, ValueError):
                print(f'\n!! {f + filename_xlsx} not found or network drive not accessible')
    # else:
    #     print(f'!! Model drivers not saved.')
    #     pass


def get_asset_level_drivers():
    '''Returns asset level drivers filtered for sub-assets being modeled. This should be called if asset_level_drivers is used anywhere outside this module.'''
    return _asset_level_drivers[_asset_level_drivers['Run Model For Sub-Asset?'] == 'Yes']


def get_gross_type_curves():
    return {'type_curves_oil': type_curves_all.type_curves_oil,
            'type_curves_gas': type_curves_all.type_curves_gas,
            'type_curves_water': type_curves_all.type_curves_water}


def get_model_level_drivers():
    if "model_level_drivers" not in globals():
        return initialize()
    else:
        global model_level_drivers
        return model_level_drivers


def get_bootstrap_prices():
    if "bootstrap_prices" not in globals():
        return initialize()
    else:
        global bootstrap_prices
        return bootstrap_prices

def initialize():
    # load model strip prices and model period to model_price_dict
    # model_price_dict = {'bootstrap_prices': dict of dfs by comdty,
    # 'model_period': DateTimeIndex,
    # 'model_prices_10yr': 10 years of model prices}

    # model variables
    global strip_pricing_date
    strip_pricing_date = model_control.strip_pricing_date

    global model_start_date
    model_start_date = model_control.model_start_date

    global model_months
    model_months = model_control.model_months

    global ethane_mode
    ethane_mode = model_control.ethane_mode

    global ngl_fixed_recoveries
    ngl_fixed_recoveries = model_control.ngl_fixed_recoveries

    global scenario_time_stamp
    scenario_time_stamp = model_control.scenario_time_stamp

    global is_test_scenario
    is_test_scenario = model_control.is_test_scenario

    global local_scenario_folder
    local_scenario_folder = model_control.local_scenario_folder

    global network_scenario_folder
    network_scenario_folder = model_control.network_scenario_folder

    global scenario_filepaths_all
    scenario_filepaths_all = model_control.get_scenario_filepaths_all()

    global model_price_dict
    model_price_dict = pr.get_bootstrap_prices(
        strip_pricing_date=strip_pricing_date,
        model_start_date=model_start_date,
        model_months=model_months,
        check_local=True,
        inflation_adjusted=False,
        ethane_mode=ethane_mode,
        output_to_excel=False)

    pprint.pprint(model_price_dict)

    global bootstrap_prices
    bootstrap_prices = model_price_dict['bootstrap_prices']

    for key in bootstrap_prices:
        try:
            bootstrap_prices[key].index = pd.DatetimeIndex(bootstrap_prices[key].index, tz='UTC')
        except TypeError:
            print('!! data is already tz-aware UTC, unable to set specified tz: UTC')

    global model_period
    model_period = model_price_dict['model_period']

    global model_prices
    model_prices = model_price_dict['model_prices_10yr']

    global summary_stats
    summary_stats = model_price_dict['summary_stats']

    # bootstrapper format template dataframe
    _template = [_ for _ in bootstrap_prices.values()][0]
    _template_index = pd.date_range(start=_template.index[0], end=_template.index[-1], freq='M', tz='UTC')

    global boots_template_df
    boots_template_df = pd.DataFrame(index=_template_index, columns=_template.columns)
    boots_template_df.fillna(0, inplace=True)

    # add template to model control
    model_control.add_to_model_control(
        object_dict={'boots_template_df': boots_template_df},
        deep_copy=True
    )

    # load live drilling schedule
    global live_ds
    live_ds = model_inputs.load_live_drilling_schedule()
    print(live_ds)

    # load asset level drivers

    global _asset_level_drivers
    _asset_level_drivers = model_inputs.load_asset_level_drivers(load_all=True)
    print(_asset_level_drivers)

    # load production splitter
    # NOTE: uses model.model_period, so must be executed after model_price_dict is built
    global production_splitter
    production_splitter = model_inputs.load_production_splitter()
    production_splitter = production_splitter.loc[[_ for _ in production_splitter.index if _ in model_period], :]
    production_splitter.index = pd.DatetimeIndex(production_splitter.index, tz='UTC')
    print(production_splitter)

    # load fees schedule
    global fees_schedule
    fees_schedule = model_inputs.load_fees_schedule()
    fees_schedule = fees_schedule.loc[[_ for _ in fees_schedule.index if _ in model_period], :]
    print(fees_schedule)

    # load D&C capex drivers
    global dnc_capex_drivers
    dnc_capex_drivers = model_inputs.load_dnc_capex_drivers()
    print(dnc_capex_drivers)

    # load monthly opex drivers
    global opex_drivers_monthly_raw
    opex_drivers_monthly_raw = model_inputs.load_opex_drivers_monthly()
    opex_drivers_monthly_raw.index = pd.DatetimeIndex(opex_drivers_monthly_raw.index, tz='UTC')

    # reset index
    global opex_drivers_monthly
    opex_drivers_monthly = pd.DataFrame(
        index=model_period,
        columns=opex_drivers_monthly_raw.columns
    ).fillna(0)

    for col in opex_drivers_monthly_raw.columns:
        opex_drivers_monthly.loc[:, col] = opex_drivers_monthly_raw[col].values[:len(model_period)]
    print(opex_drivers_monthly)

    # load SG&A from monthly opex drivers
    global sg_and_a
    sg_and_a = pd.Series(opex_drivers_monthly.loc[:, 'sg_and_a'])

    # load model type curves
    global type_curves_all
    type_curves_all = tc.TypeCurves()

    # load rig crew timing
    global rig_crew_timing
    rig_crew_timing = model_inputs.load_rig_crew_timing()
    print(rig_crew_timing)

    # load current hedges
    global current_hedges
    current_hedges = model_inputs.load_current_hedges()

    # load PDP, infra capex, working cap balance
    global pdp_input_dict
    pdp_input_dict = model_inputs.load_pdp_drivers(model_control.driver_input_codes)
    # filter down to modeled sub-assets only
    pdp_input_dict = {k: v for k, v in pdp_input_dict.items() if k in get_asset_level_drivers().index}
    print(f'| PDP Inputs Modeled:\n {pdp_input_dict}')

    # load infrastructure capex in boots_template_df format
    global infra_capex_dict
    infra_capex_dict = {}

    # load working cap balance in boots_template_df format
    global working_cap_balance_dict
    working_cap_balance_dict = {}
    # adjust to model period
    for subasset, pdp_df in pdp_input_dict.items():
        pdp_input_for_sub_asset = pdp_input_dict[subasset]
        pdp_input_for_sub_asset = pdp_input_for_sub_asset.loc[
                                  [_ for _ in pdp_input_for_sub_asset.index if _ in model_period], :]
        pdp_input_for_sub_asset.fillna(0, inplace=True)
        pdp_input_for_sub_asset.index = pd.DatetimeIndex(pdp_input_for_sub_asset.index, tz='UTC')
        pdp_input_dict[subasset] = pdp_input_for_sub_asset

        infra_capex = pd.DataFrame().reindex_like(boots_template_df)
        infra_capex.fillna(0.0, inplace=True)
        working_cap_balance = pd.DataFrame().reindex_like(boots_template_df)
        working_cap_balance.fillna(0.0, inplace=True)

        for col in infra_capex.columns:
            infra_capex.loc[:, col] = pdp_input_for_sub_asset.loc[
                [_ for _ in infra_capex.index if _ in pdp_input_for_sub_asset.index],
                'Infrastructure / Other Capex'
            ]
            infra_capex.fillna(0.0, inplace=True)

            working_cap_balance.loc[:, col] = pdp_input_for_sub_asset.loc[
                [_ for _ in working_cap_balance.index if _ in pdp_input_for_sub_asset.index],
                'Capex From Prior Periods'
            ]
            working_cap_balance.fillna(0.0, inplace=True)

        infra_capex_dict[subasset] = infra_capex
        working_cap_balance_dict[subasset] = working_cap_balance

    # load historical financials by sub-asset
    global historical_financials_dict
    historical_financials_dict = model_inputs.load_historical_financials(model_control.driver_input_codes)
    # filter down to modeled sub-assets only
    historical_financials_dict = {k: v for k, v in historical_financials_dict.items() if
                                  k in get_asset_level_drivers().index}
    print(f'| Historical financials modeled:\n {historical_financials_dict}')

    # create the model level drivers dictionary
    # outputs with single dataframes
    global model_level_drivers
    model_level_drivers = {
        'asset_level_drivers': _asset_level_drivers,
        'live_ds': live_ds,
        'dnc_capex_drivers': dnc_capex_drivers,
        'model_prices': model_prices,
        'fees_schedule': fees_schedule,
        'production_splitter': production_splitter,
        'opex_drivers_monthly': opex_drivers_monthly,
        'current_hedges': current_hedges,
        'type_curves_oil': type_curves_all.type_curves_oil,
        'type_curves_gas': type_curves_all.type_curves_gas,
        'type_curves_water': type_curves_all.type_curves_water,
    }

    # outputs with sub-asset level dataframes
    model_level_drivers.update({f'pdp_input_dict_' + subasset: df for subasset, df in pdp_input_dict.items()})
    model_level_drivers.update({f'infra_capex_' + subasset: df for subasset, df in infra_capex_dict.items()})
    model_level_drivers.update(
        {f'working_cap_balance_' + subasset: df for subasset, df in working_cap_balance_dict.items()})
    model_level_drivers.update(
        {f'hist_financials_' + subasset: df for subasset, df in historical_financials_dict.items()})
    model_level_drivers.update({f'bootstrap_prices_{comdty}': df for comdty, df in bootstrap_prices.items()})
    model_level_drivers.update({f'summary_stats_{comdty}': df for comdty, df in summary_stats.items()})

    return model_level_drivers


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# EXECUTION #-----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

if __name__ == "__main__":
    initialize()
