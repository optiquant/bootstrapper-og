import _model.model_control as model_control
from _model.useful_functions import *

import pandas as pd
import numpy as np
import math
import datetime as dt
from datetime import date
from pandas.tseries.offsets import *
from time import perf_counter
import gzip
from collections import *
import IPython.display as display
import win32com.client as win32  # for outlook emailing
from sklearn.neighbors import KernelDensity

pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)

# PLOTLY
from kaleido.scopes.plotly import PlotlyScope
import plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px

model_prices_excluded = []

excluded_prices = {
    'wti_cma': [0.00],
    'wti': [0.00],
    'hh': [0.00],
    'brent': [1114.27]}

ChartData = namedtuple('ChartData', 'title x y x_name y_name')

master_heatmap_data = {}

_fig_width = 2200
_fig_height = 1500
_font_size = 11
_vertical_spacing = 0.06

# default percentiles for MCS
default_percentiles = model_control.default_percentiles
string_default_percentiles = model_control.string_default_percentiles
scenario_time_stamp = model_control.get_scenario_time_stamp()
scenario_filepaths_all = model_control.get_scenario_filepaths_all()


# ---------------------------------------------- ROOT FOLDERS ----------------------------------------------
def root_folder_daily_prices():
    '''Returns filepath for daily price updates.'''
    filepath = f'C:/Users/vdesai/Git/bootstrapper-og/daily_price_updates/'
    print(f'/n| Daily price updates location: {filepath}')
    return {'parent_folder': filepath.strip('daily_price_updates/'),
            'root_folder': filepath}


def root_folder_comex_data():
    '''Returns filepath for all comex data.'''
    filepath = f'C:/Users/vdesai/Git/bootstrapper-og/settlements_comex/'
    print(f'\n| COMEX data location: {filepath}')
    return {'parent_folder': filepath.strip('comex_settlements/'),
            'root_folder': filepath}


def root_folder_mcs_data(c_nick):
    '''Returns filepath for MCS price data.'''
    c_code = get_comdty_code(c_nick)
    filepath = f'C:/Users/vdesai/Git/bootstrapper-og/_price_data/{c_code}/mcs_prices/'
    print(f'\n| MCS data location: {filepath}')
    return {'parent_folder': filepath.strip('mcs_prices/'),
            'root_folder': filepath}


def root_folder_nymex_data():
    '''Returns filepath for all nymex data.'''
    filepath = f'C:/Users/vdesai/Git/bootstrapper-og/settlements_nymex/'
    print(f'\n| NYMEX data location: {filepath}')
    return {'parent_folder': filepath.strip('nymex_settlements/'),
            'root_folder': filepath}


def root_folder_price_data(c_nick, as_of_date):
    '''Returns filepath to store price_data json files for commodity. Returns dict of {folder, filepath}'''
    c_code = get_comdty_code(c_nick)
    folder = f'C:/Users/vdesai/Git/bootstrapper-og/_price_data/{c_code}/'
    filepath = folder + f'_prices_{c_code}_{string_date(as_of_date)}.json'
    print(f'\n| Price data location: {filepath}')
    return {'parent_folder': folder,
            'root_folder': filepath}


# ----------------------------------------------  PRICE FUNCTIONS ----------------------------------------------
def get_conversion_ratios():
    '''Conversion ratios for various commodities.
    Returns: a dict of conversion ratios with keys => 'none' (i.e. 1:1), 'mmbtu/bbl', 'gal/bbl - energy', 'gal/mmbtu - energy',
    'gal/bbl - econ', 'gal/mmbtu - econ'
        '''
    global conversion_ratios
    conversion_ratios = {
        'none': 1 / 1,
        'mmbtu/bbl': 6 / 1,
        'gal/bbl - energy': 42 / 1,
        'gal/mmbtu - energy': 7 / 1,
        'gal/bbl - econ': 3 / 1,
        'gal/mmbtu - econ': 20 / 1
    }
    print(conversion_ratios)
    return conversion_ratios


def get_ngl_composite_dict(ethane_mode='recovery'):
    ngl_composite_labels = ['Theoretical Yield (Bbl/Mcf)', 'Fixed Recovery (Contractual)', 'Actual Yield (Bbl/Mcf)',
                            '% of Barrel']
    if ethane_mode == 'recovery':
        # fixed recov: {0.85;0.95;0.99;0.99;0.99}
        # act vol: {61.3214285713881;44.604761904694;15.6042857142621;4.38428571435643;17.2778571428336}
        # % of stream: {0.428244339542612;0.311501823218186;0.108974092505998;0.0306180984992042;0.120661646234}
        ngl_composite_data = list(
            zip([72.1428571428095, 46.9523809523095, 15.761904761881, 4.42857142864286, 17.4523809523571],
                [0.85, 0.95, 0.99, 0.99, 0.99],
                [61.3214285713881, 44.604761904694, 15.6042857142621, 4.38428571435643, 17.2778571428336],
                [0.428244339542612, 0.311501823218186, 0.108974092505998, 0.0306180984992042, 0.120661646234]))
    elif ethane_mode == 'rejection':
        # fixed recov: {0.4;0.9;0.97;0.97;0.97}
        # act vol: {28.8571428571238;42.2571428570786;15.2890476190245;4.29571428578357;16.9288095237864}
        # % of stream: {0.268119645073275;0.39262272778518;0.142054743306276;0.0399126620172709;0.157290221817999}
        ngl_composite_data = list(
            zip([72.1428571428095, 46.9523809523095, 15.761904761881, 4.42857142864286, 17.4523809523571],
                [0.4, 0.9, 0.97, 0.97, 0.97],
                [28.8571428571238, 42.2571428570786, 15.2890476190245, 4.29571428578357, 16.9288095237864],
                [0.268119645073275, 0.39262272778518, 0.142054743306276, 0.0399126620172709, 0.157290221817999]))
    global ngl_composite_dict
    ngl_composite_dict = OrderedDict()
    for idx, ngl in enumerate(ngl_list):
        ngl_composite_dict[ngl] = OrderedDict()
        for l_idx, label in enumerate(ngl_composite_labels):
            ngl_composite_dict[ngl][label] = ngl_composite_data[idx][l_idx]
    return ngl_composite_dict


def update_web_data():
    '''Pulls most recent web data from CME Group, and stores in csv dataframes "nymex" and "comex".'''

    global nymex
    global comex
    nymex = pd.read_csv(r'ftp://ftp.cmegroup.com/pub/settle/nymex_future.csv')
    comex = pd.read_csv(r'ftp://ftp.cmegroup.com/pub/settle/comex_future.csv')

    global nymex_trade_date
    global comex_trade_date
    nymex_trade_date = string_date(nymex['TRADEDATE'][0])
    comex_trade_date = string_date(comex['TRADEDATE'][0])

    print('\n| Updating NYMEX and COMEX data')
    product_descriptions = sorted(nymex['PRODUCT DESCRIPTION'].unique())
    print(f'\n| Data as of {nymex_trade_date}')
    print(f'| Products in current NYMEX data:\n {product_descriptions}')
    save_updated_prices(product_descriptions)


def save_updated_prices(product_descriptions: list):
    '''Saves new NYMEX and COMEX data to drive in price_data.json format.'''
    global nymex
    global comex
    global nymex_trade_date
    global comex_trade_date

    # save nymex and comex prices (raw)
    nymex_folder, nymex_filepath = (root_folder_nymex_data()['parent_folder'],
                                    root_folder_nymex_data()['root_folder'])
    nymex_filepath = nymex_filepath + f'/nymex_{nymex_trade_date}.json'
    save_to_json(nymex, nymex_folder, filepath=nymex_filepath)
    comex_folder, comex_filepath = (root_folder_comex_data()['parent_folder'],
                                    root_folder_comex_data()['root_folder'])
    comex_filepath = comex_filepath + f'/comex_{comex_trade_date}.json'
    save_to_json(comex, comex_folder, filepath=comex_filepath)

    # check that desired indexes are in nymex data
    not_found = []
    for c_name in commodity_reference:
        c_desc = get_comdty_desc(get_comdty_nick(c_name), print_result=False)
        if c_desc not in product_descriptions:
            not_found.append(c_desc)

    for c_desc in not_found:
        manual_nymex_update(product_description=c_desc, not_found=not_found)

    # update price_data_dict for today in the appropriate commodty folder
    for c_name in commodity_reference:
        # c_name = 'WTI Oil'
        c_nick = get_comdty_nick(c_name)
        c_code = get_comdty_code(c_nick)

        # check if prices have been updated. If not, update.
        test = get_price_data(c_nick, nymex_trade_date, nearest_prev=False)
        if len(test) == 0:
            try:
                print(f'\n >> Updating {c_nick}: {nymex_trade_date}...')
                data = nymex[nymex['PRODUCT SYMBOL'] == c_code]

                price_data = make_price_data(data)

                folder, filepath = (root_folder_price_data(c_nick, nymex_trade_date)['parent_folder'],
                                    root_folder_price_data(c_nick, nymex_trade_date)['root_folder'])
                save_to_json(price_data, folder, filepath)

            except (AttributeError, ValueError, FileNotFoundError, NameError):
                print(f'\n| Historical price data not found: {c_nick} >> {c_code} >> {as_of_date}')
        else:
            print(f'\n| Historical prices found for {c_nick} >> {nymex_trade_date}')
            print(test)
            print(test.info())


def make_price_data(data):
    '''Returns a dataframe of standard format price_data using CME format dataframe "data".'''
    # reset index
    data = data.reset_index().drop(columns='index')
    trade_dates = pd.Series([string_date(_) for _ in data['TRADEDATE']], name='Trade Date')

    data['CONTRACT YEAR'] = data['CONTRACT YEAR'].astype(int)
    data['CONTRACT MONTH'] = data['CONTRACT MONTH'].astype(int)

    contract_dates = pd.Series(
        [string_date(pd.to_datetime(f'{y}/{m}/20') + MonthEnd(0)) for y, m in zip(
            data['CONTRACT YEAR'], data['CONTRACT MONTH']
        )
         ],
        name='Contract Date'
    )

    price_data = {'comdty_code': data['PRODUCT SYMBOL'],
                  'comdty_desc': data['PRODUCT DESCRIPTION'],
                  'trade_date': trade_dates,
                  'contract_date': contract_dates,
                  'contract_year': data['CONTRACT YEAR'],
                  'contract_mth': data['CONTRACT MONTH'],
                  'future_mth_idx': data.index,
                  'settle_price': data['SETTLE'],
                  'open_interest': data['PRIOR INT'],
                  'volume': data['EST. VOL'],
                  'last_trade_date': '2999-12-31'}

    price_data = pd.DataFrame(price_data)
    return price_data


# todo: finish this function and replicate the manual price data function for the generic historical settlement file
def make_price_data_from_alt_source(data):
    '''Returns a dataframe of standard format price_data using CME format dataframe "data" for settlement dates prior to last trading day.'''
    # reset index
    data = data.reset_index().drop(columns='index')
    trade_dates = pd.Series([string_date(_) for _ in data['BizDt']], name='Trade Date')

    # standardize symbol/c_code references ("Sym" column in nymex.settle.[date].s
    nymex_sym_to_c_code_ref = {
        'CSX': 'CS',
        'CL': 'CL',
        'WTT': 'WTT',
        'FF': 'FF',
        'CY': 'CY',
        'HCL': 'HCL',
        'NG': 'NG',
        'NW': '',
        'NHN': 'NHN',
        'AC0': 'C0',
        'B0': 'B0',
        'A8I': '8I',
        'A7Q': '7Q'
    }

    # replace the "Sym" column with the c_code reference
    for sym, c_code in nymex_sym_to_c_code_ref.items():
        print(f'| Replacing {sym} with {c_code}')
        print(data['Sym'])
        data['Sym'] = [nymex_sym_to_c_code_ref[sym] for _ in data['Sym']]
        print(data['Sym'])

    # todo: START HERE >> add a product description column
    # data['PRODUCT DESCRIPTION'] = [get_comdty_nick() for c_code in data['Sym']]

    data['CONTRACT YEAR'] = data['MMY'].astype(int)[:4]
    data['CONTRACT MONTH'] = data['MMY'].astype(int)[4:]

    contract_dates = pd.Series(
        [
            string_date(pd.to_datetime(f'{y}/{m}/20') + MonthEnd(0)) for y, m in zip(
            data['CONTRACT YEAR'], data['CONTRACT MONTH']
        )
        ],
        name='Contract Date'
    )
    price_data = {'comdty_code': data['Sym'],
                  'comdty_desc': data['PRODUCT DESCRIPTION'],
                  'trade_date': trade_dates,
                  'contract_date': contract_dates,
                  'contract_year': data['CONTRACT YEAR'],
                  'contract_mth': data['CONTRACT MONTH'],
                  'future_mth_idx': data.index,
                  'settle_price': data['SETTLE'],
                  'open_interest': data['PRIOR INT'],
                  'volume': data['EST. VOL'],
                  'last_trade_date': '2999-12-31'}

    price_data = pd.DataFrame(price_data)
    return price_data


