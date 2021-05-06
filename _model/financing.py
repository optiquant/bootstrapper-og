import model_control
import lookup
import model_drivers
import hedging
import pandas as pd
from collections import namedtuple
from pandas.tseries.offsets import MonthEnd, MonthBegin
from useful_functions import *

# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

sg_and_a = model_drivers.sg_and_a
scenario_timestamp = model_control.new_scenario()
historical_financials_dict = model_drivers.historical_financials_dict
infra_capex_dict = model_drivers.infra_capex_dict
working_cap_balance_dict = model_drivers.working_cap_balance_dict
asset_level_drivers = model_drivers.get_asset_level_drivers()
boots_template_df = model_drivers.boots_template_df
chart_months = model_control.chart_months

# set the filepaths for saving financing module outputs
scenario_root_folders = model_control.get_scenario_root_folders()
scenario_filepaths_all = model_control.get_scenario_filepaths_all()
save_to = 'both'  # or 'local' or 'network'
fp_local = scenario_root_folders['local_scenario_folder']
fp_network = scenario_root_folders['network_scenario_folder']
print(f'\n$$$ Financing outputs will be saved to {save_to}: {[_ for _ in (fp_local, fp_network)]}')

# data source for EBITDAX and FCF used in this module
existing_scenario_data_source = model_control.existing_scenario_data_source
fp = scenario_root_folders[f'{existing_scenario_data_source}_scenario_folder']

# dates for model
balance_sheet_date = pd.to_datetime(model_control.balance_sheet_date)
print(f'\n| Balance Sheet Date: {string_date(balance_sheet_date)}')

model_period = model_drivers.model_period
ttm_period = pd.date_range(end=balance_sheet_date, start=balance_sheet_date + MonthEnd(-11), freq='M', tz='UTC')
print(f'| TTM Period: {ttm_period}')
print(f'| Model Period: {model_period}')
# date range for TTM through model period
ttm_through_model_period_dates = pd.date_range(
    start=ttm_period[0],
    end=model_period[-1],
    freq='M',
    tz='UTC'
)


# acquisition input dictionary
global acquisition_inputs
acquisition_inputs = {}

# starting capital structure, based on the balance sheet date. this is updated using the historical_financials_dict.
starting_balances = {
    'hist_monthly_ebitdax': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                                      index=ttm_through_model_period_dates,
                                      name='hist_monthly_ebitdax').fillna(0),
    'ttm_ebitdax_hedged': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                                    index=ttm_through_model_period_dates,
                                    name='ttm_ebitdax_hedged').fillna(0),
    'bs_cash': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                         index=ttm_through_model_period_dates,
                         name='bs_cash').fillna(0),
    'debt_1L': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                         index=ttm_through_model_period_dates,
                         name='debt_1L').fillna(0),
    'debt_2L': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                         index=ttm_through_model_period_dates,
                         name='debt_2L').fillna(0),
    'mezz_pref': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                           index=ttm_through_model_period_dates,
                           name='mezz_pref').fillna(0),
    'pref_equity_class_A': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                                     index=ttm_through_model_period_dates,
                                     name='pref_equity_class_A').fillna(0),
    'common_equity_class_B': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                                       index=ttm_through_model_period_dates,
                                       name='common_equity_class_B').fillna(0),
    'net_total_leverage': pd.Series(data=np.zeros_like(range(len(ttm_through_model_period_dates))),
                                    index=ttm_through_model_period_dates,
                                    name='net_total_leverage').fillna(0)
}

input_column_mapper = {
    'hist_monthly_ebitdax': 'EBITDAX',
    'ttm_ebitdax_hedged': 'TTM EBITDAX',
    'bs_cash': 'BS Cash',
    'debt_1L': '1L Debt',
    'debt_2L': '2L Debt',
    'mezz_pref': 'Mezz Pref',
    'pref_equity_class_A': 'Pref Equity - Class A',
    'common_equity_class_B': 'Common Equity - Class B',
    'net_total_leverage': 'Net Leverage'
}

# capital structure inputs
_libor = 0.0025

# todo: figure out how to incorporate acquisition financing costs
refi_maturity_dates = {
    'bs_cash': pd.to_datetime('12/31/2222', utc=True),
    'debt_1L': pd.to_datetime('12/31/2222', utc=True),
    'debt_2L': pd.to_datetime('5/31/2024', utc=True),
    'mezz_pref': pd.to_datetime('12/31/2222', utc=True),
    'pref_equity_class_A': pd.to_datetime('12/31/2222', utc=True),
    'common_equity_class_B': pd.to_datetime('12/31/2222', utc=True)
}

cash_rates = {
    'bs_cash': 0.00,
    'debt_1L': 0.0375 + _libor,
    'debt_2L': 0.075 + _libor,
    'mezz_pref': 0.12,
    'pref_equity_class_A': 0.00,
    'common_equity_class_B': 0.00
}

pik_rates = {
    'bs_cash': 0.00,
    'debt_1L': 0.00,
    'debt_2L': 0.00,
    'mezz_pref': 0.00,
    'pref_equity_class_A': 0.00,
    'common_equity_class_B': 0.00
}

commitments_borrowing_base = {
    'bs_cash': 0.00,
    'debt_1L': 215000.0,
    'debt_2L': 100000.0,
    'mezz_pref': 0.00,
    'pref_equity_class_A': 0.00,
    'common_equity_class_B': 0.00
}

fee_rates = {
    'bs_cash': 0.00,
    'debt_1L': 0.005,
    'debt_2L': 0.00,
    'mezz_pref': 0.00,
    'pref_equity_class_A': 0.00,
    'common_equity_class_B': 0.00
}

