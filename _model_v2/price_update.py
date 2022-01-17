import requests
import io
import os
import re
import json
import pandas as pd
from pandas.tseries.offsets import MonthEnd, BDay
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime
import seaborn as sns
from matplotlib import rcParams
import matplotlib.pyplot as plt
import matplotlib.ticker as tkr

# show all columns
pd.set_option('display.max_columns', None)

PRICE_DATA_FOLDER = r'c:/users/viren/documents/consulting/_price_data/'
hist_days = [0, 1, 2, 3, 4, 5, 6, 10, 20, 60]
STRIP_PRICING_FILE = {}
MASTER_HEATMAP_DATA = {}
CURRENT_TRADE_DATE = None
PRICE_CHART_DATES = []

# commodity reference
# {comdty_code: [comdty_name, comdty_desc, comdty_nick, comdty_unit, comdty_scale]
COMDTY_REF = {
    'CS': ['WTI CMA', 'Wti Financial Futures', 'wti_cma', '$/Bbl', 2.00],
    'CL': ['WTI Oil', 'Light Sweet Crude Oil Futures', 'wti', '$/Bbl', 2.00],
    'WTT': ['MidCush - WTT', 'Wti Midland (argus) Vs. Wti Trade Month Futures', 'midcush_wtt', '$/Bbl', 0.10],
    'FF': ['MidCush - FF', 'Wti Midland(argus) Vs. Wti Financial Futures', 'midcush_ff', '$/Bbl', 0.10],
    'CY': ['Brent Oil', 'Brent Financial Futures', 'brent', '$/Bbl', 2.00],
    # 'HCL': ['WTI Houston Oil', 'Wti Houston Crude Oil Futures', 'wti_hou', '$/Bbl', 1.00],
    'NG': ['HH Gas', 'Henry Hub Natural Gas Futures', 'hh', '$/MMBtu', 0.50],
    # 'NW': ['Waha Diff', 'Waha Natural Gas (platts Iferc) Basis Futures', 'waha_gas_diff', '$/MMBtu', 0.25],
    # 'NHN': ['HSC Gas Diff', 'Houston Ship Channel Natural Gas (platts Iferc) Ba', 'hsc_gas_diff', '$/MMBtu', 0.25],
    'C0': ['Ethane Mt.Belvieu', 'Mont Belvieu Ethane (opis) Futures', 'ethane', '$/gal', 0.05],
    'B0': ['Propane Mt.Belvieu LDH', 'Mont Belvieu Ldh Propane (opis) Futures', 'propane', '$/gal', 0.05],
    'D0': ['n-Butane', 'Mont Belvieu Normal Butane (opis) Futures', 'n_butane', '$/gal', 0.05],
    '8I': ['iso-Butane', 'Mont Belvieu Iso-butane (opis) Futures', 'iso_butane', '$/gal', 0.05],
    '7Q': ['Nat. Gasoline', 'Mont Belvieu Natural Gasoline (opis) Futures', 'nat_gasoline', '$/gal', 0.05]
}




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
                           contract_year=lambda x: x['MMY'].astype('str').str.slice(stop=4).astype('int64'),
                           contract_month=lambda x: x['MMY'].astype('str').str.slice(start=4).astype('int64'),
                           contract_date=lambda x: [datetime(year=y, month=m, day=28) + MonthEnd(0) for y, m in
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

        price_files = [price_files[_] for _ in hist_days]
        print(price_files)

        for file in price_files:
            price_json = pd.read_json(os.path.join(price_folder, file))
            price_data_dict[c_code].append(price_json)
    return price_data_dict


def manual_update_function():
    """Helper function for manual updates of historical price data. Update as necessary."""

    # _fp = 'c:/users/viren/documents/consulting/_price_data/'
    # # use this to update individual price data jsons
    # dates = ['2021-12-31', '2021-12-30', '2021-12-29']
    # files = [os.path.join(_fp, f'{c_code}/_prices_{c_code}_{date}.json') for c_code in COMDTY_REF for date in dates]
    # print(files)
    #
    # # regex to get the comdty_code from the filename
    # _ptrn = re.compile(r'\s*(?<=(s\_){1})(\w{2})(?=(\_{1}\d{4}))*')

    _fp = 'c:/users/viren/documents/consulting/_price_data/nymex_price_data/'
    files = [os.path.join(_fp, 'nymex.settle.20211229.s.csv'),
             os.path.join(_fp, 'nymex.settle.20211230.s.csv'),
             os.path.join(_fp, 'nymex.settle.20211231.s.csv'),
             os.path.join(_fp, 'nymex.settle.20220103.s.csv'),
             os.path.join(_fp, 'nymex.settle.20220104.s.csv'),
             os.path.join(_fp, 'nymex.settle.20220105.s.csv'),
             os.path.join(_fp, 'nymex.settle.20220106.s.csv'),
             os.path.join(_fp, 'nymex.settle.20220107.s.csv')
             ]

    for f in files:
        print(f)
        data = pd.read_csv(f)
        # show only the relevant columns
        print('>>> prior:\n', data.head()[['MMY', 'contract_year', 'contract_month', 'contract_date']])
        # updates contract_date col for the dates chosen
        data = data.assign(contract_year=lambda x: x['MMY'].astype('str').str.slice(stop=4).astype('int64'),
                           contract_month=lambda x: x['MMY'].astype('str').str.slice(start=4).astype('int64'),
                           contract_date=lambda x: [datetime(year=y, month=m, day=28) + MonthEnd(0) for y, m in
                                                    zip(x.contract_year, x.contract_month)])
        # show only the relevant columns
        print('>>> updated:\n', data.head()[['MMY', 'contract_year', 'contract_month', 'contract_date']])
        # convert dates to readable form
        data.trade_date = pd.to_datetime(data.trade_date).dt.strftime('%Y-%m-%d')
        data.contract_date = pd.to_datetime(data.contract_date).dt.strftime('%Y-%m-%d')
        data.last_trade_date = pd.to_datetime(data.last_trade_date).dt.strftime('%Y-%m-%d')
        data.to_csv(f)


def check_replace_missing(chart_dates):
    """Replaces missing dates with the nearest previous date available in the price chart dates."""
    global PRICE_CHART_DATES
    missing_dates = [_ for _ in chart_dates if _ not in PRICE_CHART_DATES]
    if len(missing_dates) > 0:
        for md in missing_dates:
            nearest_prev = map(lambda x: pd.to_timedelta(pd.to_datetime(x) - pd.to_datetime(md)), PRICE_CHART_DATES)
            nearest_prev = list(filter(lambda x: x.days < 0, nearest_prev))
            nearest_prev = PRICE_CHART_DATES[np.argmax(nearest_prev)]
            print(f'{md} not found in price chart dates --> replacing with {nearest_prev}')
            repl_index = chart_dates.index(md)
            chart_dates[repl_index] = nearest_prev
    return chart_dates


def build_price_update_charts():
    global PRICE_DATA_FOLDER
    global STRIP_PRICING_FILE
    global MASTER_HEATMAP_DATA
    global hist_days
    global CURRENT_TRADE_DATE
    global PRICE_CHART_DATES
    c_codes = COMDTY_REF.keys()
    # c_codes = ['CL']
    for c_code in c_codes:
        # get all price files for this commodity
        # c_code = c_codes[0]
        c_name = COMDTY_REF[c_code][0]

        files = os.listdir(os.path.join(PRICE_DATA_FOLDER, f'{c_code}/'))
        # only include files with a date
        _ptrn = re.compile(r'\s*\_{1}\d{4}(\-\d{2}){2}')
        files = list(filter(lambda x: re.search(_ptrn, x), files))
        print(f'{c_code}: {len(files)} price data files found.')

        # get the trade dates
        ALL_TRADE_DATES = list(map(lambda x: re.search('\d{4}(\-\d{2}){2}', x).group(), files))

        # get the current trade date
        CURRENT_TRADE_DATE = ALL_TRADE_DATES[-1]
        print('CURRENT_TRADE_DATE:', CURRENT_TRADE_DATE)

        # all dates
        _price_chart_start = pd.to_datetime('1/1/2009')
        PRICE_CHART_DATES = list(filter(lambda x: pd.to_datetime(x) >= _price_chart_start, ALL_TRADE_DATES))
        CHART_MONTHS = 24

        # regex to get the comdty_code from the filename
        _ptrn = re.compile(r'\s*(?<=(\_prices\_){1})(\w+)(?=(\_{1}\d{4}))')

        # get the data from the files
        chart_files = [_ for _ in files if any([f in _ for f in PRICE_CHART_DATES])]
        print(f'chart_files: {len(chart_files)}')
        json_data = []
        for idx, _f in enumerate(chart_files):
            c_code = re.search(_ptrn, _f).group()
            if idx in [0, len(chart_files)-1]:
                print(_f)
            try:
                data = json.load(open(os.path.join(PRICE_DATA_FOLDER, f'{c_code}/{_f}'), 'r'))
                json_data.append(data)
            except ValueError as e:
                print(c_code, ':', e)

        # make dataframes from the jsons
        price_data = [pd.DataFrame(_) for _ in json_data]
        # trim each to chart months
        price_data = [_.iloc[:CHART_MONTHS, :] for _ in price_data]
        # concatenate all the price history
        price_data = pd.concat(price_data, ignore_index=True)
        # create a legend column, and convert dates
        price_data = price_data.assign(
            Legend=lambda x: [' | '.join(_) for _ in zip(x['comdty_code'].map(str), x['trade_date'].map(str))],
            trade_date=lambda x: pd.to_datetime(x['trade_date']).dt.strftime('%Y-%m-%d'),
            contract_date=lambda x: pd.to_datetime(x['contract_date']).dt.strftime('%Y-%m-%d')
        )
        # filter out unneeded columns
        price_data = price_data[['Legend', 'trade_date', 'contract_date', 'settle_price']]
        print(price_data)

        # ------------------ CHARTS ------------------ #
        fig, axes = plt.subplots(2, 2, sharey=False, sharex=False, figsize=(16, 10))
        fig.suptitle(f'{c_name} Futures (CME Code: {c_code}) | Price Unit: {COMDTY_REF[c_code][3]}')

        # -------- STRIP CHART --------- #
        # strip movement, last x days
        days_of_strip = 7
        strip_chart_dates = filter(lambda x: x <= days_of_strip, hist_days[::-1])
        strip_chart_dates = list(
            map(lambda x: (pd.to_datetime(CURRENT_TRADE_DATE) - BDay(x)).strftime('%Y-%m-%d'), strip_chart_dates))
        # check if all these are in price chart dates
        strip_chart_dates = check_replace_missing(strip_chart_dates)
        print(f'strip_chart_dates: {strip_chart_dates}')
        # days of strip for chart 1
        strip_chart_data = price_data[price_data['trade_date'].isin(strip_chart_dates)]
        print(strip_chart_data)

        axes[0][0].set_title(f'Last {len(strip_chart_dates)} Trading Days Strip')
        palette = 'magma_r'
        ax = sns.lineplot(ax=axes[0, 0],
                          data=strip_chart_data, hue='Legend',
                          palette=palette,
                          x='contract_date', y='settle_price',
                          marker='o'
                          )
        if c_code in ['NG']:
            ax.legend(loc='upper right', title=c_name)
            _xytext = (0, 10)
        else:
            ax.legend(loc='upper right', title=c_name)
            _xytext = (0, 10)

        # annotate latest strip
        latest_prices = price_data[price_data['trade_date'] == strip_chart_dates[-1]]
        # add this to the strip pricing file
        _spf = latest_prices.assign(
            commodity=lambda x: f'{c_name} | {c_code}'
        )
        _spf.drop(columns=['Legend'], inplace=True)
        STRIP_PRICING_FILE[c_code] = _spf

        for idx, (x, y) in enumerate(zip(latest_prices['contract_date'].values,
                                         latest_prices['settle_price'].values)):
            # adjust position to alternate above or below
            _txt = _xytext if idx % 2 == 0 else (_xytext[0], _xytext[1])
            ax.annotate(text=f'{y:.2f}',  # annotation text
                        xy=(x, y),  # datapoint being labeled
                        xycoords='data',  # coordinate system for xy
                        xytext=_txt,  # where should the text be
                        textcoords='offset points',  # coordinate system for xytext
                        ha='center',  # horizontal alignment of the text
                        size=9,  # fontsize
                        color=sns.color_palette(palette, n_colors=7)[-1],  # use the last color of the palette
                        bbox=dict(boxstyle='square',
                                  alpha=0.95,
                                  pad=0.01,
                                  facecolor='white',
                                  edgecolor='white'
                                  ),  # what should the box look like
                        arrowprops=dict(
                            arrowstyle='-',
                            ls='dashed',
                            color=sns.color_palette(palette, n_colors=7)[-1])  # what should the line look like
                        )

        x_labels = pd.to_datetime(strip_chart_data.contract_date).dt.strftime("%b-%y").unique()
        ax.set_xticklabels(labels=x_labels, rotation=90, ha='center', va='top')
        ax.yaxis.set_major_formatter(tkr.FuncFormatter(lambda y, p: f'{y:.2f}'))
        ax.grid()

        # ---------- HEATMAP CHART ------------#
        # heatmap dates
        axes[0][1].set_title('Futures Movement Heatmap')
        print(f'| Building heatmap data for {c_code} >> ')
        heatmap_chart_dates = list(
            map(
                lambda x: (pd.to_datetime(CURRENT_TRADE_DATE) - BDay(x)).strftime('%Y-%m-%d'),
                filter(lambda x: x > 0, hist_days[::-1])
            )
        )
        # check if all these are in price chart dates
        heatmap_chart_dates = check_replace_missing(heatmap_chart_dates)
        print(f'heatmap_chart_dates: {heatmap_chart_dates}')

        # calculate the deltas to prior settlements
        current_strip_prices = latest_prices['settle_price'].values
        heatmap_data = pd.DataFrame(price_data[price_data['trade_date'].isin(heatmap_chart_dates)])
        heatmap_data['future_month'] = 0
        heatmap_data['current_strip_vs'] = ''

        # calculate deltas
        for idx, tr_d in enumerate(heatmap_chart_dates):
            hd = heatmap_data.loc[heatmap_data['trade_date'] == tr_d, 'settle_price']
            heatmap_data.at[heatmap_data['trade_date'] == tr_d, 'settle_price'] = current_strip_prices - hd.values[:len(
                current_strip_prices)]
            heatmap_data.at[heatmap_data['trade_date'] == tr_d, 'future_month'] = [
                f'Month {_ + 1}' for _ in range(len(current_strip_prices))]
            bus_days_between = np.busday_count(pd.to_datetime(tr_d).date(), pd.to_datetime(CURRENT_TRADE_DATE).date())
            heatmap_data.at[heatmap_data['trade_date'] == tr_d, 'current_strip_vs'] = f'T-{bus_days_between}'
        heatmap_data = heatmap_data[['current_strip_vs', 'settle_price', 'future_month']]
        heatmap_data = heatmap_data.pivot(index='current_strip_vs', columns='future_month', values='settle_price')
        heatmap_data.sort_index(axis=0,
                                key=lambda x: x.str.slice(start=len('T-')).astype('int64'),
                                inplace=True)
        heatmap_data.sort_index(axis=1,
                                key=lambda x: x.str.slice(start=len('Month ')).astype('int64'),
                                inplace=True)
        print(heatmap_data)
        MASTER_HEATMAP_DATA[c_code] = heatmap_data

        ax = sns.heatmap(heatmap_data,
                         annot=True,
                         fmt='.2f',
                         linewidths=0.5,
                         center=0.0,
                         ax=axes[0, 1],
                         cbar=False,
                         cmap=sns.color_palette('inferno', as_cmap=True),
                         cbar_kws=dict(orientation='horizontal'),
                         annot_kws=dict(size=9,
                                        rotation=50),
                         )
        ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
        for _, spine in ax.spines.items():
            spine.set_visible(True)

        # ---------- FRONT MONTH SETTLEMENT HISTORY ----------#
        axes[1][0].set_title(
            f'Front Month Settlement History: {min(price_data["trade_date"])} to {max(price_data["trade_date"])}'
        )

        data = []
        # get every CHART_MONTHS-th row
        rows_in_price_data = len(price_data.index)
        data_indexes = [_ * CHART_MONTHS for _ in range(int(rows_in_price_data / CHART_MONTHS))]
        price_chart_data = price_data.loc[data_indexes, ['trade_date', 'settle_price']]
        # drop excluded prices
        if c_code not in ['WTT', 'FF', 'NW', 'NHN']:
            price_chart_data = price_chart_data[price_chart_data['settle_price'] > 0.0]
            price_chart_data = price_chart_data[price_chart_data['settle_price'] < 500.0]
        price_chart_data.reset_index(drop=True, inplace=True)

        palette = 'YlGnBu'
        ax = sns.lineplot(ax=axes[1, 0],
                          data=price_chart_data,
                          palette=palette,
                          x='trade_date',
                          y='settle_price'
                          )

        price_chart_data['x_labels'] = pd.to_datetime(price_chart_data.trade_date).dt.strftime("%b-%y")
        print(price_chart_data.head())
        # sparsify
        ax.set_xticks(range(len(price_chart_data.x_labels)))
        ax.set_xticklabels(labels=price_chart_data.x_labels, rotation=90, ha='center', va='top')
        _sparsify_by = len(price_chart_data) // 20
        ax.xaxis.set_major_locator(tkr.MultipleLocator(_sparsify_by))
        ax.yaxis.set_major_formatter(tkr.FuncFormatter(lambda y, p: f'{y:.2f}'))
        ax.grid()

        # ---------- HISTOGRAM OF FRONT MONTH SETTLEMENTS (+ STATS) ----------#
        axes[1][1].set_title(
            f'Distribution of Front Month Settlements: {min(price_chart_data["trade_date"])} to {max(price_chart_data["trade_date"])}'
        )
        histogram_data = pd.DataFrame(price_chart_data)
        stats = histogram_data.describe()
        stats.columns = ['summary_stats']
        stats.update(pd.DataFrame(stats.loc['mean':]).applymap('{:,.2f}'.format))
        stats.update(pd.DataFrame(stats.loc['count']).applymap('{:,f}'.format))
        print(stats)
        ax = sns.histplot(histogram_data,
                          ax=axes[1, 1],
                          x='settle_price',
                          cumulative=False,
                          color=sns.color_palette('inferno')[0],
                          bins=120,
                          stat='probability',
                          kde=True,
                          )

        if c_code in ['NG', 'B0', 'C0', 'D0', 'I8', '7Q']:
            _bbox = [.85, .48, .12, .5]
        else:
            _bbox = [.05, .48, .12, .5]

        ax.table(cellText=stats.values,
                 rowLabels=stats.index,
                 colLabels=stats.columns,
                 fontsize=22,
                 colWidths=[0.15, 0.25],
                 cellLoc='right', rowLoc='center',
                 cellColours=[['w'], ['w'], ['w'], ['w'], ['w'], ['w'], ['w'], ['w']],
                 loc='right', bbox=_bbox)

        ax.xaxis.set_major_formatter(tkr.FuncFormatter(lambda y, p: f'{y:.2f}'))

        plt.tight_layout()
        _fp = os.path.join(
            PRICE_DATA_FOLDER,
            f'_price_updates/{CURRENT_TRADE_DATE}_{c_name}_{c_code}.png')
        plt.savefig(_fp)
        plt.show()
        plt.close(fig)


# ------------ MASTER HEATMAP AND STRIP PRICING DATA ------------- #
def build_master_heatmap():
    fig, axes = plt.subplots(6, 2, sharey=False, sharex=False, figsize=(20, 30))
    # fig.suptitle(f'Futures Movement Heatmap (as of {CURRENT_TRADE_DATE})')
    global MASTER_HEATMAP_DATA
    global CURRENT_TRADE_DATE
    print(MASTER_HEATMAP_DATA)
    for xax in range(len(axes)):
        for yax in range(len(axes[0])):
            try:
                c_code = list(COMDTY_REF.keys())[xax * 2 + yax]
                c_name = COMDTY_REF[c_code][0]
                print(f'>> Adding {c_code} to master heatmap')
                axes[xax][yax].set_title(f'{c_name} | {c_code}')
                data = MASTER_HEATMAP_DATA[c_code]
                ax = sns.heatmap(data,
                                 annot=True,
                                 fmt='.2f',
                                 linewidths=0.5,
                                 center=0.0,
                                 ax=axes[xax, yax],
                                 cbar=False,
                                 cmap=sns.color_palette('inferno', as_cmap=True),
                                 cbar_kws=dict(orientation='horizontal'),
                                 annot_kws=dict(size=9,
                                                rotation=50),
                                 )
                ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
                ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

            except (KeyError, IndexError):
                print(f'!! data for axes[{xax},{yax}] not found.')
                axes[xax, yax].axis('off')

    plt.tight_layout()
    _fp = os.path.join(PRICE_DATA_FOLDER,
                       f'_price_updates\\{CURRENT_TRADE_DATE}_master_heatmap.png')
    plt.savefig(_fp)
    plt.show()
    plt.close(fig)

def save_strip_pricing_data():
    # make a big dataframe
    global STRIP_PRICING_FILE
    dfs = list(STRIP_PRICING_FILE.values())
    STRIP_PRICING_FILE = pd.concat(dfs, ignore_index=True)
    STRIP_PRICING_FILE.reset_index(inplace=True, drop=True)
    # save to excel

    STRIP_PRICING_FILE.to_excel(
        os.path.join(
            PRICE_DATA_FOLDER,
            f'_price_updates/{CURRENT_TRADE_DATE}_strip_prices.xlsx')
    )

    print(STRIP_PRICING_FILE, STRIP_PRICING_FILE.info())


# --------------------------------------------------------------------------------------------------- #
# --------------------------------------------- EXECUTION ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #

# use this to update historical data jsons from the raw data

# manual_update_function()

settlement_data = get_nymex_settlement_data()
normalize_daily_data(settlement_data)
build_price_update_charts()
build_master_heatmap()
save_strip_pricing_data()


