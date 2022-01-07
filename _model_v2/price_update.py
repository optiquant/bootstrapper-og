import os
import requests
import io
import re
import pandas as pd
from matplotlib import rcParams
from matplotlib import pyplot as plt
from pandas.tseries.offsets import *
from datetime import datetime
from bs4 import BeautifulSoup
import seaborn as sns

# show all columns
pd.set_option('display.max_columns', None)

# commodity reference
# {comdty_code: [comdty_name, comdty_desc, comdty_nick, comdty_unit, comdty_scale]
COMDTY_REF = {
    'CS': ['WTI CMA', 'Wti Financial Futures', 'wti_cma', '$/Bbl', 5.00],
    'CL': ['WTI Oil', 'Light Sweet Crude Oil Futures', 'wti', '$/Bbl', 5.00],
    'WTT': ['MidCush - WTT', 'Wti Midland (argus) Vs. Wti Trade Month Futures', 'midcush_wtt', '$/Bbl', 1.00],
    'FF': ['MidCush - FF', 'Wti Midland(argus) Vs. Wti Financial Futures', 'midcush_ff', '$/Bbl', 1.00],
    'CY': ['Brent Oil', 'Brent Financial Futures', 'brent', '$/Bbl', 5.00],
    # 'HCL': ['WTI Houston Oil', 'Wti Houston Crude Oil Futures', 'wti_hou', '$/Bbl', 5.00],
    'NG': ['HH Gas', 'Henry Hub Natural Gas Futures', 'hh', '$/MMBtu', 0.50],
    # 'NW': ['Waha Diff', 'Waha Natural Gas (platts Iferc) Basis Futures', 'waha_gas_diff', '$/MMBtu', 0.50],
    # 'NHN': ['HSC Gas Diff', 'Houston Ship Channel Natural Gas (platts Iferc) Ba', 'hsc_gas_diff', '$/MMBtu', 0.50],
    'C0': ['Ethane Mt.Belvieu', 'Mont Belvieu Ethane (opis) Futures', 'ethane', '$/gal', 0.05],
    'B0': ['Propane Mt.Belvieu LDH', 'Mont Belvieu Ldh Propane (opis) Futures', 'propane', '$/gal', 0.10],
    'D0': ['n-Butane', 'Mont Belvieu Normal Butane (opis) Futures', 'n_butane', '$/gal', 0.1],
    '8I': ['iso-Butane', 'Mont Belvieu Iso-butane (opis) Futures', 'iso_butane', '$/gal', 0.1],
    '7Q': ['Nat. Gasoline', 'Mont Belvieu Natural Gasoline (opis) Futures', 'nat_gasoline', '$/gal', 0.20]
}



# local save folder for normalized nymex data
PRICE_DATA_FOLDER = "C:\\Users\\viren\\Documents\\Consulting\\_price_data\\"
CURRENT_TRADE_DATE = None
DAYS_OF_STRIP_T_MINUS = [0, 1, 2, 3, 4, 5, 10, 15, 30, 60]