fee_basis = {
    'bs_cash': None,
    'debt_1L': 'undrawn_commitments',
    'debt_2L': None,
    'mezz_pref': None,
    'pref_equity_class_A': None,
    'common_equity_class_B': None
}

# capital cost by tranche
CapitalTranche = namedtuple(
    'CapitalTranche', [
        'tranche_name',
        'refi_maturity_date',
        'starting_balance',
        'borrowing_base',
        'cash_rate',
        'pik_rate',
        'fee_rate',
        'fee_basis',
        'cash_expense',
        'pik_expense',
        'fee_expense',
        'balance_eop',
        'change_in_balance_eop'
    ]
)

# dictionary of CapitalTranche namedtuples
parentco_capital_structure = {
    'bs_cash': None,
    'debt_1L': None,
    'debt_2L': None,
    'mezz_pref': None,
    'pref_equity_class_A': None,
    'common_equity_class_B': None
}


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# FUNCTIONS #-----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#


def _initialize():
    # get the forecast EBITDAX dataframe
    global forecast_cash_ebitdax_ex_sga
    try:
        # add the historical EBITDAX to the forecast EBITDAX from economics module
        forecast_cash_ebitdax_ex_sga = economics.ebitdax.ebitdax_unhedged_total_all_k
    except (NameError, AttributeError, ValueError):
        filename = 'ebitdax_unhedged_total_all_k.xlsx'
        forecast_cash_ebitdax_ex_sga = pd.read_excel(fp + 'econs/' + filename)
        forecast_cash_ebitdax_ex_sga.rename(columns={'index': 'Date'}, inplace=True)
        forecast_cash_ebitdax_ex_sga.set_index('Date', inplace=True, drop=True)
        forecast_cash_ebitdax_ex_sga.index = pd.DatetimeIndex(forecast_cash_ebitdax_ex_sga.index, tz='UTC')
        model_control.add_to_scenario_filepaths(tail='econs/ebitdax_unhedged_total_all_k.xlsx')

    # get the forecast FCF dataframe
    global forecast_fcf
    try:
        # add the historical EBITDAX to the forecast EBITDAX from economics module
        forecast_fcf = economics.fcf.fcf_unhedged_total_all_k
    except (NameError, AttributeError, ValueError):
        filename = 'fcf_unhedged_total_all_k.xlsx'
        forecast_fcf = pd.read_excel(fp + 'econs/' + filename)
        forecast_fcf.rename(columns={'index': 'Date'}, inplace=True)
        forecast_fcf.set_index('Date', inplace=True, drop=True)
        forecast_fcf.index = pd.DatetimeIndex(forecast_fcf.index, tz='UTC')
        model_control.add_to_scenario_filepaths(tail='econs/fcf_unhedged_total_all_k.xlsx')

    # cash flow before M&A and financing = EBITDAX less capex less cash interest exp
    global fcf_after_ma_and_financing
    fcf_after_ma_and_financing = forecast_fcf.copy(deep=True).fillna(0)

    # get the parentco total capex (DC&F)
    global parentco_total_capex
    try:
        # get the parentco capex from the model_control (it's calculated in economics module and added to the model control)
        # if running the financing module independently, we would need to read this from the drive
        parentco_total_capex = model_control.parentco_capex['capex_total_all_k']
    except (NameError, AttributeError, ValueError):
        filename = 'parentco_capex_total_all_k.xlsx'
        parentco_total_capex = pd.read_excel(fp + 'econs/' + filename)
        parentco_total_capex.rename(columns={'index': 'Date'}, inplace=True)
        parentco_total_capex.set_index('Date', inplace=True, drop=True)
        parentco_total_capex.index = pd.DatetimeIndex(parentco_total_capex.index, tz='UTC')
        model_control.add_to_scenario_filepaths(tail='econs/' + filename)


def load_cap_struc_starting_balances():
    '''Loads the capital structure for parentco, by aggregating each sub-asset's historical financials.'''
    global acquisition_inputs
    for sub_asset, df in historical_financials_dict.items():
        # populate the parentco capital structure by summing the inputs across sub-assets
        for line_item, value in starting_balances.items():
            input_column = input_column_mapper[line_item]
            print(f'\n$$$ Loading {input_column} --> {line_item}')

            # add the historical financials / capital strucure starting balances
            if line_item is not 'net_total_leverage':
                if sub_asset == 'Farmar':
                    historicals_start = pd.to_datetime(model_period[0]+MonthEnd(-11), utc=True)
                else:
                    historicals_start = pd.to_datetime(acquisition_inputs[sub_asset]['effective_month'] + MonthEnd(-11),utc=True)

                # just add the ebitdax / cash flow from the active month onwards
                start_month = max(historicals_start, ttm_period[0])
                historicals_added_to_pro_forma = historical_financials_dict[sub_asset].loc[start_month:, input_column]
                starting_balances[line_item][historicals_added_to_pro_forma.index] += historicals_added_to_pro_forma
            else:
                print(f'\n!! Net leverage calculated later for {sub_asset}.')
            print(f'\n| parentco {line_item} starting balances updated --> {sub_asset}:\n {starting_balances[line_item].head(36)}')
    #_q = input('Continue? >>> ')


