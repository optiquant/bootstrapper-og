import matplotlib.colors

import _model_v2.price_update as pu
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as tkr
import os
from matplotlib import rcParams
import glob
import re
from pandas.tseries.offsets import MonthEnd, BDay
import numpy as np
import json

pd.set_option('display.max_columns', None)


# -----------------------------------------------------------------------------------------------------------#
# ------------------------------------------ FUNCTIONS ------------------------------------------------------#
# -----------------------------------------------------------------------------------------------------------#

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


# -----------------------------------------------------------------------------------------------------------#
# ------------------------------------------ EXECUTION ------------------------------------------------------#
# -----------------------------------------------------------------------------------------------------------#

PRICE_DATA_FOLDER = 'c:/users/viren/documents/consulting/_price_data/'
hist_days = [0, 1, 2, 3, 4, 5, 6, 10, 20, 60]

# get all price files for this commodity
c_codes = ['CL']
c_code = c_codes[0]
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
for _f in chart_files:
    c_code = re.search(_ptrn, _f).group()
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
fig.suptitle(f'{pu.COMDTY_REF[c_code][0]} Futures (CME Code: {c_code}) | Price Unit: {pu.COMDTY_REF[c_code][3]}')

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

# annotate latest strip
latest_prices = price_data[price_data['trade_date'] == strip_chart_dates[-1]]
for x, y in zip(latest_prices['contract_date'].values,
                latest_prices['settle_price'].values):
    ax.annotate(text=f'{y:.2f}',  # annotation text
                xy=(x, y),  # datapoint being labeled
                xycoords='data',  # coordinate system for xy
                xytext=(15, 25),  # where should the text be
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

#---------- FRONT MONTH SETTLEMENT HISTORY ----------#
axes[1][0].set_title('Front Month Settlement History')

data = []
# get every CHART_MONTHS-th row
rows_in_price_data = len(price_data.index)
data_indexes = [_*CHART_MONTHS for _ in range(int(rows_in_price_data / CHART_MONTHS))]
price_chart_data = price_data.loc[data_indexes,['trade_date', 'settle_price']]
# drop zero prices
price_chart_data = price_chart_data[price_chart_data['settle_price'] != 0.0]
price_chart_data.reset_index(drop=True, inplace=True)

palette = 'YlGnBu'
ax = sns.lineplot(ax=axes[1, 0],
                  data=price_chart_data,
                  palette=palette,
                  x='trade_date', y='settle_price'
                  )

price_chart_data['x_labels'] = pd.to_datetime(price_chart_data.trade_date).dt.strftime("%b-%y")
print(price_chart_data.head())
# sparsify
ax.set_xticks(range(len(price_chart_data.x_labels)))
ax.set_xticklabels(labels=price_chart_data.x_labels, rotation=90, ha='center', va='top')
_sparsify_by = 100
ax.xaxis.set_major_locator(tkr.MultipleLocator(_sparsify_by))
ax.yaxis.set_major_formatter(tkr.FuncFormatter(lambda y, p: f'{y:.2f}'))
ax.grid()



#---------- HISTOGRAM OF FRONT MONTH SETTLEMENTS (+ STATS) ----------#
axes[1][1].set_title('Distribution of Front Month Settlements')
histogram_data = pd.DataFrame(price_chart_data)
print(histogram_data.describe())
# todo: start here! finish histogram and overlaid stats, then do excel file, email, then done!

plt.tight_layout()
plt.show()
#
