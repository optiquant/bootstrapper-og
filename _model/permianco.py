from _model.useful_functions import *

import os
import pandas as pd
import numpy as np
import win32com.client as win32  # for outlook emailing
import re

pd.set_option('display.max_columns', None)

# PLOTLY
import plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px
from kaleido.scopes.plotly import PlotlyScope

# ----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#

# permianco bond prices
local_filepath = r'C:\/Users\/vdesai\/Git\/bootstrapper-og\/bond-comps\/'
network_filepath = r'\/FILE01\/TDrive\/Finance-Strategy\/PermianCo Credit Comps\/'

local_filename = sorted(filter(lambda x: ".csv" in x,os.listdir(local_filepath)))[-1]

as_of_date = pd.to_datetime(local_filename.strip(".csv").split("-")[1])
_q = input(f"\n| PermianCo bond comps updating as of >> {string_date(as_of_date)} // UTC: {as_of_date.tzinfo} >> Hit enter to continue.")

save_to_folder_local = local_filepath + f'/\\outputs/\\'
save_to_folder_network = network_filepath

# namedtuple for chart data
ChartData = namedtuple('ChartData', 'title x x_name y y_name data_labels')

# acceptable exchanges for pricing data are: Refinitiv Pricing Service (EJV), FINRA (FNR)
acceptable_exchanges = ['EJV', 'FNR']
acceptable_fields = {
    'EJV': [
        'ticker', 'company_name', 'security_description', 'eom_amount_outstanding', 'issue_date',
        'issue_price', 'maturity_date', 'coupon_rate', 'current_coupon_class_description', 'current_coupon_class_code',
        'accrued_interest', 'exchange_code', 'exchange_description', "trade_date", "bid_price",
        "ask_price", "close_price", "current_yield", "original_yield_to_maturity", "current_yield_to_maturity",
        "isma_yield_to_maturity", "isma_yield_to_worst", "native_yield_to_worst", "next_call_date", "next_call_price",
        "volume"
    ],
    'FNR': [
        'ticker', 'company_name', 'security_description', 'eom_amount_outstanding', 'issue_date',
        'issue_price', 'maturity_date', 'coupon_rate', 'current_coupon_class_description', 'current_coupon_class_code',
        'accrued_interest', 'exchange_code', 'exchange_description', "trade_date", "close_price",
        "original_yield_to_maturity", "next_call_date", "next_call_price", "volume"
    ]
}

parse_dates = ['Issue Date', 'Maturity Date', 'Trade Date', 'Next Call Date', 'Next Put Date']
column_datatypes = {
    "Ticker": "str",
    "Company Name": "str",
    "Security Description": "str",
    "EOM Amount Outstanding": "float",
    "Issue Date": "str",
    "Issue Price": "float",
    "Maturity Date": "str",
    "Coupon Rate": "float",
    "Current Coupon Class Description": "str",
    "Current Coupon Class Code": "str",
    "Accrued Interest": "float",
    "Exchange Code": "str",
    "Exchange Description": "str",
    "Underlying Exchange Code": "str",
    "Trade Date": "str",
    "Bid Price": "float",
    "Ask Price": "float",
    "Close Price": "float",
    "Current Yield": "float",
    "Original Yield to Maturity": "float",
    "Current Yield To Maturity": "float",
    "ISMA Yield To Maturity": "float",
    "ISMA Yield To Worst": "float",
    "Native Yield To Worst": "float",
    "Next Call Date": "str",
    "Next Call Price": "float",
    "Next Put Date": "str",
    "Next Put Price": "float",
    "Option Adjusted AL Volatility": "float",
    "Option Adjusted Price Volatility": "float",
    "Option Adjusted Zero Vol Spread": "float",
    "Volatility": "float",
    "Volume": "float"
}

bond_data_refinitiv = pd.DataFrame(columns=acceptable_fields['EJV'])
bond_data_finra = pd.DataFrame(columns=acceptable_fields['FNR'])