def calc_parentco_ebitdax_hedged():
    '''Calculates monthly EBITDAX for the parentco, starting at T-12 months, and ending at the model_period end. The parentco_cash_ebitdax_hedged dataframe calculated by this function is used to calculate parentco's rolling TTM EBITDAX.'''
    global parentco_cash_ebitdax_hedged
    global forecast_cash_ebitdax_ex_sga
    global hedge_settlements_total_all_k
    global ttm_through_model_period_dates
    global fcf_after_ma_and_financing

    # set up the parentco EBITDAX dataframe
    # note: starts at the beginning of the TTM period, so cannot just create a dataframe like boots_template_df
    # populate forecast / future cash EBITDAX
    parentco_cash_ebitdax_hedged = pd.DataFrame(index=ttm_through_model_period_dates, columns=boots_template_df.columns)
    parentco_cash_ebitdax_hedged.fillna(0, inplace=True)
    for col in parentco_cash_ebitdax_hedged.columns:
        parentco_cash_ebitdax_hedged.loc[forecast_cash_ebitdax_ex_sga.index, col] += forecast_cash_ebitdax_ex_sga.loc[:, col].values
        parentco_cash_ebitdax_hedged.loc[model_period, col] -= sg_and_a.loc[model_period].values
        fcf_after_ma_and_financing.loc[model_period, col] -= sg_and_a.loc[model_period].values

    # net out hedge settlements
    parentco_cash_ebitdax_hedged = net_hedge_settlements(input_dataframe=parentco_cash_ebitdax_hedged)
    print(f'\n| Parentco cash EBITDAX (net of hedges) >>\n {parentco_cash_ebitdax_hedged.head(36)}')

    # calculate rolling TTM covenant EBITDAX
    global parentco_rolling_ttm_ebitdax_hedged
    parentco_rolling_ttm_ebitdax_hedged = parentco_cash_ebitdax_hedged.rolling(12).sum().fillna(0)
    print(f'\n| Parentco Rolling TTM EBITDAX (hedged / future only) >>\n {parentco_rolling_ttm_ebitdax_hedged.head(36)}')
    #_q = input('Continue? >>> ')

    # adjust historical TTM EBITDAX calculation for acquisitions (non-cash; for covenant calculation purposes only)

    # for each acquired sub-asset in the acquisition_inputs
    for sub_asset in asset_level_drivers.index:
        # dataframe for historical EBITDAX of each sub-asset (index = ttm to model period), fillna(0)
        historical_ebitdax = pd.DataFrame(index=ttm_through_model_period_dates, columns=boots_template_df.columns).fillna(0)
        sub_asset_historicals = historical_financials_dict[sub_asset]
        try:
            active_month = pd.to_datetime(acquisition_inputs[sub_asset]['effective_month'],
                                          utc=True)
        except KeyError:
            active_month = pd.to_datetime(asset_level_drivers.loc[sub_asset, 'Asset Active Date']+MonthEnd(1),
                                          utc=True)

        # adjust the historical TTM EBITDAX for parentco
        for col in historical_ebitdax.columns:
            # populate the historical EBITDAX
            _common_index = sub_asset_historicals.index.intersection(historical_ebitdax.index)
            historical_ebitdax.loc[_common_index, col] += sub_asset_historicals.loc[_common_index, 'EBITDAX'].values
            # calculate the rolling TTM for this sub-asset
            historical_ebitdax[col] = historical_ebitdax[col].rolling(12).sum().fillna(0)
            # zero out TTM EBITDAX prior to active month
            _pre_acq_months = [_ for _ in historical_ebitdax.index if _ < active_month]
            if len(_pre_acq_months) > 0:
                historical_ebitdax.loc[_pre_acq_months, :] = 0.0

            # add the rolling TTM to the parentco rolling TTM *only* from the active month onwards
            parentco_rolling_ttm_ebitdax_hedged.loc[historical_ebitdax.index, col] += historical_ebitdax[col].values

    # trim parentco TTM ebitdax and forecast cash EBITDAX to model period
    parentco_rolling_ttm_ebitdax_hedged = parentco_rolling_ttm_ebitdax_hedged.loc[model_period, :]
    parentco_cash_ebitdax_hedged = parentco_cash_ebitdax_hedged.loc[model_period, :]
    print(f'| ParentCo Rolling TTM EBITDAX (hedged / historical adjusted >>> \n {parentco_rolling_ttm_ebitdax_hedged.head(36)}')



def net_hedge_settlements(input_dataframe: pd.DataFrame):
    '''Adds hedge settlements to the passed input dataframe (e.g. can be monthly EBITDAX, FCF, revenue etc).
    Args:
        |-- input_dataframe, pandas DataFrame: dataframe reindexed like model_drivers.boots_template_df
        '''
    global hedge_settlements_total_all_k
    _index_rows = [_ for _ in input_dataframe.index if _ in hedge_settlements_total_all_k.index]
    for col in input_dataframe.columns:
        input_dataframe.loc[_index_rows, col] += hedge_settlements_total_all_k.loc[_index_rows, col].values
    return input_dataframe



def initialize_parentco_capital_structure():
    '''Updates data for each tranche in the capital structure.'''
    tranche_input_data = {}
    global parentco_capital_structure
    # load input data for each tranche of parentco capital
    for tranche_name in parentco_capital_structure:
        tranche_input_data['tranche_name'] = tranche_name
        tranche_input_data['refi_maturity_date'] = refi_maturity_dates[tranche_name]
        tranche_input_data['starting_balance'] = starting_balances[tranche_name]
        tranche_input_data['borrowing_base'] = commitments_borrowing_base[tranche_name]
        tranche_input_data['cash_rate'] = cash_rates[tranche_name]
        tranche_input_data['pik_rate'] = pik_rates[tranche_name]
        tranche_input_data['fee_rate'] = fee_rates[tranche_name]
        tranche_input_data['fee_basis'] = fee_basis[tranche_name]
        tranche_input_data['cash_expense'] = pd.DataFrame().reindex_like(boots_template_df)
        tranche_input_data['cash_expense'].fillna(0, inplace=True)
        tranche_input_data['pik_expense'] = pd.DataFrame().reindex_like(boots_template_df)
        tranche_input_data['pik_expense'].fillna(0, inplace=True)
        tranche_input_data['fee_expense'] = pd.DataFrame().reindex_like(boots_template_df)
        tranche_input_data['fee_expense'].fillna(0, inplace=True)
        tranche_input_data['balance_eop'] = pd.DataFrame().reindex_like(boots_template_df)
        tranche_input_data['balance_eop'].fillna(0, inplace=True)
        tranche_input_data['change_in_balance_eop'] = pd.DataFrame().reindex_like(boots_template_df)
        tranche_input_data['change_in_balance_eop'].fillna(0, inplace=True)
        # instantiate a CapitalTranche namedtuple, add to the parentco capital
        parentco_capital_structure[tranche_name] = CapitalTranche(**tranche_input_data)

    print(f'\n| PARENTCO CAPITAL STRUCTURE >>>\n')
    print(parentco_capital_structure)


