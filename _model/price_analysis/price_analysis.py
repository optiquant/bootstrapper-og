import _model.prices as pr
from _model.useful_functions import *
import os
import pandas as pd
import numpy as np
import json
import glob
from datetime import datetime
import csv
from pprint import pprint

import matplotlib.pyplot as plt
import matplotlib

# PLOTLY
from kaleido.scopes.plotly import PlotlyScope
import plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px


def extract_futures_by_index(future_months: int):
    '''Extracts the first future_months number of futures prices for the set of commodity indexes in c_nicks. Saves results to a csv file in the save_to_folder.
    Args:
        |-- future_months, int: number of futures months to extract from stored price data.
        '''
    for future_month_index in range(future_months):
        data = []
        for c_nick in c_nicks:
            # Place your JSON data in a directory named 'data/'
            src = price_data_folders[c_nick]

            # Change the glob if you want to only look through files with specific names
            # all files
            files = glob.glob(f'{src}/_prices_*', recursive=True)

            historical_date_range = [string_date(_) for _ in pd.date_range(start=mcs_start_end_dates[c_nick].sim_start,
                                                                           end=mcs_start_end_dates[c_nick].sim_end,
                                                                           freq='d',
                                                                           tz='UTC')]

            # strip files that do not contain a historical date
            print(f'\n| All files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')
            files = [f for f in files for date in historical_date_range if date in f]
            print(f'\n| Filtered files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')

            # Loop through files
            for single_file in files:
                with open(single_file, 'r') as f:
                    json_file = json.load(f)
                    try:
                        if json_file['settle_price'][str(future_month_index)] != 0.0:
                            data.append([
                                json_file['comdty_code'][str(future_month_index)],
                                json_file['comdty_desc'][str(future_month_index)],
                                json_file['trade_date'][str(future_month_index)],
                                json_file['contract_date'][str(future_month_index)],
                                json_file['future_mth_idx'][str(future_month_index)],
                                json_file['settle_price'][str(future_month_index)],
                            ])
                    except KeyError:
                        error_log.append(f'{c_nick}_fm{future_month_index}_{f}')

            # Sort the data
            # data.sort()

        # Add headers
        data.insert(0,
                    ['comdty_code', 'comdty_desc', 'trade_date', 'contract_date', 'future_month_index', 'settle_price'])

        # Export to CSV by future month (each csv should have all commodities)
        # Add the date to the file name to avoid overwriting it each time.
        with open(f'{save_to_folder}\\future_month_{future_month_index}_prices.csv', "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Updated CSV for {future_month_index}")

    print(error_log)


def default_stats():
    return ['count', 'mean', 'std', 'min', '5%', '10%', '25%', '50%', '75%', '90%', '95%', 'max', '-3sig', '-2sig',
            '-1sig', '+1sig', '+2sig', '+3sig']


def build_summary_stats(c_nick: str, data: list, future_month_index: int, save_to_xls=False):
    data = pd.Series(data)
    summary_stats = {**data.describe([0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])}
    print(summary_stats)

    mean = summary_stats['mean']
    summary_stats['-1sig'], summary_stats['+1sig'] = [mean - summary_stats['std'], mean + summary_stats['std']]
    summary_stats['-2sig'], summary_stats['+2sig'] = [mean - 2 * summary_stats['std'],
                                                      mean + 2 * summary_stats['std']]
    summary_stats['-3sig'], summary_stats['+3sig'] = [mean - 3 * summary_stats['std'],
                                                      mean + 3 * summary_stats['std']]

    summary_stats = pd.Series(summary_stats, name=str(future_month_index)).reindex(default_stats())
    if c_nick in ngl_nicks:
        if convert_gal_to_mmbtu:
            conv_ratio = gal_mmbtu_conv_ratio
            print(f'\n| Using gal-mmbtu conversion ratio >> {str(conv_ratio)}')
        else:
            conv_ratio = 1.0

        # adjust prices to $/MMBtu if NGL
        summary_stats.loc['mean':'+3sig'] *= conv_ratio
        print(f'| Converted summary_stats:\n{summary_stats}')

    print(summary_stats)

    if save_to_xls:
        save_to_excel(output_dataframe=summary_stats,
                      folder=save_to_folder,
                      filename=f'{c_nick}_prices_fm{future_month_index}_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.xlsx')

    return summary_stats


