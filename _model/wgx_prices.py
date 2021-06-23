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
from pandas.tseries.offsets import MonthEnd, Day

import matplotlib.pyplot as plt
import matplotlib

# PLOTLY
from kaleido.scopes.plotly import PlotlyScope
import plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px



'''Calculates the Wet Gas Price Index (WGX).'''

trade_date = input('| Enter as of date for gas index update (m/d/yy) >> ')
trade_date = pd.to_datetime(trade_date, utc=True)

_whichindex = input('| Which index to calculate? Dry gas (D) / Wet Gas (W) / Vent Gas (V) >> ').lower()
if _whichindex == 'd':
    print('|-- Dry gas selected.')
    c_nicks = ['hh', 'waha_gas_diff']
else:
    print('|-- Wet or vent gas selected.')
    c_nicks = ['hh', 'waha_gas_diff', 'ethane', 'propane', 'iso_butane', 'n_butane', 'nat_gasoline']

mcs_data_folders = {c_nick: pr.root_folder_mcs_data(c_nick)['root_folder'] for c_nick in c_nicks}
price_data_folders = {c_nick: pr.root_folder_price_data(c_nick)['root_folder'] for c_nick in c_nicks}
print(price_data_folders)

# save_to_folder = r'T:/Finance-Strategy/Price Analysis/'
# save_to_folder = r'T:/Finance-Strategy/Price Analysis/absolute time index/'
save_to_folder = r'T:/Finance-Strategy/WGX/seasonal index/'
root_folder = r'T:/Finance-Strategy/WGX/'

default_percentiles = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
convert_gal_to_mmbtu = False
gal_mmbtu_conv_ratio = pr.get_conversion_ratios()['gal/mmbtu - energy']
ngl_nicks = get_ngl_nicks()
mcs_start_end_dates = pr.get_mcs_start_end_dates(sim_end=trade_date)


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

# read in inputs
gx_gas_sample_input_df = pd.read_excel(root_folder+"__GAS SAMPLE INPUT/gx_gas_sample_input.xlsx", sheet_name='input', index_col=[1])
gx_gas_sample_input = dict(gx_gas_sample_input_df)
print(gx_gas_sample_input)


input_map = {
    "Wet Gas BTU/CF": 'mmbtu_per_mcf_wet_gas',
    "Tailgate BTU/CF": 'mmbtu_per_mcf_dry_gas',
    "Ethane": None,
    "Propane": None,
    "Isobutane": None,
    "Nor Butane": None,
    "Nat Gasoline": None,
    "Nat Gasoline": None,
    "Hexanes": None
}

mmbtu_per_mcf_wet_gas = gx_gas_sample_input['value'].at['wet_gas_btu_cf']
mmbtu_per_mcf_dry_gas = gx_gas_sample_input['value'].at['dry_gas_btu_cf']
t_and_f_per_ngl_gal = gx_gas_sample_input['value'].at['ngl_tf_per_gal']

# number of gallons per mcf
gal_per_mcf = {
    k: sum(v) for k, v in {'ethane': [gx_gas_sample_input['value'].at['c2']],
                           'propane': [gx_gas_sample_input['value'].at['c3']],
                           'n_butane': [gx_gas_sample_input['value'].at['nc4']],
                           'iso_butane': [gx_gas_sample_input['value'].at['ic4']],
                           'nat_gasoline': [gx_gas_sample_input['value'].at['ic5'],
                                            gx_gas_sample_input['value'].at['nc5'],
                                            gx_gas_sample_input['value'].at['c6']
                                            ]
                           }.items()
}
print(f'\n| gal_per_mcf >> {gal_per_mcf}')

_1 = input('| Hit enter to continue if gas sample is ok >> ')
gx_start_date = '1/1/2010'

if _whichindex == 'd':
    gx_c_nick = 'dgx'
    gx_c_code = 'DGX'
    gx_c_name = 'Dry Gas Index (DGX)'
    gx_c_unit = '$/Mcf'

elif _whichindex == 'w':
    gx_c_nick = 'wgx'
    gx_c_code = 'WGX'
    gx_c_name = 'Wet Gas Index (WGX)'
    gx_c_unit = '$/Mcf'