def manual_nymex_update(product_description: str, not_found: list):
    '''Allows entering of NYMEX futures prices manually if price index is not found in FTP file.'''
    global nymex_trade_date
    trade_date = nymex_trade_date
    filepath = root_folder_nymex_data()['root_folder']
    filename = f'/nymex_{nymex_trade_date}.json'

    print(f'\n!! Not found in current NYMEX data: {not_found}')

    # get the commodity code and product symbol from the commodity reference
    c_nick = get_comdty_nick(search_term=product_description,
                             search_term_type='comdty_desc',
                             print_result=True)
    c_code = get_comdty_code(c_nick)
    product_symbol = c_code

    _q = input(
        f'>>> Search existing data for {product_description} (will roll forward prior day if not found)? Y/N >>> ')
    if _q.lower() == 'y':
        prior_prices = dict(get_price_data(c_nick=c_nick, as_of_date=trade_date, nearest_prev=True))
        futures_months = pd.to_datetime(prior_prices['contract_date'].values, utc=True)
        settle_prices = [_ for _ in prior_prices['settle_price'].values]
    else:
        futures_start = input(f'| Enter futures start month for {product_symbol} (m/d/yyyy) >>> ')
        num_months = int(input(f'| Number of futures months for {product_symbol} (int) >>> '))
        futures_months = pd.date_range(start=futures_start, periods=num_months, freq='M', tz='UTC')
        settle_prices = []
        for _month in futures_months:
            _settle_p = input(
                f'|-- Enter settlement price for {product_symbol} | futures month: {string_date(_month)} >>> ')
            settle_prices.append(float(_settle_p))

    # make the dataframe
    futures_prices = pd.DataFrame(
        index=futures_months,
        data=settle_prices,
        columns=[product_symbol]
    )
    print(f'|-- Futures prices for {product_symbol} >>> {futures_prices}')

    CME_month_codes = {
        1: 'F',
        2: 'G',
        3: 'H',
        4: 'J',
        5: 'K',
        6: 'M',
        7: 'N',
        8: 'Q',
        9: 'U',
        10: 'V',
        11: 'X',
        12: 'Z',
    }

    global nymex
    for contract_date in futures_prices.index:
        column_data = {
            'PRODUCT SYMBOL': product_symbol,
            'CONTRACT MONTH': str(int(contract_date.month)),
            'CONTRACT YEAR': str(int(contract_date.year)),
            'CONTRACT DAY': str(int(contract_date.day)),
            'CONTRACT': product_symbol + CME_month_codes[int(contract_date.month)] + str(
                np.mod(int(contract_date.year), 100)),
            'PRODUCT DESCRIPTION': product_description,
            'OPEN': np.nan,
            'HIGH': np.nan,
            'HIGH AB INDICATOR': np.nan,
            'LOW': np.nan,
            'LOW AB INDICATOR': np.nan,
            'LAST': np.nan,
            'LAST AB INDICATOR': np.nan,
            'SETTLE': futures_prices.loc[contract_date, product_symbol],
            'PT CHG': np.nan,
            'EST. VOL': np.nan,
            'PRIOR SETTLE': np.nan,
            'PRIOR VOL': np.nan,
            'PRIOR INT': np.nan,
            'TRADEDATE': trade_date
        }

        # index to which this data is to be added
        _nymex_index = len(nymex.index)
        for col_name in column_data:
            nymex.loc[_nymex_index, col_name] = column_data[col_name]
            print(nymex.loc[_nymex_index, col_name])

    nymex.to_json(filepath + filename)
    _continue = input(f'>>> Hit enter to continue.')
    return nymex


def get_price_data(c_nick, as_of_date, nearest_prev=True):
    '''Gets the historical EOD futures settlement prices for a commodity.
    Args:
         \n c_nick, str: the nickname for the commodity
         \n as_of_date, datetime: the trade date for the settlement prices
         \n nearest_prev, bool: if the as_of_date arg is not in the historical data, will return the nearest previous date
    Returns:
         \n A dataframe of historical settlement prices for the strip
         '''
    c_code = get_comdty_code(c_nick)
    as_of_date = string_date(as_of_date)
    filepath = root_folder_price_data(c_nick, as_of_date)['root_folder']
    if os.path.isfile(filepath):
        results = pd.read_json(filepath)
        return results
    else:
        if nearest_prev:
            as_of_date = string_date(pd.to_datetime(as_of_date) - BDay(1))
            print(f'\n| Returning previous business day: {as_of_date}')
            results = get_price_data(c_nick, as_of_date, nearest_prev)
        else:
            print(f'\n| Historical price data not found: {c_nick} >> {c_code} >> {as_of_date}')
            results = pd.DataFrame()
    return results


def get_price_data_cme(c_nick, as_of_date):
    '''Returns a tuple of (_raw_price_data, as_of_date), where as_of_date is the nearest preceding settlement, if
    the passed as_of_date is a holiday or not available in the historical CME data.
    Arguments: c_nick = commodity nickname per the commodity_reference; as_of_date = trading date requested.
    '''
    date_limit = pd.to_datetime('10/21/2019')
    c_code = get_comdty_code(c_nick)
    day = pd.to_datetime(as_of_date).day
    month = pd.to_datetime(as_of_date).month
    year = pd.to_datetime(as_of_date).year
    # multiple source files - f = final, p = preliminary, e = early report
    global hist_data_filepath
    hist_data_filepath = r'C:/Users/vdesai/Desktop/Model/Python/___Pricing Model/historical pricing file/CME Data/{0}/{1:0>2d}/{2:0>2d}/EOD/XNYM/{0}{1:0>2d}{2:0>2d}-EOD_xnym_{3}_fut_0-eth_f.csv.gz'.format(
        year, month, day, c_code.lower())

    if pd.to_datetime(as_of_date) <= date_limit:
        try:
            with gzip.open(hist_data_filepath, 'rb') as f:
                df = pd.read_csv(f, sep=',')
                return (df, as_of_date)
        except (FileNotFoundError, pd.io.common.EmptyDataError):
            print(f"\n| File Not Found: {c_code} >> {string_date(as_of_date)}.")
    else:
        print(f"\n| End of dataset reached or date is after 10/21/2019.")


def get_dates(c_nick, date_type='start'):
    '''Returns price history dates for c_nick ('start' or 'end').'''

    def has_date(input_str):
        '''checks if an input_string has a date in it.'''
        years = [f'{_:4d}' for _ in range(1800, 2400)]
        months = [f'{_:02d}' for _ in range(1, 13)]
        days = [f'{_:02d}' for _ in range(1, 32)]
        (has_yr, has_mth, has_day) = ([_ for _ in years if input_str.find(str(_)) != -1],
                                      [_ for _ in months if input_str.find(str(_)) != -1],
                                      [_ for _ in days if input_str.find(str(_)) != -1])
        if all([_ != [] for _ in (has_yr, has_mth, has_day)]):
            return True
        else:
            return False

    c_code = get_comdty_code(c_nick)
    global nymex_trade_date
    try:
        filepath = root_folder_price_data(c_nick, as_of_date=nymex_trade_date)['parent_folder']
    except NameError:
        nymex_trade_date = input(f'| Enter trade date (m/d/yy) >> ')
        nymex_trade_date = pd.to_datetime(nymex_trade_date, utc=True)
        filepath = root_folder_price_data(c_nick, as_of_date=nymex_trade_date)['parent_folder']

    if date_type in ['start', 'end']:
        prices_available = [_ for _ in os.listdir(filepath)]
        min_date = min([_.partition(
            f'_prices_{c_code}_')[2].partition('.json')[0] for _ in prices_available if _.partition(
            f'_prices_{c_code}_')[2].partition('.json')[0] != ''])
        max_date = max([_.partition(
            f'_prices_{c_code}_')[2].partition('.json')[0] for _ in prices_available if _.partition(
            f'_prices_{c_code}_')[2].partition('.json')[0] != ''])
    else:
        raise Exception(TypeError, 'Invalid date_type passed. Pass either "start" or "end".')

    if date_type == 'start':
        if has_date(min_date):
            print(f'Prices start >> {c_nick}: {c_code} >> {string_date(min_date)}')
            return string_date(min_date)
        else:
            print(f'| Invalid min_date found: {min_date}')
    elif date_type == 'end':
        if has_date(max_date):
            print(f'Prices end >> {c_nick}: {c_code} >> {string_date(max_date)}')
            return string_date(max_date)
        else:
            print(f'| Invalid max_date found: {max_date}')


def get_final_price_for_contract(c_nick, as_of_date, contract_date='6/30/2020', max_days_searched=250):
    '''Returns the last settlement dataframe for this contract if in the past.'''
    as_of_date = string_date(as_of_date)
    contract_date = string_date(contract_date)
    futures_df = get_price_data(c_nick, as_of_date=as_of_date)
    print('\n' + contract_date)
    print(futures_df)

    if any([_ == contract_date for _ in futures_df['contract_date']]):
        # display.clear_output(wait = True)
        tr_d = futures_df['trade_date'].iloc[0]
        c_name = futures_df['comdty_desc'].iloc[0]
        print(f'\n| Last trade date: {c_name} | {contract_date} contract >> {tr_d}')
    else:
        print(f'\n| NOT FOUND >> Contract date {contract_date}  on {as_of_date}')
        # check prior trade day
        as_of_date = string_date(pd.to_datetime(as_of_date) - BDay(1))
        print(f'| Trying {as_of_date}...')
        # re-run function if the contract is not more than 4 futures months out
        if max_days_searched > 0:
            time_delta = pd.to_timedelta(pd.to_datetime(contract_date) - pd.to_datetime(as_of_date), unit='d')
            if time_delta < pd.to_timedelta(120, unit='d'):
                futures_df = get_final_price_for_contract(c_nick, as_of_date, contract_date,
                                                          max_days_searched=max_days_searched - 1)
        else:
            print(f'| max_days_searched limit reached.')
    return futures_df


def get_model_prices(strip_pricing_date='7/17/20',
                     start_date='default',
                     ethane_mode='recovery',
                     output_to_excel=True
                     ):
    '''Returns a dataframe of strip pricing as of strip_pricing_date for all
    keys in commodity_reference.
    Args:
        | -- strip_pricing_date, str: strip pricing date, in string format ('m/d/yy')
        | -- start_date, str (date): date in string format, or 'default'. 'default'
            will return a model_period beginning at the start of the trade month prior
            to the latest NYMEX trade date.
        | -- ethane_mode, str: 'rejection' or 'recovery'. Will adjust NGL composite prices
            for ethane rejection or recovery modes, respectively. See documentations for
            get_ngl_composite_dict() for additional info.
        '''
    as_of_date = strip_pricing_date  # '7/18/20'

    global model_prices
    global model_prices_excluded
    global hist_final_settle
    global futures_df

    if 'model_prices' in globals() and model_prices[
        'as_of_date'].iloc[0] == string_date(strip_pricing_date):
        # model_prices already exists
        # and as_of_date == strip_pricing_date
        return model_prices
    else:
        model_period = get_model_period(months=120, start_date=start_date)
        model_prices = pd.DataFrame(index=model_period, columns=commodity_reference.keys())
        model_prices = model_prices.reset_index()
        model_prices.rename(columns={'index': ''}, inplace=True)
        model_prices['as_of_date'] = [string_date(as_of_date) for _ in model_period]
        model_prices.set_index('', inplace=True)
        model_prices = pd.DataFrame(model_prices.iloc[:, -1]).join(model_prices.iloc[:, :-1])
        for c_name in commodity_reference:
            c_nick = get_comdty_nick(c_name)
            if c_nick not in model_prices_excluded:
                futures_df = get_price_data(c_nick, as_of_date=as_of_date).loc[
                             :, ['contract_date', 'settle_price']
                             ]
                futures_df.rename(columns={'contract_date': '',
                                           'settle_price': c_name}, inplace=True)
                futures_df.set_index('', inplace=True)
                print(futures_df)

                date_range = tuple({_ for _ in model_prices.index if _ in futures_df.index})
                model_prices.loc[date_range, c_name] = futures_df.loc[date_range, c_name]
                model_prices = model_prices.ffill(axis=0)

                global nan_values
                nan_values = model_prices[c_name][model_prices[c_name].isna()]
                print(model_prices, nan_values)

                if len(nan_values.index) > 0:
                    for idx in nan_values.index:
                        hist_final_settle = get_final_price_for_contract(
                            c_nick,
                            as_of_date=as_of_date,
                            contract_date=idx)

                        # print(hist_final_settle)
                        try:
                            model_prices.loc[idx, c_name] = hist_final_settle[
                                hist_final_settle['contract_date'] == string_date(idx)
                                ]['settle_price'].values.squeeze()

                        except ValueError:
                            print(f'!! Contract date not found: {idx}')
                else:
                    print(f'| Excluding: {c_name}')

        # add WTI midland, waha and hsc gas prices
        model_prices['WTI Midland (CL-WTT)'] = model_prices['WTI Oil'] + model_prices['MidCush - WTT']
        model_prices['Waha Gas'] = model_prices['HH Gas'] + model_prices['Waha Diff']
        model_prices['HSC Gas'] = model_prices['HH Gas'] + model_prices['HSC Gas Diff']

        # add ratios
        conv_ratios = get_conversion_ratios()
        model_prices['WTI Oil:HH Gas'] = model_prices['WTI Oil'] / (model_prices['HH Gas'] * conv_ratios[
            'mmbtu/bbl'])
        model_prices['Ethane:WTI Oil'] = model_prices['Ethane Mt.Belvieu'] * conv_ratios[
            'gal/bbl - energy'] / model_prices['WTI Oil']
        model_prices['Propane:WTI Oil'] = model_prices['Propane Mt.Belvieu LDH'] * conv_ratios[
            'gal/bbl - energy'] / model_prices['WTI Oil']
        model_prices['n-Butane:WTI Oil'] = model_prices['n-Butane'] * conv_ratios[
            'gal/bbl - energy'] / model_prices['WTI Oil']
        model_prices['iso-Butane:WTI Oil'] = model_prices['iso-Butane'] * conv_ratios[
            'gal/bbl - energy'] / model_prices['WTI Oil']
        model_prices['Nat. Gasoline:WTI Oil'] = model_prices['Nat. Gasoline'] * conv_ratios[
            'gal/bbl - energy'] / model_prices['WTI Oil']

        model_prices['Ethane:HH Gas'] = model_prices['Ethane Mt.Belvieu'] * conv_ratios[
            'gal/mmbtu - energy'] / model_prices['HH Gas']
        model_prices['Propane:HH Gas'] = model_prices['Propane Mt.Belvieu LDH'] * conv_ratios[
            'gal/mmbtu - energy'] / model_prices['HH Gas']
        model_prices['n-Butane:HH Gas'] = model_prices['n-Butane'] * conv_ratios[
            'gal/mmbtu - energy'] / model_prices['HH Gas']
        model_prices['iso-Butane:HH Gas'] = model_prices['iso-Butane'] * conv_ratios[
            'gal/mmbtu - energy'] / model_prices['HH Gas']
        model_prices['Nat. Gasoline:HH Gas'] = model_prices['Nat. Gasoline'] * conv_ratios[
            'gal/mmbtu - energy'] / model_prices['HH Gas']

        # NGL Composite
        try:
            ngl_comp_dict = get_ngl_composite_dict(ethane_mode=ethane_mode)
        except (ValueError, KeyError):
            e_m = input(
                f'!! Invalid argument passed: ethane_mode must be "recovery" or "rejection". Enter choice: ')
            ngl_comp_dict = get_ngl_composite_dict(ethane_mode=e_m)

        barrel_pct = {ngl: ngl_composite_dict[ngl]['% of Barrel'] for ngl in ngl_composite_dict}
        barrel_pct = pd.DataFrame(barrel_pct.items()).T
        barrel_pct.columns = barrel_pct.loc[0, :]
        barrel_pct.drop(index=[0], inplace=True)
        barrel_pct.reset_index(inplace=True, drop=True)

        global ngl_prices
        ngl_prices = model_prices.loc[:, [_ for _ in ngl_composite_dict]]
        ngl_prices = ngl_prices * barrel_pct.values
        ngl_prices[f'NGL Composite (eth. {ethane_mode})'] = ngl_prices.sum(axis=1)

        model_prices[f'NGL Composite (eth. {ethane_mode})'] = ngl_prices[f'NGL Composite (eth. {ethane_mode})']
        model_prices.ffill(axis=0, inplace=True)
        if output_to_excel:
            save_to_excel(
                model_prices.reset_index().copy(deep=True),
                folder='C:/Users/vdesai/Desktop/Model/Python/', filename='TCR - Model Prices.xlsx')

            folder_network = r'\/FILE01\/TDrive\/Finance-Strategy\/Daily_Price_Updates\/'
            try:
                save_to_excel(
                    model_prices.reset_index().copy(deep=True),
                    folder=folder_network, filename='TCR - Model Prices.xlsx')
            except (OSError, PermissionError):
                _q = input("Save to network folder failed. Try again? Y/N")
                if _q.lower() == 'y':
                    save_to_excel(
                        model_prices.reset_index().copy(deep=True),
                        folder=folder_network, filename='TCR - Model Prices.xlsx')
                else:
                    print("!! File not saved to network drive.")

        return model_prices


