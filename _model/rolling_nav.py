import _model.return_functions as return_functions
import _model.model_control as model_control
import _model.model_drivers as model_drivers
from _model.useful_functions import *

import pandas as pd
from pandas.tseries.offsets import MonthEnd
import pprint

# variables needed
# for each sub-asset modeled:
# --> PDP net production --> from model inputs
# --> realized prices (all scenarios) --> from
# --> PDP opex --> from model inputs
# --> PDP production taxes --> calculate based on asset level drivers
#
# --> calculate the FCF of each development well --> use a generic well starting at 1st of month + POP dates to slide that cash flow wedge out to the appropriate period
# --> algo: for each POP date: get generic sw_fcf --> add it to total FCF from the POP date onwards --> re-calc NPV for that POP month onwards wedge --> next POP date
# --> POP date and price deck aligned to this -->
# --> development wells schedule for each sub-asset (extract from the master drilling schedule)
# infrastructure capex
# calculate the rolling PV-x of current PDP - at all price scenarios
# make a development cash flow wedge from the single well cash flow (net)
# calculate the rolling PV-x of the development wedge - at all price scenarios
# calculate the rolling PV-x of the infrastructure capex - at all price scenarios
# optional: include rolling PV-x of hedges (get the hedge settlement dataframes)


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #---------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

def initialize():
    global local_scenario_folder
    global network_scenario_folder
    local_scenario_folder, network_scenario_folder = model_control.get_scenario_root_folders().values()
    print(local_scenario_folder)

    # NAV months limit of 10 years (to reduce calculation intensity)
    global nav_months_limit
    nav_months_limit = 144

    # get the gross type curves from model drivers
    global tc_oil
    global tc_gas
    global tc_water
    tc_oil, tc_gas, tc_water = model_drivers.get_gross_type_curves().values()
    print(tc_oil, tc_gas, tc_water)

    # drivers for each sub-asset
    global asset_level_drivers
    asset_level_drivers = model_drivers.get_asset_level_drivers()
    # _q = input('pause')

    global modeled_subassets
    modeled_subassets = [_ for _ in asset_level_drivers.index]

    # other inputs
    global other_inputs
    other_inputs = {}

    # model period
    global model_period
    model_period = model_drivers.model_period

    # get pdp, infra capex, and working cap balance input for these subassets
    input_identifiers = ['pdp_input_dict_', 'infra_capex_', 'working_cap_balance_']

    for subasset in modeled_subassets:
        for ip in input_identifiers:
            _input_df = model_drivers.model_level_drivers[ip + subasset]
            _common_dates = [_ for _ in model_period if _ in _input_df.index]
            other_inputs[ip + subasset] = _input_df.loc[_common_dates, :]

    print(other_inputs)

    # calculate PDP cash flow for each subasset:
    # --> split up the total NGL stream into its components
    # --> multiply the net production by the net realized prices dataframe for each commodity

    global currentPDP_inputs
    currentPDP_inputs = {k.replace('pdp_input_dict_', ''): v for k, v in other_inputs.items() if 'pdp' in k}
    print(currentPDP_inputs)

    # production splitter
    global production_splitter
    production_splitter = model_drivers.production_splitter

    # D&C capex drivers
    global dnc_capex_drivers
    dnc_capex_drivers = model_drivers.dnc_capex_drivers

    # master drilling schedule
    global master_drilling_schedule
    master_drilling_schedule = pd.read_excel(local_scenario_folder + '\/drivers\/master_drilling_schedule.xlsx',
                                             parse_dates=True,
                                             sheet_name='Data')
    master_drilling_schedule = master_drilling_schedule.set_index('index', drop=True)

    global master_outputs
    master_outputs = {}

    global include_pdp_gas_marketing
    include_pdp_gas_marketing = model_control.include_pdp_gas_marketing

    # dev program NRI production streams (all wells)
    global newPDP_nri_prod_by_well
    newPDP_nri_prod_by_well = ['oil', 'gas_btu', 'ethane', 'propane', 'iso_butane', 'n_butane', 'nat_gasoline']
    newPDP_nri_prod_by_well = ['nri_prod_' + _ + '_by_well' for _ in newPDP_nri_prod_by_well]
    newPDP_nri_prod_by_well = {
        k: pd.read_excel(local_scenario_folder + f'\/production\/{k}.xlsx',
                         index_col='index',
                         parse_dates=True,
                         sheet_name='Data') for k in newPDP_nri_prod_by_well
    }

    # dev program WI production streams (all wells)
    global newPDP_wi_prod_by_well
    newPDP_wi_prod_by_well = ['oil', 'water']


    newPDP_wi_prod_by_well = ['wi_prod_' + _ + '_by_well' for _ in newPDP_wi_prod_by_well]
    newPDP_wi_prod_by_well = {
        k: pd.read_excel(local_scenario_folder + f'\/production\/{k}.xlsx',
                         index_col='index',
                         parse_dates=True,
                         sheet_name='Data') for k in newPDP_wi_prod_by_well
    }

    # add "ngl" to ngl keys
    global ngl_nicks
    ngl_nicks = get_ngl_nicks()

    newPDP_nri_prod_by_well.update({
        k.replace(ngl_nick, 'ngl_' + ngl_nick): v for k, v in newPDP_nri_prod_by_well.items() for ngl_nick in ngl_nicks if
        ngl_nick in k
    })
    # remove old keys
    newPDP_nri_prod_by_well = {k: v for k, v in newPDP_nri_prod_by_well.items() if any([_ in k for _ in ['oil', 'gas', 'ngl']])}

    print(f'newPDP NRI production streams: {[_ for _ in newPDP_nri_prod_by_well.keys()]}')

    # net realized prices list
    global net_realized_price_list
    net_realized_price_list = ['net_realized_price_oil_midland_mbbl',
                               'net_realized_price_oil_houston_mbbl',
                               'net_realized_price_gas_hsc_bbtu_shrunk',
                               'net_realized_price_gas_waha_bbtu_shrunk',
                               'net_realized_price_ngl_ethane_mbbl',
                               'net_realized_price_ngl_propane_mbbl',
                               'net_realized_price_ngl_iso_butane_mbbl',
                               'net_realized_price_ngl_n_butane_mbbl',
                               'net_realized_price_ngl_nat_gasoline_mbbl']

    # read in from scenario folder (local or network) and make a dict
    global net_realized_prices
    net_realized_prices = {
        k: pd.read_excel(local_scenario_folder + r'\/econs\/' + k + '.xlsx', parse_dates=True, sheet_name='Data') for k
        in net_realized_price_list}

    # set indexes
    net_realized_prices = {k: v.set_index('index', drop=True) for k, v in net_realized_prices.items()}
    # make tz-aware
    for k, v in net_realized_prices.items():
        v.index = v.index.tz_localize(tz='UTC')

    print(f'\n| Net realized prices:\n')
    pprint.pprint(net_realized_prices)

    global currentPDP_discount_rate
    # try:
    #     currentPDP_discount_rate = float(
    #         input(f'\n>>> Enter discount rate for PDP (used for current PDP and converted PUDs) >>> '))
    # except (ValueError, KeyError):
    #     currentPDP_discount_rate = 0.12

    currentPDP_discount_rate = 0.12
    print(f'| Using PDP discount rate of {currentPDP_discount_rate * 100:.2f}%')

    global newPDP_discount_rate
    newPDP_discount_rate = currentPDP_discount_rate

    global dev_program_discount_rate
    # try:
    #     dev_program_discount_rate = float(
    #         input(f'\n>>> Enter discount rate for dev program (remaining PUDs at time t) >>> '))
    # except (ValueError, KeyError):
    #     dev_program_discount_rate = 0.25
    dev_program_discount_rate = 0.25
    print(f'| Using PUD discount rate of {dev_program_discount_rate * 100:.2f}%')

    # dev program total cash flow
    global total_net_cash_flow
    total_net_cash_flow = pd.DataFrame().reindex_like([_ for _ in net_realized_prices.values()][0]).fillna(0)

    # total parentco unhedged EBITDAX
    global ebitdax_unhedged_total_all_k
    ebitdax_unhedged_total_all_k = pd.read_excel(local_scenario_folder + '\/econs\/ebitdax_unhedged_total_all_k.xlsx',
                                             parse_dates=True,
                                             sheet_name='Data')
    ebitdax_unhedged_total_all_k = ebitdax_unhedged_total_all_k.set_index('index', drop=True)
    ebitdax_unhedged_total_all_k = ebitdax_unhedged_total_all_k.reindex_like(total_net_cash_flow)

    # total parentco capex
    # todo: potentially change this to financing_parentco_capex to account for infrastructure etc
    global parentco_capex_total_all_k
    parentco_capex_total_all_k = pd.read_excel(local_scenario_folder + '\/econs\/parentco_capex_total_all_k.xlsx',
                                                 parse_dates=True,
                                                 sheet_name='Data')
    parentco_capex_total_all_k = parentco_capex_total_all_k.set_index('index', drop=True)
    parentco_capex_total_all_k = parentco_capex_total_all_k.reindex_like(total_net_cash_flow)

    # update dev program net cash flow
    # this is currently the *total* net cash flow (PDP + development), excluding financing and hedges.
    # This should be differenced with current PDP and each new PDP's cash flow
    total_net_cash_flow.add(ebitdax_unhedged_total_all_k).add(parentco_capex_total_all_k)
    print(f'\n| Total Net Cash Flow:\n{total_net_cash_flow}')

    master_outputs.update({f'total_net_cash_flow': total_net_cash_flow})

    # # create a blank dataframe for the remaining PV of the dev program
    # global rolling_nav_TOTAL_dev
    # rolling_nav_TOTAL_dev = pd.DataFrame().reindex_like(total_net_cash_flow).fillna(0)


