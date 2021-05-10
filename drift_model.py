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
        # Stopped here
        df_drift = df_drift.rename(columns={elapsed_name : "usElapsed", timestamp_name : "usAckAckTimestamp", 'usDriftSampleStd' : 'usDriftSample'})
        df_drift['sTime'] = df_drift['usElapsed'] / 1000000

        for i, row in df_drift.iterrows():
            rtt_correction = (row[rtt_name] - self.rtt_base) / 2;
            #print(f'RTT correction: {rtt_correction}')
            df_drift.at[i, 'usDriftSample'] = row['usElapsed'] - (self.get_time_base(row['usAckAckTimestamp']) + row['usAckAckTimestamp']) - rtt_correction

        df_drift['usDriftRMA'] = df_drift['usDriftSample'].ewm(com=7, adjust=False).mean()
        return df_drift


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

    str_local_clock  = "SYS" if local_sys else "STD"
    str_remote_clock = "SYS" if remote_sys else "STD"
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    fig.update_layout(title=f'Local {str_local_clock} Remote {str_remote_clock}')
    fig.add_trace(go.Scatter(x=df_drift['sTime'], y=df_drift['usDriftSample'],
                    mode='lines+markers',
                    name='Drift Sample, us'),
                    row=1, col=1)

    fig.add_trace(go.Scatter(x=df_drift['sTime'], y=df_drift['usDriftRMA'],
                    mode='lines+markers',
                    name='Drift RMA, us'),
                    row=1, col=1)

    fig.add_trace(go.Scatter(x=df_driftlog['sTime'], y=df_driftlog['usRTTStd'],
                    mode='lines+markers',
                    name='Instant RTT steady, us'),
                    row=2, col=1)

    fig.add_trace(go.Scatter(x=df_driftlog['sTime'], y=df_driftlog['usRTTStdRma'],
                    mode='lines+markers',
                    name='RTT RMA steady, us'),
                    row=2, col=1)

    fig.show()


if __name__ == '__main__':
    main()