def get_model_period(months=36, start_date='default'):
    '''Returns monthly model format DateTimeIndex.
    Args:
        | -- months, int: number of months to return for model_period index
        | -- start_date, str/string date: date in string format, or 'default'. 'default'
            will return a model_period beginning at the start of the trade month prior
             to the latest NYMEX trade date.
    '''
    # model start date and projection period
    global model_start
    if start_date == 'default':
        model_start = pd.to_datetime(nymex_trade_date, utc=True) + MonthEnd(-1)
    else:
        model_start = pd.to_datetime(start_date, utc=True) + MonthEnd(1)
    global forecast_months
    forecast_months = months  # 25 years
    global model_period
    model_period = pd.date_range(start=model_start,
                                 periods=forecast_months,
                                 freq='M',
                                 tz='UTC')

    print(f'| Projection period >>\n{model_period}')
    return model_period


# ------------------------------------- MONTE CARLO DATA-MAKER --------------------------------------
@timer
def run_mcs_data_maker(c_nick=None):
    '''Updates MCS prices for c_nick if there is new data available. If c_nick is None, will udpate for all commodities.'''

    def data_maker(c_nick):
        # get latest historical settlement data for MCS and filepath
        c_code = get_comdty_code(c_nick)
        c_name = get_comdty_name(c_nick)

        mcs_data = get_mcs_data_historical(c_nick)
        mcs_data.drop(index=[mcs_data.index[-1]], inplace=True)

        mcs_folder, mcs_filepath = (root_folder_mcs_data(c_nick)['parent_folder'],
                                    root_folder_mcs_data(c_nick)['root_folder'])
        current_mcs_data_end = max(mcs_data.index)

        earliest_date = pd.to_datetime(get_dates(c_nick, date_type='start'))
        latest_date = pd.to_datetime(get_dates(c_nick, date_type='end'))

        # if latest data is more recent than latest MCS data
        if current_mcs_data_end < latest_date:
            # update master MCS data with new dates
            for td in pd.date_range(current_mcs_data_end + BDay(1), latest_date, freq='B'):
                price_data = get_price_data(c_nick, as_of_date=td, nearest_prev=False)
                if len(price_data) != 0:
                    price_data = price_data.iloc[0]
                    mcs_data.loc[td] = price_data
                    print(td, price_data)

            # save to a new file
            f = root_folder_mcs_data(c_nick)['root_folder']

            mcs_data_filepath = f + f'_mcs_prices_{c_code}_{string_date(earliest_date)}_{string_date(latest_date)}.json'
            mcs_data.index.name = '_settlement_at'  # need _at suffix for index name so pd.read_json can convert dates

            try:
                mcs_data.to_json(mcs_data_filepath)
                print(f'\n>>>> MCS data updated for {c_name}-{c_code} at {mcs_data_filepath}')
            except (FileNotFoundError, FileExistsError, PermissionError):
                print(f'!! MCS data file not saved.')
        else:
            print(f'| Latest MCS data is same as latest price data. No update needed.')

    if c_nick is None:
        # update all
        for c_name in commodity_reference:
            c_nick = get_comdty_nick(c_name)
            data_maker(c_nick)
    else:
        data_maker(c_nick)


def get_mcs_data_historical(c_nick):
    '''Returns a dataframe of Monte Carlo Simulation data for commodity.'''
    # c_nick = 'wti'
    c_code = get_comdty_code(c_nick)
    # get the latest mcs_prices for commodity
    mcs_folder, mcs_filepath = (root_folder_mcs_data(c_nick)['parent_folder'],
                                root_folder_mcs_data(c_nick)['root_folder'])
    try:
        print(f'\n| MCS Price Scenarios available for {c_nick}:')
        available_mcs_data = [_ for _ in os.listdir(mcs_filepath)][-1]
        print(available_mcs_data)
        results = pd.read_json(mcs_filepath + available_mcs_data, convert_dates=True)

        print(results)
        return results
    except IndexError:
        print(f'!! Error: No MCS data found for {c_nick}')


# ------------------------------------- DAILY PRICE UPDATE CHARTS --------------------------------------
@timer
def update_daily_prices(c_nick='wti',
                        update_all=True,
                        start_date=None,
                        futures_months=24,
                        days_of_historical_futures=30,
                        fm_idx=0):
    global email_filepaths
    email_filepaths = {}

    global image_filepaths
    image_filepaths = {}
    # months_to_attach = {commodity: months}
    global months_to_attach
    months_to_attach = {'wti_cma': futures_months,
                        'wti': futures_months,
                        'midcush_wtt': futures_months,
                        'midcush_ff': futures_months,
                        'brent': futures_months,
                        'wti_hou': futures_months,
                        'hh': futures_months,
                        'waha_gas_diff': futures_months,
                        'hsc_gas_diff': futures_months,
                        'ethane': futures_months,
                        'propane': futures_months,
                        'n_butane': futures_months,
                        'iso_butane': futures_months,
                        'nat_gasoline': futures_months}

    global price_chart_data
    price_chart_data = OrderedDict()

    if update_all:
        for c_nick in months_to_attach:
            daily_price_update(c_nick, start_date, futures_months, days_of_historical_futures, fm_idx)
    else:
        daily_price_update(c_nick, start_date, futures_months, days_of_historical_futures, fm_idx)


def daily_price_update(c_nick,
                       start_date,
                       futures_months,
                       days_of_historical_futures,
                       fm_idx):
    if start_date is None:
        default_start_date = '1/1/2003'
    else:
        default_start_date = start_date

    # futures month for historical requested_chart --> 0 = first futures month
    futures_month = fm_idx
    c_name = get_comdty_name(c_nick)
    c_unit = get_comdty_unit(c_nick)
    print(c_name, c_unit)

    # request field adjustment
    hh_start_date = '1/1/2009'
    ic4_start_date = '10/22/2019'
    wti_hou_start_date = '11/5/2018'

    if c_nick == 'iso_butane' and start_date < ic4_start_date:
        default_start_date = ic4_start_date
    elif c_nick == 'wti_hou' and start_date < wti_hou_start_date:
        default_start_date = wti_hou_start_date
    elif c_nick == 'hh' and start_date < hh_start_date:
        default_start_date = hh_start_date
    else:
        default_start_date = default_start_date

    # make requested_chart data
    chart_data = namedtuple('chart_data', 'title x y x_name y_name')

    global chart_data_dict
    chart_data_dict = OrderedDict()

    # price history dict --> {c_name : {trade_date: price_dict}}
    global price_history
    price_history = OrderedDict()

    earliest_date = get_dates(c_nick, 'start')
    latest_date = get_dates(c_nick, 'end')
    start = max(string_date(default_start_date), earliest_date)
    end = latest_date
    price_history[c_name] = OrderedDict()
    chart_date_range = pd.date_range(start, end, freq='B')

    for td in chart_date_range:
        price = get_price_data(c_nick, as_of_date=td, nearest_prev=True)
        price = dict(price)

        price = {d: price[d][futures_month] for d, v in price.items()}

        if c_nick not in excluded_prices:
            price_history[c_name][string_date(td)] = price
        elif price['settle_price'] not in excluded_prices[c_nick]:
            price_history[c_name][string_date(td)] = price

    print(f'| Price history length: {len(price_history[c_name])}')

    chart_data_dict[f'Month {futures_month + 1} | L30 Days'] = chart_data(
        title=f'{c_name} | Last 60 days',
        x=list(price_history[c_name].keys())[-60:],
        y=[v['settle_price'] for k, v in price_history[c_name].items()][-60:],
        x_name='Trade Date',
        y_name=f'Futures Month #{futures_month + 1} Settlement ({c_unit})'
    )

    chart_data_dict[f'Month {futures_month + 1}'] = chart_data(
        title=f'{c_name} | {string_date(start)} to {string_date(latest_date)}',
        x=list(price_history[c_name].keys()),
        y=[v['settle_price'] for k, v in price_history[c_name].items()],
        x_name='Trade Date',
        y_name=f'Futures Month #{futures_month + 1} Settlement ({c_unit})'
    )

    global futures_to_attach
    futures_to_attach = OrderedDict()

    global months_to_attach
    # for each day of historical futures requested
    for trade_date_idx in range(days_of_historical_futures):
        try:
            trade_date = chart_date_range[trade_date_idx - days_of_historical_futures]
            # get the no. of futures months from the months_to_attach dict
            price = get_price_data(c_nick, as_of_date=trade_date, nearest_prev=False)
            if len(price) > 0:
                print(f'| Price data found: trade_date_idx: {trade_date_idx} >> {trade_date}')
                months_req = months_to_attach[c_nick]
                price = price.iloc[:months_req]

                # make strip pricing for each trade date
                # futures to attach = {trade_date: chart_data(title, x, y, x_name, y_name)}
                trade_date_key = string_date(trade_date)
                futures_to_attach[trade_date_key] = chart_data(
                    title=f"{trade_date_key} Futures",
                    x=[string_date(pd.to_datetime(_) + MonthBegin(-1)) for _ in price['contract_date']],
                    y=[_ for _ in price['settle_price']],
                    x_name='',
                    y_name=''
                )
        except IndexError:
            print(f'| trade_date not found in chart_data_range')

    # for heatmap
    # T-x days for price changes
    heatmap_t_minus_days = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 60, 90]
    current_futures = []
    prior_heatmap_futures = {}
    heatmap_data = []
    heatmap_x_labels = [f'Month {_ + 1}' for _ in range(months_to_attach['wti_cma'])]
    heatmap_y_labels = []

    # index the futures to attach
    for idx, key in enumerate(futures_to_attach):
        t_minus_days = len(futures_to_attach) - 1 - idx
        if t_minus_days in heatmap_t_minus_days:
            print(f'{t_minus_days} FOUND in {heatmap_t_minus_days}')
            # save the prior futures for heatmap calculations
            prior_heatmap_futures[key] = [_ for _ in futures_to_attach[key].y]
            # update the y-labels
            heatmap_y_labels.append(f'T-{t_minus_days} days')
        elif idx == len(futures_to_attach) - 1:
            # save the current futures
            current_futures = [_ for _ in futures_to_attach[key].y]
        else:
            print(f'{t_minus_days} not found in {heatmap_t_minus_days}')

    # update heatmap chart data
    for idx, td in enumerate(prior_heatmap_futures):
        price_change = [curr - prior for curr, prior in zip(current_futures, prior_heatmap_futures[td])]
        heatmap_data.append(price_change)

    heatmap_chart_data = {
        'data': heatmap_data,
        'x_labels': heatmap_x_labels,
        'y_labels': heatmap_y_labels
    }

    # add this heatmap chart's data to the master heatmap data
    master_heatmap_data[c_nick] = heatmap_chart_data

    # run charts
    daily_price_charts(c_nick, chart_data_dict, futures_to_attach, heatmap_chart_data)