def load_acquisition_inputs():
    '''Loads acquisition purchase price and financing structure for each modeled sub-asset.'''
    # get the acquisition inputs for each sub-asset
    global acquisition_inputs

    for subasset in asset_level_drivers.index:
        if subasset != 'Farmar':
            acquisition_inputs[subasset] = {
                'effective_date': asset_level_drivers.loc[subasset, 'Asset Active Date'],
                'effective_month': asset_level_drivers.loc[subasset, 'Asset Active Date'] + MonthBegin(0) + MonthEnd(1),
                'purchase_price': float(asset_level_drivers.loc[subasset, 'Acquisition Consideration']),
                'bs_cash': float(asset_level_drivers.loc[subasset, 'BS Cash at Model Start']),
                'debt_1L': float(asset_level_drivers.loc[subasset, '1L Debt at Model Start']),
                'debt_2L': float(asset_level_drivers.loc[subasset, '2L Debt at Model Start']),
                'mezz_pref': float(asset_level_drivers.loc[subasset, 'Mezz Pref at Model Start']),
                'pref_equity_class_A': float(asset_level_drivers.loc[subasset, 'Pref Equity at Model Start']),
                'common_equity_class_B': float(asset_level_drivers.loc[subasset, 'Other Equity at Model Start']),
                'borrowing_base_contribution': float(asset_level_drivers.loc[subasset, '1L Borrowing Base'])
            }
            print(f'\n| ACQUISITION INPUTS >>> {subasset}\n {acquisition_inputs[subasset]}')


def net_acquisition_financing(idx: int):
    '''Nets out acquisition purchase price and financing from appropriate parentco capital tranches.'''
    global acquisition_inputs
    global fcf_after_ma_and_financing

    for subasset in acquisition_inputs:
        effective_month = pd.to_datetime(acquisition_inputs[subasset]['effective_month'], utc=True)
        # if this month is the acquisition's effective month
        if model_period[idx] == effective_month:
            print(f'| {subasset} acquisition modeled as effective in: {effective_month}')

            # update the cash flow dataframes with this acquisition's purchase price
            fcf_after_ma_and_financing.iloc[idx, :] -= pd.Series(
                data=acquisition_inputs[subasset]['purchase_price'],
                index=fcf_after_ma_and_financing.columns
            )


            # acquisition financing tranches
            _acq_financing_tranches = {
                k: v for k, v in acquisition_inputs[subasset].items() if k in parentco_capital_structure and k != 'debt_1L'
            }

            # update the cash flow dataframes for the financing cash flow (should map to sources and uses)
            for tranche_name, value in _acq_financing_tranches.items():
                fcf_after_ma_and_financing.iloc[idx, :] += pd.Series(
                    data=value,
                    index=fcf_after_ma_and_financing.columns
                )


def get_prior_period_balance(_tranche_name: str, idx: int):
    '''Returns prior period balance for this capital tranche.'''
    cap_tranche = parentco_capital_structure[_tranche_name]
    # if this is the first period, calculate expenses using the starting balance
    prior_month = model_period[idx] + MonthEnd(-1)
    prior_period_balance = pd.Series(index=boots_template_df.columns, dtype='float64')
    if idx == 0:
        # calc cash and PIK expenses
        prior_period_balance.fillna(cap_tranche.starting_balance.loc[prior_month], inplace=True)
    else:
        prior_period_balance.fillna(cap_tranche.balance_eop.loc[prior_month], inplace=True)
    return prior_period_balance


def net_cash_expense_and_fees(_tranche_name: str, idx: int):
    '''Nets out cash dividend/interest expense and cash fees for this period from free cash flow.'''
    global fcf_after_ma_and_financing
    cap_tranche = parentco_capital_structure[_tranche_name]
    prior_period_balance = get_prior_period_balance(_tranche_name, idx)

    if fee_basis == 'undrawn_commitments':
        cap_tranche.fee_expense.iloc[idx, :] = cap_tranche.fee_rate / 12 * (
                cap_tranche.borrowing_base - prior_period_balance)
    else:
        cap_tranche.fee_expense.iloc[idx, :] = cap_tranche.fee_rate / 12 * prior_period_balance

    cap_tranche.cash_expense.iloc[idx, :] = cap_tranche.cash_rate / 12 * prior_period_balance
    cap_tranche.cash_expense.iloc[idx, :] += cap_tranche.fee_expense.iloc[idx, :]
    cap_tranche.cash_expense.fillna(0, inplace=True)
    print(f'\n|-- FCF after M&A, before financing: {fcf_after_ma_and_financing.iloc[idx, :]}')
    print(f'|-- {_tranche_name} cash expenses (incl. fees): {cap_tranche.cash_expense.iloc[idx, :]}')
    print(f'|-- {_tranche_name} cash fees: {cap_tranche.fee_expense.iloc[idx, :]}')
    fcf_after_ma_and_financing.iloc[idx, :] -= cap_tranche.cash_expense.iloc[idx, :]
    fcf_after_ma_and_financing.fillna(0, inplace=True)
    print(f'|-- FCF after M&A and financing: {fcf_after_ma_and_financing.iloc[idx, :]}')