def calc_currentPDP_rolling_nav(subasset):
    global total_net_cash_flow
    global rolling_nav_TOTAL_dev

    prod_prefix = f'currentPDP_nri_prod_{subasset}_'
    currentPDP_production = {
        prod_prefix + 'oil_midland_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - Oil (MBbl)'] *
                                          production_splitter['oil_midland_pct'],
        prod_prefix + 'oil_houston_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - Oil (MBbl)'] *
                                          production_splitter['oil_houston_pct'],
        prod_prefix + 'gas_hsc_bbtu_shrunk': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - Residue Gas - All (MMcf)'] *
                                             production_splitter['gas_hsc_pct'] * gas_btu_factor_residue,
        prod_prefix + 'gas_waha_bbtu_shrunk': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - Residue Gas - All (MMcf)'] *
                                              production_splitter['gas_waha_pct'] * gas_btu_factor_residue,
        prod_prefix + 'ngl_ethane_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - NGL - All Streams (MBbl)'] *
                                         production_splitter['ngl_ethane_pct'] * ngl_pct_of_barrel['ethane'],
        prod_prefix + 'ngl_propane_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - NGL - All Streams (MBbl)'] *
                                          production_splitter['ngl_propane_pct'] * ngl_pct_of_barrel['propane'],
        prod_prefix + 'ngl_iso_butane_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - NGL - All Streams (MBbl)'] *
                                             production_splitter['ngl_iso_butane_pct'] * ngl_pct_of_barrel[
                                                 'iso_butane'],
        prod_prefix + 'ngl_n_butane_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - NGL - All Streams (MBbl)'] *
                                           production_splitter['ngl_n_butane_pct'] * ngl_pct_of_barrel['n_butane'],
        prod_prefix + 'ngl_nat_gasoline_mbbl': currentPDP_inputs[subasset].loc[:, 'PDP NRI Prod - NGL - All Streams (MBbl)'] *
                                               production_splitter['ngl_nat_gasoline_pct'] * ngl_pct_of_barrel[
                                                   'nat_gasoline'],
    }

    # fill NAs
    currentPDP_production = {k: v.fillna(0) for k, v in currentPDP_production.items()}

    # zero out periods before asset active month
    for k, v in currentPDP_production.items():
        # print(v)
        v.loc[:prior_month] = 0.0
        # print(v)
        # _q = input('Hit enter to continue')
        currentPDP_production[k] = v

    # price to production mapper
    price_to_production_mapper = dict(zip(net_realized_price_list, currentPDP_production.keys()))


    print(f'\n| PDP net production:\n')
    pprint.pprint(currentPDP_production)

    # add to master outputs
    master_outputs.update(currentPDP_production)

    # ---- PDP REVENUE ----
    currentPDP_revenue = {}
    currentPDP_revenue_prefix = f'revenue_{subasset}_currentPDP_'

    for realized_price, production_stream in price_to_production_mapper.items():
        # make a dataframe for PDP revenue
        revenue = pd.DataFrame().reindex_like(net_realized_prices[realized_price]).fillna(0)

        # calc revenue
        for col in revenue:
            revenue[col] = net_realized_prices[realized_price].loc[:, col] * currentPDP_production[
                production_stream] * [42.0 if 'ngl' in production_stream else 1.0][0]

        _label = production_stream.replace('mbbl', 'k').replace('bbtu_shrunk', 'k').replace(prod_prefix, '')
        currentPDP_revenue[currentPDP_revenue_prefix + _label] = revenue

    print(f'\n| PDP gross revenue:\n')
    pprint.pprint(currentPDP_revenue)

    # PDP oil, gas, NGL revenue totals
    currentPDP_revenue_oil = {k: v for k, v in currentPDP_revenue.items() if 'oil' in k}
    currentPDP_revenue_gas = {k: v for k, v in currentPDP_revenue.items() if 'gas' in k}
    currentPDP_revenue_ngl = {k: v for k, v in currentPDP_revenue.items() if 'ngl' in k}

    # sum up the values and save to 'all' keys by commodity
    currentPDP_revenue[currentPDP_revenue_prefix + 'oil_all_k'] = sum(currentPDP_revenue_oil.values())
    currentPDP_revenue[currentPDP_revenue_prefix + 'gas_all_k'] = sum(currentPDP_revenue_gas.values())
    currentPDP_revenue[currentPDP_revenue_prefix + 'ngl_all_k'] = sum(currentPDP_revenue_ngl.values())

    # sum up the 'all's and add to a new 'total' key in currentPDP_revenue
    currentPDP_revenue[currentPDP_revenue_prefix + 'total_all_k'] = currentPDP_revenue[currentPDP_revenue_prefix + 'oil_all_k'] + \
                                                      currentPDP_revenue[currentPDP_revenue_prefix + 'gas_all_k'] + \
                                                      currentPDP_revenue[currentPDP_revenue_prefix + 'ngl_all_k']
    # add to master outputs
    # master_outputs.update(currentPDP_revenue)

    # PDP sev and ad val taxes
    sev_tax_rate_oil = float(asset_level_drivers.loc[subasset, 'Severance Taxes - Oil'])
    sev_tax_rate_gas = float(asset_level_drivers.loc[subasset, 'Severance Taxes - Gas'])
    sev_tax_rate_ngl = float(asset_level_drivers.loc[subasset, 'Severance Taxes - NGL'])
    ad_val_tax_rate = float(asset_level_drivers.loc[subasset, 'Ad Valorem Taxes'])

    sev_taxes_oil = currentPDP_revenue[currentPDP_revenue_prefix + 'oil_all_k'] * sev_tax_rate_oil
    sev_taxes_gas = currentPDP_revenue[currentPDP_revenue_prefix + 'gas_all_k'] * sev_tax_rate_gas
    sev_taxes_ngl = currentPDP_revenue[currentPDP_revenue_prefix + 'ngl_all_k'] * sev_tax_rate_ngl

    total_sev_taxes = sum([sev_taxes_oil, sev_taxes_gas, sev_taxes_ngl])

    # net severance taxes
    currentPDP_revenue_net_taxes = currentPDP_revenue[currentPDP_revenue_prefix + 'total_all_k'] - total_sev_taxes

    # net ad val taxes
    currentPDP_revenue_net_taxes = currentPDP_revenue_net_taxes * (1 - ad_val_tax_rate)

    # add to master outputs
    # master_outputs.update({f'{currentPDP_revenue_prefix}_total_net_taxes_k': currentPDP_revenue_net_taxes})

    # PDP LOE for subasset
    currentPDP_loe_all = pd.Series(currentPDP_inputs[subasset].loc[asset_active_month:, 'PDP Opex ($k)'],
                            index=model_period).ffill().fillna(0)
    # master_outputs.update({'currentPDP_loe_all_k': currentPDP_loe_all})
    print(f'\n| PDP operating expenses:\n{currentPDP_loe_all}')

    # PDP midstream (if model_control says True)
    # since the midstream fees are netted out as part of the diff, these need to be netted out of the PDP cash flow
    # calculate gas marketing fees for subasset
    if include_pdp_gas_marketing[subasset] is True:
        # get the asset drivers
        gas_all_mmcf_preshrink = currentPDP_production[prod_prefix + 'gas_hsc_bbtu_shrunk'] + \
                                 currentPDP_production[prod_prefix + 'gas_waha_bbtu_shrunk']

        gas_all_mmcf_preshrink = gas_all_mmcf_preshrink / (1 - gas_shrink) / gas_btu_factor_residue
        gas_all_bbtu_preshrink = gas_all_mmcf_preshrink * gas_btu_factor_wellhead

        currentPDP_marketing_nitrogen = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_nitrogen_k'][0]
        currentPDP_marketing_electricity = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_electricity_k'][0]
        currentPDP_marketing_gathering = gas_all_bbtu_preshrink * opex_unit_cost_mapper['marketing_gathering_k'][0]
        currentPDP_marketing_processing = gas_all_bbtu_preshrink * opex_unit_cost_mapper['marketing_processing_k'][0]
        currentPDP_marketing_sold_gas_compr = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_sold_gas_compr_k'][0]

        currentPDP_marketing_all = currentPDP_marketing_nitrogen + \
                            currentPDP_marketing_electricity + \
                            currentPDP_marketing_gathering + \
                            currentPDP_marketing_processing + \
                            currentPDP_marketing_sold_gas_compr
    else:
        currentPDP_marketing_all = pd.Series().reindex_like([_ for _ in currentPDP_production.values()][0]).fillna(0)

    print(f'\n| PDP gas marketing fees:\n{currentPDP_marketing_all}')
    # master_outputs.update({'currentPDP_marketing_all': currentPDP_marketing_all})

    # net PDP cash flow
    currentPDP_net_cash_flow = currentPDP_revenue_net_taxes.copy(deep=True).fillna(0)

    for col in currentPDP_net_cash_flow:
        currentPDP_net_cash_flow[col] -= currentPDP_loe_all
        currentPDP_net_cash_flow[col] -= currentPDP_marketing_all

    print(f'\n| Net PDP Cash Flow >> {subasset}:\n{currentPDP_net_cash_flow}')
    master_outputs.update({f'currentPDP_net_cash_flow_{subasset}': currentPDP_net_cash_flow})


    # rolling PV-x
    currentPDP_rolling_pv = currentPDP_net_cash_flow.copy(deep=True)


    # roll through the dataframe
    for price_scenario in currentPDP_rolling_pv:
        for date in currentPDP_rolling_pv.index[:nav_months_limit]:
            #  calculate NPV for asset active month onwards
            if date >= asset_active_month:
                # calc rolling PV for current PDP
                values = currentPDP_rolling_pv.loc[date:, price_scenario].values
                dates = currentPDP_rolling_pv.loc[date:, price_scenario].index.values
                npv = return_functions.xnpv(rate=currentPDP_discount_rate, values=values, dates=dates)
                currentPDP_rolling_pv.at[date, price_scenario] = npv

                # todo: calc rolling PV for remaining dev program cash flows
                # subtract the current PDP cash flow wedge from this date onwards
                # total_net_cash_flow.loc[date:, price_scenario] -= currentPDP_net_cash_flow.loc[date:, price_scenario]
                #
                # values = total_net_cash_flow.loc[date:, price_scenario].values
                # dates = total_net_cash_flow.loc[date:, price_scenario].index.values
                # npv = return_functions.xnpv(rate=dev_program_discount_rate, values=values, dates=dates)
                # rolling_nav_TOTAL_dev.at[date, price_scenario] = npv

    currentPDP_rolling_pv.iloc[nav_months_limit:, :] = 0

    print(
        f'\n| Rolling PDP PV-{currentPDP_discount_rate * 100:.1f} >> {subasset}: {price_scenario}\n{currentPDP_rolling_pv.head(36)}')
    # _q = input('\nHit enter to continue')

    # update master outputs
    master_outputs.update({f'currentPDP_rolling_pv_{subasset}': currentPDP_rolling_pv})
    # master_outputs.update({f'rolling_nav_TOTAL_dev': rolling_nav_TOTAL_dev,
    #                        'total_net_cash_flow': total_net_cash_flow})