def build_relative_time_indexes(future_months: int, summary_stats: dict):
    for c_nick in c_nicks:
        # c_nick = 'ethane'
        c_code = get_comdty_code(c_nick)

        chart_data[c_nick] = {}

        summary_stats[c_nick] = pd.DataFrame(columns=[str(_) for _ in range(future_months)], index=default_stats())

        for future_month_index in range(future_months):
            #     future_month_index = 1
            csv_file = pd.read_csv(f'{save_to_folder}\\future_month_{future_month_index}_prices.csv')
            csv_file = csv_file[csv_file['comdty_code'] == c_code]
            # print(f'Future Month >> {future_month_index}\n{csv_file.head()}\n{csv_file.info()}')

            data = csv_file['settle_price'].to_list()
            _stats = build_summary_stats(c_nick,
                                         data=data,
                                         future_month_index=future_month_index,
                                         save_to_xls=False
                                         )

            chart_data[c_nick][future_month_index] = data

            summary_stats[c_nick].update(_stats)

        print(summary_stats[c_nick])
        filename = f'{c_nick}_index_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.csv'
        summary_stats[c_nick].to_csv(f'{save_to_folder}\\{filename}')


def extract_futures_by_month(num_contract_months: int):
    '''Extracts the set of futures prices for each month in the year (Jan - Dec), over the stored price history, for the set of commodity indexes in c_nicks.
     Saves results to a csv file in the save_to_folder.
    Args:
        |--
        '''

    contract_months = range(1, num_contract_months + 1)
    print(contract_months)
    error_log = {}

    # loop through 12 contract months
    for contract_month in contract_months:
        data = []
        for c_nick in c_nicks:
            error_log[c_nick] = []
            historical_date_range = [string_date(_) for _ in pd.date_range(start=mcs_start_end_dates[c_nick].sim_start,
                                                                           end=mcs_start_end_dates[c_nick].sim_end,
                                                                           freq='d',
                                                                           tz='UTC')]
            # Place your JSON data in a directory named 'data/'
            src = price_data_folders[c_nick]

            # Change the glob if you want to only look through files with specific names
            # all files
            files = glob.glob(f'{src}/_prices_*', recursive=True)
            # strip files that do not contain a historical date
            print(f'\n| All files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')
            files = [f for f in files for date in historical_date_range if date in f]
            print(f'\n| Filtered files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')

            # Loop through files for historical period
            for single_file in files:
                print(single_file)
                with open(single_file, 'r') as f:
                    json_file = json.load(f)
                    try:
                        # filter out the correct contract month indexes
                        indexes = [index for datapoint, values_dict in json_file.items() for index, value in
                                   values_dict.items()
                                   if datapoint == 'contract_mth' and value == contract_month]
                        print(f'| Indexes for contract month {contract_month} >> {indexes}')

                        filtered_json = {k: {index: value for index, value in v.items() if index in indexes} for k, v in
                                         json_file.items()}
                        for index in indexes:
                            if filtered_json['settle_price'][str(index)] != 0.0:
                                # add to data
                                data.append([
                                    json_file['comdty_code'][str(index)],
                                    json_file['comdty_desc'][str(index)],
                                    json_file['trade_date'][str(index)],
                                    json_file['contract_date'][str(index)],
                                    json_file['future_mth_idx'][str(index)],
                                    json_file['settle_price'][str(index)],
                                ])
                    except KeyError:
                        error_log[c_nick].append(f'{c_nick}_cm{contract_month}_{f}')

        # Add headers one each dataset is complete (i.e. for 12 months for this commodity, for all historical dates)
        data.insert(0,
                    ['comdty_code', 'comdty_desc', 'trade_date', 'contract_date', 'future_month_index', 'settle_price'])
        print(f'\n| # of datapoints for {c_nick} --> {len(data)}')

        # Export to CSV by future month (each csv should have all commodities)
        # Add the date to the file name to avoid overwriting it each time.
        with open(f'{save_to_folder}\\contract_month_{contract_month}_prices.csv', "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Updated CSV for contract month: {contract_month}")

        pprint(f'!! Errors: {error_log}')


