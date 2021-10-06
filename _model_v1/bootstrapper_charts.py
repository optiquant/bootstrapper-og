import _model_v1.model_drivers as model_drivers
import _model_v1.model_control as model_control
from _model_v1.useful_functions import *

import pandas as pd
import os
from collections import namedtuple
import chart_studio.plotly as py
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from kaleido.scopes.plotly import PlotlyScope
from pandas.tseries.offsets import *

####################################

# chart colors and formatting
# oil, gas, NGL colors
f_size = 13
chart_months = model_control.chart_months
oil_green = hex_to_rgba('#005500', a=1.0, values=True)
oil_strip_color = hex_to_rgba('#ef8700', a=1.0, values=True)

gas_red = hex_to_rgba('#ff0025', a=1.0, values=True)
gas_strip_color = hex_to_rgba('#4400dd', a=1.0, values=True)

ngl_blue = hex_to_rgba('#0555ff', a=1.0, values=True)
ngl_strip_color = hex_to_rgba('#e00098', a=1.0, values=True)

limit_line_color = hex_to_rgba('#c8c8c8', a=1.0, values=True)
_grid_color = hex_to_rgba('#dcdcdc', a=1.0, values=False)

# other colors
generic_bright_blue = hex_to_rgba('#488fff', a=1.0, values=True)
dark_magenta = hex_to_rgba('#992088', a=1.0, values=True)
soft_magenta = hex_to_rgba('#d277e5', a=1.0, values=True)
generic_pale_grey = hex_to_rgba('#f1f1f1', a=1.0, values=True)
generic_pale_blue = hex_to_rgba('#c4cef6', a=1.0, values=True)
light_blue = hex_to_rgba('#488fff', a=1.0, values=True)


bold_red = hex_to_rgba('#aa0000', a=1.0, values=True)
bold_dark_green = hex_to_rgba('#005500', a=1.0, values=True)
pastel_orange = hex_to_rgba('#e39f58', a=1.0, values=True)
bold_orange = hex_to_rgba('#ff8202', a=1.0, values=True)
generic_yellow = hex_to_rgba('#ffc332', a=1.0, values=True)

# namedtuples to access chart colors easily
# for bootstrapper chart formats, we need to reference median, limit, and strip colors
# for non-bootstrapper charts, one or more of the ChartColor attributes can be the same
ChartColor = namedtuple('ChartColor', ['color_1', 'color_2', 'color_3', 'color_4', 'color_5'])
oil_colors = ChartColor(color_1=oil_green,
                        color_2=limit_line_color,
                        color_3=oil_strip_color,
                        color_4=generic_pale_blue,
                        color_5=generic_pale_grey
                        )
gas_colors = ChartColor(color_1=gas_red,
                        color_2=limit_line_color,
                        color_3=gas_strip_color,
                        color_4=generic_pale_blue,
                        color_5=generic_pale_grey
                        )
ngl_colors = ChartColor(color_1=ngl_blue,
                        color_2=limit_line_color,
                        color_3=ngl_strip_color,
                        color_4=generic_pale_blue,
                        color_5=generic_pale_grey
                        )
generic_blues = ChartColor(color_1=generic_pale_blue,
                           color_2=generic_bright_blue,
                           color_3=dark_magenta,
                           color_4=soft_magenta,
                           color_5=generic_pale_grey
                           )
other_colors = ChartColor(color_1=dark_magenta,
                          color_2=generic_yellow,
                          color_3=light_blue,
                          color_4=pastel_orange,
                          color_5=bold_orange
                          )


# ----------------------------------------------------------------------------------------------------------------------#
# --------------------------------------------# GENERIC BOOTSTRAPPER CHART #--------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#
def get_dash_outputs():
    global dash_outputs
    try:
        return dash_outputs
    except NameError:
        print(f"!! dash_outputs not defined")


