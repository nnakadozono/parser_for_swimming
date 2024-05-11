import os
import shutil
import json
import numpy as np
import pandas as pd

def df_from_dictionary(dictionary, parse_dates=[], index_col=None, value_name=None, sort_index=True):
    df = pd.DataFrame(dictionary)
    for key in parse_dates:
        df[key] = pd.to_datetime(df[key])
    if index_col is not None:
        df.set_index(index_col, drop=False, inplace=True)
        if sort_index:
            df.sort_index(inplace=True)
    if value_name is not None:
        if 'value' in df.columns:
            df.rename(columns={'value': value_name}, inplace=True)
    return df

def create_swimmingData(zipfilename):
    zipfilename = os.path.expanduser(zipfilename)
    filename = zipfilename.replace('.zip', '.json')
    mydir = os.path.dirname(zipfilename)

    shutil.unpack_archive(zipfilename, mydir)
    with open(filename) as f:
        swimmingData = json.load(f)

    workoutSummary = df_from_dictionary(swimmingData["workoutSummary"], parse_dates=['startDate', 'endDate'], index_col='startDate')
    workoutEventSegment = df_from_dictionary(swimmingData["workoutEventSegment"], parse_dates=['start', 'end'], index_col='start')
    workoutEventLap = df_from_dictionary(swimmingData["workoutEventLap"], parse_dates=['start', 'end'], index_col='start')

    distanceSwimming = df_from_dictionary(swimmingData["distanceSwimming"], parse_dates=['startDate', 'endDate'], index_col='startDate', value_name='distanceSwimming')
    heartRate = df_from_dictionary(swimmingData["heartRate"], parse_dates=['startDate', 'endDate'], index_col='startDate', value_name='heartRate')
    swimmingStrokeCount = df_from_dictionary(swimmingData["swimmingStrokeCount"], parse_dates=['startDate', 'endDate'], index_col='startDate', value_name='swimmingStrokeCount')

    return {
        'workoutSummary': workoutSummary,
        'workoutEventSegment': workoutEventSegment,
        'workoutEventLap': workoutEventLap,
        'distanceSwimming': distanceSwimming,
        'heartRate': heartRate,
        'swimmingStrokeCount': swimmingStrokeCount
    }


def style(x):
    if x == 0: return '??'
    elif x == 1: return 'Mixed'
    elif x == 2: return 'Fr'
    elif x == 3: return 'Bc'
    elif x == 4: return 'Br'
    elif x == 5: return 'Fly'
    elif x == 6: return 'Kick'

def get_heart_rate(lap, heart):
    return heart.loc[lap.startDate : lap.endDate]['heartRate'].mean()

def format_time(x):
    if x == pd.Timedelta(seconds=0):
        return ""
    else:
        return f"{x.components.minutes:02}:{x.components.seconds:02}"

def format_lap(x):
    if x == pd.Timedelta(seconds=0):
        return ""
    else:
        return f"{x.components.minutes:01}'{x.components.seconds:02}''"  