def get_nymex_settlement_data():
    """Requests the most recent 5 days NYMEX settlement data from CME Group, and saves the csv files."""

    settlement_data = {}
    # urls for price data
    nymex_url = r'https://www.cmegroup.com/ftp/settle/'
    extension = r'nymex.settle.20220104.s.csv'
    extension_tags = [r'nymex.settle.', r'.csv']

    # custom headers (browser version must match)
    # ref: https://stackoverflow.com/questions/51092889/receiving-http-error-403-forbidden-csv-download/51093473
    hdr = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
           "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
           "X-Requested-With": "XMLHttpRequest"}  # change the version of the browser accordingly

    # response from server
    response = requests.get(nymex_url, headers=hdr)

    # get the recent nymex settlement data currently on the page
    parser = 'html.parser'
    soup = BeautifulSoup(response.content, parser, from_encoding='utf-8')
    links = soup.find_all('a', href=True)
    _ptrn = re.compile(r'(nymex.settle.)([0-9]+)\S*(.csv)$')
    links = list(map(lambda x: x['href'],
                     filter(lambda lnk: re.search(_ptrn, lnk['href']),
                            links)))
    print(links)

    for idx, link in enumerate(links):
        print(f'| Getting data for {idx}: {link}')
        # get the response from the server
        response = requests.get(nymex_url + link, headers=hdr)
        # create a file object from the response object
        file_object = io.StringIO(response.content.decode('utf-8'))
        # read the csv file object
        data = pd.read_csv(file_object)
        # normalize and save data
        # filter out commodities we don't need
        data = data.loc[data['ID'].isin(COMDTY_REF)]
        print(f'| Commodities found in NYMEX data: {data.ID.unique()}')
        data.reset_index(inplace=True)
        data.rename(columns={'index': 'raw_index'}, inplace=True)
        data = data.assign(comdty_code=lambda x: x['ID'],
                           comdty_name=lambda x: [COMDTY_REF[_][0] for _ in x['ID']],
                           comdty_desc=lambda x: [COMDTY_REF[_][1] for _ in x['ID']],
                           comdty_nick=lambda x: [COMDTY_REF[_][2] for _ in x['ID']],
                           trade_date=lambda x: x['BizDt'].astype('datetime64[D]'),
                           contract_year=lambda x: x['MatDt'].str.slice(stop=4).astype('int64'),
                           contract_month=lambda x: x['MatDt'].str.slice(start=5, stop=7).astype('int64'),
                           contract_date=lambda x: [datetime(year=y, month=m, day=28) + MonthEnd(1) for y, m in
                                                    zip(x.contract_year, x.contract_month)],
                           future_month_index=lambda x: range(len(x['ID'])),
                           settle_price=lambda x: x['SettlePrice'],
                           comdty_unit=lambda x: [COMDTY_REF[_][3] for _ in x['ID']],
                           open_interest=lambda x: x['PrevDayOI'],
                           volume=lambda x: x['PrevDayVol'],
                           last_trade_date=lambda x: x['LastTrdDt'].astype('datetime64[D]')
                           )
        print(data.head())
        # save to drive
        filepath = os.path.join(PRICE_DATA_FOLDER, 'nymex_price_data\\' + link)
        try:
            data.to_csv(filepath)
            print(f'>> Raw data saved to {filepath}\n')
        except FileNotFoundError:
            # create folder
            os.makedirs(PRICE_DATA_FOLDER + 'nymex_price_data\\')
            data.to_csv(filepath)
            print(f'>> Raw data saved to {filepath}\n')
        settlement_data[idx] = data

    return settlement_data


def normalize_daily_data(settlement_data):
    """Extract individual commodities from raw settlement data and saves to the respective price_data folders."""

    # settlement data has all commodities
    for hist_day, data in settlement_data.items():
        for c_code in COMDTY_REF:
            # filter for this commodity
            filtered_data = data[data.comdty_code == c_code]
            price_data_json = {
                'comdty_code': {},'comdty_name': {},'comdty_desc': {},
                'trade_date': {},'contract_year': {},'contract_month': {},'contract_date': {},
                'future_month_index': {},'settle_price': {},'comdty_unit': {},'open_interest': {},
                'volume': {},'last_trade_date': {}
            }
            for field in price_data_json:
                _reset_data = filtered_data[field].reset_index(drop=True)
                price_data_json[field].update(_reset_data)
            # save the price_data_json
            price_data_json = pd.DataFrame(price_data_json)
            # convert dates to readable
            price_data_json.trade_date = pd.to_datetime(price_data_json.trade_date).dt.strftime('%Y-%m-%d')
            price_data_json.contract_date = pd.to_datetime(price_data_json.contract_date).dt.strftime('%Y-%m-%d')
            price_data_json.last_trade_date = pd.to_datetime(price_data_json.last_trade_date).dt.strftime('%Y-%m-%d')
            # save to drive
            trade_date = f'{price_data_json.trade_date[0]}'
            # if this is the most recent settlement, updated the current trade date
            if hist_day == max(settlement_data.keys()):
                global CURRENT_TRADE_DATE
                CURRENT_TRADE_DATE = trade_date
            filepath = os.path.join(PRICE_DATA_FOLDER, c_code + '\\' + f'_prices_{c_code}_{trade_date}.json')
            try:
                price_data_json.to_json(filepath)
                print(f'>> {COMDTY_REF[c_code][0]}//{c_code} updated: {filepath}\n')
            except FileNotFoundError:
                # create folder
                os.makedirs(PRICE_DATA_FOLDER + c_code + '\\')
                price_data_json.to_json(filepath)
                print(f'>> {COMDTY_REF[c_code][0]}//{c_code} updated: {filepath}\n')