# bootstrapper format charts
def bootstrapper_charts(chart_data_filepaths=[],
                        chart_names=[],
                        chart_dfs=[],
                        grid_rows=1,
                        grid_columns=1,
                        width=2000,
                        height=1750,
                        vert_spacing=0.1,
                        y_axis_tickformat='$,.2f\xa0',
                        y_axis_unit='$/Bbl',
                        figure_title=f'Bootstrap Prices Modeled',
                        chart_filename='price_charts',
                        ):
    """
    Creates a set of "bootstrapper format" charts for the dataframes in the passed filepaths.
    """
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    def save_and_show(fig, chart_filename):
        # save and show figure
        filename_html = f'{scenario_time_stamp}_{chart_filename}.html'
        filename_png = f'{scenario_time_stamp}_{chart_filename}.png'
        filename_pdf = f'{scenario_time_stamp}_{chart_filename}.pdf'

        # local filepath
        local_data_filepath = [f for f in scenario_filepaths_all['local']][0]
        local_folder = local_data_filepath.partition(scenario_time_stamp)[
                           0] + '\/' + scenario_time_stamp + '\/' + "\/charts\/"
        # network filepath
        network_data_filepath = [f for f in scenario_filepaths_all['network']][0]
        network_folder = network_data_filepath.partition(scenario_time_stamp)[
                             0] + '\/' + scenario_time_stamp + '\/' + "\/charts\/"

        # local save - html
        save_chart(fig, local_folder, local_folder + filename_html)
        # network save - html
        save_chart(fig, network_folder, network_folder + filename_html)

        # local save - PNG
        fig.write_image(local_folder + filename_png, width=width, height=height)
        # network save - PNG
        fig.write_image(network_folder + filename_png, width=width, height=height)

        # local save - PDF
        fig.write_image(local_folder + filename_pdf, width=width, height=height)
        # network save - PDF
        fig.write_image(network_folder + filename_pdf, width=width, height=height)

        # add fig to the global dash outputs
        global dash_outputs
        dash_outputs[chart_filename] = fig
        # todo: make a folder for dash outputs / app outputs, and save these figs down there

        # show fig
        fig.show()

    # chart color mappers
    # dict structure: {chart name contains 'x' : chart color}
    chart_color_mapper = {
        ('wti', 'wti_hou', 'midcush_ff', 'oil'): oil_colors,
        ('hh', 'waha_gas_diff', 'hsc_gas_diff', 'gas_'): gas_colors,
        ('ethane', 'propane', 'n_butane', 'iso_butane', 'nat_gasoline', 'ngl'): ngl_colors,
        ('loe', 'marketing', 'prod_taxes', 'capex'): generic_blues,
        ('revenue_total_all', 'opex_total_all', 'capex_total_all', 'fcf', 'ebitdax',
         'financing', 'parentco'): other_colors
    }

    ############################## SET UP FIGURE GRID ##############################
    # coordinate grid
    rows = grid_rows
    cols = grid_columns
    chart_coords = line_to_grid(linear_range=chart_names, grid_shape=[rows, cols])

    # each filepath points to chart dataframes --> index=[0:len(model_period)], cols=Dates and price scenarios
    # create a new chart for each dataframe
    # chart_data: dict to store all charts (one key per chart)
    chart_data = {}
    # chart_series: dict to store each series shown on the fig
    # populate chart_series, then add to chart_data
    chart_series = {}

    ############################## TABLE FORMAT CHARTS ##############################
    # table format chart (for NPV/Returns)

    if any([kw in _ for _ in chart_names for kw in ['npv_returns']]):
        # for each data table in the chart_dfs dictionary
        # todo: a similar big price deck table above the NPV, highlighting the strip
        for chart_name in chart_names:
            # chart_name = 'npv_returns' # test code!
            chart_data[chart_name] = []
            chart_df = chart_dfs[chart_name]
            num_columns = len(chart_df.columns)
            fig = make_subplots(rows=rows,
                                cols=cols,
                                horizontal_spacing=0.1,
                                vertical_spacing=vert_spacing,
                                specs=[[{"type": "table", "colspan": cols}] * cols] * rows
                                )

            chart_df.rename(columns={'index': f'{chart_name}'}, inplace=True)
            column_alignment = ['left'] + ['center'] * (num_columns - 1)
            column_font_colors = ['rgb(40,40,40)'] * (num_columns)

            chart_series[chart_name] = go.Table(
                header=dict(values=[_ for _ in chart_df.columns],
                            font=dict(color=hex_to_rgba('#bc50aa', a=1.0, values=False),
                                      size=f_size),
                            line_color=_grid_color,
                            fill_color='white',
                            height=28,
                            align=column_alignment),
                cells=dict(values=[chart_df.loc[:, _].tolist() for _ in chart_df.columns],
                           align=column_alignment,
                           line=dict(color=_grid_color),
                           font=dict(color=column_font_colors,
                                     size=f_size),
                           format=[None] + [",.2f"] * (num_columns - 1),
                           # prefix = [None] + ['$'] *2,
                           # suffix=[None] * 4,
                           height=28,
                           fill=dict(color=['rgba(245,245,245, 1.00)'] + ['white'] * (num_columns - 1))))

            # add the series for each col_name to the chart_data dict -->
            # keys: chart names, values: list of series (graph objects)
            chart_data[chart_name].append(chart_series[chart_name])

        print(f'| chart_data keys: {[_ for _ in chart_data]} // values: {[type(_) for _ in chart_data.values()]}')
        print(f'| chart_coords: {chart_coords}')
        # outside loop over columns of chart dataframes
        for idx, chart_name in enumerate(chart_data):
            row_position, col_position = chart_coords[idx]
            # list of data series for this chart
            chart_df = chart_data[chart_name]
            for df in chart_df:
                fig.add_trace(df, row=row_position, col=col_position)


    # else this is a not a table format chart
    else:
        ############################## BOOTSTRAPPER FORMAT CHARTS ##############################

        fig = make_subplots(rows=rows,
                            cols=cols,
                            horizontal_spacing=0.1,
                            vertical_spacing=vert_spacing,
                            specs=[[{"type": "xy"}] * cols] * rows
                            )

        # CREATE CHART OBJECTS FOR EACH SERIES
        # create a graph object for each chart in the legend labels list
        for chart_name in chart_names:
            # chart_name = 'wti' # test code!
            chart_data[chart_name] = []
            # truncate to chart_months only
            chart_df = chart_dfs[chart_name].iloc[:chart_months, :]
            # columns are an index, convert to list
            col_list = [_ for _ in chart_df.columns][1:]
            print(col_list)
            print(chart_df)

            # colors for this chart
            base_colors = [v for k, v in chart_color_mapper.items() if any([_ in chart_name for _ in k])][0]
            median_color = base_colors.color_1
            limit_color = base_colors.color_2
            strip_color = base_colors.color_3
            print(f'| median_color: {median_color}\n| strip_color: {strip_color}\n| limit_color: {limit_color}')
            # x axis values. note: y values are defined in the for-loop for each data series below
            x_vals = [string_date(pd.to_datetime(_) - MonthBegin(1)) for _ in model_period[:len(chart_df.index)]]
            print(x_vals)
            for col_name in col_list:
                # if this dataframe is a bootstrapper format dataframe (columns = MCS price scenarios)
                if any([_ == '50%' for _ in col_list]):
                    # formatting for each price _scenario line
                    # annotations (to implement formatting for data labels)
                    # if 'Strip' in col_name or '$' in col_name:
                    if '%' not in col_name or 'Strip' in col_name:
                        # REGULAR TEXT LABELS:
                        # _m = 'lines+markers+text' if chart_months <= 24 else 'lines+markers'
                        # FOR ANNOTATIONS
                        _m = 'lines+markers' if chart_months <= 24 else 'lines+markers'
                        _mode, _markersize, _line_width, _dash_dot = [_m, 11, 2.0, None]
                        r, g, b, a = strip_color
                        _markercolor = f'rgba({r},{g},{b},{a})'

                    elif col_name == '50%':
                        _mode, _markersize, _line_width, _dash_dot = ['lines+markers', 10, 1.0, 'dash']
                        r, g, b, a = midrange_color(med_color=median_color,
                                                    lim_color=limit_color,
                                                    percentile=float(col_name.rstrip('%')) / 100)
                        _markercolor = f'rgba({r},{g},{b},{a})'

                    elif col_name == '25%' or col_name == '75%':
                        _mode, _markersize, _line_width, _dash_dot = ['lines+markers', 12, 1.0, 'dash']
                        r, g, b, a = midrange_color(med_color=median_color,
                                                    lim_color=limit_color,
                                                    percentile=float(col_name.rstrip('%')) / 100)
                        _markercolor = f'rgba({r},{g},{b},{a})'

                    elif col_name == '10%' or col_name == '90%':
                        _mode, _markersize, _line_width, _dash_dot = ['markers', 10, 1.0, None]
                        r, g, b, a = midrange_color(med_color=median_color,
                                                    lim_color=limit_color,
                                                    percentile=float(col_name.rstrip('%')) / 100)
                        _markercolor = f'rgba({r},{g},{b},{a})'

                    elif col_name == '5%' or col_name == '95%':
                        _mode, _markersize, _line_width, _dash_dot = ['markers', 8, 1.0, None]
                        r, g, b, a = midrange_color(med_color=median_color,
                                                    lim_color=limit_color,
                                                    percentile=float(col_name.rstrip('%')) / 100)
                        _markercolor = f'rgba({r},{g},{b},{a})'
                    else:
                        _mode, _markersize, _line_width, _dash_dot = ['markers', 8, 1.5, None]
                        r, g, b, a = midrange_color(med_color=median_color,
                                                    lim_color=limit_color,
                                                    percentile=float(col_name.rstrip('%')) / 100)
                        _markercolor = f'rgba({r},{g},{b},{a})'

                    try:
                        x = float(col_name.rstrip("%")) / 100
                    except ValueError:
                        x = 'strip'
                    if isinstance(x, float):
                        if x < 0.50:
                            _markersymbol = 'triangle-down'
                        elif x > 0.50:
                            _markersymbol = 'triangle-up'
                        elif x == 0.50:
                            _markersymbol = 'circle-dot'
                    else:
                        _markersymbol = 'circle-dot'
                # else if this dataframe is unit stream format dataframe (columns = some unit stream descriptor)
                else:
                    _mode, _markersize, _line_width, _dash_dot = ['lines+markers', 10, 1.5, None]
                    r, g, b, a = midrange_color(med_color=median_color,
                                                lim_color=limit_color,
                                                percentile=0.50)
                    _markercolor = f'rgba({r},{g},{b},{a})'
                    _markersymbol = 'circle-dot'

                y_vals = [_ for _ in chart_df[col_name].values.squeeze()]

                chart_series[col_name] = go.Scattergl(
                    y=y_vals,
                    x=x_vals,
                    name=f'{chart_name} | {col_name}',
                    mode=_mode,
                    marker=dict(color=_markercolor,
                                size=_markersize,
                                symbol=_markersymbol
                                ),
                    line=dict(width=_line_width,
                              dash=_dash_dot,
                              color=_markercolor),
                    text=[f' {_:,.2f}' for idx, _ in enumerate(y_vals)],  # alternating: if np.mod(idx,2) == 0 else ''
                    textposition=['top center' if np.mod(idx, 2) == 0 else 'bottom center' for idx, _ in
                                  enumerate(y_vals)],
                    textfont_size=f_size,
                    textfont_color=_markercolor,
                    textfont_family='sans-serif'
                )

                # add the series for each col_name to the chart_data dict -->
                # keys: chart names, values: list of series (graph objects)
                chart_data[chart_name].append(chart_series[col_name])

        print(f'| chart_data keys: {[_ for _ in chart_data]} // values: {[_ for _ in chart_data.values()]}')
        print(f'| chart_coords: {chart_coords}')

        ############################## ADD CHART OBJECTS TO THE FIG ##############################
        # outside loop over columns of chart dataframes
        for idx, chart_name in enumerate(chart_data):
            row_position, col_position = chart_coords[idx]
            # list of data series for this chart
            data_series = chart_data[chart_name]
            for series in data_series:
                fig.add_trace(series, row=row_position, col=col_position)
                # update annotations (data labels with formatting) for pricing scenarios and production charts
                # non-price charts - used to choose the correct number format for data labels
                non_price_charts = [
                    'financing', 'revenue_', 'rev_k', 'taxes_', 'loe_',
                    'marketing_', 'opex_', 'capex_',
                    'ebitdax', 'fcf',
                    '_mbbl', '_mmcf', '_bbtu'
                ]

                # if this is a price chart (non-strip / series name is not in non-price charts list), label only last datapoint
                if not (any([_ in series['name'] for _ in non_price_charts])) and 'Strip' not in series['name']:
                    # only label the last price for the price scenarios
                    idx = -1
                    x = series['x'][idx]
                    y = series['y'][idx]
                    # correct number format depending on if this is a price chart or not
                    # if this is a leverage chart, make it 0.00x
                    if 'leverage' in series['name']:
                        num_format = f'{y:,.2f}x'
                    elif 'financing' in series['name']:
                        num_format = f'{y:,.0f}'
                    else:
                        num_format = f'{y:,.2f}'

                    print(f'| Price annotations: x = {x}, y = {y}')
                    fig.add_annotation(
                        x=x,
                        y=y,
                        xref="x",
                        yref="y",
                        text=num_format,
                        showarrow=True,
                        font=dict(
                            family="sans-serif",
                            size=f_size,
                            color=series['marker']['color']
                        ),
                        align="center",
                        arrowhead=None,
                        arrowsize=None,
                        arrowwidth=None,
                        arrowcolor=series['marker']['color'],
                        ax=0,
                        ay=-15,
                        bordercolor=series['marker']['color'],
                        borderwidth=1,
                        borderpad=1,
                        bgcolor='white',
                        opacity=0.9,
                        row=row_position,
                        col=col_position
                    )

                # if this series is a strip pricing scenario, or a production dataseries, and chart_months <=24, label all datapoints
                if any([_ in series['name'] for _ in ('Strip', '_mbbl', '_mmcf', '_bbtu')]) and chart_months <= 24:
                    for idx, x in enumerate(series['x']):
                        y = series['y'][idx]
                        # correct number format depending on if this is a price chart or not
                        if 'leverage' in series['name']:
                            num_format = f'{y:,.2f}x'
                        elif 'financing' in series['name']:
                            num_format = f'{y:,.0f}'
                        elif any([_ in chart_name for _ in non_price_charts]):
                            num_format = f'{y: ,.0f}'
                        # if this is a leverage chart, make it 0.00x
                        else:
                            num_format = f'{y:,.2f}'

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
                                size=f_size + 1,
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
                            row=row_position,
                            col=col_position
                        )

            # Update xaxis properties
            fig.update_xaxes(dict(title_text=chart_name,
                                  nticks=25,
                                  tickangle=-45,
                                  tickfont_size=f_size,
                                  gridcolor='rgba(175,175,175,0.75)'),
                             row=row_position,
                             col=col_position)
            # Update yaxis properties
            fig.update_yaxes(dict(title_text=[y_axis_unit if 'leverage' not in chart_name else 'x'][0],
                                  tickformat=[y_axis_tickformat if 'leverage' not in chart_name else ',.2f' + 'x'][0],
                                  nticks=20,
                                  tickfont_size=f_size,
                                  linecolor='rgba(100,100,100,0.75)',
                                  zeroline=True,
                                  zerolinecolor='rgba(80,80,80,0.75)',
                                  gridcolor='rgba(200,200,200,0.75)'),
                             row=row_position,
                             col=col_position)

    ############################## UPDATE LAYOUT, SAVE, AND SHOW ##############################
    fig.update_layout(title=figure_title,
                      plot_bgcolor='rgba(255,255,255,1.0)',
                      width=width,
                      height=height,
                      showlegend=True,
                      legend=dict(title_text=None,  # 'Percentile Outcomes',
                                  orientation='v',
                                  y=1.00,
                                  x=1.01,
                                  font_size=f_size)
                      )

    save_and_show(fig, chart_filename)


