# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from drift_model import drift_tracer


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

# df = pd.read_csv('datasets/drift-trace-flip-2.csv')
df = pd.read_csv('datasets/_data_germany_useast/drift-trace-useast.csv')
local_sys = False
remote_sys = False

df['sTime'] = df['usElapsedStd'] / 1000000

tracer = drift_tracer(df, not local_sys, not remote_sys)
df_drift = tracer.calculate_drift(df)
print(df_drift)

# 1a
fig_drift_v1_4_2 = go.Figure()
fig_drift_v1_4_2.add_trace(go.Scattergl(
    name='Sample',
    mode='lines', x=df_drift['sTime'], y=df_drift['usDriftSample_v1_4_2']
))
fig_drift_v1_4_2.add_trace(go.Scattergl(
    name='EWMA',
    mode='lines', x=df_drift['sTime'], y=df_drift['usDriftEWMA_v1_4_2']
))
fig_drift_v1_4_2.update_layout(
    title='Drift Model v1.4.2',
    xaxis_title='Time, seconds (s)',
    yaxis_title='Drift, microseconds (us)',
    legend_title="Drift",
    # font=dict(
    #     family="Courier New, monospace",
    #     size=18,
    #     color="RebeccaPurple"
    # )
)

fig_drift_corrected_on_rtt = go.Figure()
fig_drift_corrected_on_rtt.add_trace(go.Scattergl(
    name='Sample',
    mode='lines', x=df_drift['sTime'], y=df_drift['usDriftSample_CorrectedOnRTT']
))
fig_drift_corrected_on_rtt.add_trace(go.Scattergl(
    name='EWMA',
    mode='lines', x=df_drift['sTime'], y=df_drift['usDriftEWMA_CorrectedOnRTT']
))
fig_drift_corrected_on_rtt.update_layout(
    title='Drift Model with Correction on RTT',
    xaxis_title='Time, seconds (s)',
    yaxis_title='Drift, microseconds (us)',
    legend_title="Drift",
    # font=dict(
    #     family="Courier New, monospace",
    #     size=18,
    #     color="RebeccaPurple"
    # )
)

# 1 b

# str_local_clock  = "SYS" if local_sys else "STD"
# str_remote_clock = "SYS" if remote_sys else "STD"

fig_drift = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    x_title='Time, seconds (s)',
    y_title='Drift, milliseconds (ms)',
    subplot_titles=('v1.4.2', 'Corrected on RTT')
)

# fig_drift.update_layout(title=f'Local {str_local_clock} Remote {str_remote_clock}')

fig_drift.add_trace(
    go.Scattergl(
        name='Sample', mode='lines',
        x=df_drift['sTime'], y=df_drift['usDriftSample_v1_4_2'] / 1000
    ),
    row=1, col=1
)
fig_drift.add_trace(
    go.Scattergl(
        name='EWMA', mode='lines',
        x=df_drift['sTime'], y=df_drift['usDriftEWMA_v1_4_2'] / 1000
    ),
    row=1, col=1
)
fig_drift.add_trace(
    go.Scattergl(
        name='Sample', mode='lines',
        x=df_drift['sTime'], y=df_drift['usDriftSample_CorrectedOnRTT'] / 1000
    ),
    row=2, col=1
)
fig_drift.add_trace(
    go.Scattergl(
        name='EWMA', mode='lines',
        x=df_drift['sTime'], y=df_drift['usDriftEWMA_CorrectedOnRTT'] / 1000
    ),
    row=2, col=1
)


fig_drift.update_layout(
    title='Drift Model',
    # xaxis_title='Time, seconds (s)',
    # yaxis_title='Drift, microseconds (us)',
    legend_title="Drift",
    # font=dict(
    #     family="Courier New, monospace",
    #     size=18,
    #     color="RebeccaPurple"
    # )
)

# 2
fig = go.Figure()
fig.add_trace(go.Scattergl(
    name='Instant',
    mode='lines', x=df['sTime'], y=df['usRTTStd'] / 1000
))
fig.add_trace(go.Scattergl(
    name='Smoothed',
    mode='lines', x=df['sTime'], y=df['usRTTStdRma'] / 1000
))
fig.update_layout(
    title="Instant vs Smoothed RTT (Steady Clocks)",
    xaxis_title="Time, seconds (s)",
    yaxis_title="RTT, milliseconds (ms)",
    # legend_title="RTT",
    # font=dict(
    #     family="Courier New, monospace",
    #     size=18,
    #     color="RebeccaPurple"
    # )
)

app.layout = html.Div([
    html.H1('Drift Tracer'),

    # dcc.Graph(
    #     id='graph-drift-v1-4-2',
    #     figure=fig_drift_v1_4_2
    # ),

    # dcc.Graph(
    #     id='graph-drift-corrected-on-rtt',
    #     figure=fig_drift_corrected_on_rtt
    # ),

    dcc.Graph(
        id='graph-drift',
        figure=fig_drift
    ),

    dcc.Graph(
        id='graph-rtt',
        figure=fig
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
