from useful_functions import *
import type_curves as tc
import pandas as pd

# mode input folder from useful_functions -
input_folder = root_folder_model_input()['root_folder']


def clean_up_csv_load(df: pd.DataFrame):
    # cleanup
    unnamed_cols = [_ for _ in df.columns if 'Unnamed:' in _]
    df = df.drop(columns=unnamed_cols)
    df.dropna(axis=0, how='all', inplace=True)
    df = df.rename(
        columns=dict(zip(df.columns, [_.strip() for _ in df.columns])))
    return df


def load_historical_financials(driver_input_codes: dict):
    '''Loads hist_financials_x from csv.
    Args:
        |-- driver_input_codes, dict: dictionary of {subasset : historical financials code}
        '''
    hist_financials_dict = {}
    for sub_asset, code in driver_input_codes.items():
        filepath = input_folder + f'/hist_financials_{code}.csv'
        hist_financials = pd.read_csv(filepath, parse_dates=True)
        hist_financials = hist_financials.set_index(pd.to_datetime(
            [xldate_to_datetime(_) for _ in hist_financials['Date']]
        )
        )
        hist_financials.index = pd.date_range(
            start=hist_financials.index[0],
            end=hist_financials.index[-1],
            freq='M',
            tz='UTC'
        )

        hist_financials.drop(columns=['Date'], inplace=True)
        hist_financials = clean_up_csv_load(hist_financials)
        hist_financials.fillna(0.0,inplace=True)
        # other initialization adjustments
        print(f'Historical Financials by Sub-Asset loaded >> hist_financials_{code}')
        hist_financials_dict[sub_asset] = hist_financials
    return hist_financials_dict


def load_pdp_drivers(driver_input_codes: dict):
    '''Loads monthly_drivers_x from csv.
    Args:
        |-- driver_input_codes, dict: dictionary of {subasset : monthly driver code}
        '''
    pdp_driver_dict = {}
    for sub_asset, code in driver_input_codes.items():
        filepath = input_folder + f'/monthly_drivers_{code}.csv'
        pdp_drivers = pd.read_csv(filepath, parse_dates=True)
        pdp_drivers = pdp_drivers.set_index(
            pd.DatetimeIndex(
                [xldate_to_datetime(_) for _ in pdp_drivers['Date']]))
        pdp_drivers.drop(columns=['Date'], inplace=True)
        pdp_drivers = clean_up_csv_load(pdp_drivers)
        # other initialization adjustments
        print(f'PDP Drivers loaded >> monthly_drivers_{code}')
        pdp_driver_dict[sub_asset] = pdp_drivers
    return pdp_driver_dict



def load_current_hedges(alt_filepath = None):
    '''Loads current_hedges from csv.'''
    if alt_filepath:
        # todo: update this to pull from the alt_filepath
        filepath = input_folder + '/current_hedges.csv'
    else:
        filepath = input_folder + '/current_hedges.csv'
    current_hedges = pd.read_csv(filepath, parse_dates=True)
    # current_hedges = current_hedges.set_index('Trade Date')
    current_hedges = clean_up_csv_load(current_hedges)
    current_hedges.reset_index(inplace=True)
    current_hedges.rename(columns={'index': 'trade_id'}, inplace=True)
    for col in current_hedges:
        # make upper case
        try:
            current_hedges[col] = [_.upper() for _ in current_hedges[col]]
        except AttributeError:
            print(f'!! Cannot convert {col} to upper case.')
        # convert date-like columns to string_date
        if any([_ in col for _ in ['date', 'mth']]):
            current_hedges[col] = [
                string_date(xldate_to_datetime(_)) for _ in current_hedges[col]]
    print('\n\n| Current Hedges loaded >> current_hedges')
    return current_hedges



def load_opex_drivers_monthly():
    '''Loads opex_drivers_monthly from csv.'''
    filepath = input_folder + '/opex_drivers_monthly.csv'
    opex_drivers_monthly = pd.read_csv(filepath, parse_dates=True)
    opex_drivers_monthly = opex_drivers_monthly.set_index(
        pd.DatetimeIndex(
            [xldate_to_datetime(_) for _ in opex_drivers_monthly['Date']]))
    opex_drivers_monthly.drop(columns=['Date'], inplace=True)
    opex_drivers_monthly = clean_up_csv_load(opex_drivers_monthly)
    # other initialization adjustments
    print('Opex Drivers Monthly loaded >> opex_drivers_monthly')
    return opex_drivers_monthly


def load_fees_schedule():
    '''Loads fees_schedule from csv.'''
    filepath = input_folder + '/fees_schedule.csv'
    fees_schedule = pd.read_csv(filepath, parse_dates=True)
    fees_schedule = fees_schedule.set_index(
        pd.DatetimeIndex(
            [xldate_to_datetime(_) for _ in fees_schedule['Date']]))
    fees_schedule.drop(columns=['Date'], inplace=True)
    fees_schedule = clean_up_csv_load(fees_schedule)
    # other initialization adjustments
    print('Fees Schedule loaded >> fees_schedule')
    return fees_schedule


