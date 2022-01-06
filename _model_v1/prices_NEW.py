import pandas as pd
from bs4 import BeautifulSoup
import requests
import urllib.request
import io
import re

# urls for price data
nymex_url = r'https://www.cmegroup.com/ftp/settle/'
extension = r'nymex.settle.20220104.s.csv'
extension_tags = [r'nymex.settle.', r'.csv']

# custom headers (browser version must match)
# ref: https://stackoverflow.com/questions/51092889/receiving-http-error-403-forbidden-csv-download/51093473
hdr = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest"} #change the version of the browser accordingly

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

# read the csv files for each link
for idx, link in enumerate(links):
    print(f'| Getting data for {idx}: {link}')
    # get the response from the server
    response = requests.get(nymex_url+link, headers=hdr)
    # create a file object from the response object
    file_object = io.StringIO(response.content.decode('utf-8'))
    # read the csv file object
    data = pd.read_csv(file_object)
    # fix column data type
    data['BizDt'] = data['BizDt'].astype('datetime64[D]')
    print(data.head())
    settlement_data[idx] = data

# commodity reference
# uses the "ID" column

COMDTY_REF = {
    'CS': ['WTI CMA',
           'Wti Financial Futures',
           'wti_cma',
           '$/Bbl',
           5.00],
    'CL': ['WTI Oil',
           'Light Sweet Crude Oil Futures',
           'wti',
           '$/Bbl',
           5.00],
    'WTT': ['MidCush - WTT',
            'Wti Midland (argus) Vs. Wti Trade Month Futures',
            'midcush_wtt',
            '$/Bbl',
            1.00],
    'FF': ['MidCush - FF',
           'Wti Midland(argus) Vs. Wti Financial Futures',
           'midcush_ff',
           '$/Bbl',
           1.00],
    'CY': ['Brent Oil',
           'Brent Financial Futures',
           'brent',
           '$/Bbl',
           5.00],
    'HCL': ['WTI Houston Oil',
            'Wti Houston Crude Oil Futures',
            'wti_hou',
            '$/Bbl',
            5.00],
    'NG': ['HH Gas',
           'Henry Hub Natural Gas Futures',
           'hh',
           '$/MMBtu',
           0.50],
    'NW': ['Waha Diff',
           'Waha Natural Gas (platts Iferc) Basis Futures',
           'waha_gas_diff',
           '$/MMBtu',
           0.50],
    'NHN': ['HSC Gas Diff',
            'Houston Ship Channel Natural Gas (platts Iferc) Ba',
            'hsc_gas_diff',
            '$/MMBtu',
            0.50],
    'C0': ['Ethane Mt.Belvieu',
           'Mont Belvieu Ethane (opis) Futures',
           'ethane',
           '$/gal',
           0.05],
    'B0': ['Propane Mt.Belvieu LDH',
           'Mont Belvieu Ldh Propane (opis) Futures',
           'propane',
           '$/gal',
           0.10],
    'D0': ['n-Butane',
           'Mont Belvieu Normal Butane (opis) Futures',
           'n_butane',
           '$/gal',
           0.1],
    '8I': ['iso-Butane',
           'Mont Belvieu Iso-butane (opis) Futures',
           'iso_butane',
           '$/gal',
           0.1],
    '7Q': ['Nat. Gasoline',
           'Mont Belvieu Natural Gasoline (opis) Futures',
           'nat_gasoline',
           '$/gal',
           0.20]
}


price_data_json = {'comdty_code': {},
                   'comdty_desc':{},
                   'trade_date':{},
                   'contract_date':{},
                   'contract_year':{},
                   'contract_mth':{},
                   'future_mth_idx':{},
                   'settle_price':{},
                   'open_interest':{},
                   'volume':{},
                   'last_trade_date':{},
                   }

# todo: get the 5 days new settlement data into this format and save to each commodity's folder in
#  the drive
# todo: create a mapping for the keys of price_data_json and the columns of the settlement data