elif _whichindex == 'v':
    gx_c_nick = 'vgx'
    gx_c_code = 'VGX'
    gx_c_name = 'Vent Gas Index (VGX)'
    gx_c_unit = '$/Mcf'



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


#----------------------------------------------------------------------------------------------------------------------#
#------------------------------------------------- FUNCTIONS ----------------------------------------------------------#
#----------------------------------------------------------------------------------------------------------------------#

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


def historical_strip_shape(commodity_list: list):
    for c_nick_index, c_nick in enumerate(commodity_list):
        # c_nick = c_nicks[3]

        historical_date_range = [string_date(_) for _ in pd.date_range(start=gx_start_date,
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

            # valid month pairs in data (so that irregular contract month data is excldued)
            data_month_pairs = [_ for _ in json_file['contract_mth'].values()]
            data_month_pairs = [(x, y) for x, y in zip(data_month_pairs[:-1], data_month_pairs[1:]) if
                                (x, y) in month_pairs]
            data_month_pairs = dict(zip([_ for _ in json_file['contract_mth'].keys()], data_month_pairs))

            # calculate price deltas
            price_deltas = {
                k: json_file['settle_price'][str(int(k) + 1)] - json_file['settle_price'][k] for k, v in
                data_month_pairs.items()
            }

            # drop price deltas of zero, and merge price deltas with month pairs
            price_deltas = {k: (data_month_pairs[k], price_delta) for k, price_delta in price_deltas.items() if
                            price_delta != 0}

            # populate the historical month delta data for this commodity
            for k, (month_pair, price_delta) in price_deltas.items():
                historical_month_deltas[c_nick][month_pair].append(price_delta)

        print(historical_month_deltas[c_nick])
        # save to folder
        for month_pair in historical_month_deltas[c_nick]:
            data = historical_month_deltas[c_nick][month_pair]
            # suffix = str(month_pair).replace('(', '').replace(')', '').replace(', ', '-')
            suffix = str(month_pair)
            save_to_json(df=pd.DataFrame(data, index=range(len(data)), columns=[c_nick]),
                         folder=f'{save_to_folder}/raw_data/',
                         filepath=f'{save_to_folder}/raw_data/{string_date(trade_date)}_month_deltas_{c_nick}_{suffix}.json'
                         )

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
                                                   chart_xlims[c_nick][1] / 10))
            axs[chart_coords].set_xticklabels(axs[chart_coords].get_xticks(), rotation=45)
            axs[chart_coords].get_xaxis().set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, p: format(float(x), chart_xformats[c_nick])))
            axs[chart_coords].get_yaxis().set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))

        plt.xlim(chart_xlims[c_nick])
        fig.tight_layout()
        fig.suptitle(f'{get_comdty_name(c_nick)} | {get_comdty_code(c_nick)}')
        fig.subplots_adjust(top=0.93)
        try:
            plt.savefig(save_to_folder+f'month_deltas/{string_date(trade_date)}_{c_nick}')
            print(f'| Saved >> month_deltas/{string_date(trade_date)}_{c_nick}')
        except (KeyError, FileNotFoundError, PermissionError, ValueError, NameError):
            print(f'!! File not saved! >> month_deltas/{string_date(trade_date)}_{c_nick}')
        # plt.show()


def summary_stats_by_month_pair():
    # statistics for month deltas
    # read in the data from the raw_data folder
    read_in_root = {
        c_nick: f'{save_to_folder}/raw_data/{string_date(trade_date)}_month_deltas_{c_nick}' for c_nick in c_nicks
    }

    print(read_in_root)
    summary_stats = {}

    for _mp in month_pairs:
        month_pair = str(_mp)
        summary_stats[month_pair] = {}
        for c_nick, filepath in read_in_root.items():
            filepath = f'{filepath}_{month_pair}.json'
            with open(filepath) as f:
                json_file = json.load(f)
                data = [_ for _ in json_file[c_nick].values()]

            summary_stats[month_pair][c_nick] = pd.DataFrame(data, columns=[c_nick]).describe(default_percentiles)
            save_to_json(df=summary_stats[month_pair][c_nick],
                         folder=f'{save_to_folder}/summary_stats/',
                         filepath=f'{save_to_folder}/summary_stats/{string_date(trade_date)}_stats_{c_nick}_{month_pair}.json'
                         )
        print(f'\n| Summary stats for {month_pair}:\n{summary_stats[month_pair]}')

    return summary_stats