# ----------------------------------------------------------------------------------------------------------------------#
# -----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#


def load_bond_prices():
    '''Load bond prices for permianco from local drive'''
    bond_prices = pd.read_csv(local_filepath + r'/' + local_filename,
                              header=1,
                              dtype=column_datatypes,
                              parse_dates=parse_dates)
    print(bond_prices.info())
    return bond_prices


# clean up bond prices
def clean_up_bond_prices(bond_prices):
    # drop first row (info)
    bond_prices.columns = [_.lower().strip().replace(" ", '_').replace("-", "") for _ in bond_prices.columns]
    bond_prices.reset_index(inplace=True, drop=True)
    # replace the nans in columns other than 'eom_amount_outstanding'
    bond_prices.fillna('nan', inplace=True)
    bond_prices.loc[:, 'eom_amount_outstanding'] = [0.0 if _ == "nan" else _ for _ in bond_prices.loc[:, 'eom_amount_outstanding'].values]
    print(bond_prices.columns)

    dropped_indexes = []
    # drop all NA rows
    for row in bond_prices.itertuples():
        nans = {k: v for k, v in row._asdict().items() if v == 'nan'}
        nan_count = len(nans)
        threshold = 0.80
        nan_share = nan_count / len(list(row))
        if nan_share >= threshold or row.trade_date != as_of_date:
                print(f'| -- Dropping "NA" row >> Index = {row.Index} >> nan_count = {nan_count} / nan_share = {nan_share} // trade_date = {row.trade_date}')
                print(f'| -- values = {list(row)}')
                dropped_indexes.append(row.Index)
                bond_prices.drop(index=[row.Index], inplace=True)

    print(f'\n| Dropped Indexes >> {len(dropped_indexes)} >> {dropped_indexes}')
    print(f'\n| Clean Bond Pricing Data // As of date: {string_date(as_of_date)}')
    print(bond_prices.info())
    print(bond_prices)



def populate_bond_dataframes(bond_prices):
    '''Populates the Refinitiv and FINRA bond data dataframes.'''
    global bond_data_refinitiv
    global bond_data_finra
    for row in bond_prices.itertuples():
        if row.exchange_code == 'EJV':
            # add to Refinitiv bond dataframe
            print(f'--- to refinitiv >> {row.Index}')
            concat_frame = pd.DataFrame(
                {k: v for k, v in row._asdict().items() if k in bond_data_refinitiv.columns},
                index=[row.Index]
            )
            bond_data_refinitiv = pd.concat([bond_data_refinitiv, concat_frame])
        elif row.exchange_code == 'FNR':
            # add to FINRA bond dataframe
            print(f'--- to FINRA >> {row.Index}')
            concat_frame = pd.DataFrame(
                {k: v for k, v in row._asdict().items() if k in bond_data_finra.columns},
                index=[row.Index]
            )
            bond_data_finra = pd.concat([bond_data_finra, concat_frame])

    # sort by issue date
    # |-- There are often multiple listings for a particular security (for example, if there have been debt redemptions or amendments to terms)
    # |-- Using the latest issuance date assures that the most current information is reflected in summary charts
    bond_data_refinitiv.sort_values(by=['issue_date'], inplace=True)
    bond_data_finra.sort_values(by=['issue_date'], inplace=True)

    print(f'\n| Refinitiv Bond Pricing Data // As of date: {string_date(as_of_date)}')
    # remove rows with duplicate security descriptions
    bond_data_refinitiv.drop_duplicates(subset=['security_description'],
                                        keep='last',
                                        ignore_index=True,
                                        inplace=True)
    print(bond_data_refinitiv)
    save_to_excel(bond_data_refinitiv, folder=save_to_folder_local, filename=f'bond_data_refinitiv-{string_date(as_of_date)}.xlsx')
    try:
        save_to_excel(bond_data_refinitiv, folder=save_to_folder_network, filename=f'latest_permianco_bond_data.xlsx')
    except (PermissionError, FileNotFoundError, OSError):
        print(f'!! Save to network drive failed: {save_to_folder_network}')

    print(f'\n| FINRA Bond Pricing Data // As of date: {string_date(as_of_date)}')
    bond_data_finra.drop_duplicates(subset=['security_description'],
                                    keep='last',
                                    ignore_index=True,
                                    inplace=True)
    print(bond_data_finra)
    save_to_excel(bond_data_finra, folder=save_to_folder_local, filename=f'bond_data_finra-{string_date(as_of_date)}.xlsx')