# -----------------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------# CHART REQUEST FUNCTIONS #----------------------------------------------#
# -----------------------------------------------------------------------------------------------------------------------#
"""
Note on data used for charts:
|-- 'bootstrap_prices': dataframes for each commodity price in json/xlsx. index=[0:len(model_period)], cols=price scenarios
|-- 'wi_volumes_total': WIVolume namedtuple --> SW prod for each prod stream. series index=[0:len(model_period)]
|-- 'nri_volumes_total': NRIVolume namedtuple --> SW prod for each prod stream. series index=[0:len(model_period)]
|-- 'revenue': SWRevenue namedtuple --> revenue streams in bootstrapper format. index=model_period, cols=price scenarios
|-- 'opex': SWOpex namedtuple --> cash expenses in bootstrapper format. index=model_period, cols=price scenarios
|-- 'capex': SWCapex namedtuple --> capex by category in bootstrapper format. index=model_period, cols=price scenarios
|-- 'ebitdax': SWEBITDAX namedtuple --> ebitdax in bootstrapper format. index=model_period, cols=price scenarios
|-- 'fcf': SWFreeCashFlow namedtuple --> fcf in bootstrapper format. index=model_period, cols=price scenarios
|-- 'npv_returns: SWNPVReturns namedtuple --> NPV/returns in bootstrapper format. index=npv/returns, cols=price scenarios
"""


