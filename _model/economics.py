import pandas as pd
import numpy as np
import pprint
from collections import namedtuple
from type_curves import TypeCurve
from pandas.tseries.offsets import *
from useful_functions import *
import model_control
import model_drivers
import market
import prices
import production_engine
import return_functions
import bootstrapper_charts

# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #---------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#

model_level_drivers = model_drivers.get_model_level_drivers()

ethane_mode = model_drivers.ethane_mode
dnc_capex_drivers = model_drivers.dnc_capex_drivers
live_ds = model_drivers.live_ds
model_period = model_drivers.model_period
forecast_length = len(model_period)
bootstrap_prices = model_drivers.bootstrap_prices
model_prices = model_drivers.model_prices
summary_stats = model_drivers.summary_stats
rig_crew_timing = model_drivers.rig_crew_timing
production_splitter = model_drivers.production_splitter
asset_level_drivers = model_drivers._asset_level_drivers
conversion_ratios = prices.get_conversion_ratios()
opex_drivers_monthly = model_drivers.opex_drivers_monthly
scenario_folder = model_drivers.local_scenario_folder
network_scenario_folder = model_drivers.network_scenario_folder
scenario_time_stamp = model_drivers.scenario_time_stamp
pdp_input_dict = model_drivers.pdp_input_dict

# working capital balance dictionary (keys --> sub-assets)
working_cap_balance_dict = model_drivers.working_cap_balance_dict

# dictionaries to store filepaths for this _scenario (pointers to central_dispatch objects)
scenario_filepaths_all = model_control.get_scenario_filepaths_all()

# modeled well list
modeled_wells_all = model_control.modeled_wells_all

# bootstrapper format template dataframe (filled with 0.0)
boots_template_df = model_control.boots_template_df

# dict for model drivers related to this _scenario
model_level_drivers = model_drivers.model_level_drivers

# add the items of the bootstrap_prices dict and the summary_stats dict
for c_nick in bootstrap_prices:
    model_level_drivers[f'bootstrap_prices_{c_nick}'] = bootstrap_prices[c_nick]
    model_level_drivers[f'summary_stats_{c_nick}'] = summary_stats[c_nick]

model_data = {}
# ActivityDates: namedtuple to access model's _activity date attributes
# NOTE: attributes here should be the same as activity_dates_input_map keys
ActivityDates = namedtuple('ActivityDates', [
    'afe',
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
    'first_oil'])

# CapexDetail: namedtuple to access model's capex attributes (including
# _activity, capex amnounts, and pay dates)
CapexDetail = namedtuple('CapexDetail', ['well_name',
                                         'scenario',  # source: input variables
                                         'd_c_f_type',  # source: capex_category_input_map._d_c_f_type
                                         'capex_category',  # source: capex_category_input_map.keys()
                                         'activity',  # source: capex_category_input_map.keys()
                                         'amount_k',  # source: dnc_capex_drivers.loc[_scenario, category]
                                         'activity_date',
                                         # source: live_ds.loc[well_name, _activity] if not generic
                                         'pay_date',  # source: live_ds.loc[well_name, _activity]
                                         'pay_delay_days',
                                         # source: dnc_capex_drivers.loc[_scenario, cat_input_map]
                                         ])

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

# namedtuple for cash opex
# reminder: avoid using "_all" except for totals
Opex = namedtuple('Opex', [
    'loe_oil_variable_k',
    'loe_water_variable_k',
    'loe_fixed_k',
    'loe_reinj_gas_compr_k',
    'loe_all_k',
    'marketing_nitrogen_k',
    'marketing_electricity_k',
    'marketing_gathering_k',
    'marketing_processing_k',
    'marketing_sold_gas_compr_k',
    'marketing_all_k',
    'opex_total_all_k'
])

model_control.add_to_model_control(
    {'WIVolume': WIVolume,
     'NRIVolume': NRIVolume,
     'Opex': Opex},
    deep_copy=True
)

# namedtuple for EBITDAX
EBITDAX = namedtuple('EBITDAX', 'ebitdax_unhedged_total_all_k')

# namedtuple for free cash flow
FreeCashFlow = namedtuple('FreeCashFlow', 'fcf_unhedged_total_all_k')


# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#

def get_well_index(_well_name):
    '''Return the index of this well_name in the drilling schedule.'''
    try:
        well_index = pd.Index(live_ds['WELL'])
        well_index = well_index.get_loc(_well_name)
        print(f'\n| Rank 2/Scheduled well index: {_well_name} >> {well_index}')
    except (IndexError, KeyError):
        modeled_well_index = dict(enumerate(modeled_wells_all))
        modeled_well_index = {v: k for k, v in modeled_well_index.items()}
        well_index = modeled_well_index[_well_name]
        print(f'\n| Rank 3/Generic well index: {_well_name} >> {well_index}')
    return well_index


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