def run_bond_charts(source='finra'):
    '''Bond charts. Source data can be "refinitiv" or "finra".'''

    _source_data_lookup = {
        'refinitiv': globals()['bond_data_refinitiv'],
        'finra': globals()['bond_data_finra']
    }

    source_data = _source_data_lookup[source]

    # CHART DEFAULTS
    chart_rows = 4
    chart_cols = 1
    _grid_color = 'rgba(220,220,220,1)'
    start_color = [180, 180, 180]  # [225, 36, 0]
    end_color = [100, 100, 100]
    f_size = 12
    # for whole figure
    figure_width = 1600
    figure_height = 1800


    fig = make_subplots(
        rows=chart_rows,
        cols=chart_cols,
        vertical_spacing=0.15,
        subplot_titles=['PermianCo Bonds Outstanding By Company',
                        f'Current Yields (as of {string_date(as_of_date)})',
                        f'Current Prices (as of {string_date(as_of_date)})',
                        'Bond Maturities'
                        ],
        specs=[
            [{'type': 'xy'}],
            [{'type': 'xy'}],
            [{'type': 'xy'}],
            [{'type': 'xy'}]
        ]
    )

    # -----------------------------------------# BONDS OUTSTANDING BY COMPANY #-----------------------------------------#
    # chart position
    _chart_row = 1
    _chart_col = 1

    # sort data
    source_data.sort_values(by=['eom_amount_outstanding'], axis=0, ascending=False, inplace=True)

    outstanding_by_company = pd.DataFrame(columns=['ticker', 'total_outstanding'])
    # sum up the data by ticker
    ticker_list = list_unique(source_data['ticker'], silent=True)
    for ticker in ticker_list:
        # total debt for this company
        total_outstanding = source_data[source_data['ticker'] == ticker]['eom_amount_outstanding'].sum()
        data = {'ticker': ticker,
                'total_outstanding': total_outstanding}
        outstanding_by_company = pd.concat([outstanding_by_company, pd.DataFrame(data, index=[len(outstanding_by_company)])])

    # sort highest to lowest
    outstanding_by_company.sort_values(by=['total_outstanding'], axis=0, ascending=False, inplace=True)

    # create chart data
    bonds_outstanding_data = ChartData(
        title='Publicly Traded Bonds Outstanding',
        x=[_ for _ in outstanding_by_company['ticker']],
        y=[_/1000000 for _ in outstanding_by_company['total_outstanding']],
        data_labels=[
            f'{ticker} | ${amt / 1000000:,.1f}' for ticker, amt in zip(
                outstanding_by_company['ticker'],
                outstanding_by_company['total_outstanding']
            )
        ],
        x_name='Ticker',
        y_name='Total Outstanding ($ MM)'
    )

    # assign colors for this data
    color_by = assign_colors_by_ticker(source_data=outstanding_by_company, chart_data=bonds_outstanding_data)

    fig.add_bar(
        x=bonds_outstanding_data.x,
        y=bonds_outstanding_data.y,
        text=bonds_outstanding_data.data_labels,
        marker=dict(color=[_ for _ in color_by.values()]),
        hovertemplate='<b>%{text}</b><br><i>Total Outstanding = $%{y:.1f}</i><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )

    # Update xaxis properties
    fig.update_xaxes(dict(title_text=bonds_outstanding_data.x_name,
                          tickangle=-45,
                          tickfont_size=f_size,
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)
    # Update yaxis properties
    fig.update_yaxes(dict(title_text=bonds_outstanding_data.y_name,
                          nticks=20,
                          tickfont_size=f_size,
                          tickformat=',.1f\xa0',
                          linecolor='rgba(10,10,10,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(15,15,15,0.75)',
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)


    # ----------------------------------------------------# YIELDS #----------------------------------------------------#
    # chart position
    _chart_row = 2
    _chart_col = 1

    # sort data
    source_data.sort_values(by=['current_yield'], axis=0, ascending=False, inplace=True)

    # create chart data
    bond_yields_data = ChartData(
        title='Current Yields',
        x=[_ for _ in source_data['security_description']],
        y={
            'current_yield': [_ for _ in source_data['current_yield']],
            'original_yield_to_maturity': [_ for _ in source_data['original_yield_to_maturity']],
            'current_yield_to_maturity': [_ for _ in source_data['current_yield_to_maturity']],
            'coupon_rate': [_ for _ in source_data['coupon_rate']]
        },
        data_labels=[
            f'${amt / 1000000:,.1f} | {desc}' for desc, amt in zip(
                source_data['security_description'],
                source_data['eom_amount_outstanding']
            )
        ],
        x_name='Security Description',
        y_name='Yield %'
    )

    # assign colors for this data
    color_by = {k: color_by[ticker] for k in bond_yields_data.data_labels for ticker in color_by if ticker in k}

    fig.add_bar(
        x=bond_yields_data.x,
        y=bond_yields_data.y['current_yield'],
        text=bond_yields_data.data_labels,
        marker=dict(color=[_ for _ in color_by.values()]),
        hovertemplate='<b>%{text}</b><br><i>Current Yield = %{y:.3f%}</i><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )

    fig.add_scatter(
        x=bond_yields_data.x,
        y=bond_yields_data.y['coupon_rate'],
        text=bond_yields_data.data_labels,
        mode='markers',
        marker=dict(color='rgba(55,55,105,0.95)',
                    symbol='triangle-up',
                    size=10
                    ),
        hovertemplate='<b>%{text}</b><br><i>Coupon Rate = %{y:.3f%}</i><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )

    # Update xaxis properties
    fig.update_xaxes(dict(title_text=bond_yields_data.x_name,
                          tickangle=-45,
                          tickfont_size=f_size,
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)
    # Update yaxis properties
    fig.update_yaxes(dict(title_text=bond_yields_data.y_name,
                          nticks=20,
                          tickfont_size=f_size,
                          tickformat=',.2f',
                          linecolor='rgba(10,10,10,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(15,15,15,0.75)',
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)


    # ----------------------------------------------------# PRICES #----------------------------------------------------#
    # chart position
    _chart_row = 3
    _chart_col = 1

    # sort data
    source_data.sort_values(by=['close_price'], axis=0, inplace=True)

    # create chart data
    bond_prices_data = ChartData(
        title='Current Prices',
        x=[_ for _ in source_data['security_description']],
        y={
            'close_price': [_ for _ in source_data['close_price']],
            'bid_price': [_ for _ in source_data['bid_price']],
            'ask_price': [_ for _ in source_data['ask_price']]
        },
        data_labels=[
            f'${amt / 1000000:,.1f} | {desc}' for desc, amt in zip(
                source_data['security_description'],
                source_data['eom_amount_outstanding']
            )
        ],
        x_name='Security Description',
        y_name='Bond Price'
    )

    # assign colors for this data
    color_by = {k: color_by[ticker] for k in bond_prices_data.data_labels for ticker in color_by if ticker in k}

    fig.add_bar(
        x=bond_prices_data.x,
        y=bond_prices_data.y['close_price'],
        text=bond_prices_data.data_labels,
        marker=dict(color=[_ for _ in color_by.values()]),
        hovertemplate='<b>%{text}</b><br><i>Price = %{y:.3f}</i><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )
    fig.add_scatter(
        x=bond_prices_data.x,
        y=[100 for _ in bond_prices_data.x],
        text=bond_prices_data.data_labels,
        marker=dict(color='rgba(15,15,15,0.95)'),
        hovertemplate='<i>Price = Par</i><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )

    # Update xaxis properties
    fig.update_xaxes(dict(title_text=bond_prices_data.x_name,
                          tickangle=-45,
                          tickfont_size=f_size,
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)
    # Update yaxis properties
    fig.update_yaxes(dict(title_text=bond_prices_data.y_name,
                          nticks=20,
                          tickfont_size=f_size,
                          tickformat=',.1f\xa0',
                          linecolor='rgba(10,10,10,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(15,15,15,0.75)',
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)

    # ------------------------------------------------# MATURITY WALLS #------------------------------------------------#
    # chart position
    _chart_row = 4
    _chart_col = 1
    # sort data
    source_data.sort_values(by=['maturity_date'], axis=0, inplace=True)

    # create chart data
    maturity_walls_data = ChartData(
        title='PermianCo Bond Maturities',
        x=[f'{_.month}-{_.year}' for _ in source_data['maturity_date']],
        y=[_ / 1000000 for _ in source_data['eom_amount_outstanding']],
        data_labels=[
            f'${amt / 1000000:,.1f} | {desc}' for desc, amt in zip(
                source_data['security_description'],
                source_data['eom_amount_outstanding']
            )
        ],
        x_name='Maturity Date',
        y_name='Bond Principal Outstanding ($ MM)'
    )

    # assign colors for this data
    color_by = {k: color_by[ticker] for k in maturity_walls_data.data_labels for ticker in color_by if ticker in k}

    fig.add_bar(
        x=maturity_walls_data.x,
        y=maturity_walls_data.y,
        text=maturity_walls_data.data_labels,
        marker=dict(color=[_ for _ in color_by.values()]),
        hovertemplate='<b>%{text}</b><extra></extra>',
        showlegend=False,
        row=_chart_row,
        col=_chart_col
    )

    # Update xaxis properties
    fig.update_xaxes(dict(title_text=maturity_walls_data.x_name,
                          tickangle=-45,
                          tickfont_size=f_size,
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)
    # Update yaxis properties
    fig.update_yaxes(dict(title_text=maturity_walls_data.y_name,
                          nticks=20,
                          tickfont_size=f_size,
                          tickformat=',.1f\xa0',
                          linecolor='rgba(10,10,10,0.75)',
                          zeroline=True,
                          zerolinecolor='rgba(15,15,15,0.75)',
                          gridcolor=_grid_color),
                     row=_chart_row,
                     col=_chart_col)

    #----------------------------------------------# FOR WHOLE FIGURE #-----------------------------------------------#
    fig.update_layout(
        title=f'PermianCo Credit Comps',
        title_xanchor='left',
        title_yanchor='top',
        plot_bgcolor='rgba(0,0,0,0)',
        width=figure_width,
        height=figure_height,
        legend=dict(orientation='v',
                    y=1.00,
                    x=1.05,
                    font_size=f_size)
    )

    save_charts(fig=fig, figure_width=figure_width, figure_height=figure_height)
    fig.show()


def assign_colors_by_ticker(source_data: pd.DataFrame, chart_data: ChartData):
    '''Assign colors by ticker to ChartData namedtuple object.'''
    # get a list of colors for each ticker
    unique_tickers = list_unique(source_data['ticker'], silent=True)
    colors = px.colors.sequential.thermal[:len(unique_tickers)]
    color_by_ticker = dict(zip(unique_tickers, colors))
    color_by = {}

    for label in chart_data.data_labels:
        for ticker, color in color_by_ticker.items():
            if ticker in label:
                print(ticker, label, color)
                color_by[ticker] = color
    print(f'Colors labeled as follows: {color_by_ticker} >>\n{color_by}')
    return color_by


def save_charts(fig, figure_width, figure_height):
    folder_local = save_to_folder_local
    folder_network = save_to_folder_network
    filename_htm = f'permianco_credit_comps_{string_date(as_of_date)}.html'
    filename_png = f'permianco_credit_comps_{string_date(as_of_date)}.png'
    filename_eml = f'permianco_credit_comps.html'  # no dates allowed

    global email_filepaths
    global image_filepaths

    email_filepaths = (folder_network + filename_htm, folder_network + filename_png)
    image_filepaths = (folder_local + filename_htm, folder_network + filename_png)

    print(image_filepaths, email_filepaths)

    scope = PlotlyScope()

    # local folder save (html and PNG)
    fig.write_html(folder_local + filename_htm, include_plotlyjs='True')
    with open(folder_local + filename_png, "wb") as f:
        f.write(scope.transform(fig, format="png", width=figure_width, height=figure_height))

    # network folder save (html and PNG)
    try:
        fig.write_html(folder_network + filename_htm, include_plotlyjs='True')
        with open(folder_network+filename_png, "wb") as f:
            f.write(scope.transform(fig, format="png", width=figure_width, height=figure_height))
    except (OSError, FileNotFoundError, PermissionError):
        print(f'!! File not found or network folder not accessible.')


def send_permianco_bond_comps_email(sender, recipients):
    outlook = win32.Dispatch('outlook.application')
    mail = outlook.CreateItem(0)
    mail.To = recipients
    # mail.Bcc = '''raju.ashu@gmail.com; ashulobodesai@gmail.com; vihandesai@gmail.com'''

    mail.Subject = f'PermianCo Credit Comps - {string_date(as_of_date)}'

    global bodytext
    bodytext = '''
    <b>
    <p style="font-size:15pt">
    PermianCo Credit Comps
    </p>
    </b>
    <p style="font-size:11.5pt">
    <br>
    Attached and below is the latest PermianCo Credit Comps update, based on market data from Refinitiv: 
    <ol style= "font-size:11.5pt">
    <li>Total publicly traded bonds outstanding (by company)
    <li>Current yields
    <li>Current prices
    <li>Maturities by bond    
    </ol> 
    <p style="font-size:11.5pt">
    <i>
    ** Note that this data does not include debt that is not publicly traded, such as RBLs, term loans, etc. 
    </i>
    <br>
    <br>
    <i>
    <a href = "T:/Finance-Strategy/PermianCo Credit Comps/">Interactive versions</a> of these charts are saved on the T: drive.
    You will need to be connected to the Triple Crown VPN if you are working remotely.
    </i>
    </p>
    <br>
    '''
    global img_prop_accessor
    img_prop_accessor = {}
    global image_filepaths
    global email_filepaths
    # filepath_prices_xls = 'C:/Users/vdesai/Desktop/Model/Python/TCR - Model Prices.xlsx'
    # attachment = mail.Attachments.Add(filepath_prices_xls)

    for idx, img in enumerate(email_filepaths):
        # Change the Paths here, if run from a different location
        signatureimage = img
        attachment = mail.Attachments.Add(signatureimage)

        # access PNG attachment to include in body of email
        if idx == 1:
            attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                                                img.replace(' ', '_'))
            bodytext = bodytext + '<html><body>_________________________<br><img src="cid:' + img.replace(' ', '_') + '"><br></body></html>'
            attachment = mail.Attachments.Add(signatureimage)
            img_prop_accessor[img] = (bodytext)

    sig_block = '''
    <html>
    <body>
    <p style="font-size:11.5pt">
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


def run_bond_comps():
    global bond_prices
    bond_prices = load_bond_prices()
    clean_up_bond_prices(bond_prices)
    populate_bond_dataframes(bond_prices)
    run_bond_charts(source='refinitiv')
    send_permianco_bond_comps_email('vdesai@triplecrownresources.com', 'vdesai@triplecrownresources.com')


# ---------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------# EXECUTION #----------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#

run_bond_comps()