# price charts
def build_price_charts():
    """Returns a grid of bootstrapper format price charts."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'bootstrap_prices'
    kw_list_1 = ['bootstrap_prices']
    kw_list_2 = ['wti', 'midcush_ff', 'wti_hou',
                 'hh', 'waha_gas_diff', 'hsc_gas_diff',
                 'ethane', 'propane', 'n_butane', 'iso_butane', 'nat_gasoline']
    grid_rows = 6
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [
        _ for _ in scenario_filepaths_all[data_source] if any(
            [kw in _ for kw in kw_list_1]) and any(
            [kw in _ for kw in kw_list_2])
    ]

    print(f'\n| Bootstrap prices filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [
        (_.partition('bootstrap_prices_')[2]).partition('.xlsx')[0] for _ in chart_data_filepaths if len(
            _.partition('bootstrap_prices_')[1]) > 1
    ]

    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))

    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.2f ',
                        y_axis_unit='$/unit',
                        figure_title=f'Price Decks Modeled',
                        chart_filename=chart
                        )


# revenue charts (totals)
def build_revenue_charts_totals():
    """Returns a grid of bootstrapper format revenue charts (totals)."""
    # get the chart data from the local (or network) _scenario folder
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'revenue_totals'
    kw_list_1 = ['revenue']
    kw_list_2 = ['total_all_k', 'oil_all_rev_k', 'gas_all_rev_k', 'ngl_all_rev_k']
    grid_rows = 2

    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [
        _ for _ in scenario_filepaths_all[data_source] if any(
            [kw in _ for kw in kw_list_1]) and any(
            [kw in _ for kw in kw_list_2])
    ]

    print(f'\n| Revenue (Totals) filepaths: {chart_data_filepaths}')

    # get the chart names
    chart_names = [
        (_.partition('.xlsx')[0]).partition('revenue_')[2] for _ in chart_data_filepaths
    ]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Revenue (Totals)',
                        chart_filename=chart + "_totals"
                        )


# revenue charts (detail by commodity stream)
def build_revenue_charts_detail(commodity='oil'):
    """Returns a grid of bootstrapper format revenue charts (details)."""
    # get the chart data from the local (or network) _scenario folder
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'revenue_detail'
    kw_list_1 = ['revenue']
    if commodity == 'oil':
        kw_list_2 = ['oil_all_rev_k', 'oil_midland_rev_k',
                     'oil_houston_rev_k']
        grid_rows = 2
    elif commodity == 'gas':
        kw_list_2 = ['gas_all_rev_k', 'gas_waha_rev_k',
                     'gas_hsc_rev_k']
        grid_rows = 2
    elif commodity == 'ngl':
        kw_list_2 = ['ngl_all_rev_k', 'ngl_ethane_rev_k',
                     'ngl_propane_rev_k', 'ngl_n_butane_rev_k',
                     'ngl_iso_butane_rev_k', 'ngl_nat_gasoline_rev_k'
                     ]
        grid_rows = 3

    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [
        _ for _ in scenario_filepaths_all[data_source] if any(
            [kw in _ for kw in kw_list_1]) and any(
            [kw in _ for kw in kw_list_2])
    ]

    print(f'\n| Revenue (detail) filepaths: {chart_data_filepaths}')

    # get the chart names
    chart_names = [
        (_.partition('.xlsx')[0]).partition('revenue_')[2] for _ in chart_data_filepaths
    ]

    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Revenue >> {commodity}',
                        chart_filename=chart + "_" + commodity
                        )


# EBITDAX and free cash flow charts
def build_ebitdax_fcf_charts():
    """Returns a grid of bootstrapper format EBITDAX and FCF charts (total)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'ebitdax_fcf'
    kw_list = ['ebitdax', 'fcf', 'cumulative_fcf']
    grid_rows = 2
    height = grid_rows * 625
    vert_spacing = 187.5 / height
    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| Cash flow and returns filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = kw_list
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Unhedged EBITDAX and Asset-Level FCF (EBITDAX less Capex)',
                        chart_filename=chart
                        )