def net_pik_expense(_tranche_name: str, idx: int):
    '''Adds PIK interest/dividend expense to the ending balance for this period.'''
    cap_tranche = parentco_capital_structure[_tranche_name]
    if cap_tranche.pik_rate != 0.0:
        prior_period_balance = get_prior_period_balance(_tranche_name, idx)
        # calculate PIK expense
        cap_tranche.pik_expense.iloc[idx, :] = cap_tranche.pik_rate / 12 * prior_period_balance
        print(f'\n|-- {_tranche_name} Balance, BOP: {cap_tranche.balance_eop.iloc[idx, :]}')
        cap_tranche.balance_eop.iloc[idx, :] += cap_tranche.pik_expense.iloc[idx, :]
        print(f'|-- {_tranche_name} PIK expense: {cap_tranche.pik_expense.iloc[idx, :]}')
        print(f'|-- {_tranche_name} Balance, EOP: {cap_tranche.balance_eop.iloc[idx, :]}')
    else:
        print(f'!! {_tranche_name} is a non-PIK security / PIK rate is 0.0%.')


def net_balance_eop(_tranche_name: str, idx: int):
    '''Calculates the EOP balance for this capital tranche.'''
    global fcf_after_ma_and_financing
    global acquisition_inputs

    cap_tranche = parentco_capital_structure[_tranche_name]
    refi_maturity_date = refi_maturity_dates[_tranche_name]
    prior_period_balance = get_prior_period_balance(_tranche_name=_tranche_name, idx=idx)
    print(f'\n$$$ {_tranche_name} balance, BOP: {prior_period_balance}')
    if model_period[idx] == refi_maturity_date:
        cap_tranche.balance_eop.iloc[idx, :] = 0.0
        fcf_after_ma_and_financing.iloc[idx, :] -= pd.Series(data=prior_period_balance,
                                                             index=fcf_after_ma_and_financing.columns)
    else:

        updated_balance_eop = None
        # adjust capital structure ending balances for acquisitions
        for subasset in acquisition_inputs:
            effective_month = pd.to_datetime(acquisition_inputs[subasset]['effective_month'], utc=True)

            if model_period[idx] != effective_month and updated_balance_eop is None:
                # just roll forward the prior month's balance
                cap_tranche.balance_eop.iloc[idx, :] = prior_period_balance
            elif model_period[idx] == effective_month:
                # if this month is an acquisition's effective month, update with acquisition financing amounts
                cap_tranche.balance_eop.iloc[idx, :] = prior_period_balance + pd.Series(
                    data=acquisition_inputs[subasset][_tranche_name],
                    index=fcf_after_ma_and_financing.columns
                )
                updated_balance_eop = cap_tranche.balance_eop.iloc[idx, :].copy(deep=True)
            elif updated_balance_eop is not None:
                # use the updated balance as the base for remainder of loop (over sub-assets)
                cap_tranche.balance_eop.iloc[idx, :] = updated_balance_eop

            print(f'\n$$$ {_tranche_name} balance, EOP: {cap_tranche.balance_eop.iloc[idx, :]}')
    #_q = input('Continue? >>> ')


def net_revolver(idx: int, cash_flow: pd.DataFrame):
    '''Sweeps cash flow for this period to the revolver.'''
    name = 'debt_1L'
    cap_tranche = parentco_capital_structure[name]
    prior_period_balance = get_prior_period_balance(name, idx)

    print(f'\n|-- Revolver, BOP: {prior_period_balance}')
    # excess cash flow calc
    # don't subtract more than the existing/BOP balance
    ecf_sweep = np.minimum(cash_flow.iloc[idx, :], prior_period_balance)

    # if this is refi/maturity period, or the remaining revolver balance is less than the excess cash flow
    if pd.to_datetime(cash_flow.index[idx]) >= cap_tranche.refi_maturity_date:
        print(f'\n| Refi/maturity period for {name}: {cash_flow.index[idx]}')
        cap_tranche.balance_eop.iloc[idx, :] -= prior_period_balance
        # remaining cash flow
        cash_flow.iloc[idx, :] -= prior_period_balance
    else:
        cap_tranche.balance_eop.iloc[idx, :] = prior_period_balance - ecf_sweep
        # remaining cash flow
        cash_flow.iloc[idx, :] -= ecf_sweep

    print(f'|-- Cash flow net of cash expenses: {ecf_sweep}')
    print(f'|-- Revolver, EOP: {cap_tranche.balance_eop.iloc[idx, :]}')
    net_balance_sheet_cash(idx=idx, cash_flow=cash_flow)


def net_balance_sheet_cash(idx: int, cash_flow: pd.DataFrame):
    name = 'bs_cash'
    cap_tranche = parentco_capital_structure[name]
    prior_period_balance = get_prior_period_balance(_tranche_name=name, idx=idx)
    print(f'\n| BS cash, BOP: {prior_period_balance}')
    print(f'| Change in cash: {cash_flow.iloc[idx, :]}')
    cap_tranche.balance_eop.iloc[idx, :] = prior_period_balance + cash_flow.iloc[idx, :]
    print(f'| BS cash, EOP: {cap_tranche.balance_eop.iloc[idx, :]}')


