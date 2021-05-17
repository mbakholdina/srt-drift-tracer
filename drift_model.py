import click
import pandas as pd
import pathlib
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


pio.templates.default = "plotly_white"


MAX_TIMESTAMP = 0xFFFFFFFF  # Full 32 bit (01h11m35s)
TSBPD_WRAP_PERIOD = (30*1000000)  # 30 s
MAX_DRIFT = 5000  # 5 ms


class drift_tracer:

    def __init__(self, df, is_local_clock_std, is_remote_clock_std):
        self.local_clock_suffix  = 'Std' if is_local_clock_std else 'Sys'
        self.remote_clock_suffix = 'Std' if is_remote_clock_std else 'Sys'
        self.rtt_clock_suffix    = self.local_clock_suffix

        # TSBPD Time Base is calculated based on the very first ACK/ACKACK pair.
        # In SRT it's done based on the conclusion handshakes.
        self.tsbpd_time_base = df['usElapsed' + self.local_clock_suffix].iloc[0] \
                               - df['usAckAckTimestamp' + self.remote_clock_suffix].iloc[0]
        self.tsbpd_wrap_check = False
        # RTT Base (or RTT0) is taken as the very first RTT sample obtained
        # from the ACK/ACKACK pair. The same is done in SRT because handshake
        # based RTT is not yet implemented.
        self.rtt_base = df['usRTT' + self.rtt_clock_suffix].iloc[0]

        elapsed_name = 'usElapsed' + self.local_clock_suffix
        timestamp_name = 'usAckAckTimestamp' + self.remote_clock_suffix
        rtt_name = 'usRTT' + self.rtt_clock_suffix

        self.df = df[[elapsed_name, timestamp_name, rtt_name]]
        self.df = self.df.rename(columns={
            elapsed_name : 'usElapsed',
            timestamp_name : 'usAckAckTimestamp',
            rtt_name: 'usRTT',
        })
        self.df['sTime'] = self.df['usElapsed'] / 1000000

        print(f'Local Clock: {self.local_clock_suffix}, Remote Clock: {self.remote_clock_suffix}')
        print(f'TSBPD Time Base: {self.tsbpd_time_base}')
        print(f'RTT Base (RTT0): {self.rtt_base}')
        print(f'Dataframe: \n {self.df}')


    def get_time_base(self, timestamp_us):
        carryover = 0

        if (self.tsbpd_wrap_check):
            if (timestamp_us < TSBPD_WRAP_PERIOD):
                carryover = MAX_TIMESTAMP + 1
            elif ((timestamp_us >= TSBPD_WRAP_PERIOD) and (timestamp_us <= (TSBPD_WRAP_PERIOD * 2))):
                self.tsbpd_wrap_check = False
                self.tsbpd_time_base += MAX_TIMESTAMP + 1
        elif (timestamp_us > (MAX_TIMESTAMP - TSBPD_WRAP_PERIOD)):
            self.tsbpd_wrap_check = True

        return (self.tsbpd_time_base + carryover)


    def calculate_drift(self):

        for i, row in self.df.iterrows():
            self.df.at[i, 'TsbpdTimeBase'] = self.get_time_base(row['usAckAckTimestamp'])

        self.df['usDriftSample_v1_4_2'] = self.df['usElapsed'] \
                                          - (self.df['TsbpdTimeBase'] + self.df['usAckAckTimestamp'])

        self.df['usDriftSample_AdjustedForRTT'] = self.df['usDriftSample_v1_4_2'] \
                                                  - (self.df['usRTT'] - self.rtt_base) / 2

        # EWMA is applied here instead of SRT model for simplification
        self.df['usDriftEWMA_v1_4_2'] = self.df['usDriftSample_v1_4_2'].ewm(com=7, adjust=False).mean()
        self.df['usDriftEWMA_AdjustedForRTT'] = self.df['usDriftSample_AdjustedForRTT'].ewm(com=7, adjust=False).mean()
        

    def replicate_srt_model(self):
        # Replicate SRT model

        # df_drift = pd.DataFrame(columns = ['sTime', 'usTsbpdTimeBase', 'usDrift', 'usOverdrift'])

        # print(self.df.shape)

        # n = int(self.df.shape[0] / 1000)
        # print(n)

        # drift = 0
        # overdrift = 0

        # previous_drift = 0
        # previous_overdrift = 0

        # for i in range(0, n):
        #     slice = self.df.iloc[1000 * i:1000 * (i + 1),:]

        #     if (i < 5 | i > 315):
        #         print(slice)

        #     drift = slice['usDriftSample_AdjustedForRTT'].mean()
        #     if (abs(drift) > MAX_DRIFT):
        #         overdrift = - MAX_DRIFT if drift < 0 else MAX_DRIFT
        #         drift = drift - overdrift
        #         # tsbpd

        #     # ??? get_time_base
        #     drift.append([slice['sTime'].iloc[0], self.tsbpd_time_base, previous_drift, previous_overdrift])
        #     drift.append([slice['sTime'].iloc[-1], self.tsbpd_time_base, previous_drift, previous_overdrift])

        #     previous_drift = drift
        #     previous_overdrift = overdrift
        #     # tsbpd
        pass


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
            x=df['sTime'], y=df['usDriftSample_AdjustedForRTT'] / 1000
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scattergl(
            name='EWMA', mode='lines',
            x=df['sTime'], y=df['usDriftEWMA_AdjustedForRTT'] / 1000
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
    tracer.calculate_drift()
    print(tracer.df)

    df_driftlog['sTime'] = df_driftlog['usElapsedStd'] / 1000000

    fig = create_fig_drift(tracer.df)
    fig.show()


if __name__ == '__main__':
    main()
