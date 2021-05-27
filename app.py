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

from drift_model import Clock, create_fig_drift_samples, create_fig_rtt, create_fig_srt_model, DriftTracer


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
            'width': '98%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=True  # Allow multiple files to be uploaded
    ),

    html.Div([
        "Local Clock Type",
        dcc.RadioItems(
            id='local-clock',
            options=[{'label': i, 'value': i} for i in [member.value for member in list(Clock)]],
            value=Clock.STD.value,
            labelStyle={'display': 'inline-block'}
        )],
        style={
            'width': '98%',
            'textAlign': 'left',
            'display': 'inline-block',
            'margin': '10px'
        }
    ),

    html.Div([
        "Remote Clock Type",
        dcc.RadioItems(
            id='remote-clock',
            options=[{'label': i, 'value': i} for i in [member.value for member in list(Clock)]],
            value=Clock.STD.value,
            labelStyle={'display': 'inline-block'}
        )],
        style={
            'width': '98%',
            'textAlign': 'left',
            'display': 'inline-block',
            'margin': '10px'
        }
    ),

    html.Div(id='output-graphs'),
])


def parse_contents(contents, filename, date, local_clock, remote_clock):
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
    tracer = DriftTracer(df, local_clock, remote_clock)
    tracer.obtain_drift_samples()
    df_srt_model = tracer.replicate_srt_model()

    fig_drift_samples = create_fig_drift_samples(tracer.df)
    fig_rtt = create_fig_rtt(df)
    fig_srt_model = create_fig_srt_model(tracer.df, df_srt_model)

    return html.Div([
        html.H5(filename),
        html.H6(datetime.datetime.fromtimestamp(date)),

        dcc.Graph(
            id='graph-drift-samples',
            figure=fig_drift_samples
        ),

        dcc.Graph(
            id='graph-rtt',
            figure=fig_rtt
        ),

        dcc.Graph(
            id='graph-srt-model',
            figure=fig_srt_model
        ),

        html.Hr(),  # horizontal line
    ])


@app.callback(
    Output('output-graphs', 'children'),
    Input('upload-data', 'contents'),
    Input('local-clock', 'value'),
    Input('remote-clock', 'value'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified')
)
def update_graphs(contents, local_clock, remote_clock, names, dates):
    local_clock = Clock.STD if local_clock == Clock.STD.value else Clock.SYS
    remote_clock = Clock.STD if remote_clock == Clock.STD.value else Clock.SYS

    if contents is not None:
        children = [
            parse_contents(c, n, d, local_clock, remote_clock) for c, n, d in
            zip(contents, names, dates)
        ]
        return children


if __name__ == '__main__':
    app.run_server(debug=True)