def calc_free_cash_flow():
    '''Calculates free cash flow before the ECF sweep (after M&A).
     Free cash flow = EBITDAX less capex less cash interest, dividends, and fees, less net acquisition financing.'''

    # loop through each capital tranche's balance_eop index
    # loop should start with capital of lowest seniority, and end with revolver
    cap_tranches_in_reverse_seniority = [[_ for _ in parentco_capital_structure.keys()][i] for i in
                                         range(len(parentco_capital_structure) - 1, 0, -1)]
    cap_tranches_in_reverse_seniority = [_ for _ in cap_tranches_in_reverse_seniority] # todo: check if required --> if 'equity' not in _
    print(cap_tranches_in_reverse_seniority)

    # net out hedge settlements from free cash flow
    global fcf_after_ma_and_financing
    print(f'$$$ Netting out hedge settlements from free cash flow after M&A/financing...')
    fcf_after_ma_and_financing = net_hedge_settlements(input_dataframe=fcf_after_ma_and_financing)
    print(forecast_fcf, fcf_after_ma_and_financing)

    global parentco_total_capex
    global parentco_infra_capex
    global parentco_working_cap_balance
    parentco_infra_capex = pd.DataFrame().reindex_like(boots_template_df).fillna(0)
    parentco_working_cap_balance = pd.DataFrame().reindex_like(boots_template_df).fillna(0)

    # net out infra capex
    for sub_asset in infra_capex_dict:
        fcf_after_ma_and_financing -= infra_capex_dict[sub_asset]
        fcf_after_ma_and_financing.fillna(0, inplace=True)
        parentco_infra_capex -= infra_capex_dict[sub_asset]
        parentco_infra_capex.fillna(0, inplace=True)
        print(f'\n$$$ FCF net of infrastructure capex {sub_asset}:\n {fcf_after_ma_and_financing}')

        fcf_after_ma_and_financing -= working_cap_balance_dict[sub_asset]
        fcf_after_ma_and_financing.fillna(0, inplace=True)
        parentco_working_cap_balance -= working_cap_balance_dict[sub_asset]
        parentco_working_cap_balance.fillna(0, inplace=True)
        print(f'\n$$$ FCF net of working capital balance {sub_asset}:\n {fcf_after_ma_and_financing}')

    # update parentco total capex dataframe
    parentco_total_capex += parentco_infra_capex
    parentco_total_capex += parentco_working_cap_balance
    print(f'\n$$$ ParentCo Total Capex:\n {parentco_total_capex}')

    # parentco hedged FCF dataframe
    global parentco_fcf_hedged
    parentco_fcf_hedged = pd.DataFrame().reindex_like(fcf_after_ma_and_financing)
    parentco_fcf_hedged.fillna(0, inplace=True)

    # calculate financing cash flow
    for idx, model_month in enumerate(model_period):
        # net out acquisition financing from this period's cash flows, and set is_acquisition_period to True
        net_acquisition_financing(idx=idx)
        for _tranche_idx, tranche_name in enumerate(cap_tranches_in_reverse_seniority):
            # net out various tranches of financing expense (interest, cash/PIK dividends)
            net_pik_expense(_tranche_name=tranche_name, idx=idx)
            net_cash_expense_and_fees(_tranche_name=tranche_name, idx=idx)
            net_balance_eop(_tranche_name=tranche_name, idx=idx)

        # update parentco hedged FCF before sweeping to revolver
        parentco_fcf_hedged.iloc[idx, :] += fcf_after_ma_and_financing.iloc[idx, :]
        # update revolver
        net_revolver(idx=idx, cash_flow=fcf_after_ma_and_financing)

    print(f'$$$ FCF net of hedge settlements, M&A, and financing:\n')
    print(fcf_after_ma_and_financing)
    print(f'$$$ ParentCo FCF prior to ECF sweep to revolver:\n')
    print(parentco_fcf_hedged)


def calc_net_total_leverage():
    '''Calculates parentco net total leverage (i.e. leverage through all "debt" tranches).'''

    global parentco_rolling_ttm_ebitdax_hedged
    debt_tranches = [_ for _ in parentco_capital_structure if 'debt' in _]
    # append bs_cash
    debt_tranches.append('bs_cash')

    # create empty dataframes for net total debt and net leverage
    global net_total_debt
    net_total_debt = pd.DataFrame().reindex_like(boots_template_df)
    net_total_debt.fillna(0.0, inplace=True)

    global net_total_leverage
    net_total_leverage = pd.DataFrame().reindex_like(boots_template_df)
    net_total_leverage.fillna(0.0, inplace=True)

    for tranche_name in debt_tranches:
        cap_tranche = parentco_capital_structure[tranche_name]
        if tranche_name != 'bs_cash':
            net_total_debt += cap_tranche.balance_eop
        else:
            net_total_debt -= cap_tranche.balance_eop

    # adjust indexes to be tz-aware if they are not
    try:
        net_total_debt.index = pd.DatetimeIndex(net_total_debt.index, tz='UTC')
    except TypeError:
        print('!! net_total_debt index is already tz-aware')
    try:
        parentco_rolling_ttm_ebitdax_hedged.index = pd.DatetimeIndex(parentco_rolling_ttm_ebitdax_hedged.index,
                                                                     tz='UTC')
    except TypeError:
        print('!! parentco_rolling_ttm_ebitdax_hedged index is already tz-aware')

    # calculate net leverage
    net_total_leverage = net_total_debt / parentco_rolling_ttm_ebitdax_hedged

    print(f'| PARENTCO net total debt:\n {net_total_debt}')
    print(f'| PARENTCO TTM EBITDAX:\n {parentco_rolling_ttm_ebitdax_hedged}')
    print(f'| PARENTCO net total leverage:\n {net_total_leverage}')