def calc_newPDP_rolling_nav(subasset):
    # Dev program / Single well PV-x
    # filter down the master drilling schedule to only this subasset
    global master_drilling_schedule
    global total_net_cash_flow
    global dev_program_discount_rate

    # get well activity dates
    subasset_activity_dates = master_drilling_schedule.loc[
                              [_ for _ in master_drilling_schedule.index if subasset.upper() in _.upper()],
                              :]
    print(f'\n| Activity dates for {subasset}: {subasset_activity_dates}')

    # trim for pop dates greater than nav_months_limit (performance)
    pop_dates = [pd.to_datetime(_, utc=True) for _ in subasset_activity_dates.loc[:, 'pop'].values]
    limit_date = model_period[0]+MonthEnd(nav_months_limit)
    pop_dates = [_ for _ in pop_dates if _ <= limit_date]
    print(pop_dates)
    # _q = input('enter to continue')
    # subasset_activity_dates = subasset_activity_dates.loc[:len(pop_dates), :]
    subasset_activity_dates = subasset_activity_dates.loc[
                              [True for _ in subasset_activity_dates['pop'] if pd.to_datetime(_, utc=True) > model_period[0] + MonthEnd(-1)],
                              :]

    print(subasset_activity_dates)
    # _q = input('enter to continue')

    # get capex payment dates
    pay_delay_cols = ["Pay Delay - Permit + Landowner (days)",
                      "Pay Delay - Build / Extend Pad (days)",
                      "Pay Delay - Cellar / Mousehole (days)",
                      "Pay Delay - Well Spud + Drilling (days)",
                      "Pay Delay - Rig Low / Prep Loc (days)",
                      "Pay Delay - Frac Well (days)",
                      "Pay Delay - Drillout + Tube up (days)",
                      "Pay Delay - Flowback (days)",
                      "Pay Delay - Facilities (days)"]

    capex_amount_cols = ["Capex - Permit + Landowner ($k)",
                         "Capex - Build / Extend Pad ($k)",
                         "Capex - Cellar / Mousehole ($k)",
                         "Capex - Well Spud + Drilling ($k)",
                         "Capex - Rig Low / Prep Loc ($k)",
                         "Capex - Frac Well ($k)",
                         "Capex - Drillout + Tube up ($k)",
                         "Capex - Flowback ($k)",
                         "Capex - Facilities ($k)"]

    capex_to_pay_delay_mapper = dict(zip(capex_amount_cols, pay_delay_cols))

    capex_to_activity_mapper = {
        "Capex - Permit + Landowner ($k)": 'permitted',
        "Capex - Build / Extend Pad ($k)": 'location_build',
        "Capex - Cellar / Mousehole ($k)": 'location_build',
        "Capex - Well Spud + Drilling ($k)": 'td',
        "Capex - Rig Low / Prep Loc ($k)": 'rig_release',
        "Capex - Frac Well ($k)": 'frac_end',
        "Capex - Drillout + Tube up ($k)": 'drill_out_start',
        "Capex - Flowback ($k)": 'compl_end',
        "Capex - Facilities ($k)": 'frac_end'
    }

    # data frame for total rolling newPDP pv-x at the subasset level
    newPDP_rolling_pv_for_subasset = pd.DataFrame().reindex_like([_ for _ in net_realized_prices.values()][0]).fillna(0)

    # ----- SINGLE WELL CAPEX ----
    # get capex scenario for each well
    for well in subasset_activity_dates.index:
        newPDP_capex_for_well = pd.Series(index=model_period, dtype='float64').fillna(0)
        # well = subasset_activity_dates.index[0]
        # if well is in D&C capex drivers, use it, else use generic
        if well in dnc_capex_drivers['CAPEX SCENARIO']:
            capex_scenario = well
        else:
            capex_scenario = asset_level_drivers.at[subasset, 'CAPEX SCENARIO']

        capex_drivers_for_well = dnc_capex_drivers[dnc_capex_drivers['CAPEX SCENARIO'] == capex_scenario].set_index(
            'CAPEX SCENARIO', drop=True)

        # calculate capex payment dates based on well activity dates
        # get the capex amounts for this well
        capex_amounts = capex_drivers_for_well.loc[:, [_ for _ in capex_to_activity_mapper.keys()]]

        pay_delays = capex_drivers_for_well.loc[:, [_ for _ in capex_to_pay_delay_mapper.values()]]
        pay_dates = {}

        # calulate pay dates
        for activity_name in subasset_activity_dates.columns:
            try:
                activity_date = pd.to_datetime(subasset_activity_dates.at[well, activity_name], utc=True)
                try:
                    capex_category = [k for k, v in capex_to_activity_mapper.items() if v == activity_name][0]
                    pay_delay_category = capex_to_pay_delay_mapper[capex_category]
                    pay_delay = pd.to_timedelta(pay_delays.at[capex_scenario, pay_delay_category], unit='d')
                    pay_dates[activity_name] = activity_date + pay_delay + MonthEnd(1)
                except IndexError:
                    raise
            except (IndexError, KeyError):
                print(f'{activity_name} not found.')

        print(well, pay_dates)
        print(capex_amounts)

        #  add capex to dev program capex for this well
        for capex_category, activity_name in capex_to_activity_mapper.items():
            pay_date = pay_dates[activity_name]
            try:
                newPDP_capex_for_well.at[pay_date] += capex_amounts.at[capex_scenario, capex_category]
            except KeyError:
                print(f'{string_date(pay_date)} ({well}/{activity_name}) is not in model period.')

        print(newPDP_capex_for_well.head(36))

        # calculate cash flow for this well
        # ------- SW PRODUCTION ------------
        # get NRI prod for this well
        nri_prod_for_well = {k.replace('_by_well', ''): pd.Series(v.loc[:, well].values, index=model_period) for k, v in
                             newPDP_nri_prod_by_well.items()}

        # split oil into midland and houston
        nri_prod_oil_total = [v for k, v in nri_prod_for_well.items() if 'oil' in k][0]
        nri_prod_oil_midland = nri_prod_oil_total * production_splitter['oil_midland_pct']
        nri_prod_oil_houston = nri_prod_oil_total * production_splitter['oil_houston_pct']
        nri_prod_for_well.update({'nri_prod_oil_midland': nri_prod_oil_midland,
                                  'nri_prod_oil_houston': nri_prod_oil_houston})

        # split gas into HSC and waha using production splitter
        nri_prod_gas_btu_total = [v for k, v in nri_prod_for_well.items() if 'gas_btu' in k][0]
        nri_prod_gas_btu_hsc = nri_prod_gas_btu_total * production_splitter['gas_hsc_pct']
        nri_prod_gas_btu_waha = nri_prod_gas_btu_total * production_splitter['gas_waha_pct']
        nri_prod_for_well.update({'nri_prod_gas_btu_hsc': nri_prod_gas_btu_hsc,
                                  'nri_prod_gas_btu_waha': nri_prod_gas_btu_waha})

        pprint.pprint({k: v.sum() for k, v in nri_prod_for_well.items()})
        newPDP_production = dict(nri_prod_for_well)

        # master_outputs.update({f'newPDP_production_{well}': newPDP_production})

        # make the price to dev production mapper
        price_to_production_mapper = {}
        for realized_price in net_realized_price_list:
            price_keys = realized_price.replace('net_realized_price_', '').replace(
                '_bbtu_shrunk', '').replace('_mbbl', '').split("_", maxsplit=1)
            prod_stream = [_ for _ in nri_prod_for_well.keys() if all([p in _ for p in price_keys])][0]
            price_to_production_mapper[realized_price] = prod_stream
        print(price_to_production_mapper)

        # ----------- newPDP REVENUE -----------
        newPDP_revenue = {}
        wellname_clean = well.replace("//","_").replace(" ","_")
        newPDP_revenue_prefix = f'revenue_{wellname_clean}_newPDP_'
        prod_prefix = f'nri_prod_'

        for realized_price, production_stream in price_to_production_mapper.items():
            # make a dataframe for PDP revenue
            revenue = pd.DataFrame().reindex_like(net_realized_prices[realized_price]).fillna(0)

            # calc revenue
            for col in revenue:
                revenue[col] = net_realized_prices[realized_price].loc[:, col] * newPDP_production[
                    production_stream] * [42.0 if 'ngl' in production_stream else 1.0][0]

            _label = production_stream.replace('btu_', '').replace(prod_prefix, '') + '_k'
            newPDP_revenue[newPDP_revenue_prefix + _label] = revenue
        print(f'\n| newPDP gross revenue:\n')
        pprint.pprint(newPDP_revenue)
        print({k: v.sum(axis=0) for k, v in newPDP_revenue.items()})
        # master_outputs.update(newPDP_revenue)

        # SW CASH FLOW

        # newPDP oil, gas, NGL revenue totals
        newPDP_revenue_oil = {k: v for k, v in newPDP_revenue.items() if 'oil' in k}
        newPDP_revenue_gas = {k: v for k, v in newPDP_revenue.items() if 'gas' in k}
        newPDP_revenue_ngl = {k: v for k, v in newPDP_revenue.items() if 'ngl' in k}

        # sum up the values and save to 'all' keys by commodity
        newPDP_revenue[newPDP_revenue_prefix + 'oil_all_k'] = sum(newPDP_revenue_oil.values())
        newPDP_revenue[newPDP_revenue_prefix + 'gas_all_k'] = sum(newPDP_revenue_gas.values())
        newPDP_revenue[newPDP_revenue_prefix + 'ngl_all_k'] = sum(newPDP_revenue_ngl.values())

        # sum up the 'all's and add to a new 'total' key in newPDP_revenue
        newPDP_revenue[newPDP_revenue_prefix + 'total_all_k'] = newPDP_revenue[newPDP_revenue_prefix + 'oil_all_k'] + \
                                                          newPDP_revenue[newPDP_revenue_prefix + 'gas_all_k'] + \
                                                          newPDP_revenue[newPDP_revenue_prefix + 'ngl_all_k']
        # add to master outputs
        # master_outputs.update(newPDP_revenue)

        # newPDP sev and ad val taxes
        sev_tax_rate_oil = float(asset_level_drivers.loc[subasset, 'Severance Taxes - Oil'])
        sev_tax_rate_gas = float(asset_level_drivers.loc[subasset, 'Severance Taxes - Gas'])
        sev_tax_rate_ngl = float(asset_level_drivers.loc[subasset, 'Severance Taxes - NGL'])
        ad_val_tax_rate = float(asset_level_drivers.loc[subasset, 'Ad Valorem Taxes'])

        sev_taxes_oil = newPDP_revenue[newPDP_revenue_prefix + 'oil_all_k'] * sev_tax_rate_oil
        sev_taxes_gas = newPDP_revenue[newPDP_revenue_prefix + 'gas_all_k'] * sev_tax_rate_gas
        sev_taxes_ngl = newPDP_revenue[newPDP_revenue_prefix + 'ngl_all_k'] * sev_tax_rate_ngl

        total_sev_taxes = sum([sev_taxes_oil, sev_taxes_gas, sev_taxes_ngl])

        # net severance taxes
        newPDP_revenue_net_taxes_for_well = newPDP_revenue[newPDP_revenue_prefix + 'total_all_k'] - total_sev_taxes

        # net ad val taxes
        newPDP_revenue_net_taxes_for_well = newPDP_revenue_net_taxes_for_well * (1 - ad_val_tax_rate)

        # add to master outputs
        # master_outputs.update({f'{newPDP_revenue_prefix}_total_net_taxes_k': newPDP_revenue_net_taxes})

        # newPDP LOE for well
        newPDP_wi_prod_oil = pd.Series(newPDP_wi_prod_by_well['wi_prod_oil_by_well'].loc[:, well].values, index=model_period,
                                    dtype='float64')
        newPDP_wi_prod_water = pd.Series(newPDP_wi_prod_by_well['wi_prod_water_by_well'].loc[:, well].values, index=model_period,
                                      dtype='float64')

        # variable LOE - oil
        var_loe_per_bbl_oil = float(asset_level_drivers.at[subasset, 'Variable Opex - Oil ($/Bbl)'])
        newPDP_var_loe_oil = newPDP_wi_prod_oil * var_loe_per_bbl_oil

        # variable LOE - water
        var_loe_per_bbl_water = float(asset_level_drivers.at[subasset, 'Variable Opex - Water ($/Bbl)'])
        newPDP_var_loe_water = newPDP_wi_prod_water * var_loe_per_bbl_water

        # fixed LOE ($/w/mo if avail, elif 0, AGL opex curve)
        newPDP_fixed_loe = pd.Series(index=model_period, dtype='float64').fillna(0)
        _fixed_loe_input = float(asset_level_drivers.at[subasset, 'Fixed Opex - Dev Program ($/W/Mo)']) / 1000
        pop_month = pd.to_datetime(subasset_activity_dates.loc[well, 'pop'], utc=True)+MonthEnd(1)
        if _fixed_loe_input != 0.0:
            newPDP_fixed_loe.loc[pop_month:] = _fixed_loe_input
        else:
            # get AGL opex curve
            shift_to = {v: k for k, v in dict(enumerate(newPDP_fixed_loe.index)).items()}
            agl_opex = currentPDP_inputs[subasset].loc[:, 'agl_opex_per_well_k'].values.squeeze()
            _filler = np.zeros(shift_to[pop_month], dtype='float64')
            agl_opex = np.concatenate((_filler, agl_opex), axis=None)

            agl_opex = pd.Series(agl_opex[:len(model_period)], index=model_period, dtype='float64').fillna(0)
            newPDP_fixed_loe.loc[:] += agl_opex
            print(newPDP_fixed_loe)
            # _q = input('fff')

        newPDP_fixed_loe.fillna(0, inplace=True)
        newPDP_loe_all = newPDP_var_loe_oil.add(newPDP_var_loe_water).add(newPDP_fixed_loe)
        newPDP_loe_all.fillna(0, inplace=True)

        # master_outputs.update({'newPDP_loe_all_k': newPDP_loe_all})
        print(f'\n| newPDP operating expenses:\n{newPDP_loe_all.head(36)}')

        # newPDP midstream (if model_control says True)
        # since the midstream fees are netted out as part of the diff, these need to be netted out of the newPDP cash flow
        # calculate gas marketing fees for well

        # get the asset drivers
        gas_all_mmcf_preshrink = newPDP_production[prod_prefix + 'gas_btu_hsc'] + \
                                 newPDP_production[prod_prefix + 'gas_btu_waha']

        gas_all_mmcf_preshrink = gas_all_mmcf_preshrink / (1 - gas_shrink) / gas_btu_factor_residue
        gas_all_bbtu_preshrink = gas_all_mmcf_preshrink * gas_btu_factor_wellhead

        newPDP_marketing_nitrogen = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_nitrogen_k'][0]
        newPDP_marketing_electricity = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_electricity_k'][0]
        newPDP_marketing_gathering = gas_all_bbtu_preshrink * opex_unit_cost_mapper['marketing_gathering_k'][0]
        newPDP_marketing_processing = gas_all_bbtu_preshrink * opex_unit_cost_mapper['marketing_processing_k'][0]
        newPDP_marketing_sold_gas_compr = gas_all_mmcf_preshrink * opex_unit_cost_mapper['marketing_sold_gas_compr_k'][0]

        newPDP_marketing_all = newPDP_marketing_nitrogen + \
                            newPDP_marketing_electricity + \
                            newPDP_marketing_gathering + \
                            newPDP_marketing_processing + \
                            newPDP_marketing_sold_gas_compr

        print(f'\n| newPDP gas marketing fees:\n{newPDP_marketing_all.head(36)}')
        # master_outputs.update({'newPDP_marketing_all': newPDP_marketing_all})

        # # net newPDP cash flow at the well level
        newPDP_net_cash_flow = newPDP_revenue_net_taxes_for_well.copy(deep=True).fillna(0)
        newPDP_ebitdax = newPDP_revenue_net_taxes_for_well.copy(deep=True).fillna(0)

        for col in newPDP_net_cash_flow:
            newPDP_ebitdax[col] -= newPDP_loe_all
            newPDP_ebitdax[col] -= newPDP_marketing_all

            newPDP_net_cash_flow[col] += newPDP_ebitdax[col]
            newPDP_net_cash_flow[col] -= newPDP_capex_for_well

        print(f'\n| Net newPDP Cash Flow >> {well}:\n{newPDP_net_cash_flow}')
        # master_outputs.update({f'newPDP_ebitdax_{wellname_clean}': newPDP_ebitdax})
        # master_outputs.update({f'newPDP_capex_for_well_{wellname_clean}': newPDP_capex_for_well})
        # master_outputs.update({f'newPDP_net_cash_flow_{wellname_clean}': newPDP_net_cash_flow})

        # rolling PV-x at the well level
        newPDP_rolling_pv_for_well = newPDP_net_cash_flow.copy(deep=True)
        # zero out cash flow before POP month
        newPDP_rolling_pv_for_well.at[:string_date(pop_month+MonthEnd(-1)), :] = 0.0

        # zero out dataframe if all negative (= well is in PDP)
        if all([_<= 0 for _ in newPDP_rolling_pv_for_well.loc[:,:].values.ravel()]):
            newPDP_rolling_pv_for_well.at[:, :] = 0.0

        # roll through the dataframe
        # first_pay_date_in_model_period = min([_ for _ in pay_dates.values() if _ in model_period])
        # print(f'| First pay date in model period for {well} >> {first_pay_date_in_model_period}')
        print(f'| POP month for {well} >> {pop_month}')
        for price_scenario in newPDP_rolling_pv_for_well:
            for date in newPDP_rolling_pv_for_well.index[:nav_months_limit]:
                #  calculate NPV for asset active month onwards
                if date >= pop_month:
                    # calc rolling pv for new PDP
                    values = newPDP_rolling_pv_for_well.loc[date:, price_scenario].values
                    dates = newPDP_rolling_pv_for_well.loc[date:, price_scenario].index.values
                    npv = return_functions.xnpv(rate=newPDP_discount_rate, values=values, dates=dates)
                    newPDP_rolling_pv_for_well.at[date, price_scenario] = npv

                    # todo: calc rolling PV for remaining dev program cash flows
                    # subtract this new PDP cash flow wedge from this date onwards
                    # total_net_cash_flow.loc[date:, price_scenario] -= newPDP_net_cash_flow.loc[date:, price_scenario]
                    #
                    # values = total_net_cash_flow.loc[date:, price_scenario].values
                    # dates = total_net_cash_flow.loc[date:, price_scenario].index.values
                    # npv = return_functions.xnpv(rate=dev_program_discount_rate, values=values, dates=dates)
                    # rolling_nav_TOTAL_dev.at[date, price_scenario] = npv


        print(
            f'\n| Rolling newPDP PV-{newPDP_discount_rate * 100:.1f} >> {subasset} >> {wellname_clean}:\n{newPDP_rolling_pv_for_well.head(36)}'
        )
        # _q = input('\nHit enter to continue')

        # zero out cash flows after the NAv month limit
        newPDP_rolling_pv_for_well.iloc[nav_months_limit:, :] = 0

        # add to the subasset level rolling PV
        newPDP_rolling_pv_for_subasset += newPDP_rolling_pv_for_well
        master_outputs.update({f'newPDP_rolling_pv_{subasset}_{wellname_clean}': newPDP_rolling_pv_for_well})

    # add to master outputs
    master_outputs.update({f'newPDP_rolling_pv_{subasset}_total': newPDP_rolling_pv_for_subasset})
    # master_outputs.update({f'total_net_cash_flow': total_net_cash_flow,
    #                        f'rolling_nav_TOTAL_dev': rolling_nav_TOTAL_dev})


