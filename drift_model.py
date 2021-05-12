import click
import pandas as pd
import pathlib
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


pio.templates.default = "plotly_white"


MAX_TIMESTAMP = 0xFFFFFFFF # Full 32 bit (01h11m35s)
TSBPD_WRAP_PERIOD = (30*1000000)


class drift_tracer:

    def __init__(self, df, is_local_clock_std, is_remote_clock_std):
        self.local_clock_suffix  = 'Std' if is_local_clock_std else 'Sys'
        self.remote_clock_suffix = 'Std' if is_remote_clock_std else 'Sys'
        self.rtt_clock_suffix    = 'Std' if is_local_clock_std else 'Sys'

        us_elapsed = df['usElapsed' + self.local_clock_suffix].iloc[0]
        us_ackack_timestamp = df['usAckAckTimestamp' + self.remote_clock_suffix].iloc[0]
        self.tsbpd_base = us_elapsed - us_ackack_timestamp
        self.rtt_base = df['usRTT' + self.rtt_clock_suffix].iloc[0]
        self.tsbpd_wrap_check = False

        print(f'Local Clock: {self.local_clock_suffix}, Remote Clock: {self.remote_clock_suffix}')
        print(f'TSBPD Time Base: {self.tsbpd_base}')
        print(f'RTT Base (RTT_0): {self.rtt_base}')


    def get_time_base(self, timestamp_us):
        carryover = 0

        if (self.tsbpd_wrap_check):
            if (timestamp_us < TSBPD_WRAP_PERIOD):
                carryover = MAX_TIMESTAMP + 1
            elif ((timestamp_us >= TSBPD_WRAP_PERIOD) and (timestamp_us <= (TSBPD_WRAP_PERIOD * 2))):
                self.tsbpd_wrap_check = False
                self.tsbpd_base += MAX_TIMESTAMP + 1
        elif (timestamp_us > (MAX_TIMESTAMP - TSBPD_WRAP_PERIOD)):
            self.tsbpd_wrap_check = True

        return (self.tsbpd_base + carryover)


    def calculate_drift(self, df):
        elapsed_name = 'usElapsed' + self.local_clock_suffix
        timestamp_name = 'usAckAckTimestamp' + self.remote_clock_suffix
        rtt_name = 'usRTT' + self.rtt_clock_suffix

        df_drift = df[[elapsed_name, timestamp_name, rtt_name, 'usDriftSampleStd']]
        df_drift = df_drift.rename(columns={
            elapsed_name : 'usElapsed',
            timestamp_name : 'usAckAckTimestamp',
            rtt_name: 'usRTT',
            'usDriftSampleStd' : 'usDriftSampleLog'
        })
        df_drift['sTime'] = df_drift['usElapsed'] / 1000000

        df_drift['usRTTCorrection'] = (df_drift['usRTT'] - self.rtt_base) / 2

        for i, row in df_drift.iterrows():
            df_drift.at[i, 'usDriftSample_v1_4_2'] = row['usElapsed'] \
                                                    - (self.get_time_base(row['usAckAckTimestamp']) + row['usAckAckTimestamp'])

        df_drift['usDriftSample_CorrectedOnRTT'] = df_drift['usDriftSample_v1_4_2'] - df_drift['usRTTCorrection']

        # EWMA is applied here instead of SRT model for simplification
        df_drift['usDriftEWMA_v1_4_2'] = df_drift['usDriftSample_v1_4_2'].ewm(com=7, adjust=False).mean()
        df_drift['usDriftEWMA_CorrectedOnRTT'] = df_drift['usDriftSample_CorrectedOnRTT'].ewm(com=7, adjust=False).mean()
        return df_drift


def create_fig_drift(df: pd.DataFrame):
    # df_drift

    # str_local_clock  = "SYS" if local_sys else "STD"
    # str_remote_clock = "SYS" if remote_sys else "STD"

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        x_title='Time, seconds (s)',
        y_title='Drift, milliseconds (ms)',
        subplot_titles=('v1.4.2', 'Corrected on RTT')
    )

    # fig_drift.update_layout(title=f'Local {str_local_clock} Remote {str_remote_clock}')

    fig.add_trace(
        go.Scattergl(
            name='Sample', mode='lines',
            x=df['sTime'], y=df['usDriftSample_v1_4_2'] / 1000
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scattergl(
            name='EWMA', mode='lines',
            x=df['sTime'], y=df['usDriftEWMA_v1_4_2'] / 1000
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scattergl(
            name='Sample', mode='lines',
            x=df['sTime'], y=df['usDriftSample_CorrectedOnRTT'] / 1000
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scattergl(
            name='EWMA', mode='lines',
            x=df['sTime'], y=df['usDriftEWMA_CorrectedOnRTT'] / 1000
        ),
        row=2, col=1
    )

    fig.update_layout(
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

    return fig


@click.command()
@click.argument(
    'filepath',
    type=click.Path(exists=True)
)
@click.option(
    '--local-sys',
    is_flag=True,
    default=False,
    help=   'Take local SYS clock.',
    show_default=True
)
@click.option(
    '--remote-sys',
    is_flag=True,
    default=False,
    help=   'Take remote SYS clock.',
    show_default=True
)
def main(filepath, local_sys, remote_sys):
    
    df_driftlog  = pd.read_csv(filepath)
    print(df_driftlog)

    tracer = drift_tracer(df_driftlog, not local_sys, not remote_sys)
    df_drift = tracer.calculate_drift(df_driftlog)
    print(df_drift)

    df_driftlog['sTime'] = df_driftlog['usElapsedStd'] / 1000000

    fig = create_fig_drift(df_drift)
    fig.show()


if __name__ == '__main__':
    main()