def save_financing_outputs(save_to: str):
    '''Saves key financing module outputs to excel.'''
    if save_to == 'local':
        fp_list = [fp_local]
    elif save_to == 'network':
        fp_list = [fp_network]
    else:
        fp_list = [fp_network, fp_local]

    for fp in fp_list:
        global net_total_debt
        global net_total_leverage
        # save balances and cash/PIK expense dataframes by capital tranche
        for name, cap_tranche in parentco_capital_structure.items():
            save_to_excel(output_dataframe=cap_tranche.balance_eop, folder=fp + 'econs/',
                          filename=f'financing_{name}_balance_eop.xlsx')
            # update scenario filepaths
            model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_{name}_balance_eop.xlsx')
            if cap_tranche.cash_rate != 0.0:
                save_to_excel(output_dataframe=cap_tranche.cash_expense, folder=fp + 'econs/',
                              filename=f'financing_{name}_cash_expense.xlsx')
                # update scenario filepaths
                model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_{name}_cash_expense.xlsx')
            if cap_tranche.fee_rate != 0.0:
                save_to_excel(output_dataframe=cap_tranche.fee_expense, folder=fp + 'econs/',
                              filename=f'financing_{name}_fee_expense.xlsx')
                model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_{name}_fee_expense.xlsx')

            if cap_tranche.pik_rate != 0.0:
                save_to_excel(output_dataframe=cap_tranche.pik_expense, folder=fp + 'econs/',
                              filename=f'financing_{name}_pik_expense.xlsx')
                model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_{name}_pik_expense.xlsx')

        # save individual cash flow / leverage dataframes
        save_to_excel(output_dataframe=parentco_total_capex, folder=fp + 'econs/',
                      filename=f'financing_parentco_capex.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_capex.xlsx')

        save_to_excel(output_dataframe=parentco_fcf_hedged, folder=fp + 'econs/',
                      filename=f'financing_parentco_fcf_hedged.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_fcf_hedged.xlsx')

        save_to_excel(output_dataframe=fcf_after_ma_and_financing, folder=fp + 'econs/',
                      filename=f'financing_fcf_after_ma_and_financing.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_fcf_after_ma_and_financing.xlsx')

        save_to_excel(output_dataframe=hedge_settlements_total_all_k, folder=fp + 'econs/',
                      filename=f'financing_hedge_settlements_total_all_k.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_hedge_settlements_total_all_k.xlsx')

        # save hedge settlements by hedge contract / hedge type
        # loop through the 2-level dict
        for contract in hedges_by_contract_type:
            for hedge_type in hedges_by_contract_type[contract]:
                hedge_df = hedges_by_contract_type[contract][hedge_type]
                save_to_excel(output_dataframe=hedge_df, folder=fp + 'econs/',
                              filename=f'financing_hedge_settlements_{contract}_{hedge_type}.xlsx')
                model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_hedge_settlements_{contract}_{hedge_type}.xlsx')

        save_to_excel(output_dataframe=parentco_cash_ebitdax_hedged, folder=fp + 'econs/',
                      filename=f'financing_parentco_cash_ebitdax_hedged.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_cash_ebitdax_hedged.xlsx')

        save_to_excel(output_dataframe=parentco_rolling_ttm_ebitdax_hedged, folder=fp + 'econs/',
                      filename=f'financing_parentco_ttm_ebitdax_hedged.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_ttm_ebitdax_hedged.xlsx')

        save_to_excel(output_dataframe=net_total_debt, folder=fp + 'econs/',
                      filename=f'financing_parentco_net_total_debt.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_net_total_debt.xlsx')

        save_to_excel(output_dataframe=net_total_leverage, folder=fp + 'econs/',
                      filename=f'financing_parentco_net_total_leverage.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_net_total_leverage.xlsx')

        save_to_excel(output_dataframe=parentco_infra_capex, folder=fp + 'econs/',
                      filename=f'financing_parentco_infra_capex.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_infra_capex.xlsx')

        save_to_excel(output_dataframe=parentco_working_cap_balance, folder=fp + 'econs/',
                      filename=f'financing_parentco_working_cap_balance.xlsx')
        model_control.add_to_scenario_filepaths(tail='econs/' + f'financing_parentco_working_cap_balance.xlsx')


def get_all_hedge_settlements():
    '''all_hedge_settlements is a 2-level nested dictionary of hedge settlement dataframes. Its values
     contain nearly all variables that may be required outside the hedging module (see "columns" below).
    |-- keys > trade_ids (0 to number of trades in model period)
    |-- values > dict of settlement dataframes
    |------ keys >> identifiers for each trade (incl price scenario) e.g. 'hh_swaps_trade_243_Strip 2020-11-11'
                key format: f'{comdty_nick}_{hedge_type_short_name}_trade_{trade_id}_{price_scenario}'
    |------ values >>
    |--------- index = contract months (so dataframes vary in len)
    |--------- columns = commodity (oil, gas, ngl), contract, comdty_nick, hedge_type, volume_hedged, volume_unit,
                        price_unit, swap_price, call_price, market_price, swap_spread, call_spread, swap_value_k,
                                            call_value_k, market_value_k, net_settlement_k
    '''
    global all_hedge_settlements
    all_hedge_settlements = hedging.get_all_hedge_settlements()
    return all_hedge_settlements