def calc_wgx(summary_stats: dict):
    # calculate the next month from the last front month settle
    # read in the data from the summary_stats folder
    # read_in_root = {
    #     c_nick: f'{save_to_folder}/summary_stats/{string_date(trade_date)}_stats_{c_nick}' for c_nick in c_nicks
    # }
    # print(read_in_root)

    # model_prices = pd.read_excel('T:/Finance-Strategy/daily_price_updates/TCR - Model Prices.xlsx',
    #                              parse_dates=True, index_col=[1])

    model_prices = pr.get_model_prices(strip_pricing_date=string_date(trade_date), start_date=string_date('7/31/20'))
    print(model_prices)

    # get the WGX price components for the front month
    current_month = trade_date + MonthEnd(1)
    price_scenarios = [f'Strip {string_date(trade_date)}', *[str(int(_ * 100)) + "%" for _ in default_percentiles]]
    print(price_scenarios)

    global strip_start
    strip_start = string_date(current_month + MonthEnd(1))
    global strip_end
    strip_end = string_date(current_month + MonthEnd(24))
    strip_dates = pd.date_range(start=strip_start, end=strip_end, freq='M', normalize=True, tz='UTC')
    print(f'\n| Strip dates:\n  {strip_dates}\n')

    wgx = {}

    if _whichindex == 'w' or _whichindex == 'v':
        btu_adj = mmbtu_per_mcf_wet_gas
    else:
        btu_adj = mmbtu_per_mcf_dry_gas

    for pr_scen in price_scenarios:
        wgx[pr_scen] = {}
        for strip_month in strip_dates:
            if 'strip' in pr_scen.lower():
                # component prices
                gx_components = dict(
                    model_prices.loc[strip_month, [get_comdty_name(c_nick) for c_nick in c_nicks]])
                # replace comdty names with c_nicks
                gx_components = {get_comdty_nick(c_name, search_term_type='comdty_name'): v for c_name, v in
                                  gx_components.items()}
                print(f'| {string_date(strip_month)} >> {gx_components}')

                # calculate WGX
                # WGX = (hh + waha) * mmbtu-mcf-wet-gas conv + ((c2-t) + (c3-t) + (nc4-t) + (ic4-t) + (c5-t)) * gal-mcf conv'''
                # the strip start / front month settle should be given.
                wgx[pr_scen][string_date(strip_month)] = (gx_components['hh'] + gx_components[
                    'waha_gas_diff']) / btu_adj

                if _whichindex != 'd':
                    wgx[pr_scen][string_date(strip_month)] += (gx_components['ethane'] - t_and_f_per_ngl_gal) * gal_per_mcf[
                                                                 'ethane'] + \
                                                             (gx_components['propane'] - t_and_f_per_ngl_gal) * \
                                                             gal_per_mcf[
                                                                 'propane'] + \
                                                             (gx_components['n_butane'] - t_and_f_per_ngl_gal) * \
                                                             gal_per_mcf[
                                                                 'n_butane'] + \
                                                             (gx_components['iso_butane'] - t_and_f_per_ngl_gal) * \
                                                             gal_per_mcf[
                                                                 'iso_butane'] + \
                                                             (gx_components['nat_gasoline'] - t_and_f_per_ngl_gal) * \
                                                             gal_per_mcf['nat_gasoline']



    print(f'\n| {gx_c_code} as of {string_date(trade_date)}: {wgx}')

    # re-sort month_pairs
    curr_month_pair = (np.mod(pd.to_datetime(strip_start).month, 12), np.mod(pd.to_datetime(strip_start).month, 12) + 1)
    print(f'curr_month_pair: {curr_month_pair}')
    curr_month_pair_index = month_pairs.index(curr_month_pair)
    print(f'curr_month_pair_index: {curr_month_pair_index}')
    resorted_month_pairs = month_pairs[curr_month_pair_index:] + month_pairs[:curr_month_pair_index]
    print(f'resorted_month_pairs: {resorted_month_pairs}')

    # todo: futures by price scenario --> build by month-pair, for current month-pair onwards
    # get the component data for this month-pair
    # note this object has a different structure >> values are dataframes of summary stats for all price scenarios
    print(f'| Reading {gx_c_code} component statistics...')
    gx_components = {f'{month_pair}': {c_nick: summary_stats[f'{month_pair}'][c_nick] for c_nick in
                                        c_nicks} for month_pair in resorted_month_pairs}

    print(gx_components)

    # iterator for the strip months
    strip_contract_dates = [_ for _ in wgx[price_scenarios[0]]]

    gx_prices = pd.DataFrame(index=price_scenarios[1:], columns=strip_contract_dates).fillna(0.0)
    # set the initial month equal to the latest front month settlement price for WGX - for all price scenarios (as an anchor point)
    front_month_settle = wgx[price_scenarios[0]][strip_contract_dates[0]]
    gx_prices.at[:, strip_contract_dates[0]] = front_month_settle

    # populate the rest of the curve and price scenarios based on the latest front month settle
    for pr_scen in price_scenarios[1:]:
        for contract in strip_contract_dates[1:]:
            prior_month_index = strip_contract_dates.index(contract) - 1
            prior_month = strip_contract_dates[prior_month_index]

            _mpair = f'{(pd.to_datetime(contract).month, np.mod(pd.to_datetime(contract).month, 12) + 1)}'
            # calculate the WGX price scenarios for this strip month, anchoring to the prior
            gx_prices.at[pr_scen, contract] = gx_prices.at[pr_scen, prior_month] + (
                    gx_components[_mpair]['hh'].at[pr_scen, 'hh'] +
                    gx_components[_mpair]['waha_gas_diff'].at[pr_scen, 'waha_gas_diff']) / btu_adj

            if _whichindex != 'd':
                gx_prices.at[pr_scen, contract] += (gx_components[_mpair]['ethane'].at[pr_scen, 'ethane']) * \
                                                   gal_per_mcf['ethane'] + \
                                                   (gx_components[_mpair]['propane'].at[pr_scen, 'propane']) * \
                                                   gal_per_mcf['propane'] + \
                                                   (gx_components[_mpair]['n_butane'].at[pr_scen, 'n_butane']) * \
                                                   gal_per_mcf['n_butane'] + \
                                                   (gx_components[_mpair]['iso_butane'].at[pr_scen, 'iso_butane']) * \
                                                   gal_per_mcf['iso_butane'] + \
                                                   (gx_components[_mpair]['nat_gasoline'].at[pr_scen, 'nat_gasoline']) * \
                                                   gal_per_mcf['nat_gasoline']



    # append the strip
    gx_prices.loc[price_scenarios[0], strip_contract_dates] = [_ for _ in wgx[price_scenarios[0]].values()]

    print(f'\n| {gx_c_code} simulated prices >>\n{gx_prices}')

    gx_prices = gx_prices.transpose()

    save_to_excel(gx_prices,
                  folder=save_to_folder,
                  filename=f'{gx_c_nick}_sim_prices_{string_date(trade_date)}_fm_{strip_start.replace("/", "_")}-{strip_end.replace("/", "_")}.xlsx'
                  )

    return gx_prices


