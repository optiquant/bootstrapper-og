import _model.model_control as model_control
import _model.model_drivers as model_drivers
from _model.useful_functions import *

import pandas as pd
import numpy as np
from collections import namedtuple
from pandas.tseries.offsets import *
import pprint

# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #---------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#

# build a really fast multi-well / multi-asset production engine
data_source = model_control.existing_scenario_data_source
model_months = model_control.model_months
asset_level_drivers = model_drivers.get_asset_level_drivers()
model_period = model_drivers.model_period
production_splitter = model_drivers.production_splitter
rig_crew_timing = model_drivers.rig_crew_timing
live_ds = model_drivers.live_ds.set_index('WELL')
modeled_wells_all = model_control.modeled_wells_all
print(f'\n| Modeled well in sequence:\n {modeled_wells_all}')

# set the filepaths for saving financing module outputs
scenario_root_folders = model_control.get_scenario_root_folders()
scenario_filepaths_all = model_control.get_scenario_filepaths_all()
save_to = 'both'  # or 'local' or 'network'
fp_local = scenario_root_folders['local_scenario_folder']
fp_network = scenario_root_folders['network_scenario_folder']
print(f'\n$$$ Production engine outputs will be saved to {save_to}: {[_ for _ in (fp_local, fp_network)]}')

# dictionaries populated here
production_engine_outputs = {}
wellhead_prod_total = {}
wi_prod_total = {}
nri_prod_total = {}

raw_tc_input = {
    'oil': model_drivers.type_curves_all.type_curves_oil,
    'gas': model_drivers.type_curves_all.type_curves_gas,
    'water': model_drivers.type_curves_all.type_curves_water
}

# dictionary for well-level drivers
well_drivers_dict = {}

# dictionary for well activity dates (keys = well names, values = ActivityDates namedtuples)
well_activity_dates_dict = {}

# namedtuples for WI / NRI volumes (including shrunk gas, market allocations, and BTU equivalents)
WIVolume = namedtuple('WIVolume', ['oil_midland_mbbl',
                                   'oil_houston_mbbl',
                                   'oil_all_mbbl',
                                   'gas_hsc_mmcf_shrunk',
                                   'gas_waha_mmcf_shrunk',
                                   'gas_all_mmcf_shrunk',
                                   'gas_hsc_bbtu_shrunk',
                                   'gas_waha_bbtu_shrunk',
                                   'gas_all_bbtu_shrunk',
                                   'ngl_ethane_mbbl',
                                   'ngl_propane_mbbl',
                                   'ngl_n_butane_mbbl',
                                   'ngl_iso_butane_mbbl',
                                   'ngl_nat_gasoline_mbbl',
                                   'ngl_all_mbbl',
                                   'water_all_mbbl'])

NRIVolume = namedtuple('NRIVolume', ['oil_midland_mbbl',
                                     'oil_houston_mbbl',
                                     'oil_all_mbbl',
                                     'gas_hsc_mmcf_shrunk',
                                     'gas_waha_mmcf_shrunk',
                                     'gas_all_mmcf_shrunk',
                                     'gas_hsc_bbtu_shrunk',
                                     'gas_waha_bbtu_shrunk',
                                     'gas_all_bbtu_shrunk',
                                     'ngl_ethane_mbbl',
                                     'ngl_propane_mbbl',
                                     'ngl_n_butane_mbbl',
                                     'ngl_iso_butane_mbbl',
                                     'ngl_nat_gasoline_mbbl',
                                     'ngl_all_mbbl'])

# mapper: _activity date attributes in model <> _activity dates in input file
activity_dates_input_map = {
    'afe': "AFE",
    'planning_staking': "PLANNING & STAKING",
    'permitted': "PERMITTED",
    'location_build': "LOCATION BUILDING",
    'spud': "SPUD",
    'pad_spud': "PAD SPUD",
    'td': "TD",
    'rig_release': "RIG RELEASE (PAD)",
    'compl_start': "COMPLETION START",
    'frac_end': "FRAC END",
    'drill_out_start': "DRILL OUT START",
    'compl_end': "COMPLETION END",
    'pop': "PUT ON PRODUCTION",
    'to_loe': "TURNED TO LOE",
    'post_drill_filing': "POST DRILL FILING REQUIREMENTS",
    'first_oil': "1ST OIL"
}
# ActivityDates: namedtuple to access model's _activity date attributes
# NOTE: attributes here should be the same as activity_dates_input_map keys
ActivityDates = namedtuple(
    'ActivityDates', ['afe',
                      'planning_staking',
                      'permitted',
                      'location_build',
                      'spud',
                      'pad_spud',
                      'td',
                      'rig_release',
                      'compl_start',
                      'frac_end',
                      'drill_out_start',
                      'compl_end',
                      'pop',
                      'to_loe',
                      'post_drill_filing',
                      'first_oil'
                      ]
)

master_drilling_schedule = pd.DataFrame(index=modeled_wells_all, columns=[_ for _ in ActivityDates._fields])

# well POP dates
well_pop_dates_dict = {}

# modeled type curve dictionary (keys: oil, gas, water, values: dataframes of TCs for each well in drilling sequence)
# each TC dataframe: index = range(0, model months), columns = well names in sequence
type_curves_modeled_dict = {}


# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#
def load_ngl_yields():
    '''Loads NGL yields by sub-asset into the dictionaries ngl_yields and ngl_pct_of_barrel. (keys = subassets, values = dicts).'''

    global ngl_yields
    ngl_yields = {}

    global ngl_pct_of_barrel
    ngl_pct_of_barrel = {}

    for sub_asset in asset_level_drivers.index:
        ngl_yields_actual = dict(
            asset_level_drivers.loc[sub_asset, [
                "NGL Yield - Actual - Ethane (Bbl / Mcf)",
                "NGL Yield - Actual - Propane (Bbl / Mcf)",
                "NGL Yield - Actual - n-Butane (Bbl / Mcf)",
                "NGL Yield - Actual - iso-Butane (Bbl / Mcf)",
                "NGL Yield - Actual - Nat. Gasoline (Bbl / Mcf)"]]
        )

        ngl_nicks = get_ngl_nicks()
        # convert string input to float
        ngl_yields_actual = {k: float(v) for k, v in zip(ngl_nicks, ngl_yields_actual.values())}
        # add to global dict
        ngl_yields[sub_asset] = ngl_yields_actual
        print(f'| NGL yields used for {sub_asset} >> {ngl_yields_actual}')

        ngl_pct_composition = {k: v / sum(ngl_yields_actual.values()) for k, v in ngl_yields_actual.items()}

        # add to global dict
        ngl_pct_of_barrel[sub_asset] = ngl_pct_composition
        print(f'| NGL % of barrel >> {ngl_pct_of_barrel}')
    return ngl_yields, ngl_pct_of_barrel


