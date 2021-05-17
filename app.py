# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import base64
import datetime
import io

import dash
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import dash_html_components as html
import pandas as pd

from drift_model import create_fig_rtt, drift_tracer, create_fig_drift


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


app.layout = html.Div([
    html.H1('Drift Tracer'),

    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),

    html.Div(id='output-graphs'),
])


def parse_contents(contents, filename, date):
    # Decode contents
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        # elif 'xls' in filename:
        #     # Assume that the user uploaded an excel file
        #     df = pd.read_excel(io.BytesIO(decoded))
    except Exception as e:
        print(e)
        return html.Div([
            'There was an error while processing this file.'
        ])

    # Build figures
    local_sys = False
    remote_sys = False

    tracer = drift_tracer(df, not local_sys, not remote_sys)
    tracer.calculate_drift()
    fig_drift = create_fig_drift(tracer.df)

    fig_rtt = create_fig_rtt(df)

    return html.Div([
        html.H5(filename),
        html.H6(datetime.datetime.fromtimestamp(date)),

        dcc.Graph(
            id='graph-drift',
            figure=fig_drift
        ),

        dcc.Graph(
            id='graph-rtt',
            figure=fig_rtt
        ),

        html.Hr(),  # horizontal line
    ])


@app.callback(
    Output('output-graphs', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified')
)
def update_output_graphs(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        children = [
            parse_contents(c, n, d) for c, n, d in
            zip(list_of_contents, list_of_names, list_of_dates)
        ]
        return children


if __name__ == '__main__':
    app.run_server(debug=True)
