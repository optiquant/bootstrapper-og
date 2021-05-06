import os
import prices as pr
from useful_functions import *
import pandas as pd
import plotly.graph_objects as go

as_of_date = '5/4/21'
as_of_date = pd.to_datetime(as_of_date, utc=True)
c_nicks = ['hh', 'waha_gas_diff', 'hsc_gas_diff', 'ethane', 'propane', 'iso_butane', 'n_butane', 'nat_gasoline']
mcs_data_folders = {c_nick: pr.root_folder_mcs_data(c_nick)['root_folder'] for c_nick in c_nicks}
print(mcs_data_folders)

save_to_folder = r'T:/Finance-Strategy/Price Analysis/'
gal_mmbtu_conv_ratio = pr.get_conversion_ratios()['gal/mmbtu - energy']
ngl_nicks = get_ngl_nicks()
print(f'\n| Using conversion ratio >> {str(gal_mmbtu_conv_ratio)}')


mcs_start_end_dates = pr.get_mcs_start_end_dates(sim_end=as_of_date)

# for c_nick in c_nicks:
#     # c_nick = c_nicks[0]
#     c_code = get_comdty_code(c_nick=c_nick)
#
#     files_in_dir = os.listdir(mcs_data_folders[c_nick])
#
#     most_recent_filename = mcs_data_folders[c_nick]+files_in_dir[-1]
#     print(most_recent_filename)
#
#     data = pd.read_json(most_recent_filename)
#     data.sort_index(ascending=False, inplace=True)
#     print(data)
#
#     settle_prices = pd.Series(data.loc[:, 'settle_price'])
#     print(settle_prices)
#
#     summary_stats = {**settle_prices.describe([0.5])}
#     print(summary_stats)
#
#     median = summary_stats['50%']
#     summary_stats['-1sig'], summary_stats['+1sig'] = [median-summary_stats['std'], median+summary_stats['std']]
#     summary_stats['-2sig'], summary_stats['+2sig'] = [median-2*summary_stats['std'], median+2*summary_stats['std']]
#     summary_stats['-3sig'], summary_stats['+3sig'] = [median-3*summary_stats['std'], median+3*summary_stats['std']]
#
#     _ordering = ['count', 'mean', 'std','min', '-3sig', '-2sig', '-1sig', '50%','+1sig','+2sig','+3sig', 'max']
#     summary_stats = pd.Series(summary_stats).reindex(_ordering)
#     if c_nick in ngl_nicks:
#         conv_ratio = gal_mmbtu_conv_ratio
#         # adjust prices to $/MMBtu if NGL
#         summary_stats.loc['mean':'max'] *= conv_ratio
#         print(f'| Converted summary_stats:\n{summary_stats}')
#
#     print(summary_stats)
#
#     save_to_excel(output_dataframe=summary_stats,
#                   folder=save_to_folder,
#                   filename=f'{c_nick}_prices_fm1_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.xlsx')


#####################################
#  multiple future months
# future months for which data is required:
future_months = 36

# extract the settlement prices for each commodity by futures month and trade date
settle_prices = {}

for c_nick in c_nicks:
    settle_prices[c_nick] = {}
    historical_date_range = [
        string_date(_) for _ in pd.date_range(start=mcs_start_end_dates[c_nick].sim_start,
                                              end=mcs_start_end_dates[c_nick].sim_end,
                                              freq='d',
                                              tz="UTC")
    ]

    for trade_date in historical_date_range:
        settle_prices[c_nick][trade_date] = {}

        for future_month_index in range(future_months):
            try:
                price = pr.get_price_data(c_nick=c_nick,
                                          as_of_date=trade_date,
                                          ).loc[future_month_index, 'settle_price']
                settle_prices[c_nick][trade_date][future_month_index] = price
            except KeyError:
                pass




# now we have all the price data required
# create statistical summaries for each futures month
summary_stats = {}

for future_month_index in range(future_months):
    summary_stats[future_month_index] = {}

    for c_nick in c_nicks:
        summary_stats[future_month_index][c_nick] = []
        historical_date_range = [
            string_date(_) for _ in pd.date_range(start=mcs_start_end_dates[c_nick].sim_start,
                                                  end=mcs_start_end_dates[c_nick].sim_end,
                                                  freq='d',
                                                  tz="UTC")
        ]

        for trade_date in historical_date_range:
            price = settle_prices[c_nick][trade_date][future_month_index]
            summary_stats[future_month_index][c_nick].append(price)

# create summary stats
for future_month_index in range(future_months):
    for c_nick in c_nicks:
        list_data = summary_stats[future_month_index][c_nick]
        stats = pd.Series(list_data).describe([0.5])
        summary_stats = {**stats.describe([0.5])}
        print(summary_stats)

        median = summary_stats['50%']
        summary_stats['-1sig'], summary_stats['+1sig'] = [median - summary_stats['std'], median + summary_stats['std']]
        summary_stats['-2sig'], summary_stats['+2sig'] = [median - 2 * summary_stats['std'],
                                                          median + 2 * summary_stats['std']]
        summary_stats['-3sig'], summary_stats['+3sig'] = [median - 3 * summary_stats['std'],
                                                          median + 3 * summary_stats['std']]

        _ordering = ['count', 'mean', 'std', 'min', '-3sig', '-2sig', '-1sig', '50%', '+1sig', '+2sig', '+3sig', 'max']
        summary_stats = pd.Series(summary_stats).reindex(_ordering)
        if c_nick in ngl_nicks:
            conv_ratio = gal_mmbtu_conv_ratio
            # adjust prices to $/MMBtu if NGL
            summary_stats.loc['mean':'max'] *= conv_ratio
            print(f'| Converted summary_stats:\n{summary_stats}')

        print(summary_stats)

        save_to_excel(output_dataframe=summary_stats,
                      folder=save_to_folder,
                      filename=f'{c_nick}_prices_fm{future_month_index+1}_{mcs_start_end_dates[c_nick].sim_start}_{mcs_start_end_dates[c_nick].sim_end}.xlsx')