def shift_adjust_unit_stream(well_pop_date, unit_stream_to_adjust: pd.Series):
    '''Takes a POP date and production stream for a and returns a shifted+adjusted production stream. The series is shifted by the number of months between the POP month for this well and the start of the model_period. The "adjust" refers to an adjustment to each month's unit stream based on the exact POP day of the month (e.g. a well that POPs on the 30th day of a 30-day month will have its first month of production adjusted down to (1/30) = 3.33% of the type curve's first month production. The remaining 96.67% of the type curve's first month production will be added to the second month, and so on.
    Args:
        well_pop_date, pd.datetime: pop date of this well. Typically referenced by activity_dates.pop
        unit_stream_to_adjust, pd.Series: a pandas series that is to be shifted
    Returns:
        unit_stream_adjusted, pd.Series: a series of the shifted+adjusted unit stream, maintaining the original index
        '''
    print(f'| POP date: {string_date(well_pop_date)}')

    pop_month = well_pop_date.month
    pop_year = well_pop_date.year
    first_month_end = pd.to_datetime(f'{pop_month}/20/{pop_year}') + MonthEnd(0)
    print(f'| First Month End: {string_date(first_month_end)}')

    days_of_prod = pd.to_timedelta(first_month_end.date() - well_pop_date.date(),
                                   unit='D') + pd.to_timedelta(1, unit='D')
    days_in_month = first_month_end.day
    print(f'| Days of prod (mo. 1): {days_of_prod}')
    print(f'| Days in month (mo. 1): {days_in_month}')

    # first month factor - adjusts the start of the unit stream by the days left in this month after well POP
    mf1 = days_of_prod.days / days_in_month
    mf2 = 1 - mf1
    print(f'| mf1 / mf2: {mf1 * 100: .2f}% / {mf2 * 100: .2f}%')

    # shifted and mf-adjusted production stream
    shift_months_mf1 = 12 * (first_month_end.year - model_period[0].year) + first_month_end.month - model_period[
        0].month
    shift_months_mf2 = shift_months_mf1 + 1
    print(f'| Shift months: {shift_months_mf1}')

    # adjusted NRI production streams
    unit_stream_shifted_mf1 = unit_stream_to_adjust.shift(shift_months_mf1).fillna(0)
    unit_stream_shifted_mf2 = unit_stream_to_adjust.shift(shift_months_mf2).fillna(0)
    unit_stream_adjusted = unit_stream_shifted_mf1 * mf1 + unit_stream_shifted_mf2 * mf2

    print(f'| EUR >> raw: {unit_stream_to_adjust.values.sum():.2f}')
    print(f'| EUR >> shifted: {unit_stream_shifted_mf1.values.sum():.2f}')
    print(f'| EUR >> adjusted: {unit_stream_adjusted.values.sum(): .2f}')
    print(f'| Raw / shifted / adjusted Unit Streams:\n')
    _rsa = pd.DataFrame(zip(unit_stream_to_adjust, unit_stream_shifted_mf1, unit_stream_adjusted),
                        columns=['raw', 'shifted', 'adjusted'])
    print(f'{_rsa}')
    return unit_stream_adjusted