#----------------------------------------------------------------------------------------------------------------------#
#-------------------------------------------------- CHARTS ------------------------------------------------------------#
#----------------------------------------------------------------------------------------------------------------------#


def save_and_show(fig):
    # save and show figure
    filename_html = f'{gx_c_nick}_prices_{string_date(trade_date)}.html'
    filename_png = f'{gx_c_nick}_prices_{string_date(trade_date)}.png'
    filename_pdf = f'{gx_c_nick}_prices_{string_date(trade_date)}.pdf'

    network_folder = save_to_folder

    # network save - html
    save_chart(fig, network_folder, network_folder + filename_html)

    # network save - PNG
    fig.write_image(network_folder + filename_png, width=_width, height=_height)

    # network save - PDF
    fig.write_image(network_folder + filename_pdf, width=_width, height=_height)

    # show fig
    fig.show()


def make_charts():
    # make charts with legends
    fig = make_subplots(
        rows=2,
        cols=1,
        horizontal_spacing=0.1,
        vertical_spacing=0.12,
        specs=[[{"type": "xy"}], [{"type": "table"}]]
    )

    chart_data = {}

    # colors
    light_blue = hex_to_rgba('#488fff', a=1.0, values=False)
    dark_magenta = hex_to_rgba('#992088', a=1.0, values=False)
    soft_magenta = hex_to_rgba('#d277e5', a=1.0, values=False)
    generic_pale_grey = hex_to_rgba('#f1f1f1', a=1.0, values=False)
    generic_pale_blue = hex_to_rgba('#c4cef6', a=1.0, values=False)
    bold_red = hex_to_rgba('#aa0000', a=1.0, values=False)
    bold_dark_green = hex_to_rgba('#005500', a=1.0, values=False)
    pastel_orange = hex_to_rgba('#e39f58', a=1.0, values=False)
    bold_orange = hex_to_rgba('#ff8202', a=1.0, values=False)
    generic_yellow = hex_to_rgba('#ffc332', a=1.0, values=False)
    ChartColor = namedtuple('ChartColor', ['color_1', 'color_2', 'color_3', 'color_4', 'color_5'])
    base_colors = ChartColor(color_1=generic_pale_blue,
                             color_2=light_blue,
                             color_3=dark_magenta,
                             color_4=soft_magenta,
                             color_5=generic_pale_grey
                             )
    other_colors = ChartColor(color_1=pastel_orange,
                              color_2=bold_orange,
                              color_3=bold_red,
                              color_4=generic_yellow,
                              color_5=bold_dark_green
                              )

    for pr_scen in gx_prices.columns:
        try:
            pr_scen_float = float(pr_scen.strip('%')) / 100
        except ValueError:
            pr_scen_float = pr_scen

        _y = [_ for _ in gx_prices.loc[:, pr_scen].values]
        _x = [string_date(pd.to_datetime(_, utc=True) + MonthEnd(-1) + Day(1)) for _ in gx_prices.index]
        _mode = ['lines+markers' if pr_scen_float in [pr_scen, 0.5, 0.25, 0.75] else
                 'markers'][0]
        _markercolor = [base_colors.color_2 if pr_scen_float == pr_scen else
                        base_colors.color_3 if pr_scen_float == 0.5 else
                        other_colors.color_2 if pr_scen_float in [0.25, 0.75] else
                        other_colors.color_1 if pr_scen_float in [0.10, 0.90] else
                        other_colors.color_4][0]
        _markersize = [11 if pr_scen_float in [pr_scen, 0.5] else
                       10 if pr_scen_float in [0.25, 0.75] else
                       8][0]
        _markersymbol = ['circle-dot' if pr_scen_float in [pr_scen, 0.5] else
                         'triangle-down' if pr_scen_float < 0.50 else
                         'triangle-up'
                         ][0]
        _line_width = 2.0
        _dash_dot = ['dash' if pr_scen_float in [0.50, 0.25, 0.75] else
                     None][0]
        _font_size = 12

        chart_data[pr_scen] = go.Scattergl(
            y=_y,
            x=_x,
            name=f'{gx_c_code} | {pr_scen}',
            mode=_mode,
            marker=dict(color=_markercolor,
                        size=_markersize,
                        symbol=_markersymbol
                        ),
            line=dict(width=_line_width,
                      dash=_dash_dot,
                      color=_markercolor),
            text=[f' {_:,.2f}' for idx, _ in enumerate(_y)],  # alternating: if np.mod(idx,2) == 0 else ''
            textposition=['top center' if np.mod(idx, 2) == 0 else 'bottom center' for idx, _ in
                          enumerate(_y)],
            textfont_size=_font_size,
            textfont_color=_markercolor,
            textfont_family='sans-serif'
        )

    for pr_scen, series in chart_data.items():
        fig.add_trace(series, row=1, col=1)

        # add annotations for strip pricing
        if 'Strip' in series['name']:
            for idx, x in enumerate(series['x']):
                y = series['y'][idx]
                num_format = f'{y: ,.2f}'
                # if this is a leverage chart, make it 0.00x
                print(f'| Strip annotations: x = {x}, y = {y}')
                fig.add_annotation(
                    x=x,
                    y=y,
                    xref="x",
                    yref="y",
                    text=num_format,
                    showarrow=True,
                    font=dict(
                        family="sans-serif",
                        size=_font_size + 1,
                        color=series['marker']['color']
                    ),
                    align="center",
                    arrowhead=None,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor=series['marker']['color'],
                    ax=0 if np.mod(idx, 2) == 0 else 0,
                    ay=-25 if np.mod(idx, 2) == 0 else 25,
                    bordercolor=None,
                    borderwidth=None,
                    borderpad=1,
                    bgcolor='white',
                    opacity=1.00,
                    row=1,
                    col=1
                )

    # Update xaxis properties
    fig.update_xaxes(dict(title_text=f'Futures Contract',
                          nticks=25,
                          tickangle=-45,
                          tickfont_size=_font_size,
                          gridcolor='rgba(175,175,175,0.75)'),
                     row=1,
                     col=1)
    # Update yaxis properties
    fig.update_yaxes(dict(title_text=f'{gx_c_code} | {gx_c_unit}',
                          tickformat=',.2f',
                          nticks=20,
                          tickfont_size=_font_size,
                          linecolor='rgba(100,100,100,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(80,80,80,0.75)',
                          gridcolor='rgba(200,200,200,0.75)'),
                     row=1,
                     col=1)

    _width = 1500
    _height = 1250
    fig.update_layout(title=f'{gx_c_name} Futures | As of {string_date(trade_date)}',
                      plot_bgcolor='rgba(255,255,255,1.0)',
                      width=_width,
                      height=_height,
                      showlegend=True,
                      legend=dict(title_text=None,  # 'Percentile Outcomes',
                                  orientation='v',
                                  y=1.00,
                                  x=1.01,
                                  font_size=_font_size)
                      )

    # add a gas composition table as chart #2
    print(gx_gas_sample_input_df)
    chart_df = gx_gas_sample_input_df.reset_index()
    chart_df = chart_df[['metric', 'id', 'unit', 'value']]
    num_columns = len(chart_df.columns)
    chart_df.rename(columns={'id': 'ID',
                             'metric': f'{gx_c_code} Component',
                             'unit': 'Unit',
                             'value': 'Value'}, inplace=True)
    column_alignment = ['left'] + ['center'] * (num_columns - 1)
    column_font_colors = ['rgb(40,40,40)'] * (num_columns)
    component_table = go.Table(
        header=dict(values=[_ for _ in chart_df.columns],
                    font=dict(color=hex_to_rgba('#bc50aa', a=1.0, values=False),
                              size=_font_size),
                    line_color='rgba(200,200,200,0.75)',
                    fill_color='white',
                    height=28,
                    align=column_alignment),
        cells=dict(values=[chart_df.loc[:, _].tolist() for _ in chart_df.columns],
                   align=column_alignment,
                   line=dict(color='rgba(200,200,200,0.75)'),
                   font=dict(color=column_font_colors,
                             size=_font_size),
                   format=[None] * (num_columns - 1) + [",.3f"],
                   # prefix = [None] + ['$'] *2,
                   # suffix=[None] * 4,
                   height=28,
                   fill=dict(color=['rgba(245,245,245, 1.00)'] + ['white'] * (num_columns - 1))))
    fig.add_trace(component_table, row=2, col=1)

    save_and_show(fig)



#----------------------------------------------------------------------------------------------------------------------#
#------------------------------------------------- EXECUTION ----------------------------------------------------------#
#----------------------------------------------------------------------------------------------------------------------#

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


# --- seasonal index --- #

# calculate historical strip shapes
historical_strip_shape(commodity_list=c_nicks)

# calculate summary stats
summary_stats = summary_stats_by_month_pair()

# calc WGX
gx_prices = calc_wgx(summary_stats)