# capex charts (drilling, completion, facilities only)
def build_capex_charts():
    """Returns a grid of bootstrapper format capex charts (total)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'capex'
    kw_list = ['capex_total_all_k', 'capex_drilling_all_k', 'capex_completion_all_k', 'capex_facilities_k']
    grid_rows = 2
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| Capex detail filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Capex: Drilling, Completion, Facilities, and Total',
                        chart_filename='capex'
                        )


# opex charts (totals by category: production taxes, fixed/variable LOE, reinj. gas compression, midstream/marketing)
def build_opex_charts_totals():
    """Returns a grid of bootstrapper format opex charts (totals)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'opex_totals'
    kw_list = ['opex_total_all_k', 'prod_taxes_all_k', 'loe_all_k', 'marketing_all_k']
    grid_rows = 2
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| Opex totals filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Opex: Totals',
                        chart_filename=chart
                        )


# opex charts (details by category: fixed / variable LOE (oil and water), reinjected gas compression)
def build_opex_charts_loe_detail():
    """Returns a grid of bootstrapper format opex charts (LOE details)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'loe_detail'

    kw_list = ['loe_all_k',
               'loe_fixed_k',
               'loe_oil_variable_k',
               'loe_reinj_gas_compr_k',
               'loe_water_variable_k']
    grid_rows = 3
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| Opex detail filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Opex: LOE Detail',
                        chart_filename=chart
                        )


# opex charts (details by category: midstream/marketing expenses)
def build_opex_charts_marketing_detail():
    """Returns a grid of bootstrapper format opex charts (gas midstream/marketing detail)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'marketing_detail'

    kw_list = ['marketing_all_k', 'marketing_electricity_k', 'marketing_gathering_k', 'marketing_nitrogen_k',
               'marketing_processing_k', 'marketing_sold_gas_compr_k']
    grid_rows = 3
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| Midstream detail filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'Opex: Gas Midstream / Marketing Detail',
                        chart_filename=chart
                        )