def load_well_drivers_dict():
    global well_drivers_dict

    # get the type curves for each modeled well
    print(f'\n| Type curves used by well >>>')

    # list of wells to include in capex
    if model_control.include_remaining_pdp_capex:
        # get the PDP wells also
        _capex_wells = model_control.pdp_wells_with_remaining_capex.copy()
        _capex_wells.extend(modeled_wells_all)
    else:
        _capex_wells = modeled_wells_all.copy()

    for well in _capex_wells:
        # get the type curve and sub_asset name from the live drilling schedule or asset-level drivers for the sub-asset
        if 'GENERIC' in well:
            sub_asset = well.partition('//')[0]
            tc_name = asset_level_drivers.loc[sub_asset, 'TYPE CURVE AREA']
            perfed_ll = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
            base_ll_capex = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
            base_ll_tc = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
            tc_multiplier = min(perfed_ll / base_ll_tc, 1.30)
            wells_on_pad = float(asset_level_drivers.loc[sub_asset, 'WELLS ON PAD'])
            _w_num = int(well.partition('//GENERIC ')[2])
            well_num_on_pad = [np.mod(_w_num, wells_on_pad) if np.mod(_w_num, wells_on_pad) != 0.0 else wells_on_pad][0]
            wi_pct = float(asset_level_drivers.loc[sub_asset, 'WI %']) / 100
            nri_pct = float(asset_level_drivers.loc[sub_asset, 'NRI %']) / 100
            gas_shrink = float(asset_level_drivers.loc[sub_asset, 'Gas Shrink'])
            gas_btu_factor_residue = float(asset_level_drivers.loc[sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
            gas_btu_factor_wellhead = float(asset_level_drivers.loc[sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
            rig_crew = asset_level_drivers.loc[sub_asset, 'Rig Crew #']
            capex_scenario_name = asset_level_drivers.loc[sub_asset, 'CAPEX SCENARIO']
        elif well in live_ds.index:
            sub_asset = live_ds.loc[well, 'SUB-ASSET']
            tc_name = live_ds.loc[well, 'TYPE CURVE AREA']
            perfed_ll = float(live_ds.loc[well, 'PERFED LATERAL LENGTH'])
            base_ll_capex = float(live_ds.loc[well, 'BASE LL FOR CAPEX'])
            # THIS IS FROM ASSET-LEVEL DRIVERS!
            base_ll_tc = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
            tc_multiplier = min(perfed_ll / base_ll_tc, 1.30)
            well_num_on_pad = float(live_ds.loc[well, 'DRILL ORDER'])
            wells_on_pad = float(live_ds.loc[well, 'WELLS ON PAD'])
            wi_pct = float(live_ds.loc[well, 'WI %']) / 100
            nri_pct = float(live_ds.loc[well, 'NRI %']) / 100
            gas_shrink = float(asset_level_drivers.loc[sub_asset, 'Gas Shrink'])
            gas_btu_factor_residue = float(asset_level_drivers.loc[sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
            gas_btu_factor_wellhead = float(asset_level_drivers.loc[sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
            rig_crew = asset_level_drivers.loc[sub_asset, 'Rig Crew #']
            capex_scenario_name = live_ds.loc[well, 'CAPEX SCENARIO']
        else:
            print(f'\n!! {well} not found in live drilling schedule, but also not generic. Review well name.')

        _well_drivers = {
            'sub_asset': sub_asset,
            'well_num_on_pad': well_num_on_pad,
            'wells_on_pad': wells_on_pad,
            'tc_name': tc_name,
            'wi_pct': wi_pct,
            'nri_pct': nri_pct,
            'gas_shrink': gas_shrink,
            'gas_btu_factor_residue': gas_btu_factor_residue,
            'gas_btu_factor_wellhead': gas_btu_factor_wellhead,
            'perfed_ll': perfed_ll,
            'base_ll_capex': base_ll_capex,
            'base_ll_tc': base_ll_tc,
            'tc_multiplier': tc_multiplier,
            'rig_crew': rig_crew,
            'capex_scenario_name': capex_scenario_name
        }

        # add well drivers to modeled type curve dictionary
        well_drivers_dict[well] = _well_drivers
        print(f'| Well drivers:\n|-- {well} >>> {_well_drivers}')

    return well_drivers_dict



def reassign_type_curves(well_drivers_dict: dict):
    '''Reassigns type curve areas for a sub-asset if multiple type curves are required.
    Args:
        |-- sub_asset, str: the name of the sub-asset whose type curves are to be split into sub-areas
        |-- well_drivers, dict: a dictionary of the drivers for each development well

    Returns: the well_drivers dictionary with type curves updated
    '''
    type_curve_sub_areas = model_control.get_reassigned_type_curve_areas()

    # get all wells for each sub-asset in the reassigned_type_curve_areas dict
    for sub_asset in type_curve_sub_areas:
        # get all wells for this sub-asset in the well_drivers_dict
        sub_asset_well_drivers = {
            well: drivers for well, drivers in well_drivers_dict.items() if drivers['sub_asset'] == sub_asset
        }

        # sub-area location count dict
        sub_area_locations_dict = type_curve_sub_areas[sub_asset]

        # get a list of all type curve name attributes
        sub_asset_tc_list = [drivers['tc_name'] for well, drivers in sub_asset_well_drivers.items()]

        start_index = 0
        for sub_area, locations in sub_area_locations_dict.items():
            # get the first x well drivers
            sub_asset_tc_list[start_index: start_index+locations] = [sub_area for _ in range(start_index, start_index+locations)]
            start_index += locations

        print(f'| sub_asset_tc_list: {sub_asset_tc_list}')

        # assign to the sub_asset_well_drivers dict
        for well_index, (well, drivers) in enumerate(sub_asset_well_drivers.items()):
            drivers['tc_name'] = sub_asset_tc_list[well_index]

        # update and return the main well_drivers_dict
        well_drivers_dict.update(sub_asset_well_drivers)
        _reassigned = {well: drivers['tc_name'] for well, drivers in well_drivers_dict.items()}
        print(f'| Reassigned type curves:\n {_reassigned}')

        #_q = input('Continue? >>> ')

    return well_drivers_dict



def get_activity_dates_for(well: str):
    # calculates _activity dates for this well, depending on if well is GENERIC or defined in the live drilling schedule

    global live_ds
    global last_generic_well_td
    well_drivers = well_drivers_dict[well]

    # subasset for well
    sub_asset = model_drivers.get_sub_asset(well)
    asset_active_date = pd.to_datetime(asset_level_drivers.loc[sub_asset, 'Asset Active Date'], utc=True)

    wells_on_pad = well_drivers['wells_on_pad']
    well_num_on_pad = well_drivers['well_num_on_pad']

    print(f'\n---- {well} ----')
    '''Calculate _activity dates for this well if GENERIC, or get dates from live drilling schedule.'''
    if 'GENERIC' in well:
        # calculate _activity dates starting from well_activity_start_date
        # set the permitted date (first capex event)
        # get the last rank 2 well (from the sorted live_ds)
        _r2w = [_ for _ in modeled_wells_all if 'GENERIC' not in _]
        _gw = [_ for _ in modeled_wells_all if 'GENERIC' in _]


        # if this is the first generic well, anchor the well activity start date to the later of the last rank 2 well, or the asset active date
        if well == _gw[0]:
            rank_2_wells_modeled = live_ds.loc[[_ in _r2w for _ in live_ds.index], :]
            # if there are any rank 2 wells modeled, anchor to final rank 2 well
            if len(rank_2_wells_modeled) > 0:
                print(f'\n| Rank 2 wells modeled: {rank_2_wells_modeled}')
                rank_2_wells_modeled.sort_values(by=['TD'], axis=0, inplace=True)
                final_rank_2_well = dict(rank_2_wells_modeled.iloc[-1, :])
                print(f'\n| Final rank 2 well:\n {final_rank_2_well}')

                # set the well activity start date
                # the later of the last rank 2 well, or the asset active date
                _anchor_date = max(pd.to_datetime(final_rank_2_well['TD'],utc=True), asset_active_date)
                well_activity_start_date = _anchor_date + rig_crew_timing[
                    'rig_move_to_next_pad'] + rig_crew_timing['permitted_to_spud']
            else:
                # else there are no rank 2 wells, so anchor the first generic well to the later of the model start or the asset active date
                well_activity_start_date = max(asset_active_date, pd.to_datetime(model_period[0]) + MonthBegin(-1))

        # else if this is not the first generic well, but is not a new pad, anchor the activity start to the last generic well modeled
        elif well != _gw[0] and well_num_on_pad != 1:
            well_activity_start_date = last_generic_well_td + rig_crew_timing[
                'skid_td_to_next_spud'] + rig_crew_timing['permitted_to_spud']

        # else if this is not the first generic well, but is a new pad, anchor the activity start to the last generic well modeled
        elif well != _gw[0] and well_num_on_pad == 1:
            well_activity_start_date = last_generic_well_td + rig_crew_timing[
                'rig_move_to_next_pad'] + rig_crew_timing['permitted_to_spud']

        permitted = well_activity_start_date
        # calc implied spud date (subtract negative timedelta)
        spud = permitted - rig_crew_timing[
            'permitted_to_spud']
        # then set other dates relative to spud, using the rig_crew_timing dict
        afe = spud + rig_crew_timing[
            'afe_to_spud']
        planning_staking = spud + rig_crew_timing[
            'planning_to_spud']
        location_build = spud + rig_crew_timing[
            'location_build_to_spud']
        if well_num_on_pad == 1:
            pad_spud = spud + rig_crew_timing[
                'pad_spud_to_first_well_spud']
        else:
            pad_spud = spud + rig_crew_timing[
                'pad_spud_to_first_well_spud'] + (-rig_crew_timing[
                'skid_td_to_next_spud']-rig_crew_timing[
                'spud_to_td'])*(well_num_on_pad-1)

        td = spud + rig_crew_timing[
            'spud_to_td']
        last_generic_well_td = pd.to_datetime(td)

        remaining_wells = wells_on_pad - well_num_on_pad
        rig_release = td + rig_crew_timing[
            'spud_to_td'] * remaining_wells + rig_crew_timing[
                          'final_td_to_rig_release']

        compl_start = rig_release + rig_crew_timing[
            'rig_release_to_frac_start']
        frac_end = compl_start + rig_crew_timing[
            'frac_days_per_well'] * wells_on_pad
        drill_out_start = frac_end + rig_crew_timing[
            'frac_end_to_drill_out_start']
        compl_end = drill_out_start + rig_crew_timing[
            'drill_out_days_per_well'] * wells_on_pad
        # todo: frac fleet move to next pad (completion should not start before the frac fleet is done with the prior pad)
        pop = compl_end + rig_crew_timing[
            'completion_end_to_pop_date']

        to_loe = pop + rig_crew_timing[
            'pop_date_to_loe']
        first_oil = pop + rig_crew_timing[
            'pop_date_to_first_oil']
        post_drill_filing = spud + rig_crew_timing[
            'spud_to_post_drill_filing_req']
    elif well in live_ds.index:
        print(f'\n>>> Loading _activity dates for: {well} ')
        # load dates from live_ds if well is in there
        #  permitted date (first capex event)
        permitted = live_ds.loc[well, 'PERMITTED']
        # spud date
        spud = live_ds.loc[well, 'SPUD']
        afe = live_ds.loc[well, 'AFE']
        planning_staking = live_ds.loc[well, 'PLANNING & STAKING']
        location_build = live_ds.loc[well, 'LOCATION BUILDING']
        pad_spud = live_ds.loc[well, 'PAD SPUD']
        td = live_ds.loc[well, 'TD']
        remaining_wells = wells_on_pad - well_num_on_pad
        rig_release = live_ds.loc[well, 'RIG RELEASE (PAD)']
        compl_start = live_ds.loc[well, 'COMPLETION START']
        frac_end = live_ds.loc[well, 'FRAC END']
        drill_out_start = live_ds.loc[well, 'DRILL OUT START']
        compl_end = live_ds.loc[well, 'COMPLETION END']
        pop = live_ds.loc[well, 'PUT ON PRODUCTION']
        to_loe = live_ds.loc[well, 'TURNED TO LOE']
        first_oil = live_ds.loc[well, '1ST OIL']
        post_drill_filing = live_ds.loc[well, 'POST DRILL FILING REQUIREMENTS']
    else:
        print('!! Activity dates not calculated. well must be "GENERIC" or defined in live_ds.')

    # Create activity_dates :: instance of ActivityDates
    activity_dates = ActivityDates(afe=afe,
                                   permitted=permitted,
                                   planning_staking=planning_staking,
                                   location_build=location_build,
                                   pad_spud=pad_spud,
                                   spud=spud,
                                   td=td,
                                   rig_release=rig_release,
                                   compl_start=compl_start,
                                   frac_end=frac_end,
                                   drill_out_start=drill_out_start,
                                   compl_end=compl_end,
                                   pop=pop,
                                   to_loe=to_loe,
                                   first_oil=first_oil,
                                   post_drill_filing=post_drill_filing
                                   )
    print(f'| Activity dates:')

    # global save_yn_wells
    # if save_yn_wells.lower() == 'y':
    #     wn = well.lower().replace(" ", "_")
    #     model_data[f'{wn}_activity_dates'] = pd.DataFrame(activity_dates._asdict().items())
    print(activity_dates)

    # add activity dates to master_drilling_schedule
    global master_drilling_schedule
    master_drilling_schedule.loc[well, :] = activity_dates._asdict()
    # if this is the last well modeled, add the master drilling schedule to the model drivers dict
    if well == modeled_wells_all[-1]:
        master_drilling_schedule.fillna(pd.to_datetime(0), inplace=True)
        # convert dates to string date format
        for col in master_drilling_schedule.columns:
            master_drilling_schedule.loc[:, col] = [string_date(_) for _ in master_drilling_schedule.loc[:, col]]
        # add to model drivers dict for output
        model_drivers.model_level_drivers[f'master_drilling_schedule'] = master_drilling_schedule

    return activity_dates


def check_live_ds_for_inputs(master_ds: pd.DataFrame):
    '''Checks the live drilling schedule for any unfilled well-level inputs.
    Args:
        |-- master_ds, pd.DataFrame: a dataframe of all wells modeled and their activity dates.
    Returns:
        |-- an updated master_ds to the caller.
        '''

    global live_ds
    print('checking live ds')
    _q = input('continue? >>> ')




def load_well_activity_dates_dict():
    '''Loads activity dates for all wells modeled.'''
    global well_activity_dates_dict

    # list of wells to include in capex
    if model_control.include_remaining_pdp_capex:
        # get the PDP wells also
        _capex_wells = model_control.pdp_wells_with_remaining_capex.copy()
        _capex_wells.extend(modeled_wells_all)
    else:
        _capex_wells = modeled_wells_all.copy()

    for well in _capex_wells:
        well_activity_dates_dict[well] = get_activity_dates_for(well)
    return well_activity_dates_dict


def load_type_curves_modeled_dict():
    # create a dataframe of oil, gas, water type curves (index = range(0, model months), cols = type curve names)

    global well_drivers_dict
    type_curves_modeled_dict = {
        'oil': pd.DataFrame(index=range(model_months), columns=[well for well in well_drivers_dict.keys()]),
        'gas': pd.DataFrame(index=range(model_months), columns=[well for well in well_drivers_dict.keys()]),
        'water': pd.DataFrame(index=range(model_months), columns=[well for well in well_drivers_dict.keys()])
    }

    # update type curve dataframes
    for tc_comdty in type_curves_modeled_dict:
        _tc_modeled_df = type_curves_modeled_dict[tc_comdty]
        _tc_modeled_df.fillna(0.0, inplace=True)
        # fill each column with the raw_tc_input data
        for well in _tc_modeled_df.columns:
            tc_name = well_drivers_dict[well]['tc_name']
            tc_multiplier = well_drivers_dict[well]['tc_multiplier']
            _tc_modeled_df.loc[:, well] = raw_tc_input[tc_comdty].loc[:, tc_name].values * tc_multiplier
        print(f'| Type curves updated for {tc_comdty}.')
    print(type_curves_modeled_dict.items())
    return type_curves_modeled_dict


def get_well_pop_dates_dict():
    global well_pop_dates_dict
    for well in modeled_wells_all:
        well_pop_dates_dict[well] = well_activity_dates_dict[well].pop
    print(f'\n| Well POP dates:  {well_pop_dates_dict}')
    return well_pop_dates_dict


def shift_adjust_type_curves():
    return


def save_production_engine_outputs(save_to='both'):
    '''Saves key module outputs to excel.'''
    global production_engine_outputs

    if save_to == 'local':
        fp_list = [fp_local]
    elif save_to == 'network':
        fp_list = [fp_network]
    else:
        fp_list = [fp_network, fp_local]

    for fp in fp_list:
        # save dataframes in production_engine_outputs
        for name, df in production_engine_outputs.items():
            save_to_excel(output_dataframe=df, folder=fp + 'production\/',
                          filename=f'{name}.xlsx')
            # update scenario filepaths
            model_control.add_to_scenario_filepaths(tail='production\/' + f'{name}.xlsx')


# GROSS TYPE CURVE/WELLHEAD PRODUCTION
def calc_gross_wellhead_production():
    '''Calculates type curve production for oil, gas, and water, by well in modeled_wells_all.'''
    model_period_indexed = dict((v.replace(tzinfo=None), k) for k, v in enumerate(model_period))
    for well in modeled_wells_all:
        # shift by appropriate periods
        # get POP month
        pop_date = pd.to_datetime(well_pop_dates_dict[well]).normalize()
        pop_month = pop_date + MonthEnd(1)
        # get shift index for this well
        shift_index = model_period_indexed[pop_month.replace(tzinfo=None)]
        # get active month for this subasset
        subasset = model_drivers.get_sub_asset(well_name=well)
        month_prior_to_active = pd.to_datetime(asset_level_drivers.at[subasset, 'Asset Active Date'], utc=True) + MonthEnd(-1)
        try:
            month_index_prior_to_active = model_period_indexed[month_prior_to_active.replace(tzinfo=None)]
        except KeyError:
            month_index_prior_to_active = -1

        mf1 = (pop_month.day - pop_date.day + 1) / pop_month.day
        mf2 = 1 - mf1
        print(f'\n| Well: {well} >> POP date: {pop_date} | POP month: {pop_month} | shift index: {shift_index}')
        # shift all TCs for this well by shift_index
        for comdty in type_curves_modeled_dict:
            print(
                f'|-- shifting: {well} | {comdty} | pop date: {pop_date} | shift index: {shift_index}\n {type_curves_modeled_dict[comdty].loc[:, well]}')
            # print(f'|-- {type_curves_modeled_dict[comdty].loc[:, well]}')

            type_curves_modeled_dict[comdty].loc[:, well] = type_curves_modeled_dict[comdty].loc[:, well].shift(
                shift_index)
            type_curves_modeled_dict[comdty].loc[:, well].fillna(0, inplace=True)
            print(f'|-- shifted to shift index --> {shift_index}')
            # print(f'|-- {type_curves_modeled_dict[comdty].loc[:, well]}')

            # adjust by mf1 / mf2
            mf1_series = type_curves_modeled_dict[comdty].loc[:, well].copy(deep=True) * mf1
            mf2_series = type_curves_modeled_dict[comdty].loc[:, well].copy(deep=True).shift(1).fillna(0) * mf2
            adjusted_series = mf1_series + mf2_series
            type_curves_modeled_dict[comdty].loc[:, well] = adjusted_series.copy(deep=True)

            # zero out months prior to asset active, if any
            if month_index_prior_to_active != -1:
                type_curves_modeled_dict[comdty].loc[:month_index_prior_to_active, well] = 0.0

            print(f'|-- {type_curves_modeled_dict[comdty].loc[:, well]}')
            print(f'|-- ADJUSTED {well}| mf1 = {mf1}, mf2 = {mf2}')

    # make model_period the index for each type curve dataframe
    for comdty in type_curves_modeled_dict:
        type_curves_modeled_dict[comdty].set_index(model_period, inplace=True)
        # add WH prod by well to production engine outputs
        production_engine_outputs[f'wellhead_prod_{comdty}_by_well'] = type_curves_modeled_dict[comdty]

        # calc total WH prod
        total = pd.DataFrame(type_curves_modeled_dict[comdty].sum(axis=1), columns=[f'wellhead_prod_{comdty}_total'])
        wellhead_prod_total[comdty] = total
        # add total WH prod to production outputs
        production_engine_outputs[total.columns[0]] = wellhead_prod_total[comdty]


# WORKING INTEREST AND NRI PRODUCTION
def calc_wi_nri_production():
    '''Calculates working interest and net revenue interest production by well, and in total.
    Returns:
         WIVolume and NRIVolume namedtuples for revenue calculations / use elsewhere in model.'''

    # get drivers by well
    wi_pct_by_well = {
        well: value for well, driver_dict in well_drivers_dict.items() for driver, value in driver_dict.items() if
        'wi_pct' in driver
    }

    nri_pct_by_well = {
        well: value for well, driver_dict in well_drivers_dict.items() for driver, value in driver_dict.items() if
        'nri_pct' in driver
    }

    gas_shrink_by_well = {
        well: value for well, driver_dict in well_drivers_dict.items() for driver, value in driver_dict.items() if
        'gas_shrink' in driver
    }

    gas_btu_factor_residue_by_well = {
        well: value for well, driver_dict in well_drivers_dict.items() for driver, value in driver_dict.items() if
        'gas_btu_factor_residue' in driver
    }

    # calculate by well and totals: WI production
    for comdty in type_curves_modeled_dict:
        # wellhead production by well dataframe - there should be only one per commodity
        prod_output_name = [
            name for name, df in production_engine_outputs.items() if
            all([_ in name for _ in ('wellhead', 'by_well', comdty)])
        ][0]

        # set up base dataframes from wellhead production by well for this comdty (oil, gas, water)
        wi_prod_by_well = [
            df.copy(deep=True) for name, df in production_engine_outputs.items() if
            all([_ in name for _ in ('wellhead', 'by_well', comdty)])
        ][0]

        nri_prod_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_by_well.fillna(0, inplace=True)

        # gas BTU specific datframes
        wi_prod_gas_btu_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_gas_btu_by_well.fillna(0, inplace=True)

        nri_prod_gas_btu_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_gas_btu_by_well.fillna(0, inplace=True)

        # NGL dataframes
        ### Working interest NGL volumes
        global wi_prod_ethane_by_well
        wi_prod_ethane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_ethane_by_well.fillna(0, inplace=True)

        global wi_prod_propane_by_well
        wi_prod_propane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_propane_by_well.fillna(0, inplace=True)

        global wi_prod_n_butane_by_well
        wi_prod_n_butane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_n_butane_by_well.fillna(0, inplace=True)

        global wi_prod_iso_butane_by_well
        wi_prod_iso_butane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_iso_butane_by_well.fillna(0, inplace=True)

        global wi_prod_nat_gasoline_by_well
        wi_prod_nat_gasoline_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_nat_gasoline_by_well.fillna(0, inplace=True)

        global wi_prod_ngl_all_by_well
        wi_prod_ngl_all_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        wi_prod_ngl_all_by_well.fillna(0, inplace=True)

        ### Net revenue interest NGL volumes
        global nri_prod_ethane_by_well
        nri_prod_ethane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_ethane_by_well.fillna(0, inplace=True)

        global nri_prod_propane_by_well
        nri_prod_propane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_propane_by_well.fillna(0, inplace=True)

        global nri_prod_n_butane_by_well
        nri_prod_n_butane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_n_butane_by_well.fillna(0, inplace=True)

        global nri_prod_iso_butane_by_well
        nri_prod_iso_butane_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_iso_butane_by_well.fillna(0, inplace=True)

        global nri_prod_nat_gasoline_by_well
        nri_prod_nat_gasoline_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_nat_gasoline_by_well.fillna(0, inplace=True)

        global nri_prod_ngl_all_by_well
        nri_prod_ngl_all_by_well = pd.DataFrame().reindex_like(wi_prod_by_well)
        nri_prod_ngl_all_by_well.fillna(0, inplace=True)

        # calculate WI and NRI production by well
        for well in wi_prod_by_well.columns:
            sub_asset = model_drivers.get_sub_asset(well)
            print(f'\n| Calculating {comdty} production for >> {well} // {sub_asset}')

            # multiply gross wellhead production by working interest
            wi_prod_by_well.loc[:, well] *= wi_pct_by_well[well]

            if comdty != 'water':
                nri_prod_by_well.loc[:, well] = wi_prod_by_well.loc[:, well] * nri_pct_by_well[well]

            if comdty == 'gas':
                # residue / shrunk gas production by well
                print(f'>> Adjusting {well} {comdty} by shrink factor: {gas_shrink_by_well[well]}...')
                wi_prod_by_well.loc[:, well] *= (1 - gas_shrink_by_well[well])
                nri_prod_by_well.loc[:, well] *= (1 - gas_shrink_by_well[well])
                print(nri_prod_by_well.loc[:, well])

                # gas BTU production by well
                print(f'\n>> {well} WI {comdty} BTU production by well: ')
                wi_prod_gas_btu_by_well.loc[:, well] = wi_prod_by_well.loc[:, well] * gas_btu_factor_residue_by_well[
                    well]
                print(wi_prod_gas_btu_by_well.loc[:, well])

                print(f'\n>> {well} NRI {comdty} BTU production by well: ')
                nri_prod_gas_btu_by_well.loc[:, well] = nri_prod_by_well.loc[:, well] * gas_btu_factor_residue_by_well[
                    well]
                print(nri_prod_gas_btu_by_well.loc[:, well])

                # NGL production by well
                sub_asset = well_drivers_dict[well]['sub_asset']
                print(f'>> Calculating {well} NGL volumes: {ngl_yields[sub_asset]}...')
                wi_prod_ethane_by_well.loc[:, well] = ngl_yields[sub_asset]['ethane'] / 1000 * wi_prod_by_well.loc[:,
                                                                                               well]
                wi_prod_propane_by_well.loc[:, well] = ngl_yields[sub_asset]['propane'] / 1000 * wi_prod_by_well.loc[:,
                                                                                                 well]
                wi_prod_n_butane_by_well.loc[:, well] = ngl_yields[sub_asset]['n_butane'] / 1000 * wi_prod_by_well.loc[
                                                                                                   :, well]
                wi_prod_iso_butane_by_well.loc[:, well] = ngl_yields[sub_asset][
                                                              'iso_butane'] / 1000 * wi_prod_by_well.loc[:, well]
                wi_prod_nat_gasoline_by_well.loc[:, well] = ngl_yields[sub_asset][
                                                                'nat_gasoline'] / 1000 * wi_prod_by_well.loc[:, well]
                wi_prod_ngl_all_by_well.loc[:, well] = sum(
                    [_ for _ in ngl_yields[sub_asset].values()]) / 1000 * wi_prod_by_well.loc[:, well]

                nri_prod_ethane_by_well.loc[:, well] = ngl_yields[sub_asset]['ethane'] / 1000 * nri_prod_by_well.loc[:,
                                                                                                well]
                nri_prod_propane_by_well.loc[:, well] = ngl_yields[sub_asset]['propane'] / 1000 * nri_prod_by_well.loc[
                                                                                                  :, well]
                nri_prod_n_butane_by_well.loc[:, well] = ngl_yields[sub_asset][
                                                             'n_butane'] / 1000 * nri_prod_by_well.loc[:, well]
                nri_prod_iso_butane_by_well.loc[:, well] = ngl_yields[sub_asset][
                                                               'iso_butane'] / 1000 * nri_prod_by_well.loc[:, well]
                nri_prod_nat_gasoline_by_well.loc[:, well] = ngl_yields[sub_asset][
                                                                 'nat_gasoline'] / 1000 * nri_prod_by_well.loc[:, well]
                nri_prod_ngl_all_by_well.loc[:, well] = sum(
                    [_ for _ in ngl_yields[sub_asset].values()]) / 1000 * nri_prod_by_well.loc[:, well]

        # add to production outputs - oil, gas
        production_engine_outputs[f'wi_prod_{comdty}_by_well'] = wi_prod_by_well
        wi_prod_total = pd.DataFrame(wi_prod_by_well.sum(axis=1).values,
                                     index=wi_prod_by_well.index,
                                     columns=[f'wi_prod_{comdty}_total'])
        production_engine_outputs[wi_prod_total.columns[0]] = wi_prod_total

        # ONLY IF THIS IS NOT WATER, ADD THE NRI STREAM
        if comdty != 'water':
            production_engine_outputs[f'nri_prod_{comdty}_by_well'] = nri_prod_by_well
            nri_prod_total = pd.DataFrame(nri_prod_by_well.sum(axis=1).values,
                                          index=nri_prod_by_well.index,
                                          columns=[f'nri_prod_{comdty}_total'])
            production_engine_outputs[nri_prod_total.columns[0]] = nri_prod_total

        if comdty == 'gas':
            # add to production outputs
            production_engine_outputs[f'wi_prod_gas_btu_by_well'] = wi_prod_gas_btu_by_well
            wi_prod_gas_btu_total = pd.DataFrame(wi_prod_gas_btu_by_well.sum(axis=1).values,
                                                 index=wi_prod_gas_btu_by_well.index,
                                                 columns=[f'wi_prod_gas_btu_total'])
            production_engine_outputs[wi_prod_gas_btu_total.columns[0]] = wi_prod_gas_btu_total

            # add to production outputs
            production_engine_outputs[f'nri_prod_gas_btu_by_well'] = nri_prod_gas_btu_by_well
            nri_prod_gas_btu_total = pd.DataFrame(nri_prod_gas_btu_by_well.sum(axis=1).values,
                                                  index=nri_prod_gas_btu_by_well.index,
                                                  columns=[f'nri_prod_gas_btu_total'])
            production_engine_outputs[nri_prod_gas_btu_total.columns[0]] = nri_prod_gas_btu_total

            # add to WI and NRI production outputs - ethane, propane, n_butane, iso_butane, nat_gasoline, ngl_all
            production_engine_outputs['wi_prod_ethane_by_well'] = wi_prod_ethane_by_well
            wi_prod_ethane_total = pd.DataFrame(wi_prod_ethane_by_well.sum(axis=1).values,
                                                index=wi_prod_ethane_by_well.index,
                                                columns=['wi_prod_ethane_total'])
            production_engine_outputs[wi_prod_ethane_total.columns[0]] = wi_prod_ethane_total

            production_engine_outputs['wi_prod_propane_by_well'] = wi_prod_propane_by_well
            wi_prod_propane_total = pd.DataFrame(wi_prod_propane_by_well.sum(axis=1).values,
                                                 index=wi_prod_propane_by_well.index,
                                                 columns=['wi_prod_propane_total'])
            production_engine_outputs[wi_prod_propane_total.columns[0]] = wi_prod_propane_total

            production_engine_outputs['wi_prod_n_butane_by_well'] = wi_prod_n_butane_by_well
            wi_prod_n_butane_total = pd.DataFrame(wi_prod_n_butane_by_well.sum(axis=1).values,
                                                  index=wi_prod_n_butane_by_well.index,
                                                  columns=['wi_prod_n_butane_total'])
            production_engine_outputs[wi_prod_n_butane_total.columns[0]] = wi_prod_n_butane_total

            production_engine_outputs['wi_prod_iso_butane_by_well'] = wi_prod_iso_butane_by_well
            wi_prod_iso_butane_total = pd.DataFrame(wi_prod_iso_butane_by_well.sum(axis=1).values,
                                                    index=wi_prod_iso_butane_by_well.index,
                                                    columns=['wi_prod_iso_butane_total'])
            production_engine_outputs[wi_prod_iso_butane_total.columns[0]] = wi_prod_iso_butane_total

            production_engine_outputs['wi_prod_nat_gasoline_by_well'] = wi_prod_nat_gasoline_by_well
            wi_prod_nat_gasoline_total = pd.DataFrame(wi_prod_nat_gasoline_by_well.sum(axis=1).values,
                                                      index=wi_prod_nat_gasoline_by_well.index,
                                                      columns=['wi_prod_nat_gasoline_total'])
            production_engine_outputs[wi_prod_nat_gasoline_total.columns[0]] = wi_prod_nat_gasoline_total

            production_engine_outputs['wi_prod_ngl_all_by_well'] = wi_prod_ngl_all_by_well
            wi_prod_ngl_all_total = pd.DataFrame(wi_prod_ngl_all_by_well.sum(axis=1).values,
                                                 index=wi_prod_ngl_all_by_well.index,
                                                 columns=['wi_prod_ngl_all_total'])
            production_engine_outputs[wi_prod_ngl_all_total.columns[0]] = wi_prod_ngl_all_total

            # NRI PRODUCTION - NGLs
            production_engine_outputs['nri_prod_ethane_by_well'] = nri_prod_ethane_by_well
            nri_prod_ethane_total = pd.DataFrame(nri_prod_ethane_by_well.sum(axis=1).values,
                                                 index=nri_prod_ethane_by_well.index,
                                                 columns=['nri_prod_ethane_total'])
            production_engine_outputs[nri_prod_ethane_total.columns[0]] = nri_prod_ethane_total

            production_engine_outputs['nri_prod_propane_by_well'] = nri_prod_propane_by_well
            nri_prod_propane_total = pd.DataFrame(nri_prod_propane_by_well.sum(axis=1).values,
                                                  index=nri_prod_propane_by_well.index,
                                                  columns=['nri_prod_propane_total'])
            production_engine_outputs[nri_prod_propane_total.columns[0]] = nri_prod_propane_total

            production_engine_outputs['nri_prod_n_butane_by_well'] = nri_prod_n_butane_by_well
            nri_prod_n_butane_total = pd.DataFrame(nri_prod_n_butane_by_well.sum(axis=1).values,
                                                   index=nri_prod_n_butane_by_well.index,
                                                   columns=['nri_prod_n_butane_total'])
            production_engine_outputs[nri_prod_n_butane_total.columns[0]] = nri_prod_n_butane_total

            production_engine_outputs['nri_prod_iso_butane_by_well'] = nri_prod_iso_butane_by_well
            nri_prod_iso_butane_total = pd.DataFrame(nri_prod_iso_butane_by_well.sum(axis=1).values,
                                                     index=nri_prod_iso_butane_by_well.index,
                                                     columns=['nri_prod_iso_butane_total'])
            production_engine_outputs[nri_prod_iso_butane_total.columns[0]] = nri_prod_iso_butane_total

            production_engine_outputs['nri_prod_nat_gasoline_by_well'] = nri_prod_nat_gasoline_by_well
            nri_prod_nat_gasoline_total = pd.DataFrame(nri_prod_nat_gasoline_by_well.sum(axis=1).values,
                                                       index=nri_prod_nat_gasoline_by_well.index,
                                                       columns=['nri_prod_nat_gasoline_total'])
            production_engine_outputs[nri_prod_nat_gasoline_total.columns[0]] = nri_prod_nat_gasoline_total

            production_engine_outputs['nri_prod_ngl_all_by_well'] = nri_prod_ngl_all_by_well
            nri_prod_ngl_all_total = pd.DataFrame(nri_prod_ngl_all_by_well.sum(axis=1).values,
                                                  index=nri_prod_ngl_all_by_well.index,
                                                  columns=['nri_prod_ngl_all_total'])
            production_engine_outputs[nri_prod_ngl_all_total.columns[0]] = nri_prod_ngl_all_total

    # TOTAL PRODUCTION STREAM SPLITS / NAMEDTUPLES
    # split up the total WI and NRI production according to the production splitter
    wi_prod_oil_total = [
        df for name, df in production_engine_outputs.items() if all([_ in name for _ in ('wi', 'oil', 'total')])
    ][0]

    nri_prod_oil_total = [
        df for name, df in production_engine_outputs.items() if all([_ in name for _ in ('nri', 'oil', 'total')])
    ][0]

    wi_prod_gas_total = [
        df for name, df in production_engine_outputs.items() if all([_ in name for _ in ('wi', 'gas', 'total')])
    ][0]

    wi_prod_gas_btu_total = [
        df for name, df in production_engine_outputs.items() if all(
            [_ in name for _ in ('wi', 'gas', 'total')]
        ) and 'btu' not in name
    ][0]

    nri_prod_gas_total = [
        df for name, df in production_engine_outputs.items() if all(
            [_ in name for _ in ('nri', 'gas', 'total')]
        ) and 'btu' not in name
    ][0]

    nri_prod_gas_btu_total = [
        df for name, df in production_engine_outputs.items() if all(
            [_ in name for _ in ('nri', 'gas', 'total', 'btu')]
        )
    ][0]

    wi_prod_water_total = [
        df for name, df in production_engine_outputs.items() if all([_ in name for _ in ('wi', 'water', 'total')])
    ][0]

    global wi_volumes_total
    # calculate volumes
    oil_midland_mbbl = production_engine_outputs['wi_prod_oil_total'].multiply(production_splitter.loc[
                                                                                   [_ for _ in production_splitter.index
                                                                                    if _ in production_engine_outputs[
                                                                                        'wi_prod_oil_total'].index], 'oil_midland_pct'
                                                                               ], axis='index')
    oil_houston_mbbl = production_engine_outputs['wi_prod_oil_total'].multiply(production_splitter.loc[
                                                                                   [_ for _ in production_splitter.index
                                                                                    if _ in production_engine_outputs[
                                                                                        'wi_prod_oil_total'].index], 'oil_houston_pct'
                                                                               ], axis='index')
    oil_all_mbbl = production_engine_outputs['wi_prod_oil_total'].multiply(production_splitter.loc[
                                                                               [_ for _ in production_splitter.index if
                                                                                _ in production_engine_outputs[
                                                                                    'wi_prod_oil_total'].index], 'oil_all_pct'
                                                                           ], axis='index')
    gas_waha_mmcf_shrunk = production_engine_outputs['wi_prod_gas_total'].multiply(production_splitter.loc[
                                                                                       [_ for _ in
                                                                                        production_splitter.index if
                                                                                        _ in production_engine_outputs[
                                                                                            'wi_prod_gas_total'].index], 'gas_waha_pct'
                                                                                   ], axis='index')
    gas_hsc_mmcf_shrunk = production_engine_outputs['wi_prod_gas_total'].multiply(production_splitter.loc[
                                                                                      [_ for _ in
                                                                                       production_splitter.index if
                                                                                       _ in production_engine_outputs[
                                                                                           'wi_prod_gas_total'].index], 'gas_hsc_pct'
                                                                                  ], axis='index')
    gas_all_mmcf_shrunk = production_engine_outputs['wi_prod_gas_total'].multiply(production_splitter.loc[
                                                                                      [_ for _ in
                                                                                       production_splitter.index if
                                                                                       _ in production_engine_outputs[
                                                                                           'wi_prod_gas_total'].index], 'gas_all_pct'
                                                                                  ], axis='index')
    gas_waha_bbtu_shrunk = production_engine_outputs['wi_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                           [_ for _ in
                                                                                            production_splitter.index if
                                                                                            _ in
                                                                                            production_engine_outputs[
                                                                                                'wi_prod_gas_btu_total'].index], 'gas_waha_pct'
                                                                                       ], axis='index')
    gas_hsc_bbtu_shrunk = production_engine_outputs['wi_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                          [_ for _ in
                                                                                           production_splitter.index if
                                                                                           _ in
                                                                                           production_engine_outputs[
                                                                                               'wi_prod_gas_btu_total'].index], 'gas_hsc_pct'
                                                                                      ], axis='index')
    gas_all_bbtu_shrunk = production_engine_outputs['wi_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                          [_ for _ in
                                                                                           production_splitter.index if
                                                                                           _ in
                                                                                           production_engine_outputs[
                                                                                               'wi_prod_gas_btu_total'].index], 'gas_all_pct'
                                                                                      ], axis='index')
    ngl_ethane_mbbl = production_engine_outputs['wi_prod_ethane_total'].multiply(production_splitter.loc[
                                                                                     [_ for _ in
                                                                                      production_splitter.index if
                                                                                      _ in production_engine_outputs[
                                                                                          'wi_prod_ethane_total'].index], 'ngl_ethane_pct'
                                                                                 ], axis='index')
    ngl_propane_mbbl = production_engine_outputs['wi_prod_propane_total'].multiply(production_splitter.loc[
                                                                                       [_ for _ in
                                                                                        production_splitter.index if
                                                                                        _ in production_engine_outputs[
                                                                                            'wi_prod_propane_total'].index], 'ngl_propane_pct'
                                                                                   ], axis='index')
    ngl_n_butane_mbbl = production_engine_outputs['wi_prod_n_butane_total'].multiply(production_splitter.loc[
                                                                                         [_ for _ in
                                                                                          production_splitter.index if
                                                                                          _ in
                                                                                          production_engine_outputs[
                                                                                              'wi_prod_n_butane_total'].index], 'ngl_n_butane_pct'
                                                                                     ], axis='index')
    ngl_iso_butane_mbbl = production_engine_outputs['wi_prod_iso_butane_total'].multiply(production_splitter.loc[
                                                                                             [_ for _ in
                                                                                              production_splitter.index
                                                                                              if _ in
                                                                                              production_engine_outputs[
                                                                                                  'wi_prod_iso_butane_total'].index], 'ngl_iso_butane_pct'
                                                                                         ], axis='index')
    ngl_nat_gasoline_mbbl = production_engine_outputs['wi_prod_nat_gasoline_total'].multiply(production_splitter.loc[
                                                                                                 [_ for _ in
                                                                                                  production_splitter.index
                                                                                                  if _ in
                                                                                                  production_engine_outputs[
                                                                                                      'wi_prod_nat_gasoline_total'].index], 'ngl_nat_gasoline_pct'
                                                                                             ], axis='index')
    ngl_all_mbbl = production_engine_outputs['wi_prod_ngl_all_total'].multiply(production_splitter.loc[
                                                                                   [_ for _ in production_splitter.index
                                                                                    if _ in production_engine_outputs[
                                                                                        'wi_prod_ngl_all_total'].index], 'ngl_nat_gasoline_pct'
                                                                               ], axis='index')
    water_all_mbbl = production_engine_outputs['wi_prod_water_total']

    wi_volumes_total = WIVolume(
        oil_midland_mbbl=oil_midland_mbbl,
        oil_houston_mbbl=oil_houston_mbbl,
        oil_all_mbbl=oil_all_mbbl,
        gas_waha_mmcf_shrunk=gas_waha_mmcf_shrunk,
        gas_hsc_mmcf_shrunk=gas_hsc_mmcf_shrunk,
        gas_all_mmcf_shrunk=gas_all_mmcf_shrunk,
        gas_waha_bbtu_shrunk=gas_waha_bbtu_shrunk,
        gas_hsc_bbtu_shrunk=gas_hsc_bbtu_shrunk,
        gas_all_bbtu_shrunk=gas_all_bbtu_shrunk,
        ngl_ethane_mbbl=ngl_ethane_mbbl,
        ngl_propane_mbbl=ngl_propane_mbbl,
        ngl_n_butane_mbbl=ngl_n_butane_mbbl,
        ngl_iso_butane_mbbl=ngl_iso_butane_mbbl,
        ngl_nat_gasoline_mbbl=ngl_nat_gasoline_mbbl,
        ngl_all_mbbl=ngl_all_mbbl,
        water_all_mbbl=water_all_mbbl
    )

    global nri_volumes_total
    # calculate volumes
    oil_midland_mbbl = production_engine_outputs['nri_prod_oil_total'].multiply(production_splitter.loc[
                                                                                    [_ for _ in
                                                                                     production_splitter.index if
                                                                                     _ in production_engine_outputs[
                                                                                         'nri_prod_oil_total'].index], 'oil_midland_pct'
                                                                                ], axis='index')
    oil_houston_mbbl = production_engine_outputs['nri_prod_oil_total'].multiply(production_splitter.loc[
                                                                                    [_ for _ in
                                                                                     production_splitter.index if
                                                                                     _ in production_engine_outputs[
                                                                                         'nri_prod_oil_total'].index], 'oil_houston_pct'
                                                                                ], axis='index')
    oil_all_mbbl = production_engine_outputs['nri_prod_oil_total'].multiply(production_splitter.loc[
                                                                                [_ for _ in production_splitter.index if
                                                                                 _ in production_engine_outputs[
                                                                                     'nri_prod_oil_total'].index], 'oil_all_pct'
                                                                            ], axis='index')
    gas_waha_mmcf_shrunk = production_engine_outputs['nri_prod_gas_total'].multiply(production_splitter.loc[
                                                                                        [_ for _ in
                                                                                         production_splitter.index if
                                                                                         _ in production_engine_outputs[
                                                                                             'nri_prod_gas_total'].index], 'gas_waha_pct'
                                                                                    ], axis='index')
    gas_hsc_mmcf_shrunk = production_engine_outputs['nri_prod_gas_total'].multiply(production_splitter.loc[
                                                                                       [_ for _ in
                                                                                        production_splitter.index if
                                                                                        _ in production_engine_outputs[
                                                                                            'nri_prod_gas_total'].index], 'gas_hsc_pct'
                                                                                   ], axis='index')
    gas_all_mmcf_shrunk = production_engine_outputs['nri_prod_gas_total'].multiply(production_splitter.loc[
                                                                                       [_ for _ in
                                                                                        production_splitter.index if
                                                                                        _ in production_engine_outputs[
                                                                                            'nri_prod_gas_total'].index], 'gas_all_pct'
                                                                                   ], axis='index')
    gas_waha_bbtu_shrunk = production_engine_outputs['nri_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                            [_ for _ in
                                                                                             production_splitter.index
                                                                                             if _ in
                                                                                             production_engine_outputs[
                                                                                                 'nri_prod_gas_btu_total'].index], 'gas_waha_pct'
                                                                                        ], axis='index')
    gas_hsc_bbtu_shrunk = production_engine_outputs['nri_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                           [_ for _ in
                                                                                            production_splitter.index if
                                                                                            _ in
                                                                                            production_engine_outputs[
                                                                                                'nri_prod_gas_btu_total'].index], 'gas_hsc_pct'
                                                                                       ], axis='index')
    gas_all_bbtu_shrunk = production_engine_outputs['nri_prod_gas_btu_total'].multiply(production_splitter.loc[
                                                                                           [_ for _ in
                                                                                            production_splitter.index if
                                                                                            _ in
                                                                                            production_engine_outputs[
                                                                                                'nri_prod_gas_btu_total'].index], 'gas_all_pct'
                                                                                       ], axis='index')
    ngl_ethane_mbbl = production_engine_outputs['nri_prod_ethane_total'].multiply(production_splitter.loc[
                                                                                      [_ for _ in
                                                                                       production_splitter.index if
                                                                                       _ in production_engine_outputs[
                                                                                           'nri_prod_ethane_total'].index], 'ngl_ethane_pct'
                                                                                  ], axis='index')
    ngl_propane_mbbl = production_engine_outputs['nri_prod_propane_total'].multiply(production_splitter.loc[
                                                                                        [_ for _ in
                                                                                         production_splitter.index if
                                                                                         _ in production_engine_outputs[
                                                                                             'nri_prod_propane_total'].index], 'ngl_propane_pct'
                                                                                    ], axis='index')
    ngl_n_butane_mbbl = production_engine_outputs['nri_prod_n_butane_total'].multiply(production_splitter.loc[
                                                                                          [_ for _ in
                                                                                           production_splitter.index if
                                                                                           _ in
                                                                                           production_engine_outputs[
                                                                                               'nri_prod_n_butane_total'].index], 'ngl_n_butane_pct'
                                                                                      ], axis='index')
    ngl_iso_butane_mbbl = production_engine_outputs['nri_prod_iso_butane_total'].multiply(production_splitter.loc[
                                                                                              [_ for _ in
                                                                                               production_splitter.index
                                                                                               if _ in
                                                                                               production_engine_outputs[
                                                                                                   'nri_prod_iso_butane_total'].index], 'ngl_iso_butane_pct'
                                                                                          ], axis='index')
    ngl_nat_gasoline_mbbl = production_engine_outputs['nri_prod_nat_gasoline_total'].multiply(production_splitter.loc[
                                                                                                  [_ for _ in
                                                                                                   production_splitter.index
                                                                                                   if _ in
                                                                                                   production_engine_outputs[
                                                                                                       'nri_prod_nat_gasoline_total'].index], 'ngl_nat_gasoline_pct'
                                                                                              ], axis='index')
    ngl_all_mbbl = production_engine_outputs['nri_prod_ngl_all_total'].multiply(production_splitter.loc[
                                                                                    [_ for _ in
                                                                                     production_splitter.index if
                                                                                     _ in production_engine_outputs[
                                                                                         'nri_prod_ngl_all_total'].index], 'ngl_nat_gasoline_pct'
                                                                                ], axis='index')

    nri_volumes_total = NRIVolume(
        oil_midland_mbbl=oil_midland_mbbl,
        oil_houston_mbbl=oil_houston_mbbl,
        oil_all_mbbl=oil_all_mbbl,
        gas_waha_mmcf_shrunk=gas_waha_mmcf_shrunk,
        gas_hsc_mmcf_shrunk=gas_hsc_mmcf_shrunk,
        gas_all_mmcf_shrunk=gas_all_mmcf_shrunk,
        gas_waha_bbtu_shrunk=gas_waha_bbtu_shrunk,
        gas_hsc_bbtu_shrunk=gas_hsc_bbtu_shrunk,
        gas_all_bbtu_shrunk=gas_all_bbtu_shrunk,
        ngl_ethane_mbbl=ngl_ethane_mbbl,
        ngl_propane_mbbl=ngl_propane_mbbl,
        ngl_n_butane_mbbl=ngl_n_butane_mbbl,
        ngl_iso_butane_mbbl=ngl_iso_butane_mbbl,
        ngl_nat_gasoline_mbbl=ngl_nat_gasoline_mbbl,
        ngl_all_mbbl=ngl_all_mbbl
    )
    return {
        'wi_volumes_total': wi_volumes_total,
        'nri_volumes_total': nri_volumes_total,
    }