def calc_rolling_pv(for_currentPDP:bool, for_newPDP:bool):

    for subasset in modeled_subassets:
        # subasset = modeled_subassets[0]
        global asset_active_month
        asset_active_month = pd.to_datetime(asset_level_drivers.loc[subasset, 'Asset Active Date'],
                                            utc=True) + MonthEnd(1)
        global prior_month
        prior_month = asset_active_month + MonthEnd(-1)

        global gas_btu_factor_residue
        gas_btu_factor_residue = float(asset_level_drivers.loc[subasset, 'Residue Gas BTU Adj (MMBTU per Mcf)'])

        global gas_shrink
        gas_shrink = float(asset_level_drivers.loc[subasset, 'Gas Shrink'])

        global gas_btu_factor_wellhead
        gas_btu_factor_wellhead = float(asset_level_drivers.loc[subasset, 'Wellhead Gas BTU Adj (MMBTU per Mcf)'])

        global ngl_nicks
        ngl_nicks = model_drivers.get_ngl_nicks()

        global ngl_yields
        ngl_yields = dict(zip(
            ngl_nicks,
            [float(_) for _ in asset_level_drivers.loc[
                               subasset,
                               'NGL Yield - Actual - Ethane (Bbl / Mcf)': 'NGL Yield - Actual - Nat. Gasoline (Bbl / Mcf)'].values
             ]
        )
        )

        global ngl_pct_of_barrel
        ngl_pct_of_barrel = {k: v / sum(ngl_yields.values()) for k, v in ngl_yields.items()}

        pprint.pprint(ngl_yields)
        pprint.pprint(ngl_pct_of_barrel)

        global opex_unit_cost_mapper
        opex_unit_cost_mapper = {
            'loe_oil_variable_k': [
                float(asset_level_drivers.loc[subasset, 'Variable Opex - Oil ($/Bbl)']),
                '$/Bbl'],
            'loe_water_variable_k': [
                float(asset_level_drivers.loc[subasset, 'Variable Opex - Water ($/Bbl)']),
                '$/Bbl'],
            'loe_fixed_k': [
                float(asset_level_drivers.loc[subasset, 'Fixed Opex - Dev Program ($/W/Mo)']) / 1000,
                '$/well/month'
            ],
            'loe_reinj_gas_compr_k': [
                1.0 if float(
                    asset_level_drivers.loc[subasset, 'Fixed Opex - Dev Program ($/W/Mo)']) / 1000 == 0 else 0.0,
                '$k/well/month'
            ],  # we use an AGL fixed opex curve per well for this
            'marketing_nitrogen_k': [
                float(asset_level_drivers.loc[subasset, 'Nitrogen Fee $/mcf']),
                '$/Mcf (NRI, pre-shrink)'],
            'marketing_electricity_k': [
                float(asset_level_drivers.loc[subasset, 'Electricity Fee $/mcf']),
                '$/Mcf (NRI, pre-shrink)'],
            'marketing_gathering_k': [
                float(asset_level_drivers.loc[subasset, 'Gathering Fee $/mmbtu']),
                '$/MMBtu (NRI, pre-shrink)'],
            'marketing_processing_k': [
                float(asset_level_drivers.loc[subasset, 'Processing Fee $/mmbtu']),
                '$/MMBtu (NRI, pre-shrink)'],
            'marketing_sold_gas_compr_k': [
                float(asset_level_drivers.loc[subasset, 'Sold Gas Compr Fee $/mcf']),
                '$/Mcf (NRI, pre-shrink)'],
        }


        calc_currentPDP_rolling_nav(subasset=subasset) if for_currentPDP else print(f'\n!! PDP rolling PV-{currentPDP_discount_rate:.1f} will not be run')

        calc_newPDP_rolling_nav(subasset=subasset) if for_newPDP else print(f'\n!! newPDP rolling PV-{newPDP_discount_rate:.1f} will not be run')