def roll_up_all_hedge_settlements():
    '''Rolls up all net settlements for all hedges.'''

    # get all hedge settlements dictionary
    global all_hedge_settlements
    if 'all_hedge_settlements' not in globals():
        all_hedge_settlements = get_all_hedge_settlements()

    # create an empty dataframe for total hedge settlements
    global hedge_settlements_total_all_k
    hedge_settlements_total_all_k = pd.DataFrame().reindex_like(boots_template_df)
    hedge_settlements_total_all_k.fillna(0, inplace=True)

    # filter down the all hedge settlements dictionary to match the filters
    global filtered_hedge_settlements
    filtered_hedge_settlements = all_hedge_settlements.copy()

    for trade_idx in filtered_hedge_settlements:
        for identifier, settlement_df in filtered_hedge_settlements[trade_idx].items():
            print(f'>>> Rolling up hedge settlements: {identifier}')
            for price_scenario in hedge_settlements_total_all_k.columns:
                if f'_{price_scenario}' in identifier:
                    # add the net_settlement_k values to the relevant index rows in hedge_settlements_total_all_k
                    _index_rows = settlement_df.index
                    hedge_settlements_total_all_k.loc[_index_rows, price_scenario] += settlement_df.loc[:,
                                                                                      'net_settlement_k']
    print(f'\n| All hedge settlements >>> ')


def roll_up_hedge_settlements(contract_filter='all', hedge_type_filter='all', trade_idx_filter='all'):
    '''Rolls up the net settlements for all hedges matching the filters.
    Args:
        -- contract_filter, str: commodity nickname filter ('wti', 'hh', 'ethane' etc, or 'all')
        -- hedge_type_filter, str: 'swaps', 'collars' etc, or 'all'
        -- trade_idx_filter, str: '0' through total number of trades in model period
        '''

    # get all hedge settlements dictionary
    global all_hedge_settlements
    if 'all_hedge_settlements' not in globals():
        all_hedge_settlements = get_all_hedge_settlements()

    # create an empty dataframe for total hedge settlements
    hedge_settlements = pd.DataFrame().reindex_like(boots_template_df)
    hedge_settlements.fillna(0, inplace=True)

    # filter down the all hedge settlements dictionary to match the filters
    global filtered_hedge_settlements
    filtered_hedge_settlements = all_hedge_settlements.copy()
    if contract_filter != 'all':
        filtered_hedge_settlements = {identifier: df for k, v in filtered_hedge_settlements.items() for identifier, df in v.items()  if contract_filter in identifier}

    if hedge_type_filter != 'all':
        filtered_hedge_settlements = {identifier: df for k, v in filtered_hedge_settlements.items() for identifier, df in v.items() if hedge_type_filter in identifier}

    if trade_idx_filter != 'all':
        filtered_hedge_settlements = {identifier: df for k, v in filtered_hedge_settlements.items() for identifier, df in v.items() if trade_idx_filter in identifier}

    #for trade_idx in filtered_hedge_settlements:
    for identifier, settlement_df in filtered_hedge_settlements.items():
        print(f'>>> Rolling up hedge settlements: {identifier}')
        for price_scenario in hedge_settlements.columns:
            if f'_{price_scenario}' in identifier:
                # add the net_settlement_k values to the relevant index rows in hedge_settlements_total_all_k
                _index_rows = settlement_df.index
                hedge_settlements.loc[_index_rows, price_scenario] += settlement_df.loc[:,'net_settlement_k']

    print(
        f'\n| Hedge settlements (filters >> commodity: {contract_filter} // hedge type: {hedge_type_filter} // trade index: {trade_idx_filter}')

    return hedge_settlements


def roll_up_hedge_settlements_by_commodity():
    '''Rolls up settlements for each hedge contract and hedge type'''
    global hedges_by_contract_type
    hedges_by_contract_type = {}
    contracts = list_unique(model_drivers.current_hedges['contract'], silent=False)
    hedge_types = list_unique(model_drivers.current_hedges['hedge_type'], silent=False)
    # append "all" so that we get a summary of all hedge types by contract
    hedge_types.append('all')

    for contract in contracts:
        contract_short_name = lookup.lookup('hedge_comdty_price_bootstrap')[contract][0]
        hedges_by_contract_type[contract] = {}
        for hedge_type in hedge_types:
            try:
                hedge_type_short_name = hedging.hedge_type_short_name_dict[hedge_type]
            except KeyError:
                hedge_type_short_name = hedge_type

            hedge_settlements = roll_up_hedge_settlements(
                contract_filter=contract_short_name,
                hedge_type_filter=hedge_type_short_name,
                trade_idx_filter='all'
            )
            if hedge_settlements.values.squeeze().sum() != 0:
                hedges_by_contract_type[contract][hedge_type] = hedge_settlements



def run_financing():
    '''Runs financing module.'''
    # initialize core drivers
    _initialize()

    load_acquisition_inputs()

    # load the parentco capital structure
    load_cap_struc_starting_balances()

    # get hedges and roll up settlements for all current hedges
    roll_up_all_hedge_settlements()

    # roll up hedge settlements by commodity (for output granularity)
    roll_up_hedge_settlements_by_commodity()

    # calculate parentco monthly historical ebitdax - net of hedges, as well as rolling TTM EBITDAX for parentco
    calc_parentco_ebitdax_hedged()

    initialize_parentco_capital_structure()


    #q = input(f'\n>>> Hit enter to proceed with FCF calculation >>> ')

    calc_free_cash_flow()

    #q = input(f'\n>>> Hit enter to proceed with net leverage calculation >>> ')

    calc_net_total_leverage()

    save_financing_outputs(save_to=save_to)


# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# EXECUTION #-----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#



# TODO: finish parentco interest expense, parentco_FCF, acquisition financing,
#  ECF sweep to revolver
#  and then build BS cash, calculate net leverage, rolling NAV (from the FCF dataframe), borrowing base estimate,
#  and equity value

# todo: pass the save folder to the hedging module to save hedge_settlements (since the settlement dict will be called from here, the financing module)
# todo: for the hedge settlements, loop through the master_hedge_settlement_dict keys, and search for the price_scenario in each key
# todo: the value will be a dataframe, but the index is not the full model_period - only the contract months for that hedge contract
# todo: the column to roll up is "net_settlement_k" for each dataframe in the values of master_hedge_settlement_dict
