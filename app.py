# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

df = pd.read_csv('datasets/drift-trace-flop-2.csv')

df['sTime'] = df['usElapsedStd'] / 1000000

# 1
# fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
# fig.update_layout(title=f'Local {str_local_clock} Remote {str_remote_clock}')
# fig.add_trace(go.Scatter(x=df_drift['sTime'], y=df_drift['usDriftSample'],
#                 mode='lines+markers',
#                 name='Drift Sample, us'),
#                 row=1, col=1)

# fig.add_trace(go.Scatter(x=df_drift['sTime'], y=df_drift['usDriftRMA'],
#                 mode='lines+markers',
#                 name='Drift RMA, us'),
#                 row=1, col=1)

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

    dcc.Graph(
        id='graph-rtt',
        figure=fig
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