def get_heatmap_price_data():

    price_data_dict = {}
    for c_code in COMDTY_REF:
        price_data_dict[c_code] = []
        price_folder = os.path.join(PRICE_DATA_FOLDER, c_code + '\\')
        _ptrn = re.compile(r'(\d){4}(\-\d{2}){2}')
        price_files = list(filter(lambda x: re.search(_ptrn, x),
                                  os.listdir(price_folder)))[::-1]

        price_files = [price_files[_] for _ in DAYS_OF_STRIP_T_MINUS]
        print(price_files)

        for file in price_files:
            price_json = pd.read_json(os.path.join(price_folder, file))
            price_data_dict[c_code].append(price_json)
    return price_data_dict


def build_heatmap_data(price_data_dict):
    heatmaps = {}
    for c_code, price_dfs in price_data_dict.items():
        latest_prices = price_dfs[0]
        print(f'| Building heatmap data for {c_code} >> ')
        strip_current = latest_prices['settle_price']

        # calculate the deltas to prior settlements
        strip_delta_t_minus = {idx: strip_current - _['settle_price'] for idx, _ \
                               in enumerate(price_dfs[1:], start=1)}
        strip_delta_t_minus = pd.DataFrame(strip_delta_t_minus)
        new_columns = {_: f'vs T-{DAYS_OF_STRIP_T_MINUS[_]}' for _ in strip_delta_t_minus.columns}
        strip_delta_t_minus.rename(columns=new_columns, inplace=True)
        strip_delta_t_minus = strip_delta_t_minus.assign(
            future_month=[f'Month {_ + 1}' for _ in strip_delta_t_minus.index]
        )
        strip_delta_t_minus.set_index('future_month', inplace=True)
        strip_delta_t_minus = strip_delta_t_minus.iloc[:24, :].T
        print(f'| {c_code} >>\n', strip_delta_t_minus)
        heatmaps[c_code] = strip_delta_t_minus
    return heatmaps

def build_heatmap_charts(heatmap_data):
    for idx, (c_code, chart_data) in enumerate(heatmap_data.items()):
        c_name = COMDTY_REF[c_code][0]
        c_unit = COMDTY_REF[c_code][3]
        rcParams['figure.figsize'] = (10, 6)
        rcParams['axes.edgecolor'] = 'black'
        rcParams['axes.linewidth'] = 0.75
        ax = sns.heatmap(chart_data,
                         annot=True, fmt='.2f',
                         linewidths=0.5,
                         center=0.0,
                         # ax=axs[idx // 3, idx % 3-1],
                         cbar=False,
                         cmap=sns.color_palette('inferno', as_cmap=True),
                         cbar_kws={"orientation": "horizontal"})
        ax.set_xticklabels(ax.get_xticklabels(), rotation=40)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
        ax.set(title=f'{c_name} | CME: {c_code} | {c_unit}')
        for _, spine in ax.spines.items():
            spine.set_visible(True)

        plt.tight_layout()
        plt.savefig(os.path.join(PRICE_DATA_FOLDER,
                                 f'_price_updates\\{CURRENT_TRADE_DATE}_{c_name}_{c_code}_heatmap.png')
                    )
        plt.show()

# --------------------------------------------------------------------------------------------------- #
# --------------------------------------------- EXECUTION ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #

settlement_data = get_nymex_settlement_data()
normalize_daily_data(settlement_data)
# todo: make charts!
price_data_dict = get_heatmap_price_data()
heatmap_data = build_heatmap_data(price_data_dict)
build_heatmap_charts(heatmap_data)

# heatmaps
# fig, axs = plt.subplots(nrows=4, ncols=3)

