import pandas as pd
import os
from pandas.tseries.offsets import *
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import urllib.request
import io
import re

# show all columns
pd.set_option('display.max_columns', None)



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

settlement_data = {}
# commodity reference
# {comdty_code: [comdty_name, comdty_desc, comdty_nick, comdty_unit, comdty_scale]
COMDTY_REF = {
    'CS': ['WTI CMA', 'Wti Financial Futures', 'wti_cma', '$/Bbl', 5.00],
    'CL': ['WTI Oil', 'Light Sweet Crude Oil Futures', 'wti', '$/Bbl', 5.00],
    'WTT': ['MidCush - WTT', 'Wti Midland (argus) Vs. Wti Trade Month Futures', 'midcush_wtt', '$/Bbl', 1.00],
    'FF': ['MidCush - FF', 'Wti Midland(argus) Vs. Wti Financial Futures', 'midcush_ff', '$/Bbl', 1.00],
    'CY': ['Brent Oil', 'Brent Financial Futures', 'brent', '$/Bbl', 5.00],
    'HCL': ['WTI Houston Oil', 'Wti Houston Crude Oil Futures', 'wti_hou', '$/Bbl', 5.00],
    'NG': ['HH Gas', 'Henry Hub Natural Gas Futures', 'hh', '$/MMBtu', 0.50],
    'NW': ['Waha Diff', 'Waha Natural Gas (platts Iferc) Basis Futures', 'waha_gas_diff', '$/MMBtu', 0.50],
    'NHN': ['HSC Gas Diff', 'Houston Ship Channel Natural Gas (platts Iferc) Ba', 'hsc_gas_diff', '$/MMBtu', 0.50],
    'C0': ['Ethane Mt.Belvieu', 'Mont Belvieu Ethane (opis) Futures', 'ethane', '$/gal', 0.05],
    'B0': ['Propane Mt.Belvieu LDH', 'Mont Belvieu Ldh Propane (opis) Futures', 'propane', '$/gal', 0.10],
    'D0': ['n-Butane', 'Mont Belvieu Normal Butane (opis) Futures', 'n_butane', '$/gal', 0.1],
    '8I': ['iso-Butane', 'Mont Belvieu Iso-butane (opis) Futures', 'iso_butane', '$/gal', 0.1],
    '7Q': ['Nat. Gasoline', 'Mont Belvieu Natural Gasoline (opis) Futures', 'nat_gasoline', '$/gal', 0.20]
}

price_data_json = {'comdty_code': {},
                   'comdty_desc': {},
                   'trade_date': {},
                   'contract_year': {},
                   'contract_month': {},
                   'contract_date': {},
                   'future_month_index': {},
                   'settle_price': {},
                   'open_interest': {},
                   'volume': {},
                   'last_trade_date': {},
                   }

# local save folder for normalized nymex data
local_folder="C:\\Users\\viren\\Documents\\Consulting\\_price_data\\"

# read the csv files for each link
for idx, link in enumerate(links):
    print(f'| Getting data for {idx}: {link}')
    # get the response from the server
    response = requests.get(nymex_url + link, headers=hdr)
    # create a file object from the response object
    file_object = io.StringIO(response.content.decode('utf-8'))
    # read the csv file object
    data = pd.read_csv(file_object)
    print(data.info())

    # normalize and save data
    # filter out commodities we don't need
    data = data.loc[data['ID'].isin(COMDTY_REF)]
    print(data.ID.unique())
    data.reset_index(inplace=True)
    data.rename(columns={'index': 'raw_index'}, inplace=True)
    data = data.assign(comdty_code=lambda x: x['ID'],
                       comdty_name=lambda x: [COMDTY_REF[_][0] for _ in x['ID']],
                       comdty_desc=lambda x: [COMDTY_REF[_][1] for _ in x['ID']],
                       comdty_nick=lambda x: [COMDTY_REF[_][2] for _ in x['ID']],
                       trade_date=lambda x: x['BizDt'].astype('datetime64[D]'),
                       contract_year=lambda x: x['MatDt'].str.slice(stop=4).astype('int64'),
                       contract_month=lambda x: x['MatDt'].str.slice(start=5, stop=7).astype('int64'),
                       contract_date=lambda x: [datetime(year=y, month=m, day=28)+MonthEnd(1) for y,m in zip(x.contract_year, x.contract_month)],
                       future_month_index=lambda x: list(dict(enumerate(x['ID'])).keys()),
                       settle_price=lambda x: x['SettlePrice'],
                       comdty_unit=lambda x: [COMDTY_REF[_][3] for _ in x['ID']],
                       open_interest=lambda x: x['PrevDayOI'],
                       volume=lambda x: x['PrevDayVol'],
                       last_trade_date=lambda x: x['LastTrdDt'].astype('datetime64[D]')
                       )
    print(data)
    # save to drive
    filepath = os.path.join(local_folder, 'nymex_price_data\\'+link)
    try:
        data.to_csv(filepath)
        print(f'>> Saved to {filepath}')
    except FileNotFoundError:
        # create folder
        os.makedirs(local_folder+'nymex_price_data\\')
        data.to_csv(filepath)
        print(f'>> Saved to {filepath}')

    settlement_data[idx] = data


# extract individual commodities and save to respective price_data folders
for hist_day in settlement_data:
    # all commodities
    data = settlement_data[hist_day]
    for c_code in COMDTY_REF:
        # filter for this commodity
        data = data[data.comdty_code == c_code]
        for field in price_data_json:
            _reset_data = data[field].reset_index(drop=True)
            price_data_json[field].update(_reset_data)
            print(f'{field}: {price_data_json[field]}')
        # save the price_data_json
        price_data_json = pd.DataFrame(price_data_json)
        # convert dates to readable
        price_data_json.trade_date = pd.to_datetime(price_data_json.trade_date).dt.strftime('%Y-%m-%d')
        price_data_json.contract_date = pd.to_datetime(price_data_json.contract_date).dt.strftime('%Y-%m-%d')
        price_data_json.last_trade_date = pd.to_datetime(price_data_json.last_trade_date).dt.strftime('%Y-%m-%d')
        # save to drive
        trade_date = f'{price_data_json["trade_date"][0]}'
        filepath = os.path.join(local_folder, c_code+'\\'+f'_prices_{c_code}_{trade_date}.json')
        try:
            price_data_json.to_json(filepath)
            print(f'>> Saved to {filepath}')
        except FileNotFoundError:
            # create folder
            os.makedirs(local_folder + c_code+'\\')
            price_data_json.to_json(filepath)
            print(f'>> Saved to {filepath}')

# todo: make charts!