def run_master_heatmap_charts(master_heatmap_data: dict):
    '''Builds the master heatmap chart.'''

    number_of_charts = len(master_heatmap_data)
    # chart coordinates dictionary
    chart_coordinates = line_to_grid(linear_range=range(number_of_charts), grid_shape=[number_of_charts, 3])

    # CHART DEFAULTS
    chart_rows = max([r for r, c in chart_coordinates.values()])
    chart_cols = max([c for r, c in chart_coordinates.values()])
    _grid_color = 'rgba(220,220,220,1)'
    start_color = [180, 180, 180]  # [225, 36, 0]
    end_color = [100, 100, 100]

    # for whole figure
    figure_width = _fig_width*3/2
    figure_height = _fig_width*3/2

    _subplot_titles = [f'{get_comdty_name(c_nick)} | {get_comdty_code(c_nick)} | {get_comdty_unit(c_nick)}' for c_nick in master_heatmap_data]
    heatmap_fig = make_subplots(
        rows=chart_rows,
        cols=chart_cols,
        vertical_spacing=_vertical_spacing,
        subplot_titles=_subplot_titles,
        specs=[
            [{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
            [{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
            [{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
            [{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
            [{'type': 'xy'}, {'type': 'xy'}, None]
        ]
    )

    # annotations should extend titles for subplots (also stored as annotations)
    annotations = [_ for _ in heatmap_fig.layout.annotations]
    for idx, (c_nick, heatmap_chart_data) in enumerate(master_heatmap_data.items()):
        # identifiers
        c_name = get_comdty_name(c_nick, print_result=True)
        c_code = get_comdty_code(c_nick, print_result=True)
        c_unit = get_comdty_unit(c_nick, print_result=True)

        # chart position
        _chart_row = chart_coordinates[idx][0]
        _chart_col = chart_coordinates[idx][1]

        _ref = "" if idx == 0 else str(idx + 1)
        _xref = 'x' + _ref
        _yref = 'y' + _ref

        # annotations for datapoints
        for t_minus_period, row in enumerate(heatmap_chart_data['data']):
            count = 0
            y_val = heatmap_chart_data['y_labels'][t_minus_period]
            for futures_month, val in enumerate(row):
                x_val = heatmap_chart_data['x_labels'][futures_month]
                count += 1
                print(f'--- {x_val} {y_val} --> annotation count: {count} >> xref = {_xref}, yref = {_yref}')
                annotations.append(
                    go.layout.Annotation(
                        text=f"{val: .2f}",
                        x=x_val,
                        y=y_val,
                        xref=_xref,
                        yref=_yref,
                        showarrow=False,
                        bgcolor='rgba(255,255,255,0.90)'
                    )
                )


        # update heatmap fig
        heatmap_fig.add_heatmap(
            z=heatmap_chart_data['data'],
            zmid=0.0,
            x=heatmap_chart_data['x_labels'],
            y=heatmap_chart_data['y_labels'],
            colorscale='thermal',
            reversescale=False,
            colorbar=dict(x=0.43, title='$ Change', thickness=15),
            showscale=False,
            row=_chart_row,
            col=_chart_col
        )


        heatmap_fig.update_xaxes(dict(side='bottom', tickangle=-45),
                                 row=_chart_row,
                                 col=_chart_col
                                 )

        # Update xaxis properties
        heatmap_fig.update_xaxes(nticks=20,
                                 tickangle=-45,
                                 tickformat='$,.2f\xa0',
                                 tickfont_size=_font_size,
                                 gridcolor=_grid_color,
                                 row=_chart_row,
                                 col=_chart_col
                                 )
        # Update yaxis properties
        heatmap_fig.update_yaxes(nticks=20,
                                 tickfont_size=_font_size,
                                 linecolor='rgba(10,10,10,0.75)',
                                 zeroline=True,
                                 zerolinecolor='rgba(15,15,15,0.75)',
                                 gridcolor=_grid_color,
                                 row=_chart_row,
                                 col=_chart_col
                                 )

    global nymex_trade_date
    heatmap_fig.update_layout(
        title=f'Commodity Heatmaps >> As of {string_date(nymex_trade_date)}',
        title_xanchor='left',
        title_yanchor='top',
        annotations=annotations,
        plot_bgcolor='rgba(0,0,0,0)',
        width=figure_width,
        height=figure_height,
        showlegend=False,
        legend=dict(orientation='v',
                    y=1.00,
                    x=1.05,
                    font_size=_font_size))

    folder_local = root_folder_daily_prices()['root_folder']
    folder_network = r'\/FILE01\/TDrive\/Finance-Strategy\/daily_price_updates\/'
    filename_htm = f'commodity_heatmaps_as_of_{string_date(nymex_trade_date)}.html'
    filename_png = f'commodity_heatmaps_as_of_{string_date(nymex_trade_date)}.png'
    filename_eml = f'commodity_heatmaps.html'  # no dates allowed

    global email_filepaths
    global image_filepaths

    email_filepaths['commodity_heatmaps'] = folder_network + filename_eml
    image_filepaths['commodity_heatmaps'] = (folder_local + filename_png, folder_network + filename_png)

    print(image_filepaths, email_filepaths)
    heatmap_fig.write_html(folder_local + filename_htm, include_plotlyjs='True')

    try:
        heatmap_fig.write_html(folder_network + filename_eml, include_plotlyjs='True')
    except (OSError, FileNotFoundError):
        print(f'!! File not found or network folder not accessible.')

    scope = PlotlyScope()
    #     with open(folder_network+filename_png, "wb") as f:
    #         f.write(scope.transform(heatmap_fig, format="png", width = 1600, height = 950))

    with open(folder_local + filename_png, "wb") as f:
        f.write(scope.transform(heatmap_fig, format="png", width=figure_width, height=figure_height))
    heatmap_fig.show()


def daily_price_charts(c_nick, chart_data_dict, futures_to_attach, heatmap_chart_data):
    fig = make_subplots(rows=3,
                        cols=2,
                        vertical_spacing=_vertical_spacing,
                        specs=[
                            [{'type': 'xy'}, {'type': 'xy'}],
                            [{}, {'type': 'xy'}],
                            [{'type': 'table'}, None]
                        ]
                        )
    # default requested_chart formatting
    _grid_color = 'rgba(220,220,220,1)'
    start_color = [180, 180, 180]  # [225, 36, 0]
    end_color = [100, 100, 100]

    annotations = []

    c_name = get_comdty_name(c_nick)
    c_unit = get_comdty_unit(c_nick)

    start = dict_drill_down(chart_data_dict, key_sequence=[1], levels=1).x[0]
    end = dict_drill_down(chart_data_dict, key_sequence=[1], levels=1).x[-1]

    # chart_data_dict keys are historical settlement identifiers. idx == 1 is typically the full history
    for chart_data_idx, _ in enumerate(chart_data_dict):
        # get summary stats for th bi
        stats = pd.DataFrame(chart_data_dict[_].y, columns=[''])
        stats = stats.describe(percentiles=[0.01, 0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95, 0.99])

        # extract stats to highlight current futures trading range (i.e. exclude count, mean, stdev)
        summary_stats_table = stats.reset_index()
        summary_stats_table = summary_stats_table.rename(
            columns={'index': 'Current Futures Trading Range (vs Historical Statistics)'})
        _values = [summary_stats_table[_].tolist() for _ in summary_stats_table.columns]
        _highlightable = _values[1][3:]  # valid values to highlight

        if chart_data_idx == 1:
            _show_legend = True
            _marker_color = f'rgba(100,111,252,1.0)'
        else:
            _show_legend = False
            _marker_color = f'rgba(255, 99, 97,1.0)'

        ##################### CHARTS 1 & 2: HISTORICAL SETTLEMENTS #####################
        fig.add_scatter(y=chart_data_dict[_].y,
                        x=chart_data_dict[_].x,
                        name=chart_data_dict[_].title,
                        row=1,
                        col=chart_data_idx + 1,
                        marker_color=_marker_color)

        ##################### CHARTS 1 & 2: FUTURES PRICES #####################
        for idx, futures_trade_date in enumerate(futures_to_attach):
            # futures prices at this idx / trade_date
            futures = dict_drill_down(futures_to_attach,
                                      key_sequence=[idx],
                                      levels=1,
                                      silent=True).y

            # custom formatting for each futures curve
            # if idx is current trade date/final key of futures_to_attach
            if idx == len(futures_to_attach) - 1:
                r, g, b, a = [210, 50, 0, 1.0]
                _mode = 'lines+markers' #'lines+markers+text'
                _markersize = 8
                _line_width = 2.0
                _dash = None
                current_trading_range = inclusive_range(futures, _highlightable)

                if chart_data_idx != 1:
                    data_labels = [f' {_:,.2f} ' for _ in futures]
                    print(f'data_labels: {data_labels}')
                else:
                    data_labels = [None for _ in futures]
            # elif idx is prior trade date
            elif idx == len(futures_to_attach) - 2:
                r, g, b, a = [0, 0, 210, 1.0]
                _mode = 'lines'
                _markersize = None
                _line_width = 2.0
                _dash = None
                data_labels = [None for _ in futures]
            # elif idx is in last 5 trade dates
            elif len(futures_to_attach) - 6 < idx < len(futures_to_attach) - 2:
                color_dict = {len(futures_to_attach) - 5: hex_to_rgba('#ffa600', a=1.0, values=True),
                              len(futures_to_attach) - 4: hex_to_rgba('#197A43', a=1.0, values=True),
                              len(futures_to_attach) - 3: hex_to_rgba('#1DBBFF', a=1.0, values=True)}
                r, g, b, a = color_dict[idx]
                _mode = 'lines'
                _markersize = None
                _line_width = 2.0
                _dash = 'dash'
                data_labels = [None for _ in futures]
            # elif idx is before T-5 trading days
            else:
                r = start_color[0] * (1 - idx / len(futures_to_attach)) + end_color[0] * (idx / len(futures_to_attach))
                g = start_color[1] * (1 - idx / len(futures_to_attach)) + end_color[1] * (idx / len(futures_to_attach))
                b = start_color[2] * (1 - idx / len(futures_to_attach)) + end_color[2] * (idx / len(futures_to_attach))
                a = 0.4
                _mode = 'markers'
                _markersize = 6
                _markersymbol = 'circle-dot'
                _line_width = 1.0
                _dash = 'dash'
                data_labels = [None for _ in futures]

            try:
                x = float(_.rstrip("%")) / 100
            except ValueError:
                x = 'strip'

            ##################### CHARTS 1 & 2: ADD FUTURES PRICES #####################
            data = go.Scatter(y=futures_to_attach[futures_trade_date].y,
                              x=futures_to_attach[futures_trade_date].x,
                              mode=_mode,
                              marker=dict(size=_markersize,
                                          color=f'rgba({r},{g},{b},{a})',
                                          symbol=_markersymbol
                                          ),
                              line=dict(width=_line_width,
                                        dash=_dash
                                        ),
                              legendgroup='grp1',
                              showlegend=_show_legend,
                              name=futures_to_attach[futures_trade_date].title,
                              #text=data_labels,
                              #textposition='top center',
                              #textfont_size=_font_size,
                              #textfont_color=f'rgba({r},{g},{b},{a})',  # 'black','crimson', #
                              #textfont_family='sans-serif',
                              connectgaps=True)

            # add_trace must be within futures loop to get all futures requested
            fig.add_trace(data,
                          row=1,
                          col=chart_data_idx + 1)

            ### ANNOTATIONS FOR FUTURES PRICES if this is the most recent trade date
            if idx == len(futures_to_attach) - 1 and chart_data_idx == 0:
                # chart position
                _ref = "" if chart_data_idx == 0 else str(chart_data_idx + 1)
                _xref = 'x' + _ref
                _yref = 'y' + _ref

                # annotations for datapoints
                count = 0
                for y_idx, y_val in enumerate(futures_to_attach[futures_trade_date].y):
                    count += 1
                    shift_direction = 1 if np.mod(y_idx,2) == 0 else -1

                    print(f'--- {futures_trade_date} {y_val} --> annotation count: {count} >> xref = {_xref}, yref = {_yref}')
                    annotations.append(
                        go.layout.Annotation(
                            text=f"{y_val: .2f}",
                            x=futures_to_attach[futures_trade_date].x[y_idx],
                            y=y_val,
                            xref=_xref,
                            yref=_yref,
                            yshift=18*shift_direction,
                            showarrow=False,
                            bgcolor='rgba(255,255,255,0.75)',
                            font=dict(
                                family='sans-serif',
                                size=_font_size,
                                color=f'rgba({r},{g},{b},1.00)'
                            )
                        )
                    )

        # update properties should be outside loop to only style axes once
        # Update xaxis properties
        fig.update_xaxes(dict(nticks=25,
                              tickangle=-45,
                              tickfont_size=_font_size,
                              gridcolor=_grid_color),
                         row=1,
                         col=chart_data_idx + 1)
        # Update yaxis properties
        fig.update_yaxes(dict(title_text=f'Settlement Price {c_unit}',
                              tickformat='$,.2f\xa0',
                              nticks=20,
                              tickfont_size=_font_size,
                              linecolor='rgba(10,10,10,0.75)',
                              zeroline=True,
                              zerolinecolor='rgba(15,15,15,0.75)',
                              gridcolor=_grid_color),
                         row=1,
                         col=chart_data_idx + 1)

        ##################### CHART 3: SUMMARY STATS TABLE #####################
        if chart_data_idx == 1:  # for full dataset
            column_alignment = ['left', 'center']
            highlight_fill_color = hex_to_rgba('#c1e7ff', a=1.0, values=False)  # hex_to_rgba('#eeeeee')
            default_font_color = 'rgba(90,90,90,1.0)'
            highlight_font_color = 'darkblue'  # 'green' 'crimson' # hex_to_rgba('#ddccff') - #c1e7ff

            # if this is the current index
            try:
                column_fill_color = [[
                    highlight_fill_color if _ in current_trading_range else 'rgba(250,250,250,1.0)' for _ in
                    _values[1]], [
                    highlight_fill_color if _ in current_trading_range else 'white' for _ in _values[1]]]
            except (NameError, ValueError):
                column_fill_color = ['rgba(245,245,245,1.0)', 'white']

            try:
                column_font_color = [[
                    highlight_font_color if _ in current_trading_range else default_font_color for _ in _values[1]], [
                    highlight_font_color if _ in current_trading_range else default_font_color for _ in _values[1]]]
            except (NameError, ValueError):
                column_font_color = [default_font_color] * 2

            fig.add_table(
                columnorder=[1, 2],
                columnwidth=[420, 250],
                header=dict(values=[_ for _ in summary_stats_table.columns],
                            align=column_alignment,
                            line_color=_grid_color,
                            font=dict(color='darkblue',
                                      size=_font_size + 2),
                            fill_color=hex_to_rgba('#eeeeee', a=1.0, values=False),
                            height=_font_size * 2.0),
                cells=dict(values=_values,
                           align=column_alignment,
                           line=dict(color=_grid_color),
                           font=dict(color=column_font_color,
                                     size=_font_size),
                           fill=dict(color=column_fill_color),
                           format=[None] + [",.2f"],
                           height=_font_size * 2.0),
                row=3,
                col=1)

            ##################### CHART 4: PRICE HISTOGRAM #####################
            fig.add_histogram(x=chart_data_dict[_].y,
                              nbinsx=250,
                              histnorm="",  # 'percent',
                              name='Front Month Settlement Price',
                              row=2,
                              col=2,
                              marker_color=hex_to_rgba('#ffa600', a=0.8, values=False))

            ##################### CHART 5: HEATMAP #####################
            # annotations
            for n, row in enumerate(heatmap_chart_data['data']):
                for m, val in enumerate(row):
                    annotations.append(
                        go.layout.Annotation(
                            text=f"{heatmap_chart_data['data'][n][m]: .2f}",
                            x=heatmap_chart_data['x_labels'][m],
                            y=heatmap_chart_data['y_labels'][n],
                            xref='x3',
                            yref='y3',
                            showarrow=False,
                            bgcolor='rgba(255,255,255,0.90)',
                            font=dict(size=_font_size)
                        )
                    )

            fig.add_heatmap(
                z=heatmap_chart_data['data'],
                zmid=0.0,
                x=heatmap_chart_data['x_labels'],
                y=heatmap_chart_data['y_labels'],
                colorscale='thermal',
                reversescale=False,
                colorbar=dict(x=0.43, title='$ Change', thickness=15),
                showscale=False,
                row=2,
                col=1
            )

            fig.update_layout(
                title={
                    'text': f"Price Change Heatmap ({c_unit})",
                    'xanchor': 'center',
                    'yanchor': 'top'
                },
                annotations=annotations
            )

            fig.update_xaxes(dict(side='bottom', tickangle=-45, tickfont_size=_font_size),
                             row=2,
                             col=1)
            fig.update_yaxes(dict(tickfont_size=_font_size),
                             row=2,
                             col=1)

            # Update xaxis properties
            fig.update_xaxes(dict(nticks=20,
                                  tickangle=-45,
                                  tickformat='$,.2f\xa0',
                                  tickfont_size=_font_size,
                                  gridcolor=_grid_color),
                             row=2,
                             col=2)
            # Update yaxis properties
            fig.update_yaxes(dict(title_text=f'# of datapoints (n)',
                                  nticks=20,
                                  tickfont_size=_font_size,
                                  tickformat=',.2f\xa0',
                                  linecolor='rgba(10,10,10,0.75)',
                                  zeroline=True,
                                  zerolinecolor='rgba(15,15,15,0.75)',
                                  gridcolor=_grid_color),
                             row=2,
                             col=2)
    # for whole figure
    figure_width = _fig_width
    figure_height = _fig_height

    fig.update_layout(title=f'{chart_data_dict[_].title}',
                      title_xanchor='left',
                      title_yanchor='top',
                      plot_bgcolor='rgba(0,0,0,0)',
                      width=figure_width,
                      height=figure_height,
                      legend=dict(orientation='v',
                                  y=1.00,
                                  x=1.05,
                                  font_size=_font_size))
    folder_local = root_folder_daily_prices()['root_folder']
    folder_network = r'\/FILE01\/TDrive\/Finance-Strategy\/Daily_Price_Updates\/'
    filename_htm = f'_price_update_{c_name}_{string_date(start)}_{string_date(end)}.html'
    filename_png = f'_price_update_{c_name}_{string_date(start)}_{string_date(end)}.png'
    filename_eml = f'_price_update_{c_name}.html'  # no dates allowed

    global email_filepaths
    global image_filepaths

    email_filepaths[c_nick] = folder_network + filename_eml
    image_filepaths[c_nick] = (folder_local + filename_png, folder_network + filename_png)

    print(image_filepaths, email_filepaths)
    fig.write_html(folder_local + filename_htm, include_plotlyjs='True')

    try:
        fig.write_html(folder_network + filename_eml, include_plotlyjs='True')
    except (OSError, FileNotFoundError):
        print(f'!! File not found or network folder not accessible.')

    scope = PlotlyScope()

    #     with open(folder_network+filename_png, "wb") as f:
    #         f.write(scope.transform(fig, format="png", width = 1600, height = 950))

    with open(folder_local + filename_png, "wb") as f:
        f.write(scope.transform(fig, format="png", width=figure_width, height=figure_height))

    fig.show()


# ------------------------------------- RATIO ANALYSIS CHARTS --------------------------------------
def ratio_analysis_charts():
    global model_prices

    ratio_data = model_prices.loc[:, [_ for _ in model_prices.columns if ":" in _ or 'NGL Composite' in _]]
    # re-order to put NGL composite first, then WTI:HH, then ratios
    ratio_data = ratio_data[[ratio_data.columns[-1]] + [_ for _ in ratio_data.columns[0:-1]]]
    grid_shape = [2, 2]
    fig = make_subplots(rows=grid_shape[0], cols=grid_shape[1], vertical_spacing=_vertical_spacing)
    chart_coords = line_to_grid(linear_range=range(len(ratio_data.columns)), grid_shape=grid_shape)

    # default requested_chart formatting
    _grid_color = 'rgba(220,220,220,1)'
    start_color = [180, 180, 180]  # [225, 36, 0]
    end_color = [100, 100, 100]

    chart_months = 18
    for idx, ratio in enumerate(ratio_data):
        print(idx, ratio)
        if 'NGL Composite' in ratio:
            r_idx = 1
            c_idx = 1
            _title_text_y = ratio + ' ($/gal)'
            _tick_format_y = '$,.3f\xa0'
            _markersymbol = 'triangle-up'
            r, g, b, a = hex_to_rgba('#ffa600', a=1.0, values=True)

        elif ratio == 'WTI Oil:HH Gas':
            r_idx = 1
            c_idx = 2
            _title_text_y = ratio + " Ratio (x)"
            _tick_format_y = ',.2f\xa0'
            _markersymbol = 'circle'
            r, g, b, a = hex_to_rgba('#1DBBFF', a=1.0, values=True)

        elif ':WTI Oil' in ratio:
            r_idx = 2
            c_idx = 1
            _title_text_y = "NGL:WTI Oil Ratio @ 42 gal/bbl"
            _tick_format_y = ',.2f\xa0'
            _markersymbol = 'diamond'
            # requested_chart series colors - grade over 5 steps
            start_idx = 2
            end_idx = 6
            r_start, g_start, b_start, a_start = hex_to_rgba(
                hex_color='#ff8106', a=1.0, values=True)
            r_end, g_end, b_end, a_end = hex_to_rgba(
                hex_color='#1d99ee', a=1.0, values=True)
            r = r_start * (end_idx - idx) / (end_idx - start_idx) + r_end * (idx - start_idx) / (end_idx - start_idx)
            g = g_start * (end_idx - idx) / (end_idx - start_idx) + g_end * (idx - start_idx) / (end_idx - start_idx)
            b = b_start * (end_idx - idx) / (end_idx - start_idx) + b_end * (idx - start_idx) / (end_idx - start_idx)
            a = 1.0

        elif ':HH Gas' in ratio:
            r_idx = 2
            c_idx = 2
            _title_text_y = "NGL:HH Gas Ratio @ 7 gal/mmbtu"
            _tick_format_y = ',.2f\xa0'
            _markersymbol = 'x'
            # requested_chart series colors - grade over 5 steps
            start_idx = 7
            end_idx = 11
            r_start, g_start, b_start, a_start = hex_to_rgba(
                hex_color='#ff8106', a=1.0, values=True)
            r_end, g_end, b_end, a_end = hex_to_rgba(
                hex_color='#1d99ee', a=1.0, values=True)
            r = r_start * (end_idx - idx) / (end_idx - start_idx) + r_end * (idx - start_idx) / (end_idx - start_idx)
            g = g_start * (end_idx - idx) / (end_idx - start_idx) + g_end * (idx - start_idx) / (end_idx - start_idx)
            b = b_start * (end_idx - idx) / (end_idx - start_idx) + b_end * (idx - start_idx) / (end_idx - start_idx)
            a = 1.0

        print(r_idx, c_idx)
        _y = ratio_data[ratio][:chart_months]
        _x = list(ratio_data[ratio].index[:chart_months])
        _mode = 'lines+markers'
        _markersize = 8

        _line_width = 2.0
        _dash = None  # 'dash'
        data_labels = [None for _ in _y]
        _show_legend = True

        data = go.Scatter(y=_y,
                          x=_x,
                          mode=_mode,
                          marker=dict(size=_markersize,
                                      color=f'rgba({r},{g},{b},{a})',
                                      symbol=_markersymbol
                                      ),
                          line=dict(width=_line_width,
                                    dash=_dash
                                    ),
                          legendgroup='grp1',
                          showlegend=_show_legend,
                          name=ratio,
                          text=data_labels,
                          textposition='top center',
                          textfont_size=_font_size,
                          textfont_color=f'rgba({r},{g},{b},{a})',  # 'black','crimson', #
                          textfont_family='sans-serif',
                          connectgaps=True)
        fig.add_trace(data,
                      row=r_idx,
                      col=c_idx)
        # Update xaxis properties - by requested_chart - move outside loop for all
        fig.update_xaxes(dict(nticks=25,
                              tickangle=-45,
                              tickfont_size=_font_size,
                              gridcolor=_grid_color),
                         row=r_idx,
                         col=c_idx)
        # Update yaxis properties - by requested_chart - move outside loop for all
        fig.update_yaxes(dict(title_text=_title_text_y,
                              tickformat=_tick_format_y,
                              nticks=20,
                              tickfont_size=_font_size,
                              linecolor='rgba(10,10,10,0.75)',
                              zeroline=True,
                              zerolinecolor='rgba(15,15,15,0.75)',
                              gridcolor=_grid_color),
                         row=r_idx,
                         col=c_idx)
    # for whole figure
    fig.update_layout(title=f'NGL Composite Index and Price Ratios',
                      title_xanchor='left',
                      title_yanchor='top',
                      plot_bgcolor='rgba(0,0,0,0)',
                      width=2000,
                      height=1600,
                      legend=dict(orientation='v',
                                  y=1.00,
                                  x=1.05,
                                  font_size=_font_size))

    as_of_date = string_date(model_prices["as_of_date"][0])
    folder_local = root_folder_daily_prices()['root_folder']
    folder_network = r'\/FILE01\/TDrive\/Finance-Strategy\/Daily_Price_Updates\/'
    filename_htm = f'_ngl_composite_and_ratios_as_of_{as_of_date}.html'
    filename_png = f'_ngl_composite_and_ratios_as_of_{as_of_date}.png'
    filename_eml = f'_ngl_composite_and_ratios.html'  # no dates allowed

    global email_filepaths
    global image_filepaths

    email_filepaths['ngl_comp_and_ratios'] = folder_network + filename_eml
    image_filepaths['ngl_comp_and_ratios'] = (folder_local + filename_png, folder_network + filename_png)

    print(image_filepaths, email_filepaths)
    fig.write_html(folder_local + filename_htm, include_plotlyjs='True')
    try:
        fig.write_html(folder_network + filename_eml, include_plotlyjs='True')
    except (FileNotFoundError, OSError):
        print(f'!! File not found or network folder not accessible.')

    scope = PlotlyScope()
    with open(folder_local + filename_png, "wb") as f:
        f.write(scope.transform(fig, format="png", width=2000, height=1600))
    fig.show()


# ------------------------------------- EMAIL DAILY PRICE UPDATE --------------------------------------

@timer
def send_daily_price_update_email(sender, recipients):
    outlook = win32.Dispatch('outlook.application')
    mail = outlook.CreateItem(0)
    mail.To = recipients

    today = get_dates('wti', date_type='end')

    mail.Subject = f'Daily Market Update - {today}'

    global bodytext
    bodytext = '''
    <b>
    <p style="font-size:20px">
    Daily Market Update
    </p>
    </b>
    <p style="font-size:15px">
    <br>
    Attached is the daily commodity price update, along with current futures prices in excel.
    <br>
    <br>
    <i>
    <a href = "T:/Finance-Strategy/daily_price_updates/">Interactive versions</a> of these charts are saved on the T: drive.
    You will need to be connected to the Triple Crown VPN if you are working remotely.
    </i>
    <br>
    '''
    global img_prop_accessor
    img_prop_accessor = {}
    global image_filepaths

    # re-order the images so heatmaps are first
    try:
        image_key_list = [_ for _ in image_filepaths.keys()]
        image_key_list.remove('commodity_heatmaps')
        image_key_list = ['commodity_heatmaps'] + image_key_list
        image_filepaths = {k: image_filepaths[k] for k in image_key_list if k in image_filepaths}
    except ValueError:
        print(f'!! commodity_heatmaps chart not found! Skipping.')

    filepath_prices_xls = 'C:/Users/vdesai/Desktop/Model/Python/TCR - Model Prices.xlsx'
    attachment = mail.Attachments.Add(filepath_prices_xls)

    for img in image_filepaths:
        # Change the Paths here, if run from a different location
        signatureimage = image_filepaths[img][0]
        attachment = mail.Attachments.Add(signatureimage)

        # access attachment image to include in body of email.
        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                                                img.replace(' ', '_'))
        bodytext = bodytext + '<html><body>_________________________<br><img src="cid:' + img.replace(' ',
                                                                                                      '_') + '"><br></body></html>'
        attachment = mail.Attachments.Add(signatureimage)
        img_prop_accessor[img] = bodytext

    sig_block = '''
    <html>
    <body>
    <br>
    <br>
    <br>__________________________________
    <br><b>Viren Desai</b>
    <br><i>VP Strategy & Finance</i>
    <br><b>Triple Crown Resources, LLC</b>
    <br>M: 281.799.1119
    <br>E: vdesai@triplecrownresources.com
    </p>
    </body>
    </html>
    '''

    bodytext = bodytext + sig_block

    mail.HTMLBody = bodytext
    mail.SentOnBehalfOfName = sender
    mail.GetInspector
    mail.Display(True)
    # mail.Send()


@timer
def run_price_update(as_of_date=None,
                     price_history_start='1/1/2003',
                     distribution_list='test'
                     ):
    update_web_data()
    if distribution_list == 'test':
        recipient_list = 'vdesai@triplecrownresources.com'
    else:
        recipient_list = '''
        npekar@triplecrownresources.com;
        rkeys@triplecrownresources.com;
        dmarkley@triplecrownresources.com;
        jpierce@triplecrownresources.com;
        rbassett@triplecrownresources.com;
        Jgreer@triplecrownresources.com;
        ajovanovic@triplecrownresources.com;
        jrivera@triplecrownresources.com;
        ldelgreco@triplecrownresources.com;
        bshelton@triplecrownresources.com;
        jpaduch@triplecrownresources.com;
        jrussell@triplecrownresources.com;
        kspratlen@triplecrownresources.com;
        awlazlo@triplecrownresources.com;
        ggilbert@triplecrownresources.com;
        fjohnson@triplecrownresources.com;
        jvasquez@triplecrownresources.com;
        vdesai@triplecrownresources.com
        '''

    print(f'\n| Latest NYMEX data: {nymex_trade_date}')
    proceed = input(f'| Email will be sent to {recipient_list}...\n| Proceed with daily price update? Y/N >>> ')
    if proceed.lower() == 'y':
        run_mcs_data_maker()
        update_daily_prices(start_date=price_history_start)

        if as_of_date:
            get_model_prices(strip_pricing_date=as_of_date, start_date='7/1/20')
        else:
            get_model_prices(strip_pricing_date=nymex_trade_date, start_date='7/1/20')

        #ratio_analysis_charts()
        global master_heatmap_data
        run_master_heatmap_charts(master_heatmap_data=master_heatmap_data)
        send_daily_price_update_email('vdesai@triplecrownresources.com', recipient_list)
    else:
        print(f'!! Price update execution stopped.')


def exclude_from_model_prices(excluded_indices: list):
    global model_prices_excluded
    model_prices_excluded = excluded_indices
    print(f'| Price indices excluded: {model_prices_excluded}')


@timer
def run_model_prices(as_of_date=None, output_start_date='7/1/20', excluded_indices=[]):
    update_web_data()
    exclude_from_model_prices(excluded_indices)
    print(f'\n| Latest NYMEX data: {nymex_trade_date}')
    proceed = input(f'| Updating model prices as of: {as_of_date}. Proceed? Y/N ')
    if proceed.lower() == 'y':
        if as_of_date:
            get_model_prices(strip_pricing_date=as_of_date, start_date=output_start_date)
        else:
            get_model_prices(strip_pricing_date=nymex_trade_date, start_date=output_start_date)
    else:
        print(f'!! Price update execution stopped.')


# ----------------------------------- BOOTSTRAP PRICES ---------------------------------------

def get_cpi_inflation():
    # CPI inflation data - all historical
    # todo: BY SEPTEMBER 2020. confirm that URL works for months after Aug 2020
    csv_link = '''https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1168&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=CPIAUCSL&scale=left&cosd=1947-01-01&coed=2020-07-01&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Monthly&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&vintage_date=2020-08-13&revision_date=2020-08-13&nd=1947-01-01'''
    cpi_inflation = pd.read_csv(csv_link)
    cpi_inflation.rename(columns={'CPIAUCSL': 'CPI'}, inplace=True)
    cpi_inflation['Annual Inflation %'] = (cpi_inflation.loc[:, 'CPI'] / cpi_inflation.loc[:, 'CPI'].shift(12) - 1)
    cpi_inflation.drop(index=range(0, 12), inplace=True)
    cpi_inflation.reset_index(inplace=True, drop=True)
    cpi_inflation.set_index('DATE', inplace=True)
    cpi_inflation.index = [pd.to_datetime(_) + MonthEnd(1) for _ in cpi_inflation.index]
    return cpi_inflation


def drop_excluded_prices(c_nick, prices_to_strip):
    '''Removes excluded / erroneous prices from simulated price dataset.'''
    try:
        prices_to_strip = prices_to_strip[prices_to_strip != excluded_prices[c_nick][0]]
        print(f'| Excluded prices for {c_nick}: {excluded_prices[c_nick]}')
        return prices_to_strip
    except KeyError:
        print(f'| Excluded prices for {c_nick}: None')
        return prices_to_strip


# called from simulate_prices_all()
def adjust_for_inflation(unadjusted_prices: pd.DataFrame):
    # adjust all the price indexes for inflation according to their time period
    cpi_adjusted_prices = []
    date_range = unadjusted_prices.index
    # dataframe of all CPI inflation available
    cpi_inflation = get_cpi_inflation()
    print(cpi_inflation)

    latest_cpi, latest_inflation = cpi_inflation.iloc[-1, :]
    # loop over settle_dates -- the date-range is the index for the dataframe
    for settle_date in date_range:
        settle_price = unadjusted_prices.loc[settle_date]
        settle_month = pd.to_datetime(settle_date) + MonthEnd(0)
        try:
            cpi_for_month, inflation_for_month = cpi_inflation.loc[settle_month, :]
        except KeyError:
            cpi_for_month, inflation_for_month = latest_cpi, latest_inflation

        cpi_adj_price = settle_price * latest_cpi / cpi_for_month
        cpi_adjusted_prices.append(cpi_adj_price)
        # print(settle_date, cpi_for_month, inflation_for_month, settle_price, cpi_adj_price)

    inflation_adj_prices = pd.DataFrame(
        data=cpi_adjusted_prices,
        index=date_range,
        columns=['CPI Adj. Price']
    )
    return inflation_adj_prices

def get_mcs_start_end_dates(sim_end):
    global mcs_start_end_dates
    global SimDates
    SimDates = namedtuple('SimDates', 'sim_start sim_end')
    sim_end = string_date(sim_end)
    mcs_start_end_dates = {
        'wti': SimDates(sim_start='2003-01-01', sim_end=sim_end),
        'wti_hou': SimDates(sim_start='2018-11-05', sim_end=sim_end),
        'midcush_ff': SimDates(sim_start='2019-07-01', sim_end='2020-03-31'),
        'hh': SimDates(sim_start='2009-01-01', sim_end=sim_end),
        'waha_gas_diff': SimDates(sim_start='2009-01-01', sim_end=sim_end),
        'hsc_gas_diff': SimDates(sim_start='2009-01-01', sim_end=sim_end),
        'ethane': SimDates(sim_start='2013-01-01', sim_end=sim_end),
        'propane': SimDates(sim_start='2013-01-01', sim_end=sim_end),
        'n_butane': SimDates(sim_start='2013-01-01', sim_end=sim_end),
        'iso_butane': SimDates(sim_start='2013-01-01', sim_end=sim_end),
        'nat_gasoline': SimDates(sim_start='2013-01-01', sim_end=sim_end)
    }
    return mcs_start_end_dates

def simulate_prices_all(sim_end, inflation_adjusted: bool):
    '''Returns simulated prices and statistics for all commodities in a namedtuple PriceStats:
     --> namedtuple returned: PriceStats. attributes: (sim_prices, summary_stats)
     --> Each attribute is a dataframe
     --> sim_prices: MCS flat prices for all price indices
     --> summary_stats: summary statistics for all price indices. '''
    if not (sim_end):
        sim_end = string_date(pd.to_datetime(date.today()) - BDay(1))

    mcs_start_end_dates = get_mcs_start_end_dates(sim_end)

    summary_stats_all = {}  # for all summary statistics (including count, mean, std)
    sim_prices_all = pd.DataFrame(index=[_ for _ in mcs_start_end_dates], columns=string_default_percentiles)

    for c_nick in mcs_start_end_dates:
        # c_nick = 'wti'
        c_name = get_comdty_name(c_nick)
        c_unit = get_comdty_unit(c_nick)
        start = mcs_start_end_dates[c_nick].sim_start
        end = mcs_start_end_dates[c_nick].sim_end
        mcs_prices_historical_raw = get_mcs_data_historical(c_nick).loc[start:end, 'settle_price']
        mcs_prices_historical_clean = drop_excluded_prices(c_nick, mcs_prices_historical_raw)
        if inflation_adjusted:
            # pass through inflation adjuster
            print(
                f'\n| Prices unadjusted for inflation:\n{mcs_prices_historical_clean.describe(default_percentiles)}'
            )
            mcs_prices_historical_clean = adjust_for_inflation(mcs_prices_historical_clean).loc[:, 'CPI Adj. Price']
            print(
                f'| Prices adjusted for inflation:\n{mcs_prices_historical_clean.describe(default_percentiles)}'
            )

        # Kernel Density Estimator on clean historical prices (with excluded_prices excluded)
        hist_prices = mcs_prices_historical_clean.values.squeeze()
        print('\n>>> Running kernel density estimator >>>\n')
        sim_results = run_KDE(data=hist_prices, c_nick=c_nick, rand_samples=10 ** 5)
        sim_random_samples = sim_results['random_samples']
        sim_logprob = sim_results['logprob']
        sim_x_d_linspace = sim_results['x_d_linspace']
        summary_stats = pd.DataFrame(hist_prices,
                                     columns=[f'Historical {c_name}']
                                     ).describe(default_percentiles)
        sim_summary_stats = pd.DataFrame(sim_random_samples,
                                         columns=[f'Simulated {c_name}']
                                         ).describe(default_percentiles)
        summary_stats = summary_stats.join(sim_summary_stats)
        summary_stats.name = c_nick
        summary_stats_all[c_nick] = summary_stats

        # run price charts
        # make historical chart data
        c_code = get_comdty_code(c_nick)
        _hist_chart_data = ChartData(
            title=f'''Prices Modeled >> {c_name} // CME Code: {c_code} | Date Range Simulated >>> {string_date(start)} to {string_date(end)}''',
            x=mcs_prices_historical_clean.index,
            y=mcs_prices_historical_clean.values,
            x_name='Trade Date',
            y_name=f'Front Month Settlement ({c_unit})')

        price_simulator_charts(c_nick=c_nick,
                               historical_chart_data=_hist_chart_data,
                               summary_stats=summary_stats,
                               random_samples=sim_random_samples,
                               logprob=sim_logprob,
                               x_d=sim_x_d_linspace,
                               histogram_bins=250,
                               histogram_norm='probability density',
                               scen_name=model_control.scenario_time_stamp
                               )

        print(f'\n>>> Simulation results >>>')

        sim_prices_all.loc[c_nick, :] = summary_stats.loc[
            string_default_percentiles, f'Simulated {c_name}'].T
        print(f'\n| Commodity nick: {c_nick}',
              f'\n| Commodity name: {get_comdty_name(c_nick)}',
              f'\n| Raw datapoints: {len(mcs_prices_historical_raw)}',
              f'\n| Cleaned datapoints: {len(mcs_prices_historical_clean)}\n{mcs_prices_historical_clean}',
              f'\n| Summary stats:\n {summary_stats}')

    print('\n| Simulated prices >>>\n')
    print(sim_prices_all)
    print('\n| Summary Statistics for Simulated Prices >>>\n')
    print(summary_stats_all)
    # return a namedtuple for ease of access
    proceed = input(f'\n| Price MCS complete. Proceed? Y/N ')

    PriceStats = namedtuple('PriceStats', 'sim_prices summary_stats')
    return PriceStats(sim_prices=sim_prices_all, summary_stats=summary_stats_all)


def update_flat_model_prices(model_prices):
    # if flat price scenario is true
    if model_control.flat_oil_scenario:
        model_prices.loc[string_date(model_control.get_flat_oil_start_date()):, 'WTI CMA'] = model_control.get_flat_oil_price()
        model_prices.loc[string_date(model_control.get_flat_oil_start_date()):, 'WTI Oil'] = model_control.get_flat_oil_price()

    if model_control.flat_gas_scenario:
        model_prices.loc[string_date(model_control.get_flat_gas_start_date()):, 'HH Gas'] = model_control.get_flat_gas_price()
    return model_prices


def get_bootstrap_prices(strip_pricing_date,
                         model_start_date='7/1/2020',
                         model_months=300,
                         check_local=False,
                         inflation_adjusted=False,
                         ethane_mode='recovery',
                         output_to_excel=False
                         ):
    '''Get  bootstrap prices (flat) and strip prices.
    Args:
        |-- strip_pricing_date, string format date: date for strip pricing
        |-- model_start_date, string format date: date for model start (beginning of month)
        |-- model_months, int: number of months in forecast period
        |-- inflation_adjusted, bool: adjust simulated prices for inflation (beta)
        |-- ethane_mode, str: 'recovery' or 'rejection' according to preference
        |-- output_to_excel, bool: output model prices to excel (True) or not (False)
        '''

    # to save each 1) commodity dataframe, 2) model period, and 3) model prices to price _scenario folder
    price_scenario_folder = 'C:/Users/vdesai/Desktop/Model/Python/___mcs_model/__PRICE_SCENARIOS/'
    _1 = strip_pricing_date.replace("/", "_")
    _2 = model_start_date.replace("/", "_")
    _3 = model_months
    _4 = ethane_mode

    # price index correspondence
    model_price_sim_price_dict = {"WTI CMA": 'wti',
                                  "WTI Houston Oil": 'wti_hou',
                                  "MidCush - FF": 'midcush_ff',
                                  "HH Gas": 'hh',
                                  "Waha Diff": 'waha_gas_diff',
                                  "HSC Gas Diff": 'hsc_gas_diff',
                                  "Ethane Mt.Belvieu": 'ethane',
                                  "Propane Mt.Belvieu LDH": 'propane',
                                  "n-Butane": 'n_butane',
                                  "iso-Butane": 'iso_butane',
                                  "Nat. Gasoline": 'nat_gasoline'}

    bootstrap_prices = {}

    # TODO: try/except the below --> the file with same params needs to exist
    price_scenario_files = [_ for _ in os.listdir(price_scenario_folder)]
    price_scenario_files = [_ for _ in price_scenario_files if f'{_1}_{_2}_{_3}_{_4}_' in _]

    _non_mcs_scenario_label = model_control.get_non_mcs_scenario_label()

    if check_local and len(price_scenario_files) > 0:
        print('| Reading local price data')

        # read in model period
        print('|-- Model period')
        price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_model_period.json'
        fp = price_scenario_folder + price_scenario_filename
        model_period = pd.read_json(fp)
        # convert to DateTimeIndex
        model_period = pd.to_datetime(sorted(model_period.iloc[:, 0]))
        print(model_period)

        # read in model prices
        print('|-- Model prices')
        price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_model_prices.json'
        fp = price_scenario_folder + price_scenario_filename
        model_prices = pd.read_json(fp)
        model_prices.index = [string_date(_) for _ in model_prices.index]

        # change strip to flat prices if needed
        model_prices = update_flat_model_prices(model_prices)
        print(model_prices)

        # read in bootstrap prices
        print('|-- Bootstrap price data:')
        for c_nick in model_price_sim_price_dict.values():
            price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_{c_nick}.json'
            fp = price_scenario_folder + price_scenario_filename
            print(f'| Reading: {fp}')
            try:
                bootstrap_prices[c_nick] = pd.read_json(fp)
                # reformat index
                bootstrap_prices[c_nick].index = [string_date(_) for _ in bootstrap_prices[c_nick].index]

                # update strip to flat model prices if needed
                # re-label last column
                old_cols = bootstrap_prices[c_nick].columns.to_list()
                new_cols = old_cols.copy()
                new_cols[-1] = _non_mcs_scenario_label
                bootstrap_prices[c_nick].rename(columns={old: new for old, new in zip(old_cols, new_cols)}, inplace=True)

                # update flat price values
                c_name = [k for k, v in model_price_sim_price_dict.items() if v == c_nick][0]
                bootstrap_prices[c_nick].loc[model_prices.index, _non_mcs_scenario_label] = model_prices.loc[:, c_name].values
                bootstrap_prices[c_nick].ffill(inplace=True)

                print(bootstrap_prices[c_nick])
            except ValueError:
                print(f'!! Bootstrap prices not found: {c_nick}')

        # _q = input('continue?')

        # read in summary stats
        print('|-- Summary Stats')
        summary_stats = {}
        for c_nick in model_price_sim_price_dict.values():
            price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_summary_stats_{c_nick}.json'
            fp = price_scenario_folder + price_scenario_filename
            summary_stats[c_nick] = pd.read_json(fp)
    # else, if the price _scenario is not found on the disk, run it
    else:
        if not (strip_pricing_date):
            strip_pricing_date = string_date(pd.to_datetime(date.today()) - BDay(1))
        else:
            strip_pricing_date = string_date(pd.to_datetime(strip_pricing_date))

        sim_prices, summary_stats = simulate_prices_all(sim_end=strip_pricing_date,
                                                        inflation_adjusted=inflation_adjusted
                                                        )

        print(
            f'\n| sim_prices: {sim_prices.index}, {sim_prices.columns}\n| summary_stats: {summary_stats} | type: {type(summary_stats)}'
        )

        model_period = get_model_period(model_months, start_date=model_start_date)
        model_prices = get_model_prices(strip_pricing_date=strip_pricing_date,
                                        start_date=model_start_date,
                                        ethane_mode=ethane_mode,
                                        output_to_excel=output_to_excel)

        # update strip to flat model prices if needed
        model_prices = update_flat_model_prices(model_prices)
        print(model_prices, _non_mcs_scenario_label)
        # _q = input('continue?')


        # create a dataframe for each price _scenario for each commodity in the sim_prices index
        for c_nick in sim_prices.index:
            bootstrap_prices[c_nick] = pd.DataFrame(
                index=model_period,
                columns=[_ for _ in sim_prices.columns] + [_non_mcs_scenario_label])

            # update flat prices
            for str_pct in string_default_percentiles:
                bootstrap_prices[c_nick].loc[:, str_pct] = sim_prices.loc[c_nick, str_pct]

            # update strip price using model_price_sim_price_dict
            model_price_key = [k for k, v in model_price_sim_price_dict.items() if v == c_nick][0]
            mod_pr = model_prices.loc[:, model_price_key]

            bootstrap_prices[c_nick].loc[: len(mod_pr), _non_mcs_scenario_label] = model_prices.loc[
                                                                                         :, model_price_key]
            bootstrap_prices[c_nick].ffill(inplace=True)

        # save 1) 2) and 3) to price _scenario folder
        # --> 1) commodity dataframes
        for c_nick in bootstrap_prices:
            price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_{c_nick}.json'
            fp = price_scenario_folder + price_scenario_filename
            save_to_json(bootstrap_prices[c_nick],
                         folder=price_scenario_folder,
                         filepath=fp)
        # --> 2) model period
        price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_model_period.json'
        fp = price_scenario_folder + price_scenario_filename
        save_to_json(pd.DataFrame(model_period),
                     folder=price_scenario_folder,
                     filepath=fp)
        # --> 3) model prices
        price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_model_prices.json'
        fp = price_scenario_folder + price_scenario_filename
        save_to_json(model_prices,
                     folder=price_scenario_folder,
                     filepath=fp)
        # --> 3) loop through summary stats and save each to folder
        for c_nick in summary_stats:
            price_scenario_filename = f'{_1}_{_2}_{_3}_{_4}_summary_stats_{c_nick}.json'
            fp = price_scenario_folder + price_scenario_filename
            save_to_json(summary_stats[c_nick],
                         folder=price_scenario_folder,
                         filepath=fp)

    return {'bootstrap_prices': bootstrap_prices,
            'model_period': model_period,
            'model_prices_10yr': model_prices,
            'summary_stats': summary_stats
            }


# ---------------------------------------------------------------------------------------------------------------------#
# -----------------------------------------------# MONTE CARLO SIMULATOR #---------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#


def run_KDE(data, c_nick, rand_samples=10 ** 5):
    '''Pass data = y values, c_nick = comdty_nick.
    Returns tuple of:
    (random samples (random_samples_dict[c_nick]),
    linear space of 5000 points between min() and max() of data (x_d),
    log probability density function (logprob = kde.score_samples(x_d)))
    '''
    # create KDE model and random samples
    data = np.array(data).squeeze()  # y_vals

    global random_samples_dict

    if 'random_samples_dict' not in globals():
        # make dictionary to store random samples
        random_samples_dict = {}
    else:
        # initialize storage
        random_samples_dict[c_nick] = []

    # bandwidth for KDE
    kde_bandwidth = get_kde_bandwidth()

    # instantiate and fit the KDE model
    kde = KernelDensity(bandwidth=kde_bandwidth[c_nick], kernel='gaussian')
    kde.fit(data[:, None])

    global x_d
    x_d = np.linspace(min(data), max(data), 5000)

    global logprob
    # score_samples returns the log of the probability density
    logprob = kde.score_samples(x_d[:, None])

    N = rand_samples
    global random_samples
    random_samples = kde.sample(n_samples=N)
    random_samples = random_samples.squeeze()  # reduce dimensionality
    random_samples_dict[c_nick] = list(random_samples)

    results_dict = {'random_samples': random_samples_dict[c_nick],
                    'logprob': logprob,
                    'x_d_linspace': x_d}

    # print(results_dict)
    return results_dict


def get_kde_bandwidth(update = {}):
    '''Returns dictionary with KDE bandwifth by commodity (keys = comdty_nick).
    Pass update = {comdty_nick: bandwidth} to update bandwidth for a commodity.'''

    global kde_bandwidth
    if 'kde_bandwidth' not in globals():
        kde_bandwidth = {'wti': 0.3,
                         'wti_hou': 0.3,
                         'midcush_ff': 0.04,
                         'midcush_wtt': 0.04,
                         'hh': 0.008,
                         'waha_gas_diff': 0.008,
                         'hsc_gas_diff': 0.008,
                         'ethane': 0.001,
                         'propane': 0.004,
                         'n_butane': 0.005,
                         'iso_butane': 0.005,
                         'nat_gasoline': 0.005
                         }
    try:
        for k in update:
            kde_bandwidth[k] = update[k]
    except (NameError, TypeError, KeyError, ValueError):
        print('Invalid / no update dict passed. Returning default bandwidths.')

    return kde_bandwidth


## Price Simulator + Charts
def price_sim_scenario_exists(c_code,
                              min_hist_trade_dates,
                              max_hist_trade_dates,
                              rand_samples):
    global scenario_time_stamp
    # folder for each _scenario - must end with _price_mcs
    folder = root_folder_model_scenarios(save_scenario_name=f'{scenario_time_stamp}_price_mcs')['root_folder']

    # filename to search for - should be 1 set of files for each key of results_dict
    filename = f'{c_code}_{min_hist_trade_dates}_{max_hist_trade_dates}_n_{rand_samples}_summary_stats.json'

    try:
        test = pd.read_json(folder + filename)
        if test is not None:
            return True
    except (FileNotFoundError, ValueError):
        return False


@timer
def price_simulator(c_nick: str,
                    start='1/1/2020',
                    end='6/16/2020',
                    sim_all=False,
                    rand_samples=100000,
                    charts=True,
                    pct=[],
                    _return=False):
    # c_nick = 'wti'
    # start = '1/1/2020'
    # end = '6/16/2020'
    # rand_samples = 100000
    # charts = False
    # pct = []
    # _return = False
    '''Returns a price simulation (price * volume) for "n" price simulations for commodity "c_nick".
    Arguments:
    >> c_nick --> commodity nickname for prices (see global commodity_reference).
    >> start, end --> start/end trade dates for historical prices to be simulated. Set to "all"
                    to set daterange start and end to first or last available data, respectively.
    >> n --> # of random price simulations.
    >> charts --> show default chart outputs.
    >> pct --> list of floats for percentiles in summary stats e.g. [0.10, 0.15, 0.25] etc. default provides
       the following percentiles for the price distribution: [1%, 5%, 10%, 25%, 50%, 75%, 90%, 95%, 99%].'''

    global scenario_time_stamp
    global excluded_prices
    global price_simulations
    if 'price_simulations' not in globals():
        price_simulations = OrderedDict()

    c_name = get_comdty_name(c_nick)
    c_unit = get_comdty_unit(c_nick)
    c_code = get_comdty_code(c_nick)

    # change start dates if needed
    ic4_start_date = '10/22/2019'
    hh_start_date = '1/1/2009'

    if c_nick == 'iso-butane' and pd.to_datetime(start) < pd.to_datetime(ic4_start_date):
        start = ic4_start_date

    # start natural gas sim at 1/1/2009
    elif c_nick == 'hh' or c_nick == 'hsc gas diff' or c_nick == 'waha diff':
        if pd.to_datetime(start) < pd.to_datetime(hh_start_date):
            start = hh_start_date

    global default_percentiles
    if len(pct) == 0:
        default_percentiles = set_default_percentiles([0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99])
    else:
        default_percentiles = pct
    print(f'| Default percentiles requested: {default_percentiles}')

    # get dates and prices
    if sim_all:
        print("| Simulation requested: all dates")
        start = get_dates(c_nick, 'start')
        end = get_dates(c_nick, 'end')

    date_range_requested = pd.date_range(start, end, freq='B')

    # for html filename
    price_scenario_name = f'{c_name}_{c_code}_{string_date(start)}_{string_date(end)}_n_{rand_samples}'
    print(f'\n| {len(date_range_requested)} MCS dates requested for {c_name}:\n    {date_range_requested}')

    global mcs_data
    global hist_prices
    global hist_trade_dates
    mcs_data = get_mcs_data(c_nick)

    s = intersect(list(date_range_requested), list(mcs_data.index))[0][0]
    e = intersect(list(date_range_requested), list(mcs_data.index))[0][-1]
    price_scenario_exists = price_sim_scenario_exists(c_code,
                                                      string_date(s),
                                                      string_date(e),
                                                      rand_samples)
    print(f'\n >>> Price _scenario exists? >> {price_scenario_exists}')

    ################# IF PRICE SCENARIO DOES NOT EXIST ############################
    if not price_scenario_exists:
        hist_prices = [mcs_data.loc[_]['settle_price'] for _ in mcs_data.index if _ in date_range_requested]
        print(f'\n| Historical prices available for {c_name}: {len(hist_prices)}')
        # exclude prices in excluded_prices for this c_nick
        try:
            hist_prices = [_ for _ in hist_prices if _ not in excluded_prices[c_nick]]
            print(
                f'\n| Prices excluded {c_name}: {excluded_prices[c_nick]}.\n| Remaining datapoints: {len(hist_prices)}')
        except KeyError:
            print(f'| No prices excluded.')

        hist_trade_dates = [mcs_data.loc[_]['trade_date'] for _ in mcs_data.index if _ in date_range_requested]
        print(f'\n| Historical trade dates available for {c_name}: {len(hist_trade_dates)}')

        # futures_months = 18
        # first_fut_month = max(hist_trade_dates)+MonthBegin(-1)
        # fut_trade_dates = pd.date_range()
        # all_trade_dates = [mcs_data.loc[_]['trade_date'] for _ in mcs_data.index if _ in date_range_requested]
        # exclude trade dates where price is in excluded_prices for this c_nick
        try:
            hist_trade_dates = [_ for _ in hist_trade_dates if mcs_data.loc[
                _, 'settle_price'] not in excluded_prices[c_nick]]
            print(f'''\n| Trade dates excluded where {c_name} price is in {excluded_prices[c_nick]}.
                  \n| Remaining datapoints: {len(hist_trade_dates)}''')
        except KeyError:
            print(f'| No trade dates excluded.')

        print(f'| Prices, dates retrieved: {len(hist_prices)}, {len(hist_trade_dates)}')
        print(pd.DataFrame(hist_prices, index=hist_trade_dates, columns=[c_name]))

        # run simulations
        global sim_results
        print('\n>>>> Running kernel density estimator >>>>\n')
        sim_results = run_KDE(hist_prices, c_nick, rand_samples)
        sim_random_samples = sim_results['random_samples']
        sim_logprob = sim_results['logprob']
        sim_x_d_linspace = sim_results['x_d_linspace']

        global summary_stats_dict
        if 'summary_stats_dict' not in globals():
            summary_stats_dict = OrderedDict()
        summary_stats = pd.DataFrame(hist_prices,
                                     columns=[f'Historical {c_name}']
                                     ).describe(default_percentiles)

        sim_summary_stats = pd.DataFrame(sim_random_samples,
                                         columns=[f'Simulated {c_name}']
                                         ).describe(default_percentiles)
        summary_stats = summary_stats.join(sim_summary_stats)
        print(f'>>>> Simulation results:\n{summary_stats}')
        summary_stats_dict[c_name] = summary_stats

        global model_prices
        global strip_pricing_date
        if 'model_prices' not in globals():
            model_prices = get_model_prices(strip_pricing_date=strip_pricing_date)

        results_dict = {'summary_stats': summary_stats,
                        'simulation_results': sim_results,
                        'historical_data': dict(zip(hist_trade_dates, hist_prices))}

        price_simulations[c_code] = OrderedDict()
        price_simulations[c_code][scenario_time_stamp] = results_dict

        # save _scenario summary to the price_data folder
        folder = root_folder_price_data(c_nick, as_of_date=strip_pricing_date)['root_folder']
        filename = f'{c_code}_{min(hist_trade_dates)}_{max(hist_trade_dates)}_n_{rand_samples}_summary_stats.json'
        save_to_json(summary_stats, folder, folder + filename, df_name='summary_stats')

        # save price simulations to model _scenario folder
        save_price_mcs_results(results=results_dict)

    ####### IF PRICE SCENARIO EXISTS ######################
    elif price_scenario_exists:
        hist_prices = [_ for _ in price_simulations[c_code][scenario_time_stamp]['historical_data'].values()]
        print(f'\n| Existing historical prices for {c_name}: {len(hist_prices)}')

        hist_trade_dates = [_ for _ in price_simulations[c_code][scenario_time_stamp]['historical_data'].keys()]
        print(f'\n| Existing trade dates for {c_name}: {len(hist_trade_dates)}')
        print(f'| Existing prices, dates: {len(hist_prices)}, {len(hist_trade_dates)}')
        print(pd.DataFrame(hist_prices, index=hist_trade_dates, columns=[c_name]))

        # run simulations
        print(f'\n>>>> Kernel density estimator has been run for {c_code} >> _scenario: {scenario_time_stamp}. >>>>\n')
        sim_results = price_simulations[c_code][scenario_time_stamp]['simulation_results']
        sim_random_samples = sim_results['random_samples']
        sim_logprob = sim_results['logprob']
        sim_x_d_linspace = sim_results['x_d_linspace']

        summary_stats = summary_stats_dict[c_name]
        print(f'>>>> Simulation results:\n{summary_stats}')
        results_dict = {'summary_stats': summary_stats,
                        'simulation_results': sim_results,
                        'historical_data': dict(zip(hist_trade_dates, hist_prices))}

    if charts:
        # make historical chart data
        start = string_date(min(hist_trade_dates))
        end = string_date(max(hist_trade_dates))
        hist_chart_data = ChartData(
            title=f'''Prices Modeled >> {c_name} // CME Code: {c_code} | Date Range Simulated >>> {start} to {end}''',
            x=hist_trade_dates,
            y=hist_prices,
            x_name='Trade Date',
            y_name=f'Front Month Settle ({c_unit})')

        # all charts output
        price_simulator_charts(c_nick,
                               historical_chart_data=hist_chart_data,
                               summary_stats=summary_stats,
                               random_samples=sim_random_samples,
                               logprob=sim_logprob,
                               x_d=sim_x_d_linspace,
                               scen_name=price_scenario_name
                               )

    if _return:
        return results_dict


def save_price_mcs_results(results: dict):
    '''Saves MCS data to model scenario folder.'''

    # local filepath
    local_scenario_folder = model_control.get_scenario_root_folders()['local_scenario_folder']
    local_folder = local_scenario_folder + "\/mcs_prices\/"
    # network filepath
    network_scenario_folder = model_control.get_scenario_root_folders()['network_scenario_folder']
    network_folder = network_scenario_folder + "\/mcs_prices\/"

    for idx, k_1 in enumerate(results_dict):
        if idx == 0:
            # summary_stats
            # save to json
            print(f'\n>> Saving: {k_1}')
            f_name = k_1
            filename_sim_results = f'{c_code}_{min(hist_trade_dates)}_{max(hist_trade_dates)}_n_{rand_samples}_{f_name}.json'
            data = pd.DataFrame(results_dict[k_1])
            save_to_json(data,
                         local_scenario_folder,
                         folder + filename_sim_results,
                         df_name=f'{k_1}')
            save_to_json(data,
                         network_scenario_folder,
                         folder + filename_sim_results,
                         df_name=f'{k_1}')
            save_to_excel(output_dataframe=data,
                          folder=local_scenario_folder,
                          filename=filename_sim_results)
            save_to_excel(output_dataframe=data,
                          folder=local_scenario_folder,
                          filename=filename_sim_results)

        elif idx == 2:
            # historical prices
            print(f'\n>> Saving: {k_1}')
            f_name = k_1
            filename_sim_results = f'{c_code}_{min(hist_trade_dates)}_{max(hist_trade_dates)}_n_{rand_samples}_{f_name}.json'
            data = pd.DataFrame(results_dict[k_1].items())
            save_to_json(data,
                         local_scenario_folder,
                         folder + filename_sim_results,
                         df_name=f'{k_1}')
            save_to_json(data,
                         network_scenario_folder,
                         folder + filename_sim_results,
                         df_name=f'{k_1}')
            save_to_excel(output_dataframe=data,
                          folder=local_scenario_folder,
                          filename=filename_sim_results)
            save_to_excel(output_dataframe=data,
                          folder=local_scenario_folder,
                          filename=filename_sim_results)

        elif isinstance(results_dict[k_1], dict) or isinstance(results_dict[k_1], OrderedDict):
            # simulation results
            for k_2 in results_dict[k_1]:
                print(f'\n>> Saving: {k_1} | {k_2}')
                f_name = k_1 + "_" + k_2
                filename_sim_results = f'{c_code}_{min(hist_trade_dates)}_{max(hist_trade_dates)}_n_{rand_samples}_{f_name}.json'
                data = pd.DataFrame(list(results_dict[k_1][k_2]))
                save_to_json(data,
                             local_scenario_folder,
                             folder + filename_sim_results,
                             df_name=f'{k_2}')
                save_to_json(data,
                             network_scenario_folder,
                             folder + filename_sim_results,
                             df_name=f'{k_2}')
                save_to_excel(output_dataframe=data,
                              folder=local_scenario_folder,
                              filename=filename_sim_results)
                save_to_excel(output_dataframe=data,
                              folder=local_scenario_folder,
                              filename=filename_sim_results)


@timer
def price_simulator_charts(c_nick,
                           historical_chart_data,
                           summary_stats,
                           random_samples,
                           logprob,
                           x_d,
                           histogram_bins=250,
                           histogram_norm='probability density',
                           scen_name=None
                           ):
    '''Returns default price simulator charts. Takes (random_samples, logprob, x_d)
    arguments from returned tuple of run_KDE() --> indexes = [0],[1], and [2].'''
    global ChartData
    ChartData = namedtuple('ChartData', 'title x y x_name y_name')
    fig = make_subplots(rows=2,
                        cols=2,
                        vertical_spacing=_vertical_spacing,
                        specs=[[{"type": "xy"}, {"type": "xy"}],
                               [{"type": "table"}, {"type": "xy"}]])

    c_name = get_comdty_name(c_nick)
    c_unit = get_comdty_unit(c_nick)

    _grid_color = 'rgba(220,220,220,1)'

    _width = _fig_width
    _height = _fig_height

    hist_price_chart = go.Scatter(y=historical_chart_data.y,
                                  x=historical_chart_data.x,
                                  name=f'{c_name} Historical Settlement Price',
                                  line_color=f'rgba(115,115,255,1.0)')
    hist_price_dist = go.Histogram(x=historical_chart_data.y,
                                   nbinsx=histogram_bins,
                                   histnorm=histogram_norm,  # 'percent',
                                   name=f'{c_name} Historical Price PDF',
                                   marker_color=f'rgba(150,150,255,0.8)')

    # summary stats table
    summary_stats = summary_stats.reset_index()
    #    summary_stats.rename(columns = {'index': ''}, inplace=True)
    summary_stats_table = summary_stats.rename(
        columns={'index': 'Historical vs Simulated Prices'})
    _values = [summary_stats_table[_].tolist() for _ in summary_stats_table.columns]
    _highlightable = _values[1][3:]  # valid values to highlight

    column_alignment = ['left'] + ['center'] * 2
    column_font_colors = ['rgb(40,40,40)'] * 3

    highlight_fill_color = hex_to_rgba('#c1e7ff', a=1.0, values=False)  # hex_to_rgba('#eeeeee')
    default_font_color = 'rgba(90,90,90,1.0)'
    highlight_font_color = 'darkblue'  # 'green' 'crimson' # hex_to_rgba('#ddccff') - #c1e7ff

    # if this is the current index
    try:
        column_fill_color = [[
            highlight_fill_color if _ in current_trading_range else 'rgba(250,250,250,1.0)' for _ in _values[1]], [
            highlight_fill_color if _ in current_trading_range else 'white' for _ in _values[1]]]
    except (NameError, ValueError):
        column_fill_color = ['rgba(245,245,245,1.0)', 'white']

    try:
        column_font_color = [[
            highlight_font_color if _ in current_trading_range else default_font_color for _ in _values[1]], [
            highlight_font_color if _ in current_trading_range else default_font_color for _ in _values[1]]]
    except (NameError, ValueError):
        column_font_color = [default_font_color] * 2

    summary_stats_table = go.Table(
        header=dict(values=[_ for _ in summary_stats_table.columns],
                    align=column_alignment,
                    line_color=_grid_color,
                    font=dict(color='darkblue',
                              size=_font_size + 2),
                    fill_color=hex_to_rgba('#eeeeee', a=1.0, values=False),
                    height=_font_size * 1.75),
        cells=dict(values=[
            summary_stats[_].tolist() for _ in summary_stats.columns],
            align=column_alignment,
            line=dict(color=_grid_color),
            font=dict(color=column_font_color,
                      size=_font_size),
            fill=dict(color=column_fill_color),
            format=[None] + [",.2f"],
            height=_font_size * 1.75))

    fig.add_table(
        columnorder=[1, 2],
        columnwidth=[400, 250],
        header=dict(),
        cells=dict(values=_values,
                   align=column_alignment,
                   line=dict(color=_grid_color),
                   font=dict(color=column_font_color,
                             size=_font_size),
                   fill=dict(color=column_fill_color),
                   format=[None] + [",.2f"],
                   height=_font_size * 1.75),
        row=2,
        col=1)

    sim_pdf = go.Scatter(y=np.exp(logprob),
                         x=x_d,
                         name=f'Simulated PDF (KDE)',
                         line_color=f'rgba(250,50,50,1.0)')
    # line_dash = 'dash') # 'dot' / 'dash'

    _histnorm = 'probability density'
    sim_price_dist = go.Histogram(x=random_samples,
                                  nbinsx=histogram_bins,
                                  histnorm=_histnorm,  # 'probability density',#'percent',
                                  name=f'''{c_name} Simulated Prices (n={len(random_samples): ,.0f})''',
                                  marker_color=f'rgba(250,175,175,0.8)')
    fig.add_traces([hist_price_chart,
                    hist_price_dist,
                    summary_stats_table,
                    sim_pdf,
                    sim_price_dist],
                   rows=[1, 1, 2, 2, 2], cols=[1, 2, 1, 2, 2])

    ## CHART 1 - HIST PRICE TIME SERIES
    # Update xaxis properties
    fig.update_xaxes(dict(title_text='Trade Date',
                          nticks=25,
                          tickangle=-45,
                          tickfont_size=_font_size,
                          gridcolor=_grid_color),
                     row=1,
                     col=1)

    # Update yaxis properties
    fig.update_yaxes(dict(title_text=f'Front Month Settle ({c_unit})',
                          tickformat='$,.2f\xa0',
                          nticks=40,
                          tickfont_size=_font_size,
                          linecolor='rgba(10,10,10,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(15,15,15,0.75)',
                          gridcolor=_grid_color),
                     row=1,
                     col=1)

    ## CHART 2 - HIST PRICE HISTOGRAM
    # TODO: to highlight futures only
    #     futures = dict_drill_down(
    #         futures_to_attach,
    #         key_sequence=[-1],
    #         return_values=True,
    #         silent=True).y
    #     stats = summary_stats_table.iloc[3:,1].to_list()
    #     current_trading_range = inclusive_range(futures, stats)

    for r in range(1, 3):
        # Update xaxis properties
        fig.update_xaxes(dict(title_text=f'Front Month Settle ({c_unit})',
                              nticks=20,
                              tickangle=-45,
                              tickformat='$,.2f\xa0',
                              tickfont_size=_font_size,
                              gridcolor=_grid_color),
                         row=r,
                         col=2)

        _title_text_y = [
            f'# of datapoints (n)' if _histnorm == '' else _histnorm][0]
        # Update yaxis properties
        fig.update_yaxes(dict(title_text=_title_text_y,
                              nticks=20,
                              tickfont_size=_font_size,
                              tickformat=',.2f\xa0',
                              linecolor='rgba(10,10,10,0.75)',
                              zeroline=True,
                              zerolinecolor='rgba(15,15,15,0.75)',
                              gridcolor=_grid_color),
                         row=r,
                         col=2)

    #     fig.update_layout(layout)
    fig.update_layout(title=f'{historical_chart_data.title}',
                      title_xanchor='left',
                      title_yanchor='top',
                      plot_bgcolor='rgba(255,255,255,1.0)',
                      width=_width,
                      height=_height,
                      legend=dict(orientation='v',
                                  y=1.00,
                                  x=1.05,
                                  font_size=_font_size))

    if scen_name is None:
        scen_name = input(prompt='\n| Enter _scenario name for price_simulator_charts: ')

    # save and show chart
    filename = f'{scen_name}_price_mcs_{c_nick}'
    save_and_show(fig, chart_filename=filename, _width=_width, _height=_height)


def save_and_show(fig, chart_filename, _width, _height):
    # save and show figure
    filename_html = f'{scenario_time_stamp}_{chart_filename}.html'
    filename_png = f'{scenario_time_stamp}_{chart_filename}.png'
    filename_pdf = f'{scenario_time_stamp}_{chart_filename}.pdf'

    # local filepath
    local_scenario_folder = model_control.get_scenario_root_folders()['local_scenario_folder']
    local_folder = local_scenario_folder + "\/charts\/"
    # network filepath
    network_scenario_folder = model_control.get_scenario_root_folders()['network_scenario_folder']
    network_folder = network_scenario_folder + "\/charts\/"

    # local save - html
    save_chart(fig, local_folder, local_folder + filename_html)
    # network save - html
    save_chart(fig, network_folder, network_folder + filename_html)

    # local save - PNG
    fig.write_image(local_folder + filename_png, width=_width, height=_height)
    # network save - PNG
    fig.write_image(network_folder + filename_png, width=_width, height=_height)

    # local save - PDF
    fig.write_image(local_folder + filename_pdf, width=_width, height=_height)
    # network save - PDF
    fig.write_image(network_folder + filename_pdf, width=_width, height=_height)

    # show fig
    fig.show()