def get_production_dataframes(wi_nri='wi', by_well=True):
    '''Returns a dict of working interest / net revenue interest production dataframes, aggregated by well, or as a total.'''
    if by_well:
        aggregation = 'by_well'
    else:
        aggregation = 'total'

    try:
        results = {
            name: df for name, df in production_engine_outputs.items() if all(
                [_ in name for _ in ('prod', wi_nri, aggregation)]
            )
        }
    except (NameError, AttributeError):
        print(f'!! production_engine_outputs may not be defined. Running production engine...')
        run_production_engine()
        results = get_production_dataframes(wi_nri, by_well)

    print(f'\n| Getting {wi_nri.upper()} {aggregation} production dataframes:')
    pprint.pprint(results)
    return results


def get_production_namedtuples(wi_nri='wi'):
    global wi_volumes_total
    global nri_volumes_total

    if wi_nri == 'wi':
        return wi_volumes_total
    elif wi_nri == 'nri':
        return nri_volumes_total


def run_production_engine():
    global ngl_yields
    global ngl_pct_of_barrel

    ngl_yields, ngl_pct_of_barrel = load_ngl_yields()

    global well_drivers_dict
    well_drivers_dict = load_well_drivers_dict()

    # reassign type curves for the well_drivers_dict
    well_drivers_dict = reassign_type_curves(well_drivers_dict=well_drivers_dict)

    global type_curves_modeled_dict
    type_curves_modeled_dict = load_type_curves_modeled_dict()

    global well_activity_dates_dict
    well_activity_dates_dict = load_well_activity_dates_dict()

    global well_pop_dates_dict
    well_pop_dates_dict = get_well_pop_dates_dict()

    calc_gross_wellhead_production()

    global wi_volumes_total
    global nri_volumes_total
    wi_volumes_total, nri_volumes_total = calc_wi_nri_production().values()

    save_production_engine_outputs()

    return wi_volumes_total, nri_volumes_total

# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# EXECUTION #----------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#