# NRI production charts (totals)
def build_nri_prod_charts_totals():
    """Returns a grid of NRI production charts (totals by stream)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'nri_prod_totals'

    kw_list_1 = ['nri_prod']
    kw_list_2 = ['oil_all_mbbl', 'gas_all_bbtu_shrunk', 'gas_all_mmcf_shrunk', 'ngl_all_mbbl']
    grid_rows = 2
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [
        _ for _ in scenario_filepaths_all[data_source] if any(
            [kw in _ for kw in kw_list_1]) and any(
            [kw in _ for kw in kw_list_2])
    ]

    print(f'\n| NRI production (totals) filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list_2 if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))

    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat=',.3f ',
                        y_axis_unit='monthly vol',
                        figure_title=f'NRI Production: Oil, Gas, NGL Totals',
                        chart_filename=chart
                        )


# NRI production charts (details by commodity stream)
def build_nri_prod_charts_detail(commodity='oil'):
    """Returns a grid of NRI production charts (detail by stream)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'nri_prod_detail'
    kw_list_1 = ['nri_prod']
    if commodity == 'oil':
        kw_list_2 = ['oil_all_mbbl', 'oil_midland_mbbl', 'oil_houston_mbbl']
        grid_rows = 2
    elif commodity == 'gas':
        kw_list_2 = ['gas_all_mmcf_shrunk', 'gas_all_bbtu_shrunk',
                     'gas_waha_mmcf_shrunk', 'gas_waha_bbtu_shrunk',
                     'gas_hsc_mmcf_shrunk', 'gas_hsc_bbtu_shrunk'
                     ]
        grid_rows = 3
    elif commodity == 'ngl':
        kw_list_2 = ['ngl_all_mbbl', 'ngl_ethane_mbbl',
                     'ngl_propane_mbbl', 'ngl_n_butane_mbbl',
                     'ngl_iso_butane_mbbl', 'ngl_nat_gasoline_mbbl'
                     ]
        grid_rows = 3

    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [
        _ for _ in scenario_filepaths_all[data_source] if any(
            [kw in _ for kw in kw_list_1]) and any(
            [kw in _ for kw in kw_list_2])
    ]

    print(f'\n| NRI production (detail) filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list_2 if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))

    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat=',.3f ',
                        y_axis_unit='monthly vol',
                        figure_title=f'NRI Production: Detail By Stream >> {commodity}',
                        chart_filename=chart + "_" + commodity
                        )