def build_absolute_time_indexes(num_contract_months: int, summary_stats: dict):
    for c_nick in c_nicks:
        # c_nick = 'ethane'
        c_code = get_comdty_code(c_nick)

        chart_data[c_nick] = {}

        contract_months = np.arange(1, num_contract_months + 1)
        summary_stats[c_nick] = pd.DataFrame(columns=[str(_) for _ in contract_months], index=default_stats())

        for contract_month in contract_months:
            csv_file = pd.read_csv(f'{save_to_folder}\\contract_month_{contract_month}_prices.csv')
            csv_file = csv_file[csv_file['comdty_code'] == c_code]
            # print(f'Future Month >> {future_month_index}\n{csv_file.head()}\n{csv_file.info()}')

            data = csv_file['settle_price'].to_list()
            _stats = build_summary_stats(c_nick,
                                         data=data,
                                         future_month_index=contract_month,
                                         save_to_xls=False
                                         )

            chart_data[c_nick][contract_month] = data

            summary_stats[c_nick].update(_stats)

        print(summary_stats[c_nick])
        filename = f'{c_nick}_abs_time_index_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.csv'
        summary_stats[c_nick].to_csv(f'{save_to_folder}\\{filename}')


# --- relative time index --- #
# future_months = 24
# error_log = []
# summary_stats = {}
# chart_data = {}
#
# extract_futures_by_index(future_months=future_months)
# build_relative_time_indexes(future_months=future_months, summary_stats=summary_stats)


# --- absolute time index --- #
# # 12 contract months --> Jan - Dec
# num_contract_months = 12
# error_log = []
# summary_stats = {}
# chart_data = {}
#
# extract_futures_by_month(num_contract_months=num_contract_months)
# build_absolute_time_indexes(num_contract_months=num_contract_months, summary_stats=summary_stats)


# --- wet gas price index --- #


'''Calculates the Wet Gas Price Index (WGX).'''

trade_date = '5/14/21'
trade_date = pd.to_datetime(trade_date, utc=True)
c_nicks = ['hh', 'waha_gas_diff', 'ethane', 'propane', 'iso_butane', 'n_butane', 'nat_gasoline']
mcs_data_folders = {c_nick: pr.root_folder_mcs_data(c_nick)['root_folder'] for c_nick in c_nicks}
price_data_folders = {c_nick: pr.root_folder_price_data(c_nick)['root_folder'] for c_nick in c_nicks}

print(price_data_folders)

# save_to_folder = r'T:/Finance-Strategy/Price Analysis/'
# save_to_folder = r'T:/Finance-Strategy/Price Analysis/absolute time index/'
save_to_folder = r'T:/Finance-Strategy/Price Analysis/seasonal index/'
convert_gal_to_mmbtu = False
gal_mmbtu_conv_ratio = pr.get_conversion_ratios()['gal/mmbtu - energy']
ngl_nicks = get_ngl_nicks()
mcs_start_end_dates = pr.get_mcs_start_end_dates(sim_end=trade_date)

mmbtu_per_mcf_wet_gas = 1.25
mmbtu_per_mcf_dry_gas = 0.96
t_and_f_per_ngl_gal = 0.08

error_log = []
excluded_prices = {
    'hh': [0.00],
    'waha_gas_diff': [0.00],
    'hsc_gas_diff': [0.00],
    'ethane': [0.00],
    'propane': [0.00],
    'iso_butane': [0.00],
    'n_butane': [0.00],
    'nat_gasoline': [0.00]
}



# number of gallons per mcf
gal_per_mcf = {
    k: sum(v) for k, v in {'ethane': [3.14],
                           'propane': [2.00],
                           'n_butane': [0.63],
                           'iso_butane': [0.18],
                           'nat_gasoline': [0.16, 0.15, 0.26]
                           }.items()
}

print(gal_per_mcf)

wg_price_start = '1/1/2010'

# for each trade date, calculate the wet gas price
price_components = {
    'hh': None,
    'waha_gas_diff': None,
    'ethane': None,
    'propane': None,
    'n_butane': None,
    'iso_butane': None,
    'nat_gasoline': None,
}

wet_gas_price = {
    'comdty_code': {},
    'comdty_desc': {},
    'trade_date': {},
    'contract_date': {},
    'contract_year': {},
    'contract_mth': {},
    'settle_price': {},
    'open_interest': {},
    'volume': {},
    'last_trade_date': {},
}

wet_gas_comdty_code = 'WGX'
wet_gas_comdty_desc = 'Wet Gas Index (WGX)'

# month pairs used to calculate price changes
month_pairs = [(1, 2),
               (2, 3),
               (3, 4),
               (4, 5),
               (5, 6),
               (6, 7),
               (7, 8),
               (8, 9),
               (9, 10),
               (10, 11),
               (11, 12),
               (12, 1)]

# dict to store calculated historical settlement price deltas for each month-pair
historical_month_deltas = {}