def grand_total_rolling_pv():
    global master_outputs
    currentPDP_total = pd.DataFrame().reindex_like([_ for _ in net_realized_prices.values()][0]).fillna(0)
    newPDP_total = pd.DataFrame().reindex_like([_ for _ in net_realized_prices.values()][0]).fillna(0)

    for subasset in modeled_subassets:
        currentPDP_total = currentPDP_total.add(master_outputs[f'currentPDP_rolling_pv_{subasset}'])
        newPDP_total = newPDP_total.add(master_outputs[f'newPDP_rolling_pv_{subasset}_total'])

    master_outputs[f'rolling_nav_TOTAL_currentPDP'] = currentPDP_total
    master_outputs[f'rolling_nav_TOTAL_newPDP'] = newPDP_total
    master_outputs[f'rolling_nav_TOTAL_allPDP'] = currentPDP_total+newPDP_total


def save_master_outputs():
    global master_outputs
    pprint.pprint(master_outputs)
    for key, df in master_outputs.items():
        save_to_excel(output_dataframe=df, folder=network_scenario_folder + '\/rolling-nav\/', filename=key + ".xlsx")
        save_to_excel(output_dataframe=df, folder=local_scenario_folder + '\/rolling-nav\/', filename=key + ".xlsx")


def run_rolling_nav():
    print('\n| Rolling NAV module')
    # _q = input('\n>>> Run rolling NAV module? (Y/N)')
    _q = 'y'
    if _q.lower() != 'n':
        initialize()
        calc_rolling_pv(for_currentPDP=True, for_newPDP=True)
        grand_total_rolling_pv()
        save_master_outputs()


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# EXECUTION #-----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#


# run_rolling_nav()