def load_production_splitter():
    '''Loads production splitter inputs from csv.'''
    filepath = input_folder + '/production_splitter.csv'
    production_splitter = pd.read_csv(filepath, parse_dates=True)
    production_splitter = production_splitter.set_index(
        pd.DatetimeIndex(
            [xldate_to_datetime(_) for _ in production_splitter['Date']]))
    production_splitter.drop(columns=['Date'], inplace=True)
    production_splitter = clean_up_csv_load(production_splitter)
    print('\n\n| Production Splitter loaded >> production_splitter')
    return production_splitter


def load_rig_crew_timing():
    '''Loads rig crew timing.'''
    # Rig crew timing in relative days
    rig_crew_timing = {
        "afe_to_spud": pd.to_timedelta(-91, unit='d'),
        "planning_to_spud": pd.to_timedelta(-122, unit='d'),
        "permitted_to_spud": pd.to_timedelta(-91, unit='d'),
        "location_build_to_spud": pd.to_timedelta(-31, unit='d'),
        "pad_spud_to_first_well_spud": pd.to_timedelta(-1, unit='d'),
        "spud_to_td": pd.to_timedelta(10, unit='d'),
        "skid_td_to_next_spud": pd.to_timedelta(0, unit='d'),
        "final_td_to_rig_release": pd.to_timedelta(0, unit='d'),
        "rig_move_to_next_pad": pd.to_timedelta(90, unit='d'),
        "rig_release_to_frac_start": pd.to_timedelta(5, unit='d'),
        "frac_days_per_well": pd.to_timedelta(11, unit='d'),
        "frac_end_to_drill_out_start": pd.to_timedelta(1, unit='d'),
        "drill_out_days_per_well": pd.to_timedelta(3, unit='d'),
        "completion_end_to_pop_date": pd.to_timedelta(1, unit='d'),
        "frac_fleet_move_to_next_pad": pd.to_timedelta(90, unit='d'),
        "pop_date_to_first_oil": pd.to_timedelta(0, unit='d'),
        "pop_date_to_loe": pd.to_timedelta(30, unit='d'),
        "spud_to_post_drill_filing_req": pd.to_timedelta(90, unit='d')
    }
    print('\n\n| Rig crew timing loaded >> rig_crew_timing')
    return rig_crew_timing


def load_type_curves():
    '''Loads type curves from csv.'''
    model_type_curves = tc.TypeCurves()
    print('\n\n| Type curves loaded >> type_curves_all')
    return model_type_curves


def load_dnc_capex_drivers():
    '''Loads D&C capex drivers from csv.'''
    filepath = input_folder + '/dnc_capex_drivers.csv'
    dnc_capex_drivers = pd.read_csv(filepath, parse_dates=True)
    dnc_capex_drivers = dnc_capex_drivers.set_index('CAPEX CODE')
    dnc_capex_drivers = clean_up_csv_load(dnc_capex_drivers)
    print('\n\n| D&C Capex Drivers loaded >> dnc_capex_drivers')
    return dnc_capex_drivers


def load_asset_level_drivers(load_all=True):
    '''Loads asset level drivers from csv.
    Args:
    -- load_all, bool: passing True will load all sub_assets in csv input. False loads only those with "Run Model For Sub-Asset? == 'Yes.
    Returns:
        asset_level_drivers, a pd.DataFrame with index=sub-asset list, columns=input fields
        '''
    filepath = input_folder + '/asset_level_drivers.csv'
    asset_level_drivers = pd.read_csv(filepath, parse_dates=True)
    asset_level_drivers = asset_level_drivers.T
    asset_level_drivers.columns = asset_level_drivers.iloc[0, :]
    asset_level_drivers = asset_level_drivers.drop(index=['SUB-ASSET'])
    asset_level_drivers = clean_up_csv_load(asset_level_drivers)
    asset_level_drivers['Asset Active Date'] = [
        xldate_to_datetime(
            pd.to_numeric(_)) for _ in asset_level_drivers['Asset Active Date']]
    if load_all==False:
        asset_level_drivers = asset_level_drivers[asset_level_drivers['Run Model For Sub-Asset?'] == 'Yes']
    print(f'\n\n| Asset-Level Drivers loaded >> asset_level_drivers')
    return asset_level_drivers


def load_live_drilling_schedule():
    '''Loads live drilling schedule from csv.'''
    filepath = input_folder+'/live_ds.csv'
    live_ds = pd.read_csv(filepath, parse_dates=True)
    for col in live_ds.loc[:, 'AFE':'1ST OIL']:
        live_ds.loc[:, col] = [
            xldate_to_datetime(_) for _ in live_ds.loc[:, col].to_list()
        ]
    # live_ds = live_ds.set_index('WELL')
    print('\n\n| Live Drilling Schedule loaded >> live_ds')
    return live_ds