for c_nick_index, c_nick in enumerate(price_components):
    #c_nick = c_nicks[3]

    historical_date_range = [string_date(_) for _ in pd.date_range(start=wg_price_start,
                                                                   end=mcs_start_end_dates[c_nick].sim_end,
                                                                   freq='d',
                                                                   tz='UTC')]

    # get all price files for this commodity, from the source folder for JSON price data
    files = glob.glob(f'{price_data_folders[c_nick]}/_prices_*', recursive=True)
    print(f'\n| All files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')

    # exclude files that do not contain a historical date
    files = [f for f in files for date in historical_date_range if date in f]
    print(f'\n| Filtered files >> count: {len(files)}\n|-- first file: {files[0]}\n|-- last file: {files[-1]}')

    historical_month_deltas[c_nick] = {k: [] for k in month_pairs}

    for f_num, file in enumerate(files):
        # print(f'| Loading {f_num}: {file}')
        with open(files[f_num], 'r') as f:
            json_file = json.load(f)

        # print(json_file['contract_mth'], json_file['settle_price'])

        # valid month pairs in data (so that irregular contract month data is excldued)
        data_month_pairs = [_ for _ in json_file['contract_mth'].values()]
        data_month_pairs = [(x, y) for x, y in zip(data_month_pairs[:-1], data_month_pairs[1:]) if (x, y) in month_pairs]
        data_month_pairs = dict(zip([_ for _ in json_file['contract_mth'].keys()], data_month_pairs))
        # print(data_month_pairs)

        # calculate price deltas
        price_deltas = {
            k: json_file['settle_price'][str(int(k)+1)]-json_file['settle_price'][k] for k, v in data_month_pairs.items()
        }

        # drop price deltas of zero, and merge price deltas with month pairs
        price_deltas = {k: (data_month_pairs[k], price_delta) for k, price_delta in price_deltas.items() if price_delta != 0}
        # print(price_deltas)

        # populate the historical month delta data for this commodity
        for k, (month_pair, price_delta) in price_deltas.items():
            historical_month_deltas[c_nick][month_pair].append(price_delta)

    print(historical_month_deltas[c_nick])

    chart_data = [(k, historical_month_deltas[c_nick][k]) for k in month_pairs]
    print(chart_data)

    chart_xlims = {
        'hh': [-0.5, 0.5],
        'waha_gas_diff': [-0.3, 0.3],
        'hsc_gas_diff': [-0.5, 0.5],
        'ethane': [-0.03, 0.03],
        'propane': [-0.1, 0.1],
        'n_butane': [-0.1, 0.1],
        'iso_butane': [-0.1, 0.1],
        'nat_gasoline': [-0.1, 0.1],
    }
    chart_xformats = {
        'hh': '.2f',
        'waha_gas_diff': '.2f',
        'hsc_gas_diff': '.2f',
        'ethane': '.3f',
        'propane': '.3f',
        'n_butane': '.3f',
        'iso_butane': '.3f',
        'nat_gasoline': '.3f',
    }



    fig, axs = plt.subplots(12, figsize=(8, 12), sharex=True, sharey=False)
    for i, (month_pair, price_delta) in enumerate(chart_data):
        # chart_coords = (i, c_nick_index)
        chart_coords = i
        print(chart_coords, month_pair)
        axs[chart_coords].hist(price_delta, bins=200)
        axs[chart_coords].set_title(f'Month delta: {month_pair}')
        axs[chart_coords].grid(b=True, which='major', axis='x', color='lightgray')
        axs[chart_coords].set_xticks(np.arange(chart_xlims[c_nick][0],
                                               chart_xlims[c_nick][1],
                                               chart_xlims[c_nick][1]/10))
        axs[chart_coords].set_xticklabels(axs[chart_coords].get_xticks(), rotation=45)
        axs[chart_coords].get_xaxis().set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, p: format(float(x), chart_xformats[c_nick])))
        axs[chart_coords].get_yaxis().set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))

    plt.xlim(chart_xlims[c_nick])
    fig.tight_layout()
    fig.suptitle(f'{get_comdty_name(c_nick)} | {get_comdty_code(c_nick)}')
    fig.subplots_adjust(top=0.93)
    plt.show()


'''Formula: 
wet gas price = (hh + waha) * mmbtu-mcf conv - wet gas + ((c2-t) + (c3-t) + (nc4-t) + (ic4-t) + (c5-t)) * gal-mcf conv'''