# NPV and returns table (PV-x, IRR, ROI)
def build_npv_returns_charts():
    """Returns a table of NPV / returns."""

    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'npv_returns'
    # summary stats table
    kw_list = ['npv_returns']
    grid_rows = 1
    height = grid_rows * 625
    vert_spacing = 187.5 / height

    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| NPV and returns filepaths >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = [_.partition(kw)[1] for _ in chart_data_filepaths for kw in kw_list if len(_.partition(kw)[1]) > 1]
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=1,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat=',.3f ',
                        y_axis_unit='',
                        figure_title=f'NPV and Returns',
                        chart_filename=chart
                        )


# hedge settlement charts
def build_hedge_settlement_charts(commodity='oil'):
    """Returns bootstrapper format hedging charts."""
    chart = f'hedge_settlements_{commodity}'
    return


# parentco financing cash flow / leverage charts
def build_financing_charts():
    """Returns a grid of bootstrapper format EBITDAX and FCF charts (total)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'parentco_fcf_and_credit_stats'
    kw_list = [
        'financing_parentco_ttm_ebitdax_hedged', 'financing_parentco_net_total_leverage',
        'financing_parentco_fcf_hedged', 'financing_parentco_capex',
        'financing_parentco_cash_ebitdax_hedged', 'financing_hedge_settlements_total_all_k',
        'financing_parentco_net_total_debt', 'financing_debt_1L_balance_eop',
        'financing_debt_2L_balance_eop', 'financing_bs_cash_balance_eop',
        'financing_parentco_working_cap_balance', 'financing_parentco_infra_capex',
        'financing_debt_1L_cash_expense', 'financing_debt_2L_cash_expense'
    ]

    grid_rows = 8
    height = grid_rows * 625
    vert_spacing = 187.5 / height
    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for kw in kw_list for _ in scenario_filepaths_all[data_source] if kw in _]
    print(f'\n| ParentCo FCF and Credit Stats >>>\n{chart_data_filepaths}')

    # read chart data
    chart_data = [pd.read_excel(fp) for fp in chart_data_filepaths]

    # make chart names from the filepaths
    chart_names = kw_list
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, chart_data))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'PARENTCO FREE CASH FLOW AND CREDIT STATS',
                        chart_filename=chart
                        )


def build_rolling_pv_charts():
    """Returns a grid of bootstrapper format EBITDAX and FCF charts (total)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'rolling_nav'
    kw_list = [
        'rolling_nav_TOTAL_pdp', 'rolling_nav_TOTAL_pud', 'rolling_nav_TOTAL_all',
        'pdp_rolling_pv', 'pud_rolling_pv'
    ]

    grid_rows = 8
    height = grid_rows * 625
    vert_spacing = 187.5 / height
    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for kw in kw_list for _ in scenario_filepaths_all[data_source] if kw in _]
    print(f'\n| Rolling PV-x for PDP and PUDs >>>\n{chart_data_filepaths}')

    # read chart data
    chart_data = [pd.read_excel(fp) for fp in chart_data_filepaths]

    # make chart names from the filepaths
    chart_names = kw_list
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, chart_data))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'ROLLING PV FOR PDP AND DEV PROGRAM',
                        chart_filename=chart
                        )



