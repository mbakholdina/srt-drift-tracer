from enum import Enum, auto

import click
import pandas as pd
from pandas.tseries.offsets import SemiMonthBegin
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


pio.templates.default = "plotly_white"


MAX_TIMESTAMP = 0xFFFFFFFF  # Full 32 bit (01h11m35s)
TSBPD_WRAP_PERIOD = (30*1000000)  # 30 s
MAX_DRIFT = 5000  # 5 ms


# Clock type
class Clock(Enum):
    STD = 'Std'  # Steady (monotonic) clock
    SYS = 'Sys'  # System clock


class DriftTracer:

    def __init__(self, df, local_clock, remote_clock):
        # df - driftlog

        # TSBPD Time Base is calculated based on the very first ACK/ACKACK pair.
        # In SRT it's done based on the conclusion handshakes.
        self.tsbpd_time_base = df['usElapsed' + local_clock.value].iloc[0] \
                               - df['usAckAckTimestamp' + remote_clock.value].iloc[0]
        self.tsbpd_wrap_check = False
        # RTT Base (or RTT0) is taken as the very first RTT sample obtained
        # from the ACK/ACKACK pair. The same is done in SRT because handshake
        # based RTT is not yet implemented.
        self.rtt_base = df['usRTT' + local_clock.value].iloc[0]

        elapsed_name = 'usElapsed' + local_clock.value
        timestamp_name = 'usAckAckTimestamp' + remote_clock.value
        rtt_name = 'usRTT' + local_clock.value

        self.df = df[[elapsed_name, timestamp_name, rtt_name]]

        print('Check')
        print(self.df)

        self.df = self.df.rename(columns={
            elapsed_name : 'usElapsed',
            timestamp_name : 'usAckAckTimestamp',
            rtt_name: 'usRTT',
        })
        self.df['sElapsed'] = self.df['usElapsed'] / 1000000

        print(f'Local Clock: {local_clock.value}, Remote Clock: {remote_clock.value}')
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


    def obtain_drift_samples(self):
        # Obtain drift samples
        # TODO: Speed this up
        for i, row in self.df.iterrows():
            self.df.at[i, 'usTsbpdTimeBase'] = self.get_time_base(row['usAckAckTimestamp'])

        self.df['usDriftSample_v1_4_2'] = self.df['usElapsed'] \
                                          - (self.df['usTsbpdTimeBase'] + self.df['usAckAckTimestamp'])

        self.df['usDriftSample_AdjustedForRTT'] = self.df['usDriftSample_v1_4_2'] \
                                                  - (self.df['usRTT'] - self.rtt_base) / 2

        # EWMA is applied here instead of SRT model for simplification
        self.df['usDriftEWMA_v1_4_2'] = self.df['usDriftSample_v1_4_2'].ewm(com=7, adjust=False).mean()
        self.df['usDriftEWMA_AdjustedForRTT'] = self.df['usDriftSample_AdjustedForRTT'].ewm(com=7, adjust=False).mean()
        

    def replicate_srt_model(self):
        # Replicate SRT model

        df = pd.DataFrame(columns = ['sElapsed', 'usDrift'])
        n = int(self.df.shape[0] / 1000)

        # print(self.df.shape)
        # print(f'n: {n}')

        previous_drift = 0
        # previous_overdrift = 0

        for i in range(0, (n + 1)):
            slice = self.df.iloc[1000 * i:1000 * (i + 1), :]
            drift = slice['usDriftSample_AdjustedForRTT'].mean()

            # if (i > 318):
            #     print(slice[['sElapsed','usDriftSample_AdjustedForRTT']])
            #     print(f'drift: {drift}')
            #     print(slice['sElapsed'].iloc[0])
            #     print(slice['sElapsed'].iloc[-1])

            # if (abs(drift) > MAX_DRIFT):
            #     overdrift = - MAX_DRIFT if drift < 0 else MAX_DRIFT
            #     drift = drift - overdrift
            #     # tsbpd

            df = df.append({'sElapsed': slice['sElapsed'].iloc[0], 'usDrift': previous_drift}, ignore_index=True)
            df = df.append({'sElapsed': slice['sElapsed'].iloc[-1], 'usDrift': previous_drift}, ignore_index=True)

            previous_drift = drift
            # previous_overdrift = overdrift
            # tsbpd

        # print(f'last i = {i}')

        return df


def create_fig_drift_samples(df: pd.DataFrame):
    # df - df from drift_tracer class after obtain_drift_samples()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        x_title='Time, seconds (s)',
        y_title='Drift, milliseconds (ms)',
        subplot_titles=('v1.4.2', 'Adjusted on RTT')
    )

    fig.add_trace(go.Scattergl(
        name='Sample', mode='lines',
        x=df['sElapsed'], y=df['usDriftSample_v1_4_2'] / 1000
    ), row=1, col=1 )
    fig.add_trace(go.Scattergl(
        name='EWMA', mode='lines',
        x=df['sElapsed'], y=df['usDriftEWMA_v1_4_2'] / 1000
    ), row=1, col=1 )
    fig.add_trace(go.Scattergl(
        name='Sample', mode='lines',
        x=df['sElapsed'], y=df['usDriftSample_AdjustedForRTT'] / 1000
    ), row=2, col=1 )
    fig.add_trace(go.Scattergl(
        name='EWMA', mode='lines',
        x=df['sElapsed'], y=df['usDriftEWMA_AdjustedForRTT'] / 1000
    ), row=2, col=1 )

    fig.update_layout(
        title='Drift Samples',
        legend_title="Drift",
        # font=dict(
        #     family="Courier New, monospace",
        #     size=18,
        #     color="RebeccaPurple"
        # )
    )

    return fig