def create_laps(swimmingData, date):
    workoutSummary = swimmingData["workoutSummary"]
    workoutEventSegment = swimmingData["workoutEventSegment"]
    workoutEventLap = swimmingData["workoutEventLap"]
    distanceSwimming = swimmingData["distanceSwimming"]
    heartRate = swimmingData["heartRate"]
    swimmingStrokeCount = swimmingData["swimmingStrokeCount"]

    workout = workoutSummary.loc[date].iloc[0]
    startWorkout = workout.startDate
    endWorkout = workout.endDate
    lapLength = workout.HKLapLength
    totalDistance = workout.DistanceSwimming_sum

    print(f'Start: {startWorkout}')
    print(f'End  : {endWorkout}')
    print(f'Distance: {totalDistance}m')
    print(f'Pool length: {lapLength}m')

    laps = workoutEventLap.merge(distanceSwimming.loc[startWorkout:endWorkout], left_index=True, right_index=True)
    laps = laps.merge(swimmingStrokeCount.loc[startWorkout:endWorkout], left_index=True, right_index=True, suffixes=('', '_y'))
    heart = heartRate.loc[startWorkout:endWorkout].copy(deep=True)

    laps.sort_index(inplace=True)
    laps['duration'] = laps['endDate'] - laps['startDate']

    laps['nextStartDate'] = laps['startDate'].shift(-1)
    first, last = laps.index[0], laps.index[-1]
    startTimestamp = startWorkout
    # startTimestamp = laps.loc[first, 'startDate']
    endTimestamp = laps.loc[last, 'endDate']
    laps.loc[last, 'nextStartDate'] = endTimestamp

    laps['durationWithRest'] = laps['nextStartDate'] - laps['startDate']
    laps['rest'] = laps['durationWithRest'] - laps['duration']
    laps['distance'] = laps['distanceSwimming'].cumsum()
    laps['time'] = laps['endDate'] - startTimestamp

    laps['style'] = laps['HKSwimmingStrokeStyle'].apply(style)
    laps['heartRate'] = laps.apply(get_heart_rate, axis=1, args=(heart,))
    
    laps['segment'] = np.nan
    for i, (idx, segment) in enumerate(workoutEventSegment.loc[startWorkout:endWorkout].iterrows()):
        s = segment.start
        e = segment.end
        laps.loc[s:e, 'segment'] = i

    cond_continue = (laps['rest'].dt.total_seconds() < 10)
    laps['durationAgg'] = np.where(cond_continue, laps['durationWithRest'], laps['duration'])
    laps['restAgg'] = pd.to_timedelta(np.where(cond_continue, pd.Timedelta(seconds=0), laps['rest']))
    laps['timeAgg'] = np.where(cond_continue, laps['nextStartDate'] - startTimestamp, laps['endDate'] - startTimestamp)
    laps.loc[first, 'durationAgg'] = laps.loc[first, 'timeAgg'] # For some reasons, the first duration doesn't match with Workout app
    # colSimpleAgg = ['distance', 'timeAgg', 'durationAgg', 'restAgg', ]
    # laps[colSimpleAgg]
       
    laps[['timeAgg_fmt']] = laps[['timeAgg']].map(format_time)
    laps[['durationAgg_fmt', 'restAgg_fmt']] = laps[['durationAgg', 'restAgg']].map(format_lap)

    laps['group100'] = (laps['distance'] // lapLength + (100/lapLength - 1)) // (100/lapLength)
    laps['group50'] = (laps['distance'] // lapLength + (50/lapLength - 1)) // (50/lapLength)
    if lapLength == 25:
        laps['group25'] = (laps['distance'] // lapLength + (25/lapLength - 1)) // (25/lapLength)


    return laps.copy(deep=True)    

def agg_style(s):
    styles = list(s.unique())
    if len(styles) == 1:
        return styles[0]
    else: 
        return 'Mixed'

def create_lap_groups(laps, by):
    grouped_laps = laps.groupby(by)[
            ['distance', 'style', 'timeAgg', 'durationAgg', 'swimmingStrokeCount', 'heartRate',  'restAgg', 'segment']
        ].agg({
            'distance': 'last', 'style': agg_style, 
            'timeAgg': 'last', 'durationAgg': 'sum', 
            'swimmingStrokeCount': 'sum', 
            'heartRate': 'mean', 'restAgg': 'sum',
            'segment': 'last'
        })
    grouped_laps[['timeAgg_fmt']] = grouped_laps[['timeAgg']].map(format_time)
    grouped_laps[['durationAgg_fmt', 'restAgg_fmt']] = grouped_laps[['durationAgg', 'restAgg']].map(format_lap)
    grouped_laps.set_index('distance', inplace=True)
    return grouped_laps

def create_segments(laps):
    by = 'segment'
    grouped_laps = laps.groupby(by)\
        .agg({
            'distanceSwimming':'sum', 
            'style': agg_style, 
            'timeAgg': 'last', 'durationAgg': 'sum', 
            'swimmingStrokeCount': 'sum', 
            'heartRate': 'mean', 'restAgg': 'sum',
        })
    grouped_laps['pace'] = grouped_laps['durationAgg']/(grouped_laps['distanceSwimming']/100)
    grouped_laps['swimmingStrokeCount'] = grouped_laps['swimmingStrokeCount']/(grouped_laps['distanceSwimming']/100)
    grouped_laps[['timeAgg_fmt']] = grouped_laps[['timeAgg']].map(format_time)
    grouped_laps[['durationAgg_fmt', 'pace_fmt', 'restAgg_fmt']] = grouped_laps[['durationAgg', 'pace', 'restAgg']].map(format_lap)

    return grouped_laps

col_laps_n = ['style', 'timeAgg_fmt', 'durationAgg_fmt', 'swimmingStrokeCount', 'heartRate', 'restAgg_fmt', 'segment']
col_laps = ['distance'] + col_laps_n 
col_segments = ['distanceSwimming', 'style', 'timeAgg_fmt', 'durationAgg_fmt', 'pace_fmt', 'swimmingStrokeCount', 'heartRate', 'restAgg_fmt']
col_rename = {
    # 'distance': 'distance', 
    'style': 'style', 
    'timeAgg_fmt': 'time', 
    'durationAgg_fmt': 'lap', 
    'swimmingStrokeCount': 'count', 
    'heartRate': 'HR', 
    'restAgg_fmt': 'rest',
    'segment': 'segment',
    'distanceSwimming': 'distance',
    'pace_fmt': 'pace'
}
# pd.set_option('display.float_format', lambda x: '%.0f' % x)