# parentco financing cash flow / leverage charts
# TODO: FINISH THIS DETAILED HEDGING CHART SET
def build_hedging_charts():
    """Returns a grid of bootstrapper format EBITDAX and FCF charts (total)."""
    global scenario_time_stamp
    global data_source
    global model_period
    global scenario_filepaths_all

    chart = 'hedging'
    kw_list = [
        'financing_hedge_settlements_total_all_k'
    ]
    grid_rows = 1
    height = grid_rows * 625
    vert_spacing = 187.5 / height
    # get the chart data from the local (or network) _scenario folder
    chart_data_filepaths = [_ for _ in scenario_filepaths_all[data_source] if any([kw in _ for kw in kw_list])]
    print(f'\n| PARENTCO HEDGE SETTLEMENT DETAIL >>>\n{chart_data_filepaths}')

    # make chart names from the filepaths
    chart_names = kw_list
    print(f'\n| Chart names: {chart_names}')

    # get the chart dataframes --> keys: chart_names, values: price dataframes
    chart_dfs = dict(zip(chart_names, [pd.read_excel(fp) for fp in chart_data_filepaths]))
    print(len(chart_data_filepaths), len(chart_dfs))
    print(f'\n| Chart dataframes loaded >> {chart}:\n{[_ for _ in chart_dfs.items()]}')

    # create charts
    bootstrapper_charts(chart_data_filepaths=chart_data_filepaths,
                        chart_names=chart_names,
                        chart_dfs=chart_dfs,
                        grid_rows=grid_rows,
                        grid_columns=2,
                        width=2250,
                        height=height,
                        vert_spacing=vert_spacing,
                        y_axis_tickformat='$,.1f ',
                        y_axis_unit='$ in k',
                        figure_title=f'PARENTCO HEDGE SETTLEMENTS',
                        chart_filename=chart
                        )


# ----------------------------------------------------------------------------------------------------------------------#
# ---------------------------------------------------# BUILD CHARTS #---------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------------#


def _initialize():
    # chart parameters
    global data_source
    data_source = model_control.get_data_source()

    # external variables
    # model_drivers.py
    global model_period
    model_period = model_drivers.model_period

    # model_control.py
    global scenario_time_stamp
    scenario_time_stamp = model_control.get_scenario_time_stamp()

    global scenario_filepaths_all
    scenario_filepaths_all = model_control.get_scenario_filepaths_all()
    print(f'\n| Model scenario filepaths (all):\n{scenario_filepaths_all}')

    global dash_outputs
    dash_outputs = {}


# build all charts
def run_econs_charts():
    '''Runs economics charts.'''
    # _q = input(f'\n>>> Run economics charts? Y/N ')
    _q = 'y'
    _initialize()

    if _q.lower() == 'y':
        build_price_charts()
        build_revenue_charts_totals()
        build_revenue_charts_detail(commodity='oil')
        build_revenue_charts_detail(commodity='gas')
        build_revenue_charts_detail(commodity='ngl')
        build_opex_charts_totals()
        build_opex_charts_loe_detail()
        build_capex_charts()
        build_ebitdax_fcf_charts()
        build_nri_prod_charts_totals()
        build_nri_prod_charts_detail(commodity='oil')
        build_nri_prod_charts_detail(commodity='gas')
        build_nri_prod_charts_detail(commodity='ngl')
        build_npv_returns_charts()
        build_financing_charts()
        # build_rolling_pv_charts()

    model_control.notify_complete(caller_name='bootstrapper_charts')
