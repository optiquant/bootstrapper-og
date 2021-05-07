import _model.prices as pr
from _model.useful_functions import *
import os
import pandas as pd
import json
import glob
from datetime import datetime
import csv

# PLOTLY
from kaleido.scopes.plotly import PlotlyScope
import plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px

as_of_date = '5/5/21'
as_of_date = pd.to_datetime(as_of_date, utc=True)
c_nicks = ['hh', 'waha_gas_diff', 'hsc_gas_diff', 'ethane', 'propane', 'iso_butane', 'n_butane', 'nat_gasoline']
mcs_data_folders = {c_nick: pr.root_folder_mcs_data(c_nick)['root_folder'] for c_nick in c_nicks}
price_data_folders = {c_nick: pr.root_folder_price_data(c_nick)['root_folder'] for c_nick in c_nicks}

print(price_data_folders)

save_to_folder = r'T:/Finance-Strategy/Price Analysis/'
gal_mmbtu_conv_ratio = pr.get_conversion_ratios()['gal/mmbtu - energy']
ngl_nicks = get_ngl_nicks()
print(f'\n| Using conversion ratio >> {str(gal_mmbtu_conv_ratio)}')

mcs_start_end_dates = pr.get_mcs_start_end_dates(sim_end=as_of_date)


def extract_futures(future_months: int):
    for future_month_index in range(future_months):
        data = []
        for c_nick in c_nicks:
            # Place your JSON data in a directory named 'data/'
            src = price_data_folders[c_nick]
            date = datetime.now()

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
        conv_ratio = gal_mmbtu_conv_ratio
        # adjust prices to $/MMBtu if NGL
        summary_stats.loc['mean':'+3sig'] *= conv_ratio
        print(f'| Converted summary_stats:\n{summary_stats}')

    print(summary_stats)

    if save_to_xls:
        save_to_excel(output_dataframe=summary_stats,
                      folder=save_to_folder,
                      filename=f'{c_nick}_prices_fm{future_month_index}_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.xlsx')

    return summary_stats


def build_indexes(future_months: int, summary_stats: dict):
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


future_months = 24
error_log = []
summary_stats = {}
chart_data = {}

extract_futures(future_months=future_months)
build_indexes(future_months=future_months, summary_stats=summary_stats)