def load_drivers():
    global well_name
    global well_index
    global asset_level_drivers
    global live_ds
    global well_drivers

    if 'GENERIC' in well_name:
        wells_on_pad = float(asset_level_drivers.loc[sub_asset, 'WELLS ON PAD'])
        _w_num = int(well_name.partition('//GENERIC ')[2])
        well_num_on_pad = [
            np.mod(_w_num, wells_on_pad) if np.mod(_w_num, wells_on_pad) != 0.0 else wells_on_pad
        ][0]
        tc_name = asset_level_drivers.loc[sub_asset, 'TYPE CURVE AREA']
        wi_pct = float(asset_level_drivers.loc[sub_asset, 'WI %']) / 100
        nri_pct = float(asset_level_drivers.loc[sub_asset, 'NRI %']) / 100
        gas_shrink = float(asset_level_drivers.loc[sub_asset, 'Gas Shrink'])
        gas_btu_factor_residue = float(asset_level_drivers.loc[sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
        gas_btu_factor_wellhead = float(asset_level_drivers.loc[sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
        perfed_ll = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
        base_ll_capex = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
        base_ll_tc = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
        tc_multiplier = min(perfed_ll / base_ll_tc, 1.30)
        rig_crew = asset_level_drivers.loc[sub_asset, 'Rig Crew #']
        capex_scenario_name = asset_level_drivers.loc[sub_asset, 'CAPEX SCENARIO']
    elif any([_ == well_name for _ in live_ds['WELL']]):
        print(f'\n>>> {well_name} found in live drilling schedule.')
        well_num_on_pad = live_ds['DRILL ORDER'][well_index]
        wells_on_pad = live_ds['WELLS ON PAD'][well_index]
        tc_name = live_ds['TYPE CURVE AREA'][well_index]
        wi_pct = float(live_ds['WI %'][well_index]) / 100
        nri_pct = float(live_ds['NRI %'][well_index]) / 100
        gas_shrink = float(asset_level_drivers.loc[sub_asset, 'Gas Shrink'])
        gas_btu_factor_residue = float(asset_level_drivers.loc[sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
        gas_btu_factor_wellhead = float(asset_level_drivers.loc[sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
        perfed_ll = float(live_ds['PERFED LATERAL LENGTH'][well_index])
        base_ll_capex = float(live_ds['BASE LL FOR CAPEX'][well_index])
        # base lateral length for the type curve (typically the same as the base LL for capex)
        base_ll_tc = float(asset_level_drivers.loc[sub_asset, 'BASE LL FOR CAPEX'])
        tc_multiplier = min(perfed_ll / base_ll_tc, 1.30)
        rig_crew = asset_level_drivers.loc[sub_asset, 'Rig Crew #']
        capex_scenario_name = live_ds['CAPEX SCENARIO'][well_index]
    else:
        print(f'\n!! {well_name} not found in live drilling schedule.')

    well_drivers = {
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
    pprint.pprint(well_drivers)
    return well_drivers


def load_activity_dates():
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

    # calculates _activity dates for this well, depending on if well is GENERIC or defined in the live drilling schedule
    global well_name
    global well_index
    global live_ds
    global well_drivers
    global last_generic_well_td

    wells_on_pad = well_drivers['wells_on_pad']
    well_num_on_pad = well_drivers['well_num_on_pad']

    print(f'---- ECONS FOR: {well_name} ----')
    '''Calculate _activity dates for this well if GENERIC, or get dates from live drilling schedule.'''
    if 'GENERIC' in well_name:
        # calculate _activity dates starting from well_activity_start_date
        # set the permitted date (first capex event)
        # get the last rank 2 well (from the sorted live_ds)
        _r2w = [_ for _ in modeled_wells_all if 'GENERIC' not in _]
        _gw = [_ for _ in modeled_wells_all if 'GENERIC' in _]
        # if this is the first generic well, anchor the well activity start date to the last rank 2 well
        if well_name == _gw[0]:
            rank_2_wells_modeled = live_ds.loc[[_ in _r2w for _ in live_ds['WELL']], :]
            # if there are any rank 2 wells modeled, anchor to final rank 2 well
            if len(rank_2_wells_modeled) > 0:
                print(f'\n| Rank 2 wells modeled: {rank_2_wells_modeled}')
                rank_2_wells_modeled.sort_values(by=['TD'], axis=0, inplace=True)
                final_rank_2_well = dict(rank_2_wells_modeled.iloc[-1, :])
                print(f'\n| Final rank 2 well:\n {final_rank_2_well}')
                # set the well activity start date to the permitted date for the generic well
                well_activity_start_date = final_rank_2_well['TD'] + rig_crew_timing[
                    'rig_move_to_next_pad'] + rig_crew_timing['permitted_to_spud']
            else:
                # else there are no rank 2 wells, so anchor the first generic well to the model start
                well_activity_start_date = pd.to_datetime(model_period[0]) + MonthBegin(-1)

        # else if this is not the first generic well, but is not a new pad, anchor the activity start to the last generic well modeled
        elif well_name != _gw[0] and well_num_on_pad != 1:
            well_activity_start_date = last_generic_well_td + rig_crew_timing[
                'skid_td_to_next_spud'] + rig_crew_timing['permitted_to_spud']

        # else if this is not the first generic well, but is a new pad, anchor the activity start to the last generic well modeled
        elif well_name != _gw[0] and well_num_on_pad == 1:
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
        pad_spud = spud + rig_crew_timing[
            'pad_spud_to_first_well_spud']
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
    elif any([_ == well_name for _ in live_ds['WELL']]):
        print(f'\n>>> Loading _activity dates for: {well_name} ')
        # load dates from live_ds if well is in there
        #  permitted date (first capex event)
        permitted = live_ds['PERMITTED'][well_index]
        # spud date
        spud = live_ds['SPUD'][well_index]
        afe = live_ds['AFE'][well_index]
        planning_staking = live_ds['PLANNING & STAKING'][well_index]
        location_build = live_ds['LOCATION BUILDING'][well_index]
        pad_spud = live_ds['PAD SPUD'][well_index]
        td = live_ds['TD'][well_index]
        remaining_wells = wells_on_pad - well_num_on_pad
        rig_release = live_ds['RIG RELEASE (PAD)'][well_index]
        compl_start = live_ds['COMPLETION START'][well_index]
        frac_end = live_ds['FRAC END'][well_index]
        drill_out_start = live_ds['DRILL OUT START'][well_index]
        compl_end = live_ds['COMPLETION END'][well_index]
        pop = live_ds['PUT ON PRODUCTION'][well_index]
        to_loe = live_ds['TURNED TO LOE'][well_index]
        first_oil = live_ds['1ST OIL'][well_index]
        post_drill_filing = live_ds['POST DRILL FILING REQUIREMENTS'][well_index]

    else:
        print('!! Activity dates not calculated. well_name must be "GENERIC" or defined in live_ds.')

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

    global save_yn_wells
    if save_yn_wells.lower() == 'y':
        wn = well_name.lower().replace(" ", "_")
        model_data[f'{wn}_activity_dates'] = pd.DataFrame(activity_dates._asdict().items())
    pprint.pprint(activity_dates._asdict())
    return activity_dates


def load_capex_detail(_well_name: str):
    # mapper for capex categories in model to capex categories in input file

    global well_drivers
    try:
        well_drivers = production_engine.well_drivers_dict[_well_name]
    except KeyError:
        _sub_asset = live_ds[live_ds['WELL'] == _well_name]['SUB-ASSET']
        well_num_on_pad = float(live_ds[live_ds['WELL'] == _well_name]['DRILL ORDER'])
        wells_on_pad = float(live_ds[live_ds['WELL'] == _well_name]['WELLS ON PAD'])
        tc_name = live_ds[live_ds['WELL'] == _well_name]['TYPE CURVE AREA']
        wi_pct = float(live_ds[live_ds['WELL'] == _well_name]['WI %']) / 100
        nri_pct = float(live_ds[live_ds['WELL'] == _well_name]['NRI %']) / 100
        gas_shrink = float(asset_level_drivers.loc[_sub_asset, 'Gas Shrink'])
        gas_btu_factor_residue = float(asset_level_drivers.loc[_sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
        gas_btu_factor_wellhead = float(asset_level_drivers.loc[_sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
        perfed_ll = float(live_ds[live_ds['WELL'] == _well_name]['PERFED LATERAL LENGTH'])
        base_ll_capex = float(live_ds[live_ds['WELL'] == _well_name]['BASE LL FOR CAPEX'])
        base_ll_tc = float(live_ds[live_ds['WELL'] == _well_name]['PERFED LATERAL LENGTH'])
        tc_multiplier = min(perfed_ll / base_ll_tc, 1.30)
        rig_crew = live_ds[live_ds['WELL'] == _well_name]['Rig Crew #']
        capex_scenario_name = live_ds[live_ds['WELL'] == _well_name]['CAPEX SCENARIO']

        well_drivers = {
            'sub_asset': _sub_asset,
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

    base_ll_capex = well_drivers['base_ll_capex']

    if any([_ == _well_name for _ in live_ds['WELL']]):
        well_index = get_well_index(_well_name)
        capex_scenario_name = live_ds['CAPEX SCENARIO'][well_index]
        perfed_ll = live_ds['PERFED LATERAL LENGTH'][well_index]
    else:
        capex_scenario_name = well_drivers['capex_scenario_name']
        perfed_ll = well_drivers['perfed_ll']

    capex_category_input_map = {
        'permit_landowner': {
            'd_c_f_type': 'd',
            'activity_ref': 'permitted',
            'capex_amt_col_name': 'Capex - Permit + Landowner ($k)',
            'pay_delay_col_name': 'Pay Delay - Permit + Landowner (days)'
        },
        'build_extend_pad': {
            'd_c_f_type': 'd',
            'activity_ref': 'location_build',
            'capex_amt_col_name': 'Capex - Build / Extend Pad ($k)',
            'pay_delay_col_name': 'Pay Delay - Build / Extend Pad (days)'
        },
        'cellar_mousehole': {
            'd_c_f_type': 'd',
            'activity_ref': 'location_build',
            'capex_amt_col_name': 'Capex - Cellar / Mousehole ($k)',
            'pay_delay_col_name': 'Pay Delay - Cellar / Mousehole (days)'
        },
        'spud_drilling': {
            'd_c_f_type': 'd',
            'activity_ref': 'td',
            'capex_amt_col_name': 'Capex - Well Spud + Drilling ($k)',
            'pay_delay_col_name': 'Pay Delay - Well Spud + Drilling (days)'
        },
        'rig_low_prep_loc': {
            'd_c_f_type': 'c',
            'activity_ref': 'rig_release',
            'capex_amt_col_name': 'Capex - Rig Low / Prep Loc ($k)',
            'pay_delay_col_name': 'Pay Delay - Rig Low / Prep Loc (days)'
        },
        'frac': {
            'd_c_f_type': 'c',
            'activity_ref': 'frac_end',
            'capex_amt_col_name': 'Capex - Frac Well ($k)',
            'pay_delay_col_name': 'Pay Delay - Frac Well (days)'
        },
        'drillout': {
            'd_c_f_type': 'c',
            'activity_ref': 'drill_out_start',
            'capex_amt_col_name': 'Capex - Drillout + Tube up ($k)',
            'pay_delay_col_name': 'Pay Delay - Drillout + Tube up (days)'
        },
        'flowback': {
            'd_c_f_type': 'c',
            'activity_ref': 'compl_end',
            'capex_amt_col_name': 'Capex - Flowback ($k)',
            'pay_delay_col_name': 'Pay Delay - Flowback (days)'
        },
        'facilities': {
            'd_c_f_type': 'f',
            'activity_ref': 'frac_end',
            'capex_amt_col_name': 'Capex - Facilities ($k)',
            'pay_delay_col_name': 'Pay Delay - Facilities (days)'
        },
        'increm_drilling_per_ft': {
            'd_c_f_type': 'd',
            'activity_ref': 'td',
            'capex_amt_col_name': 'Capex - Increm Drilling ($/ft)',
            'pay_delay_col_name': 'Pay Delay - Well Spud + Drilling (days)'
        },
        'increm_completion_per_ft': {
            'd_c_f_type': 'c',
            'activity_ref': 'frac_end',
            'capex_amt_col_name': 'Capex - Increm Completion ($/ft)',
            'pay_delay_col_name': 'Pay Delay - Frac Well (days)'
        }
    }

    print('\n| Well Capex Detail: ')
    # dict to store CapexDetail namedtuples. keys: categories, values: CapexDetail instances
    global capex_detail
    capex_detail = {}

    # incremental lateral footage for capex
    increm_ll = perfed_ll - base_ll_capex
    increm_per_ft_capex = {
        'spud_drilling': capex_category_input_map['increm_drilling_per_ft']['capex_amt_col_name'],
        'frac': capex_category_input_map['increm_completion_per_ft']['capex_amt_col_name']
    }

    # Create capex_detail :: instance of CapexDetail
    for idx, cat in enumerate(capex_category_input_map):
        # gather attribute values
        _scenario = capex_scenario_name
        _activity = capex_category_input_map[cat]['activity_ref']
        _capex_category = cat
        _d_c_f_type = capex_category_input_map[cat]['d_c_f_type']
        _capex_col = capex_category_input_map[cat]['capex_amt_col_name']
        _amount_k = dnc_capex_drivers[_capex_col][
            dnc_capex_drivers['CAPEX SCENARIO'] == _scenario
            ].values[0]

        # add on incremental costs to _amount_k if category is "spud_drilling" or "frac"
        if _capex_category in increm_per_ft_capex:
            _increm_capex_col = increm_per_ft_capex[_capex_category]
            increm_total = dnc_capex_drivers[_increm_capex_col][
                               dnc_capex_drivers['CAPEX SCENARIO'] == _scenario].values[0] * increm_ll / 1000
        else:
            increm_total = 0.0
        # add to _amount_k
        _amount_k += increm_total

        activity_dates = production_engine.well_activity_dates_dict[_well_name]
        _activity_date = [v for k, v in activity_dates._asdict().items() if str(k) == _activity][0]
        pay_delay_col = capex_category_input_map[cat]['pay_delay_col_name']
        _pay_delay_days = pd.to_timedelta(
            dnc_capex_drivers[pay_delay_col][
                dnc_capex_drivers['CAPEX SCENARIO'] == capex_scenario_name].values[0], unit='d')
        _pay_date = _activity_date + _pay_delay_days

        # create CapexDetail namedtuple instance, using attribute values
        capex_detail[cat] = CapexDetail(
            well_name=_well_name,
            scenario=_scenario,
            activity=_activity,
            capex_category=_capex_category,
            d_c_f_type=_d_c_f_type,
            amount_k=_amount_k,
            activity_date=_activity_date,
            pay_date=_pay_date,
            pay_delay_days=_pay_delay_days
        )

    print(f'|-- capex_detail:')
    pprint.pprint(capex_detail)
    return capex_detail


def calc_capex():
    global capex_detail
    global well_name
    ############# CAPEX #############
    # namedtuple for cash capex (use the capex_detail attribute to build a schedule by price case)
    # reminder: avoid using "_all" except for totals

    Capex = namedtuple('Capex', [
        'capex_permit_landowner_k',
        'capex_build_extend_pad_k',
        'capex_cellar_mousehole_k',
        'capex_spud_drilling_k',
        'capex_drilling_all_k',
        'capex_rig_low_prep_loc_k',
        'capex_frac_k',
        'capex_drillout_k',
        'capex_flowback_k',
        'capex_completion_all_k',
        'capex_facilities_k',
        'capex_total_all_k'
    ])

    # instantiate a filler dataframe in boots_template_df format for each attribute of Capex
    # use deep copies since dataframes are mutable
    filler_boots_df = pd.DataFrame().reindex_like(boots_template_df)
    filler_boots_df.fillna(0, inplace=True)

    global capex
    capex = Capex(
        capex_permit_landowner_k=filler_boots_df.copy(deep=True),
        capex_build_extend_pad_k=filler_boots_df.copy(deep=True),
        capex_cellar_mousehole_k=filler_boots_df.copy(deep=True),
        capex_spud_drilling_k=filler_boots_df.copy(deep=True),
        capex_drilling_all_k=filler_boots_df.copy(deep=True),
        capex_rig_low_prep_loc_k=filler_boots_df.copy(deep=True),
        capex_frac_k=filler_boots_df.copy(deep=True),
        capex_drillout_k=filler_boots_df.copy(deep=True),
        capex_flowback_k=filler_boots_df.copy(deep=True),
        capex_completion_all_k=filler_boots_df.copy(deep=True),
        capex_facilities_k=filler_boots_df.copy(deep=True),
        capex_total_all_k=filler_boots_df.copy(deep=True),
    )

    # parse capex amounts and pay dates by category into model format
    # loop through raw capex categories (will match keys of capex_category_input_map)
    for cat, capex_detail in capex_detail.items():
        # check if capex category is used in final model capex dataframes (will not be 1:1)
        # this approach will inherently skip fields like "incremental $/ft" and "_all" totals (calculated later)
        model_field = 'capex_' + cat + '_k'

        if model_field in [_ for _ in capex._fields]:
            print(f'\n| Capex category: {model_field}')
            # get the filler_boots_df from capex
            f_df = capex._asdict()[model_field]
            # add the amount to the correct model period
            amount = -1 * capex_detail.amount_k
            _pay_date = pd.to_datetime(capex_detail.pay_date)
            pay_month = string_date(_pay_date + MonthEnd(1))
            prev_mth = string_date(_pay_date + MonthEnd(-1))
            next_mth = string_date(_pay_date + MonthEnd(2))
            print(f'| Pay date: {string_date(_pay_date)}\n| Pay month: {pay_month}\n| Amount ($k): {amount}')
            try:
                f_df.loc[pay_month, :] += amount
            except KeyError:
                print(f'!! amount not added: {pay_month} may not be in the index.')
            print(f_df.loc[prev_mth:next_mth, :])
        else:
            print(
                f'\n!! {model_field} not found in capex. Valid fields: {[_ for _ in capex._fields]}\n'
            )
    # pprint.pprint(capex._asdict())

    # update the "_all" capex streams (components per all_capex_mapper)
    all_capex_mapper = {
        'capex_drilling_all_k': ['capex_permit_landowner_k',
                                 'capex_build_extend_pad_k',
                                 'capex_cellar_mousehole_k',
                                 'capex_spud_drilling_k'],
        'capex_completion_all_k': ['capex_rig_low_prep_loc_k',
                                   'capex_frac_k',
                                   'capex_drillout_k',
                                   'capex_flowback_k'],
        'capex_total_all_k': ['capex_drilling_all_k',
                              'capex_completion_all_k',
                              'capex_facilities_k']
    }

    for all_capex, components in all_capex_mapper.items():
        print(f'\n| Calculating: {all_capex}\n| Components: {components}')
        # the updated capex dataframe in model format
        all_capex_df = capex._asdict()[all_capex]
        for component_df_name in components:
            component_df = capex._asdict()[component_df_name]
            print(f'\n| Adding: {component_df_name} to {all_capex}...')
            all_capex_df += component_df
            print(f'|-- Running total >>\n{all_capex_df.sum(axis=0)}')

    pprint.pprint(capex)

    # add capex to model_data
    global save_yn_wells
    if save_yn_wells.lower() == 'y':
        for item_name, item_df in capex._asdict().items():
            wn = well_name.lower().replace(" ", "_")
            model_data[f'{wn}_sw_{item_name}'] = item_df
    print(f'\n| total capex (drilling, completion, facilities):\n{capex.capex_total_all_k}')
    return capex


def load_pdp_prod_opex():
    '''Loads PDP production inputs by subasset and processes the raw input into model-appropriate formats.'''
    global pdp_input_dict
    global working_cap_balance_dict

    # asset_level_drivers inputs required: gas_shrink, btu_adj, WI %, NRI % by subasset , ngl yields (actual) --> calc % of bbl
    # other inputs reqd: production splitter
    for sub_asset, pdp_input in pdp_input_dict.items():
        # use the pdp_input to create the WIVolume and NRIVolume namedtuples for PDP
        gas_shrink = float(asset_level_drivers.loc[sub_asset, 'Gas Shrink'])
        gas_btu_factor_residue = float(asset_level_drivers.loc[sub_asset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])
        gas_btu_factor_wellhead = float(asset_level_drivers.loc[sub_asset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])
        wi_pct = float(asset_level_drivers.loc[sub_asset, 'WI %']) / 100
        nri_pct = float(asset_level_drivers.loc[sub_asset, 'NRI %']) / 100
        print(
            f'| WI % / NRI % / gas shrink / residue gas BTU for {sub_asset} PDP >> {wi_pct} / {nri_pct} / {gas_shrink} / {gas_btu_factor_residue}')
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
        print(f'| NGL yields used for PDP >> {ngl_yields_actual}')
        ngl_pct_of_bbl = {k: v / sum(ngl_yields_actual.values()) for k, v in ngl_yields_actual.items()}
        print(f'| NGL % of barrel >> {ngl_pct_of_bbl}')

        ################## PDP WI PRODUCTION ##################
        # PDP wellhead oil
        asset_active_date = pd.to_datetime(asset_level_drivers.loc[sub_asset, 'Asset Active Date'], utc=True)
        _input_series = pdp_input['PDP Wellhead Prod - Oil (MBbl)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_wh_oil = pd.DataFrame(
            index=model_period,
            columns=['_pdp_wh_oil']
        )
        _pdp_wh_oil.fillna(0.0, inplace=True)
        _pdp_wh_oil.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[:,
                                                            None]

        # oil - midland // mbbl
        _oil_midland_mbbl = _pdp_wh_oil.multiply(
            production_splitter.loc[:, 'oil_midland_pct'], axis='index'
        ) * wi_pct
        _oil_houston_mbbl = _pdp_wh_oil.multiply(
            production_splitter['oil_houston_pct'].values[:forecast_length], axis='index'
        ) * wi_pct
        _oil_all_mbbl = _pdp_wh_oil.multiply(
            production_splitter['oil_all_pct'].values[:forecast_length], axis='index'
        ) * wi_pct

        # PDP wellhead gas
        _input_series = pdp_input['PDP Wellhead Prod - Gas (MMcf)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_wh_gas = pd.DataFrame(
            index=model_period,
            columns=['_pdp_wh_gas']
        )
        _pdp_wh_gas.fillna(0.0, inplace=True)
        _pdp_wh_gas.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[:,
                                                            None]

        _gas_waha_mmcf_shrunk = _pdp_wh_gas.multiply(
            production_splitter['gas_waha_pct'].values[:forecast_length], axis='index'
        ) * wi_pct * (1 - gas_shrink)
        _gas_hsc_mmcf_shrunk = _pdp_wh_gas.multiply(
            production_splitter['gas_hsc_pct'].values[:forecast_length], axis='index'
        ) * wi_pct * (1 - gas_shrink)
        _gas_all_mmcf_shrunk = _pdp_wh_gas.multiply(
            production_splitter['gas_all_pct'].values[:forecast_length], axis='index'
        ) * wi_pct * (1 - gas_shrink)
        _gas_waha_bbtu_shrunk = _gas_waha_mmcf_shrunk * gas_btu_factor_residue
        _gas_hsc_bbtu_shrunk = _gas_hsc_mmcf_shrunk * gas_btu_factor_residue
        _gas_all_bbtu_shrunk = _gas_all_mmcf_shrunk * gas_btu_factor_residue

        # PDP WI NGL
        _input_series = pdp_input['PDP WI Prod - NGL - All Streams (MBbl)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_wi_ngl = pd.DataFrame(
            index=model_period,
            columns=['_pdp_wi_ngl']
        )
        _pdp_wi_ngl.fillna(0.0, inplace=True)
        _pdp_wi_ngl.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[:,
                                                            None]

        _ngl_ethane_mbbl = _pdp_wi_ngl.multiply(ngl_pct_of_bbl['ethane'], axis='index').multiply(
            production_splitter['ngl_ethane_pct'].values[:forecast_length], axis='index'
        )
        _ngl_propane_mbbl = _pdp_wi_ngl.multiply(ngl_pct_of_bbl['propane'], axis='index').multiply(
            production_splitter['ngl_propane_pct'].values[:forecast_length], axis='index'
        )
        _ngl_n_butane_mbbl = _pdp_wi_ngl.multiply(ngl_pct_of_bbl['n_butane'], axis='index').multiply(
            production_splitter['ngl_n_butane_pct'].values[:forecast_length], axis='index'
        )
        _ngl_iso_butane_mbbl = _pdp_wi_ngl.multiply(ngl_pct_of_bbl['iso_butane'], axis='index').multiply(
            production_splitter['ngl_iso_butane_pct'].values[:forecast_length], axis='index'
        )
        _ngl_nat_gasoline_mbbl = _pdp_wi_ngl.multiply(ngl_pct_of_bbl['nat_gasoline'], axis='index').multiply(
            production_splitter['ngl_nat_gasoline_pct'].values[:forecast_length], axis='index'
        )
        _ngl_all_mbbl = _pdp_wi_ngl.multiply(production_splitter['ngl_all_pct'].values[:forecast_length], axis='index')

        # PDP wellhead water
        _input_series = pdp_input['PDP Wellhead Prod - Water (MBbl)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_wh_water = pd.DataFrame(
            index=model_period,
            columns=['_pdp_wh_water']
        )
        _pdp_wh_water.fillna(0.0, inplace=True)
        _pdp_wh_water.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[
                                                              :, None]

        _water_all_mbbl = _pdp_wh_water.multiply(wi_pct, axis='index')

        pdp_wi_prod_by_stream = WIVolume(
            oil_midland_mbbl=_oil_midland_mbbl,
            oil_houston_mbbl=_oil_houston_mbbl,
            oil_all_mbbl=_oil_all_mbbl,
            gas_waha_mmcf_shrunk=_gas_waha_mmcf_shrunk,
            gas_hsc_mmcf_shrunk=_gas_hsc_mmcf_shrunk,
            gas_all_mmcf_shrunk=_gas_all_mmcf_shrunk,
            gas_waha_bbtu_shrunk=_gas_waha_bbtu_shrunk,
            gas_hsc_bbtu_shrunk=_gas_hsc_bbtu_shrunk,
            gas_all_bbtu_shrunk=_gas_all_bbtu_shrunk,
            ngl_ethane_mbbl=_ngl_ethane_mbbl,
            ngl_propane_mbbl=_ngl_propane_mbbl,
            ngl_n_butane_mbbl=_ngl_n_butane_mbbl,
            ngl_iso_butane_mbbl=_ngl_iso_butane_mbbl,
            ngl_nat_gasoline_mbbl=_ngl_nat_gasoline_mbbl,
            ngl_all_mbbl=_ngl_all_mbbl,
            water_all_mbbl=_water_all_mbbl
        )

        # add namedtuples to model_data
        for item_name, item_df in pdp_wi_prod_by_stream._asdict().items():
            model_data[f'pdp_wi_prod_{sub_asset.lower()}_{item_name}'] = item_df
        print(f'\n| PDP WI Volumes: {sub_asset} >>>')
        print(pdp_wi_prod_by_stream)
        add_to_roll_up_dict(additions=pdp_wi_prod_by_stream, addition_type='wi_prod')

        ################## NRI volumes ##################
        # NRI production calculations with shift adjustment
        # PDP NRI oil
        _input_series = pdp_input['PDP NRI Prod - Oil (MBbl)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_nri_oil = pd.DataFrame(
            index=model_period,
            columns=['_pdp_nri_oil']
        )
        _pdp_nri_oil.fillna(0.0, inplace=True)
        _pdp_nri_oil.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[:,
                                                             None]

        _oil_midland_mbbl = _pdp_nri_oil.multiply(production_splitter['oil_midland_pct'].values[:forecast_length],
                                                  axis='index')
        _oil_houston_mbbl = _pdp_nri_oil.multiply(production_splitter['oil_houston_pct'].values[:forecast_length],
                                                  axis='index')
        _oil_all_mbbl = _pdp_nri_oil.multiply(production_splitter['oil_all_pct'].values[:forecast_length], axis='index')

        # PDP NRI gas
        _input_series = pdp_input['PDP NRI Prod - Residue Gas - All (MMcf)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_nri_gas_shrunk = pd.DataFrame(
            index=model_period,
            columns=['_pdp_nri_gas_shrunk']
        )
        _pdp_nri_gas_shrunk.fillna(0.0, inplace=True)
        _pdp_nri_gas_shrunk.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[
                                                                    _pdp_start_month: _pdp_end_month].values[:, None]

        _gas_waha_mmcf_shrunk = _pdp_nri_gas_shrunk.multiply(
            production_splitter['gas_waha_pct'].values[:forecast_length], axis='index')
        _gas_hsc_mmcf_shrunk = _pdp_nri_gas_shrunk.multiply(production_splitter['gas_hsc_pct'].values[:forecast_length],
                                                            axis='index')
        _gas_all_mmcf_shrunk = _pdp_nri_gas_shrunk.multiply(production_splitter['gas_all_pct'].values[:forecast_length],
                                                            axis='index')
        _gas_waha_bbtu_shrunk = _gas_waha_mmcf_shrunk.multiply(gas_btu_factor_residue, axis='index')
        _gas_hsc_bbtu_shrunk = _gas_hsc_mmcf_shrunk.multiply(gas_btu_factor_residue, axis='index')
        _gas_all_bbtu_shrunk = _gas_all_mmcf_shrunk.multiply(gas_btu_factor_residue, axis='index')

        # PDP NRI NGLs
        _input_series = pdp_input['PDP NRI Prod - NGL - All Streams (MBbl)']
        fill_values = _input_series.loc[
            [_ for _ in _input_series.index if _ in model_period and _ >= asset_active_date]
        ]
        _pdp_start_month = max(fill_values.index[0], model_period[0])
        _pdp_end_month = min(fill_values.index[-1], model_period[-1])
        _pdp_nri_ngl = pd.DataFrame(
            index=model_period,
            columns=['_pdp_nri_ngl']
        )
        _pdp_nri_ngl.fillna(0.0, inplace=True)
        _pdp_nri_ngl.loc[_pdp_start_month: _pdp_end_month] = fill_values.loc[_pdp_start_month: _pdp_end_month].values[:,
                                                             None]

        _ngl_ethane_mbbl = _pdp_nri_ngl * ngl_pct_of_bbl['ethane']
        _ngl_propane_mbbl = _pdp_nri_ngl * ngl_pct_of_bbl['propane']
        _ngl_n_butane_mbbl = _pdp_nri_ngl * ngl_pct_of_bbl['n_butane']
        _ngl_iso_butane_mbbl = _pdp_nri_ngl * ngl_pct_of_bbl['iso_butane']
        _ngl_nat_gasoline_mbbl = _pdp_nri_ngl * ngl_pct_of_bbl['nat_gasoline']
        _ngl_all_mbbl = _pdp_nri_ngl

        pdp_nri_prod_by_stream = NRIVolume(
            oil_midland_mbbl=_oil_midland_mbbl,
            oil_houston_mbbl=_oil_houston_mbbl,
            oil_all_mbbl=_oil_all_mbbl,
            gas_waha_mmcf_shrunk=_gas_waha_mmcf_shrunk,
            gas_hsc_mmcf_shrunk=_gas_hsc_mmcf_shrunk,
            gas_all_mmcf_shrunk=_gas_all_mmcf_shrunk,
            gas_waha_bbtu_shrunk=_gas_waha_bbtu_shrunk,
            gas_hsc_bbtu_shrunk=_gas_hsc_bbtu_shrunk,
            gas_all_bbtu_shrunk=_gas_all_bbtu_shrunk,
            ngl_ethane_mbbl=_ngl_ethane_mbbl,
            ngl_propane_mbbl=_ngl_propane_mbbl,
            ngl_n_butane_mbbl=_ngl_n_butane_mbbl,
            ngl_iso_butane_mbbl=_ngl_iso_butane_mbbl,
            ngl_nat_gasoline_mbbl=_ngl_nat_gasoline_mbbl,
            ngl_all_mbbl=_ngl_all_mbbl
        )

        # add namedtuples to model_data
        for item_name, item_df in pdp_nri_prod_by_stream._asdict().items():
            model_data[f'pdp_nri_prod_{sub_asset.lower()}_{item_name}'] = item_df
        print(f'\n| PDP NRI Volumes: {sub_asset} >>>')
        print(pdp_nri_prod_by_stream)
        add_to_roll_up_dict(additions=pdp_nri_prod_by_stream, addition_type='nri_prod')

        # PDP opex
        filler_df = pd.DataFrame().reindex_like(boots_template_df)
        filler_df.fillna(0, inplace=True)
        _pdp_opex = pd.DataFrame().reindex_like(boots_template_df)
        for col in _pdp_opex.columns:
            fill_values = -pdp_input.loc[
                [_ for _ in pdp_input.index if _ in model_period and _ >= asset_active_date], 'PDP Opex ($k)'
            ]
            _opex_start_month = max(fill_values.index[0], model_period[0])
            _opex_end_month = min(fill_values.index[-1], model_period[-1])

            _pdp_opex.fillna(0.0, inplace=True)
            _pdp_opex.loc[_pdp_start_month: _pdp_end_month, col] = fill_values.loc[
                                                                   _pdp_start_month: _pdp_end_month].values

        # pre-shrink / shift-adjusted gas volumes for this subasset
        gas_all_mmcf_preshrink = pdp_nri_prod_by_stream.gas_all_mmcf_shrunk.div(1 - gas_shrink)

        # if PDP opex includes gas marketing expenses, update here. Else use zero.
        opex_unit_cost_mapper = get_opex_unit_cost_mapper(sub_asset=sub_asset)
        # apply the gas marketing fees to these by price scenario column
        marketing_nitrogen_k = filler_df.copy(deep=True)
        marketing_electricity_k = filler_df.copy(deep=True)
        marketing_gathering_k = filler_df.copy(deep=True)
        marketing_processing_k = filler_df.copy(deep=True)
        marketing_sold_gas_compr_k = filler_df.copy(deep=True)

        if model_control.include_pdp_gas_marketing[sub_asset] is True:
            for price_scenario in filler_df.columns:
                marketing_nitrogen_k.loc[:, price_scenario] -= (gas_all_mmcf_preshrink.values * opex_unit_cost_mapper[
                    'marketing_nitrogen_k'][0]).squeeze()
                marketing_electricity_k.loc[:, price_scenario] -= (
                        gas_all_mmcf_preshrink.values * opex_unit_cost_mapper[
                    'marketing_electricity_k'][0]).squeeze()
                marketing_gathering_k.loc[:, price_scenario] -= (gas_all_mmcf_preshrink.values \
                                                                 * gas_btu_factor_wellhead \
                                                                 * opex_unit_cost_mapper['marketing_gathering_k'][0]
                                                                 ).squeeze()
                marketing_processing_k.loc[:, price_scenario] -= (gas_all_mmcf_preshrink.values \
                                                                  * gas_btu_factor_wellhead \
                                                                  * opex_unit_cost_mapper['marketing_processing_k'][0]
                                                                  ).squeeze()
                marketing_sold_gas_compr_k.loc[:, price_scenario] -= (gas_all_mmcf_preshrink * opex_unit_cost_mapper[
                    'marketing_sold_gas_compr_k'][0]).squeeze()

        marketing_all_k = marketing_nitrogen_k + \
                          marketing_electricity_k + \
                          marketing_gathering_k + \
                          marketing_processing_k + \
                          marketing_sold_gas_compr_k

        pdp_opex = Opex(
            loe_oil_variable_k=filler_df.copy(deep=True),
            loe_water_variable_k=filler_df.copy(deep=True),
            loe_fixed_k=_pdp_opex,
            loe_reinj_gas_compr_k=filler_df.copy(deep=True),
            loe_all_k=_pdp_opex,
            marketing_nitrogen_k=marketing_nitrogen_k,
            marketing_electricity_k=marketing_electricity_k,
            marketing_gathering_k=marketing_gathering_k,
            marketing_processing_k=marketing_processing_k,
            marketing_sold_gas_compr_k=marketing_sold_gas_compr_k,
            marketing_all_k=marketing_all_k,
            opex_total_all_k=_pdp_opex + marketing_all_k
        )

        # add namedtuples to model_data
        for item_name, item_df in pdp_opex._asdict().items():
            model_data[f'pdp_opex_{sub_asset.lower()}_{item_name}'] = item_df
        print(f'\n| PDP Opex: {sub_asset} >>>')
        print(pdp_opex)
        add_to_roll_up_dict(additions=pdp_opex, addition_type='opex')


def load_wi_nri_production():
    '''Loads total modeled WI and NRI production from the production engine.
        Returns:
            a dictionary of WIVolume and NRIVolume namedtuples --> {'wi_volumes_total': WIVolume,
            'nri_volumes_total': NRIVolume}
            '''
    global wi_volumes_total
    global nri_volumes_total
    wi_volumes_total, nri_volumes_total = production_engine.run_production_engine()

    # add namedtuples to model_data
    if save_yn_wells.lower() == 'y':
        for item_name, item_df in wi_volumes_total._asdict().items():
            wn = _well_name.lower().replace(" ", "_")
            model_data[f'{wn}_wi_prod_{item_name}'] = item_df
    print(f'\n| WI Volumes (total) >>>')
    print(wi_volumes_total)

    # add namedtuples to model_data
    if save_yn_wells.lower() == 'y':
        for item_name, item_df in nri_volumes_total._asdict().items():
            wn = _well_name.lower().replace(" ", "_")
            model_data[f'{wn}_nri_prod_{item_name}'] = item_df
    print(f'\n| NRI Volumes (total) >>>')
    print(nri_volumes_total)
    return {'wi_volumes_total': wi_volumes_total,
            'nri_volumes_total': nri_volumes_total}


def calc_revenue():
    '''Calculate MCS revenue for a production stream.'''
    # get net realized prices for this well
    # keys: prod streams, values: dataframes with index = model period, columns = MCS + strip price scenarios
    global revenue
    global parentco_nri_prod_by_stream
    nri_volumes_total = NRIVolume(**parentco_nri_prod_by_stream)

    global net_realized_price_dict
    if 'net_realized_price_dict' not in globals():
        net_realized_price_dict = market.get_net_realized_prices(
            nri_prod_by_stream=nri_volumes_total,
            include_fees=True
        )

    # add items of the net_realized_price dict to the model_level_drivers dict (for output later)
    for c_nick in net_realized_price_dict:
        model_data[f'net_realized_price_{c_nick}'] = net_realized_price_dict[c_nick]
        print(f'| {c_nick} added to model_data dict.')

    ############# REVENUE #############
    # namedtuple and mapper for revenue
    # reminder: avoid using "_all" except for totals
    Revenue = namedtuple(
        'Revenue', ['oil_midland_rev_k',
                    'oil_houston_rev_k',
                    'oil_all_rev_k',
                    'gas_hsc_rev_k',
                    'gas_waha_rev_k',
                    'gas_all_rev_k',
                    'ngl_ethane_rev_k',
                    'ngl_propane_rev_k',
                    'ngl_n_butane_rev_k',
                    'ngl_iso_butane_rev_k',
                    'ngl_nat_gasoline_rev_k',
                    'ngl_all_rev_k',
                    'revenue_total_all_k']
    )

    # mapper: revenue streams --> production streams
    # NOTE: keys should map to Revenue attributes EXCEPT revenue_total_all_k (calc'd after the rest)
    revenue_prod_stream_mapper = {
        'oil_midland_rev_k': 'oil_midland_mbbl',
        'oil_houston_rev_k': 'oil_houston_mbbl',
        'oil_all_rev_k': 'oil_all_mbbl',
        'gas_hsc_rev_k': 'gas_hsc_bbtu_shrunk',
        'gas_waha_rev_k': 'gas_waha_bbtu_shrunk',
        'gas_all_rev_k': 'gas_all_bbtu_shrunk',
        'ngl_ethane_rev_k': 'ngl_ethane_mbbl',
        'ngl_propane_rev_k': 'ngl_propane_mbbl',
        'ngl_n_butane_rev_k': 'ngl_n_butane_mbbl',
        'ngl_iso_butane_rev_k': 'ngl_iso_butane_mbbl',
        'ngl_nat_gasoline_rev_k': 'ngl_nat_gasoline_mbbl',
        'ngl_all_rev_k': 'ngl_all_mbbl'
    }

    # mapper: prod streams --> keys of conversion_ratios
    unit_conversion_mapper = {
        'oil_midland_mbbl': 'none',
        'oil_houston_mbbl': 'none',
        'oil_all_mbbl': 'none',
        'gas_hsc_bbtu_shrunk': 'none',
        'gas_waha_bbtu_shrunk': 'none',
        'gas_all_bbtu_shrunk': 'none',
        'ngl_ethane_mbbl': 'gal/bbl - energy',
        'ngl_propane_mbbl': 'gal/bbl - energy',
        'ngl_n_butane_mbbl': 'gal/bbl - energy',
        'ngl_iso_butane_mbbl': 'gal/bbl - energy',
        'ngl_nat_gasoline_mbbl': 'gal/bbl - energy',
        'ngl_all_mbbl': 'gal/bbl - energy'
    }

    # mapper: "_all" / total revenue attributes to their component parts for summing
    # includes an entry for total revenue across all streams (revenue_total_all_k)
    all_revenue_mapper = {
        'oil_all_rev_k': ['oil_midland_rev_k', 'oil_houston_rev_k'],
        'gas_all_rev_k': ['gas_hsc_rev_k', 'gas_waha_rev_k'],
        'ngl_all_rev_k': ['ngl_ethane_rev_k',
                          'ngl_propane_rev_k',
                          'ngl_n_butane_rev_k',
                          'ngl_iso_butane_rev_k',
                          'ngl_nat_gasoline_rev_k'],
        'revenue_total_all_k': ['oil_all_rev_k',
                                'gas_all_rev_k',
                                'ngl_all_rev_k']
    }

    # dictionary used to construct the revenue namedtuple after individual streams are calculated
    rev_dict = {}

    # calculate net revenue by production stream (nri_volumes_total * net_realized_prices)
    for rev_stream_name, prod_stream_name in revenue_prod_stream_mapper.items():
        print(f'\n| Revenue >> {model_control.modeled_wells_all}')
        # if this production stream is not a total, or a gas stream in MMcf (since gas prices are in $/MMBtu)
        if not (any([_ in prod_stream_name for _ in ['_all', '_mmcf']])):
            nri_prod_stream = nri_volumes_total._asdict()[prod_stream_name]
            conv_ratio_key = unit_conversion_mapper[prod_stream_name]
            prices = net_realized_price_dict[prod_stream_name] * conversion_ratios[conv_ratio_key]

            print(f'| Revenue stream: {rev_stream_name} \n| Production stream: {prod_stream_name}')
            print(
                f'| Realized Prices (unit conversion: {conv_ratio_key} --> {conversion_ratios[conv_ratio_key]}):\n{prices}')

            net_revenue = pd.DataFrame().reindex_like(boots_template_df)
            net_revenue.fillna(0, inplace=True)
            # net revenue for this production stream
            for col in net_revenue:
                net_revenue[col] = prices[col] * nri_prod_stream.values.squeeze()
            print(f'\n| Net Revenue >> {rev_stream_name}\n{net_revenue}')
            # deep copy net_revenue to the rev_dict (since net_revenue is mutable and changes with each loop,
            # a shallow copy or simply "=" creates a reference to a mutating object in memory)
            rev_dict[rev_stream_name] = net_revenue.copy(deep=True)
        else:
            print(f'\n!! Net realized prices not found for: {prod_stream_name}\n')

    # update the "_all" revenue streams for oil, gas, NGLs, and total (components per all_revenue_mapper)
    for all_rev, components in all_revenue_mapper.items():
        print(f'\n| Calculating: {all_rev}\n| Components: {components}')
        rev_dict[all_rev] = pd.DataFrame().reindex_like(boots_template_df)
        rev_dict[all_rev].fillna(0, inplace=True)
        for component_df in components:
            print(f'\n|-- Current component: {component_df}\n{rev_dict[component_df]}')
            rev_dict[all_rev] += rev_dict[component_df]
            print(f'\n|-- Total {all_rev}:\n{rev_dict[all_rev]}')

    # create revenue attribute (Revenue namedtuple)
    revenue = Revenue(**rev_dict)

    # add revenue to requested_chart data
    for item_name, item_df in revenue._asdict().items():
        model_data[f'revenue_{item_name}'] = item_df
    print(revenue)
    print(f'\n| revenue (all streams):\n{revenue.revenue_total_all_k}')
    return revenue


def calc_prod_taxes():
    '''Calculate production taxes for a production stream'''
    global revenue
    global forecast_length

    ProdTaxes = namedtuple('ProdTaxes', [
        'prod_taxes_severance_oil_k',
        'prod_taxes_severance_gas_k',
        'prod_taxes_severance_ngl_k',
        'prod_taxes_severance_all_k',
        'prod_taxes_ad_valorem_k',
        'prod_taxes_total_all_k'
    ])

    # |-- revenue net of severance taxes (sev taxes deducted later)
    rev_net_sev_taxes = revenue.revenue_total_all_k.copy(deep=True)

    # |-- generic unit stream (a series of "1s" with index = model_period.index)
    generic_unit_stream = pd.DataFrame(index=boots_template_df.index, columns=[0])
    generic_unit_stream.fillna(1.0, inplace=True)

    # mapper: prod_taxes --> unit cost driver ($ per unit or % of unit stream)
    prod_taxes_unit_cost_mapper = {
        'prod_taxes_severance_oil_k': [
            asset_level_drivers.loc['Farmar', 'Severance Taxes - Oil'],
            '%'],
        'prod_taxes_severance_gas_k': [
            asset_level_drivers.loc['Farmar', 'Severance Taxes - Gas'],
            '%'],
        'prod_taxes_severance_ngl_k': [
            asset_level_drivers.loc['Farmar', 'Severance Taxes - NGL'],
            '%'],
        'prod_taxes_ad_valorem_k': [
            asset_level_drivers.loc['Farmar', 'Ad Valorem Taxes'],
            '%']
    }

    # mapper: production tax line items --> unit streams to multiply by unit costs above
    #  $/unit * unit stream --> dataframe in net_realized_prices format
    prod_taxes_unit_stream_mapper = {
        'prod_taxes_severance_oil_k': revenue.oil_all_rev_k,
        'prod_taxes_severance_gas_k': revenue.gas_all_rev_k,
        'prod_taxes_severance_ngl_k': revenue.ngl_all_rev_k,
        'prod_taxes_ad_valorem_k': rev_net_sev_taxes
    }

    # dict to construct ProdTaxes namedtuple after components are calculated
    prod_taxes_dict = {}

    # all_prod_taxes_mapper
    all_prod_taxes_mapper = {
        'prod_taxes_severance_all_k': ['prod_taxes_severance_oil_k',
                                       'prod_taxes_severance_gas_k',
                                       'prod_taxes_severance_ngl_k'],
        'prod_taxes_total_all_k': ['prod_taxes_severance_all_k',
                                   'prod_taxes_ad_valorem_k']
    }

    # calculate prod tax items, then create the ProdTaxes namedtuple instance
    for prod_taxes_line_item, [unit_cost, unit] in prod_taxes_unit_cost_mapper.items():
        # convert string input to float
        unit_cost = float(unit_cost)
        print(f'\n>>> Calculating {prod_taxes_line_item}\n| Unit Cost Value: {unit_cost: .3f} | Unit: {unit}')
        unit_stream = prod_taxes_unit_stream_mapper[prod_taxes_line_item].copy(deep=True)
        # trim index to length of forecast periods
        unit_stream = unit_stream.iloc[:forecast_length]
        print(f'\n| Raw unit stream for {prod_taxes_line_item}:\n', unit_stream)
        # rename the unit stream if it has a "name" attribute
        try:
            unit_stream.name = prod_taxes_line_item
        except AttributeError:
            print(f'\n!! unit_stream does not have a "name" attribute.\n')

        # set the unit_stream index to the boots_template_df index
        try:
            unit_stream.index = boots_template_df.index
        except AttributeError:
            print(f'\n!! unit_stream does not have an "index" attribute.\n')

        # multiply the unit stream by the unit cost to get the total prod taxes dataframe or series
        tot_prod_taxes = -unit_cost * unit_stream
        if tot_prod_taxes.shape == boots_template_df.shape:
            # if tot_prod_taxes is a dataframe like boots_template_df, just add it to the opex_dict
            prod_taxes_dict[prod_taxes_line_item] = tot_prod_taxes
        else:
            # create a dataframe in the format of boots_template_df with the tot_opex series
            total_expense_df = pd.DataFrame().reindex_like(boots_template_df)
            for col in total_expense_df.columns:
                total_expense_df[col] = tot_prod_taxes
            prod_taxes_dict[opex_line_item] = total_expense_df
        print(f'\n| Total prod taxes ($k) >> {prod_taxes_line_item}:\n{prod_taxes_dict[prod_taxes_line_item]}')

        if 'severance' in prod_taxes_line_item:
            # subtract sev taxes from rev_net_sev_taxes dataframe (initially set to revenue.revenue_total_all_k)
            print(rev_net_sev_taxes)
            rev_net_sev_taxes += prod_taxes_dict[prod_taxes_line_item]
            print(f'| Revenue net of {prod_taxes_line_item}:\n{rev_net_sev_taxes}')

    # update the "_all" prod taxes streams (components per all_prod_taxes_mapper)
    for all_prod_taxes, components in all_prod_taxes_mapper.items():
        print(f'\n| Calculating: {all_prod_taxes}\n| Components: {components}')
        prod_taxes_dict[all_prod_taxes] = pd.DataFrame().reindex_like(boots_template_df)
        prod_taxes_dict[all_prod_taxes].fillna(0, inplace=True)
        for component_df in components:
            print(f'\n|-- Current component: {component_df}\n{prod_taxes_dict[component_df]}')
            prod_taxes_dict[all_prod_taxes] += prod_taxes_dict[component_df]
            print(f'\n|-- Total {all_prod_taxes}:\n{prod_taxes_dict[all_prod_taxes]}')

    # create prod_taxes attribute (ProdTaxes namedtuple)
    global prod_taxes
    prod_taxes = ProdTaxes(**prod_taxes_dict)

    # add prod_taxes to model_data
    for item_name, item_df in prod_taxes._asdict().items():
        model_data[f'{item_name}'] = item_df
    print(prod_taxes)
    print(f'\n| total prod taxes (all):\n{prod_taxes.prod_taxes_total_all_k}')
    return prod_taxes


def get_opex_unit_cost_mapper(sub_asset: str):
    '''Returns a dictionary to map a sub-asset's operating expenses to the unit cost inputs in the asset_level_drivers dataframe.'''

    global asset_level_drivers
    mapper = {
        'loe_oil_variable_k': [
            float(asset_level_drivers.loc[sub_asset, 'Variable Opex - Oil ($/Bbl)']),
            '$/Bbl'],
        'loe_water_variable_k': [
            float(asset_level_drivers.loc[sub_asset, 'Variable Opex - Water ($/Bbl)']),
            '$/Bbl'],
        'loe_fixed_k': [
            float(asset_level_drivers.loc[sub_asset, 'Fixed Opex - Dev Program ($/W/Mo)']) / 1000,
            '$/well/month'
        ],
        'loe_reinj_gas_compr_k': [
            1.0 if float(
                asset_level_drivers.loc[sub_asset, 'Fixed Opex - Dev Program ($/W/Mo)']) / 1000 == 0 else 0.0,
            '$k/well/month'
        ],  # we use an AGL fixed opex curve per well for this
        'marketing_nitrogen_k': [
            float(asset_level_drivers.loc[sub_asset, 'Nitrogen Fee $/mcf']),
            '$/Mcf (NRI, pre-shrink)'],
        'marketing_electricity_k': [
            float(asset_level_drivers.loc[sub_asset, 'Electricity Fee $/mcf']),
            '$/Mcf (NRI, pre-shrink)'],
        'marketing_gathering_k': [
            float(asset_level_drivers.loc[sub_asset, 'Gathering Fee $/mmbtu']),
            '$/MMBtu (NRI, pre-shrink)'],
        'marketing_processing_k': [
            float(asset_level_drivers.loc[sub_asset, 'Processing Fee $/mmbtu']),
            '$/MMBtu (NRI, pre-shrink)'],
        'marketing_sold_gas_compr_k': [
            float(asset_level_drivers.loc[sub_asset, 'Sold Gas Compr Fee $/mcf']),
            '$/Mcf (NRI, pre-shrink)'],
    }

    return mapper


def calc_opex():
    '''Calculate opex for each modeled well and total.'''

    # WI oil and water production by well
    wi_prod_by_well_dict = production_engine.get_production_dataframes(wi_nri='wi', by_well=True)
    wi_prod_oil_by_well = [df for name, df in wi_prod_by_well_dict.items() if 'oil' in name][0]
    wi_prod_water_by_well = [df for name, df in wi_prod_by_well_dict.items() if 'water' in name][0]

    # NRI shrunk gas production by well
    nri_prod_by_well_dict = production_engine.get_production_dataframes(wi_nri='nri', by_well=True)
    nri_gas_all_mmcf_shrunk_by_well = [
        df for name, df in nri_prod_by_well_dict.items() if
        all([_ in name and 'btu' not in name for _ in ('nri', 'gas')])
    ][0]

    # dict to construct Opex namedtuple instance after components are calculated (for all wells)
    global opex_dict
    opex_dict = {}

    # template dataframe for opex by well
    opex_by_well = pd.DataFrame().reindex_like(wi_prod_oil_by_well)
    opex_by_well.fillna(0, inplace=True)

    # Template unit streams for the opex_unit_stream_mapper defined below
    # |-- generic unit stream (a series of "1s" with index = model_period.index)
    generic_unit_stream = pd.DataFrame(index=boots_template_df.index, columns=[0])
    generic_unit_stream.fillna(1.0, inplace=True)

    # all_opex_mapper
    all_opex_mapper = {
        'loe_all_k': ['loe_oil_variable_k',
                      'loe_water_variable_k',
                      'loe_reinj_gas_compr_k',
                      'loe_fixed_k'],
        'marketing_all_k': ['marketing_nitrogen_k',
                            'marketing_electricity_k',
                            'marketing_gathering_k',
                            'marketing_processing_k',
                            'marketing_sold_gas_compr_k'],
        'opex_total_all_k': ['loe_all_k',
                             'marketing_all_k']
    }

    for well_name in wi_prod_oil_by_well.columns:
        global forecast_length
        global roll_up_dict

        well_drivers = production_engine.well_drivers_dict[well_name]
        activity_dates = production_engine.well_activity_dates_dict[well_name]
        gas_shrink = well_drivers['gas_shrink']
        sub_asset = well_drivers['sub_asset']
        gas_btu_factor_wellhead = well_drivers['gas_btu_factor_wellhead']

        # calculate pre-shrink / shift-adjusted gas volumes for this well
        gas_all_mmcf_preshrink_shift_adj = nri_gas_all_mmcf_shrunk_by_well.loc[:, well_name] / (1 - gas_shrink)

        # generic stream of 1s starting at the POP date for this well
        generic_unit_stream_adjusted = shift_adjust_unit_stream(
            well_pop_date=activity_dates.pop,
            unit_stream_to_adjust=generic_unit_stream.loc[:, 0]
        )

        # per well fixed opex (AGL opex) is variable at the sub-asset level, so it's most efficient to include the input in the PDP input dict
        _unit_stream_to_adjust = pd.Series(index=model_period).fillna(0)
        _unit_stream_to_adjust.loc[pdp_input_dict[sub_asset].index] += pdp_input_dict[sub_asset].loc[:,
                                                                       'agl_opex_per_well_k'].values
        _unit_stream_to_adjust.ffill(inplace=True)

        agl_opex_per_well_adjusted = shift_adjust_unit_stream(
            well_pop_date=activity_dates.pop,
            unit_stream_to_adjust=_unit_stream_to_adjust
        )

        # mapper for opex line items --> unit streams to multiply by unit costs above
        #  $/unit * unit stream --> dataframe in net_realized_prices format
        opex_unit_stream_mapper = {
            'loe_oil_variable_k': wi_prod_oil_by_well.loc[:, well_name],
            'loe_water_variable_k': wi_prod_water_by_well.loc[:, well_name],
            'loe_fixed_k': generic_unit_stream_adjusted,
            'loe_reinj_gas_compr_k': agl_opex_per_well_adjusted,
            'marketing_nitrogen_k': gas_all_mmcf_preshrink_shift_adj,
            'marketing_electricity_k': gas_all_mmcf_preshrink_shift_adj,
            'marketing_gathering_k': gas_all_mmcf_preshrink_shift_adj * gas_btu_factor_wellhead,
            'marketing_processing_k': gas_all_mmcf_preshrink_shift_adj * gas_btu_factor_wellhead,
            'marketing_sold_gas_compr_k': gas_all_mmcf_preshrink_shift_adj,
        }

        # mapper: operating expenses --> unit cost driver ($ per unit or % of unit stream)
        opex_unit_cost_mapper = get_opex_unit_cost_mapper(sub_asset)

        # calculate cash expense items, then create the opex namedtuple instance
        for opex_line_item, [unit_cost, unit] in opex_unit_cost_mapper.items():
            # convert string input to float
            unit_cost = float(unit_cost)
            print(f'\n>>> Calculating {opex_line_item}\n| Unit Cost Value: {unit_cost: .3f} | Unit: {unit}')
            unit_stream = opex_unit_stream_mapper[opex_line_item].copy(deep=True)
            # trim index to length of forecast periods
            unit_stream = unit_stream.iloc[:forecast_length]
            print(f'\n| Raw unit stream for {opex_line_item}:\n', unit_stream)
            # rename the unit stream if it has a "name" attribute
            try:
                unit_stream.name = opex_line_item
            except AttributeError:
                print(f'\n!! unit_stream does not have a "name" attribute.\n')

            # set the unit_stream index to the boots_template_df index
            try:
                unit_stream.index = boots_template_df.index
            except AttributeError:
                print(f'\n!! unit_stream does not have an "index" attribute.\n')

            # multiply the unit stream by the unit cost to get the total opex dataframe or series
            tot_opex = -unit_cost * unit_stream
            if tot_opex.shape == boots_template_df.shape:
                # if tot_opex is a dataframe like boots_template_df, just add it to the opex_dict
                try:
                    opex_dict[opex_line_item] += tot_opex
                except KeyError:
                    opex_dict[opex_line_item] = tot_opex
            else:
                # create a dataframe in the format of boots_template_df with the tot_opex series
                total_expense_df = pd.DataFrame().reindex_like(boots_template_df)
                for col in total_expense_df.columns:
                    total_expense_df[col] = tot_opex
                try:
                    opex_dict[opex_line_item] += total_expense_df
                except KeyError:
                    opex_dict[opex_line_item] = total_expense_df
            print(f'\n| Total opex ($k) >> {opex_line_item}:\n{opex_dict[opex_line_item]}')

        # update the "_all" opex streams (components per all_opex_mapper)
        for all_opex, components in all_opex_mapper.items():
            print(f'\n| Calculating: {all_opex}\n| Components: {components}')
            opex_dict[all_opex] = pd.DataFrame().reindex_like(boots_template_df)
            opex_dict[all_opex].fillna(0, inplace=True)
            for component_df in components:
                print(f'\n|-- Current component: {component_df}\n{opex_dict[component_df]}')
                opex_dict[all_opex] += opex_dict[component_df]
                print(f'\n|-- Total {all_opex}:\n{opex_dict[all_opex]}')

    # create opex attribute (Opex namedtuple) after all wells opex has been added to opex_dict
    global opex
    opex = Opex(**opex_dict)

    # add opex to model_data
    if save_yn_wells.lower() == 'y':
        for item_name, item_df in opex._asdict().items():
            # wn = well_name.lower().replace(" ", "_")
            model_data[f'total_opex_{item_name}'] = item_df
    print(opex)
    print(f'\n| total opex (all):\n{opex.opex_total_all_k}')
    return opex


def calc_ebitdax_fcf():
    global parentco_opex
    global parentco_capex
    global prod_taxes

    # EBITDAX
    global ebitdax

    # economic cutoff for negative EBITDAX
    rev_net_prod_taxes = revenue.revenue_total_all_k + prod_taxes.prod_taxes_total_all_k
    pco_opex_abs = -parentco_opex['opex_total_all_k'].copy(deep=True)
    mask_1 = pco_opex_abs <= rev_net_prod_taxes
    mask_2 = pco_opex_abs > rev_net_prod_taxes
    pco_opex_abs = pco_opex_abs * mask_1 + rev_net_prod_taxes * mask_2
    parentco_opex['opex_total_all_k'] = -pco_opex_abs.copy(deep=True)

    # calc EBITDAX
    ebitdax = EBITDAX(
        ebitdax_unhedged_total_all_k=revenue.revenue_total_all_k + \
                                     prod_taxes.prod_taxes_total_all_k + \
                                     parentco_opex['opex_total_all_k']
    )

    print(f'\n| EBITDAX (revenue less opex - ex SG&A and hedges):\n{ebitdax}')
    # add namedtuple to model_data
    for item_name, item_df in ebitdax._asdict().items():
        model_data[f'{item_name}'] = item_df

    # free cash flow
    global fcf
    fcf = FreeCashFlow(
        fcf_unhedged_total_all_k=ebitdax.ebitdax_unhedged_total_all_k + parentco_capex['capex_total_all_k'])
    print(f'\n| free cash flow (EBITDAX less capex):\n{fcf}')

    # add namedtuple to model_data
    for item_name, item_df in fcf._asdict().items():
        model_data[f'{item_name}'] = item_df

    global cumulative_fcf
    cumulative_fcf = FreeCashFlow(fcf_unhedged_total_all_k=fcf.fcf_unhedged_total_all_k.cumsum(axis=0))
    # add namedtuple to model_data
    for item_name, item_df in cumulative_fcf._asdict().items():
        model_data[f'cumulative_{item_name}'] = item_df

    return {'ebitdax_unhedged_total_all_k': ebitdax,
            'fcf_unhedged_total_all_k': fcf,
            'cum_unhedgedulative_fcf_total_all_k': cumulative_fcf
            }


def calc_npv_returns(_ebitdax: namedtuple, _fcf: namedtuple):
    # NPV and Returns calculations
    print(f'\n| NPV and returns >> {model_control.modeled_wells_all}')
    # define desired NPV discount rates
    npv_rates = [0.00, 0.08, 0.09, 0.10, 0.15, 0.20, 0.25, 0.35, 0.45, 0.50]
    string_npv_rates = [f'PV-{_ * 100:.0f}' for _ in npv_rates]
    npv_rates_pv_x = dict(zip(npv_rates, string_npv_rates))

    # namedtuple for NPV and returns
    NPVReturns = namedtuple('NPVReturns', 'npv_returns')

    # dataframe for NPVs and returns. index = NPVReturns fields, columns = MCS+Strip price scenarios
    npv_returns = pd.DataFrame(index=string_npv_rates, columns=_fcf.fcf_unhedged_total_all_k.columns)
    # --> 1) PV-x calc
    for npv_rate, pv_x in npv_rates_pv_x.items():
        if npv_rate == 0.00:
            # if PV-0, just sum up the FCF
            npv_returns.loc[pv_x, :] = _fcf.fcf_unhedged_total_all_k.sum(axis=0)
        else:
            # for each price _scenario
            for price_scen in npv_returns.columns:
                # get the  FCF
                fcf_for_price_scen = _fcf.fcf_unhedged_total_all_k.loc[:, price_scen]
                # calculate the PV-x for this price _scenario
                npv_returns.loc[pv_x, price_scen] = return_functions.xnpv(
                    rate=npv_rate,
                    values=fcf_for_price_scen.values,
                    dates=[pd.to_datetime(_) for _ in fcf_for_price_scen.index]
                )

    # --> 2) IRR calc
    irr = pd.DataFrame(index=['IRR %'], columns=npv_returns.columns)
    for price_scen in irr.columns:
        # get FCF for this price _scenario
        fcf_for_price_scen = _fcf.fcf_unhedged_total_all_k.loc[:, price_scen]
        irr.loc['IRR %', price_scen] = return_functions.xirr(
            values=fcf_for_price_scen.values,
            dates=[pd.to_datetime(_) for _ in fcf_for_price_scen.index]
        )

    # --> 3) ROI calc
    roi = pd.DataFrame(index=['ROI x'], columns=npv_returns.columns)
    roi.loc['ROI x', :] = ebitdax.ebitdax_unhedged_total_all_k.sum(axis=0) / -capex.capex_total_all_k.sum(axis=0)

    # append IRR and ROI to the NPV dataframe
    npv_returns = npv_returns.append(irr).append(roi)

    # nan-out the ROI if PV-0 of cash flow is negative
    for col in npv_returns:
        if npv_returns.loc['PV-0', col] <= 0.0:
            npv_returns.loc['ROI x', col] = np.nan

    # instantiate the NPVReturns namedtuple
    npv_returns = NPVReturns(npv_returns=npv_returns)
    print(npv_returns)

    # add namedtuple to model_data
    for item_name, item_df in npv_returns._asdict().items():
        model_data[f'{item_name}'] = item_df
    print(f'\n| chart data >>\n{model_data}\n| model data keys: {[_ for _ in model_data]}')
    return npv_returns


def save_model_outputs(local_only=False):
    global model_data
    global well_drivers
    global save_yn_model

    if 'save_yn_model' not in globals():
        # save_yn_model = input(f'\n| Save model results? Y/N ')
        save_yn_model = 'y'

    if save_yn_model.lower() == 'y':
        # save model data to json and xlsx
        print(f'\n| Saving model results >>>')
        for model_data_key, model_data_df in model_data.items():
            folder = f'{scenario_folder}econs/'
            network_folder = f'{network_scenario_folder}econs/'
            folder_list = [folder, network_folder] if local_only is False else [folder]

            # save to json, local and T:drive
            filename_json = f'{model_data_key}.json'
            filename_xlsx = f'{model_data_key}.xlsx'

            for f in folder_list:
                # save filepath
                if f == folder:
                    if f + filename_xlsx not in scenario_filepaths_all['local']:
                        scenario_filepaths_all['local'].append(f + filename_xlsx)
                else:
                    if f + filename_xlsx not in scenario_filepaths_all['network']:
                        scenario_filepaths_all['network'].append(f + filename_xlsx)
                # fp = f + filename_json
                # # save the dataframe for this field to _scenario folder json
                # try:
                #     save_to_json(model_df,
                #                  folder=f,
                #                  filepath=fp)
                # except (FileNotFoundError, PermissionError, ValueError):
                #     print(f'\n!! {fp} not found or network drive not accessible')
                try:
                    # save to excel
                    save_to_excel(model_data_df,
                                  folder=f,
                                  filename=filename_xlsx)
                except (FileNotFoundError, PermissionError, ValueError, OSError):
                    print(f'\n!! {f + filename_xlsx} not found or network drive not accessible')

        model_control.add_to_model_control(
            object_dict={'scenario_filepaths_all': scenario_filepaths_all},
            deep_copy=True
        )

        # save the model drivers updated with bootstrap / realized prices
        model_drivers.save_model_drivers(_model_level_drivers=model_level_drivers, local_only=False)
    else:
        print(f'!! model data not saved.')
        pass


def calc_production_capex_opex():
    '''Return the index of this well_name in the drilling schedule.'''
    global save_yn_wells
    if 'save_yn_wells' not in globals():
        # save_yn_wells = input('| Save individual well results? Y/N')
        save_yn_wells = 'n'

    # loads total WI and NRI production from the production engine, and adds the namedtuples returned
    # to the roll-up dictionary
    global wi_volumes_total
    global nri_volumes_total
    wi_volumes_total, nri_volumes_total = load_wi_nri_production().values()
    add_to_roll_up_dict(additions=wi_volumes_total, addition_type='wi_prod')
    add_to_roll_up_dict(additions=nri_volumes_total, addition_type='nri_prod')

    # calc capex and add to roll-up dictionary
    global capex_detail
    global capex

    # list of wells to include in capex
    _capex_wells = modeled_wells_all.copy()
    # get the PDP wells also
    if model_control.include_remaining_pdp_capex:
        _capex_wells.extend(model_control.pdp_wells_with_remaining_capex)

    for well in _capex_wells:
        capex_detail = load_capex_detail(_well_name=well)
        print(f'>> Capex for {well}: {capex_detail}')
        capex = calc_capex()
        add_to_roll_up_dict(additions=capex, addition_type='capex')

    # calc opex
    global opex
    opex = calc_opex()
    add_to_roll_up_dict(additions=opex, addition_type='opex')


def update_model_data():
    # add parentco production, capex, opex to the model_data dictionary
    global parentco_wi_prod_by_stream
    global parentco_nri_prod_by_stream
    global parentco_capex
    global parentco_opex

    print(f'\n| Updating model_data with production, capex, opex...')
    for item_name, item_df in parentco_wi_prod_by_stream.items():
        model_data[f'parentco_wi_prod_{item_name}'] = item_df

    for item_name, item_df in parentco_nri_prod_by_stream.items():
        model_data[f'parentco_nri_prod_{item_name}'] = item_df

    for item_name, item_df in parentco_capex.items():
        model_data[f'parentco_{item_name}'] = item_df

    for item_name, item_df in parentco_opex.items():
        model_data[f'parentco_opex_{item_name}'] = item_df


def calc_cash_flow():
    global ebitdax
    global fcf
    global cumulative_fcf
    global npv_returns

    calc_revenue()
    calc_prod_taxes()
    ebitdax, fcf, cumulative_fcf = calc_ebitdax_fcf().values()
    npv_returns = calc_npv_returns(_ebitdax=ebitdax, _fcf=fcf)
    save_model_outputs()
    model_control.notify_complete(caller_name='economics.calc_cash_flow')


def add_to_roll_up_dict(additions: namedtuple, addition_type: str):
    '''Adds namedtuple dataframes to the roll-up dictionary, to be rolled up by the relevant roll-up function.
    Args:
        |-- additions, dict: a dictionary of namedtuples whose dataframe attributes are to be rolled up
        |-- addition_type, str: any of 'wi_prod', 'nri_prod', 'capex', or 'opex'
        '''
    global roll_up_dict
    if 'roll_up_dict' not in globals():
        roll_up_dict = {
            'wi_prod': [],
            'nri_prod': [],
            'capex': [],
            'opex': [],
            'pdp_opex': []
        }

    # add the namedtuple in additions
    roll_up_dict[addition_type].append(additions)

    print(f'\n| Added to {addition_type} roll-up dictionary >>> {len(additions)} items.')


def roll_up_production():
    '''Rolls up WI and NRI production.
    Returns:
        A tuple of two dictionaries --> [parentco_wi_prod_by_stream,parentco_nri_prod_by_stream]
         '''
    global parentco_wi_prod_by_stream
    global parentco_nri_prod_by_stream
    global roll_up_dict

    # _wi_prod_by_stream, well_econs.WIVolume namedtuple: WI production named tuple, with all WI production streams as attributes
    # for each namedtuple in the roll-up dict
    for _wi_prod_by_stream in roll_up_dict['wi_prod']:
        # accumulate the items to the parentco dict
        if 'parentco_wi_prod_by_stream' in globals():
            for k, v in _wi_prod_by_stream._asdict().items():
                print(f'\n| parentco_wi_prod_by_stream found: {k} >>>\n {parentco_wi_prod_by_stream[k]}')
                parentco_wi_prod_by_stream[k] = parentco_wi_prod_by_stream[k] + v.values
                print(f'\n| parentco_wi_prod_by_stream updated: {k} >>>\n {parentco_wi_prod_by_stream[k]}')
        else:
            parentco_wi_prod_by_stream = dict(**_wi_prod_by_stream._asdict())
            print(f'\n| New parentco_wi_prod_by_stream created:\n{parentco_wi_prod_by_stream}')

    # _nri_prod_by_Stream, well_econs.NRIVolume namedtuple: NRI production named tuple, with all NRI production streams as attributes
    # for each namedtuple in the roll-up dict
    for _nri_prod_by_stream in roll_up_dict['nri_prod']:
        # accumulate the items to the parentco dict
        if 'parentco_nri_prod_by_stream' in globals():
            for k, v in _nri_prod_by_stream._asdict().items():
                print(f'\n| parentco_nri_prod_by_stream found: {k} >>>\n {parentco_nri_prod_by_stream[k]}')
                parentco_nri_prod_by_stream[k] = parentco_nri_prod_by_stream[k] + v.values
                print(f'| Existing parentco_nri_prod_by_stream updated: {k} >>>\n {parentco_nri_prod_by_stream[k]}')
        else:
            parentco_nri_prod_by_stream = dict(**_nri_prod_by_stream._asdict())
            print(f'\n| New parentco_nri_prod_by_stream created: \n{parentco_nri_prod_by_stream}')

    return parentco_wi_prod_by_stream, parentco_nri_prod_by_stream


def roll_up_capex():
    '''Rolls up capex by well.
    Returns:
        A dictionary: parentco_capex
         '''
    global parentco_capex
    global roll_up_dict

    # _capex, well_econs.Capex namedtuple: capex named tuple, with all capex categories as attributes
    # for each namedtuple in the roll-up dict
    for _capex in roll_up_dict['capex']:
        # accumulate the items to the parentco dict
        if 'parentco_capex' in globals():
            for k, v in _capex._asdict().items():
                print(f'\n| parentco_capex found:{k} >>>\n {parentco_capex[k]}')
                parentco_capex[k] = parentco_capex[k] + v.values
                print(f'\n| Existing parentco_capex updated:{k} >>>\n {parentco_capex[k]}')
        else:
            parentco_capex = dict(**_capex._asdict())
            print(f'\n| New parentco_capex created:\n{parentco_capex}')

    model_control.add_to_model_control({'parentco_capex': parentco_capex}, deep_copy=False)
    return parentco_capex


def roll_up_opex():
    '''Rolls up opex by well.
    Returns:
        A dictionary: parentco_opex
         '''
    global parentco_opex

    print(f'\n$$$ Rolling up Dev program opex...')
    # dev program opex
    # _opex, well_econs.Opex namedtuple: opex named tuple, with all opex items as attributes
    # for each namedtuple in the roll-up dict
    for _opex in roll_up_dict['opex']:
        # accumulate the items to the parentco dict
        if 'parentco_opex' in globals():
            for k, v in _opex._asdict().items():
                print(f'\n| parentco_opex found:{k} >>>\n {parentco_opex[k]}')
                parentco_opex[k] = parentco_opex[k] + v.values
                print(f'\n| Existing parentco_opex updated:{k} >>>\n {parentco_opex[k]}')
        else:
            parentco_opex = dict(**_opex._asdict())
            print(f'\n| New parentco_opex created:\n{parentco_opex}')

    print(f'\n$$$ Rolling up PDP opex...')
    # PDP opex
    for _opex in roll_up_dict['pdp_opex']:
        # accumulate the items to the parentco dict
        if 'parentco_opex' in globals():
            for k, v in _opex._asdict().items():
                print(f'\n| parentco_opex found:{k} >>>\n {parentco_opex[k]}')
                parentco_opex[k] = parentco_opex[k] + v.values
                print(f'\n| Existing parentco_opex updated:{k} >>>\n {parentco_opex[k]}')
        else:
            parentco_opex = dict(**_opex._asdict())
            print(f'\n| New parentco_opex created:\n{parentco_opex}')

    return parentco_opex


def parentco_roll_up():
    '''Creates the parentco roll-up dictionaries for production, capex, and opex, and adds them to the model_data dictionary for excel output / charts.'''

    global parentco_wi_prod_by_stream
    global parentco_nri_prod_by_stream
    parentco_wi_prod_by_stream, parentco_nri_prod_by_stream = roll_up_production()

    global parentco_capex
    parentco_capex = roll_up_capex()

    global parentco_opex
    parentco_opex = roll_up_opex()

    model_control.notify_complete(caller_name='economics.parentco_roll_up')

########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
