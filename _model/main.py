import _model.run_model as run_model

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import pandas as pd

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__) #, external_stylesheets=external_stylesheets)

# assume a long-form df
# see https://plotly.com/python/px-arguments/ for more options

# df = pd.DataFrame({
#     "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
#     "Amount": [4, 1, 2, 2, 4, 5],
#     "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"]
# })
#
# fig = px.bar(df, x="Fruit", y="Amount", color="City", barmode="group")

# todo: write a function to read in the dash / app outputs from the model scenario folder
# todo: !!! important: do not import any of the model modules, or there is a risk that the model will re-run
#  (multiple imports of model_control.py)
# fig_list = get_dash_outputs()

# note element tags need to start with uppercase
# app.layout = html.Div(children=[
#     html.H1(children="Testing"),
#     dcc.Graph(id='example-graph',
#               figure=fig
#               ),
#     html.Div(children='''
#     This is a <div></div>
#     '''),
# ])

app_children = [
    [html.Div(children=chart_filename),
     dcc.Graph(id=chart_filename,
               figure=fig)
     ] for chart_filename, fig in fig_list.items()
                ]

app.layout = html.Div(children=[
    html.H1(children="Bootstrapper OG"),
    *[_ for nested_list in app_children for _ in nested_list],
])


if __name__ == '__main__':
    app.run_server(debug=True)