def create_fig_rtt(df: pd.DataFrame):
    # df - driftlog

    df['sTimeStd'] = df['usElapsedStd'] / 1000000

    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        name='Instant',
        mode='lines', x=df['sTimeStd'], y=df['usRTTStd'] / 1000
    ))
    fig.add_trace(go.Scattergl(
        name='Smoothed',
        mode='lines', x=df['sTimeStd'], y=df['usSmoothedRTTStd'] / 1000
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
    
    return fig


def create_fig_srt_model(df_drift_samples: pd.DataFrame, df_srt_model: pd.DataFrame):
    # df_drift_samples - df from drift_tracer class after obtain_drift_samples()
    # df_srt_model - df from drift_tracer class after replicate_srt_model()

    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        name='Drift Samples',
        mode='lines', x=df_drift_samples['sElapsed'], y=df_drift_samples['usDriftSample_AdjustedForRTT'] / 1000
    ))
    fig.add_trace(go.Scattergl(
        name='Drift (SRT Model)',
        mode='lines', x=df_srt_model['sElapsed'], y=df_srt_model['usDrift'] / 1000
    ))
    fig.update_layout(
        title="Drift Samples (Adjusted on RTT) vs Drift (SRT Model)",
        xaxis_title="Time, seconds (s)",
        yaxis_title="Drift, milliseconds (ms)",
        # legend_title="RTT",
        # font=dict(
        #     family="Courier New, monospace",
        #     size=18,
        #     color="RebeccaPurple"
        # )
    )
    
    return fig


def print_drift_samples_statistics(df: pd.DataFrame, colname: str):
    # df - drift_samples

    total_drift = (df[colname].iloc[-1] - df[colname].iloc[0]) / 1000
    time_elapsed = df['sElapsed'].iloc[-1] - df['sElapsed'].iloc[0]
    drift_rate = round(total_drift / time_elapsed, 3)
    total_drift = round(total_drift, 2)
    time_elapsed = round(time_elapsed, 2)

    mean = round(df[colname].mean() / 1000, 2)
    std = round(df[colname].std() / 1000, 2)
    min = round(df[colname].min() / 1000, 2)
    max = round(df[colname].max() / 1000, 2)

    if (colname == 'usDriftSample_AdjustedForRTT'):
        print('Drift samples adjusted on RTT')

    if (colname == 'usDriftSample_v1_4_2'):
        print('Drift samples v1.4.2')

    print(f"Offset mean, ms:            {mean}")
    print(f"Offset std, ms:             {std}")
    print(f"Offset min, ms:             {min}")
    print(f"Offset max, ms:             {max}")
    print(f'Total Drift, ms:            {total_drift}')
    print(f'Average Drift Rate, ms/s:   {drift_rate}')
    print("")

    print(mean)
    print(std)
    print(min)
    print(max)
    print(total_drift)
    print(drift_rate)
    print("")


def print_rtt_statistics(df: pd.DataFrame):
    # df - driftlog
    df['Instant RTT, ms'] = df['usRTTStd'] / 1000
    df['Smoothed RTT, ms'] = df['usSmoothedRTTStd'] / 1000

    print(df[['Instant RTT, ms', 'Smoothed RTT, ms']].describe())
    print("")

    instant = df['Instant RTT, ms']
    smoothed = df['Smoothed RTT, ms']

    print("Instant RTT")
    print(round(instant.mean(), 2))
    print(round(instant.std(), 2))
    print(round(instant.min(), 2))
    print(round(instant.max(), 2))
    print("")

    print("Smoothed RTT")
    print(round(smoothed.mean(), 2))
    print(round(smoothed.std(), 2))
    print(round(smoothed.min(), 2))
    print(round(smoothed.max(), 2))
    print("")


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
    local_clock = Clock.SYS if local_sys else Clock.STD
    remote_clock = Clock.SYS if remote_sys else Clock.STD

    df_driftlog  = pd.read_csv(filepath)
    print('Data from Log')
    print(df_driftlog)

    tracer = DriftTracer(df_driftlog, local_clock, remote_clock)
    tracer.obtain_drift_samples()
    drift_samples = tracer.df
    print('Drift Samples')
    print(drift_samples)

    print_drift_samples_statistics(drift_samples, 'usDriftSample_v1_4_2')
    print_drift_samples_statistics(drift_samples, 'usDriftSample_AdjustedForRTT')
    print_rtt_statistics(df_driftlog)
    
    df_srt_model = tracer.replicate_srt_model()
    print('SRT Model')
    print(df_srt_model)

    fig_1 = create_fig_drift_samples(drift_samples)
    fig_1.show()

    fig_2 = create_fig_rtt(df_driftlog)
    fig_2.show()

    fig_3 = create_fig_srt_model(drift_samples, df_srt_model)
    fig_3.show()


if __name__ == '__main__':
    main()
