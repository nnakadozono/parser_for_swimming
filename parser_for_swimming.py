import sys, os
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


def get_et_root(exportFilename='export.xml'):
    tree = ET.parse(exportFilename)
    return tree.getroot()


def get_record_by_type(root, type):
    records = []
    for record in root.findall(f"Record[@type='{type}']"):
        #print(ET.dump(distanceSwimming))
        records.append(record)

    dicts = []
    for record in records:
        recordDict = {}
        for k, v in record.attrib.items():
            recordDict[k] = v
        dicts.append(recordDict)
    df = pd.DataFrame(dicts)
    timeColumns = ['creationDate', 'startDate', 'endDate']
    for timeColumn in timeColumns:
        df[timeColumn] = pd.to_datetime(df[timeColumn])
    df['value'] = pd.to_numeric(df['value'])
    df.set_index('startDate', inplace=True, drop=False)
    
    return df


def get_workout_tags(root):
    workoutTags = []
    for workoutTag in root.findall('Workout'):
        #print(workout.tag)
        if workoutTag.attrib['workoutActivityType'] == 'HKWorkoutActivityTypeSwimming':
            workoutTags.append(workoutTag)
    return workoutTags


def get_workout_summary(workoutTags):
    dicts = []
    for workoutTag in workoutTags:
        recordDict = {}
        for k, v in workoutTag.attrib.items():
            recordDict[k] = v

        for child in workoutTag.findall('WorkoutStatistics'):
            type = child.attrib['type'].replace('HKQuantityTypeIdentifier', '')
            for k, v in child.attrib.items():
                if k in ['type', 'creationDate', 'startDate', 'endDate']: continue
                if k in ['sum', 'average', 'minumum', 'maximum']:
                    v = float(v)
                recordDict[f"{type}_{k}"] = v

        for child in workoutTag.findall('MetadataEntry'):
            k, v = child.attrib['key'], child.attrib['value']
            recordDict[k] = v

        dicts.append(recordDict)

    df = pd.DataFrame(dicts)
    timeColumns = ['creationDate', 'startDate', 'endDate']
    for col in timeColumns:
        df[col] = pd.to_datetime(df[col])
    numericColumns = ['duration', ]
    for col in numericColumns:
        df[col] = pd.to_numeric(df[col])

    # df.set_index('creationDate', inplace=True)
    # df.index = df['startDate'].dt.date
    df.set_index('startDate', inplace=True)

    return df
    

def get_workout_event_segment(workoutTags):
    dicts = []
    for workoutTag in workoutTags:
        for child in workoutTag.findall("WorkoutEvent[@type='HKWorkoutEventTypeSegment']"):
            recordDict = {}
            for k, v in child.attrib.items():
                if k in ['type']: continue
                recordDict[k] = v

                for entry in child.findall('MetadataEntry'):
                    k, v = entry.attrib['key'], entry.attrib['value']
                    recordDict[k] = v

            dicts.append(recordDict)

    df = pd.DataFrame(dicts)
    timeColumns = ['date']
    for col in timeColumns:
        df[col] = pd.to_datetime(df[col])
    numericColumns = ['HKSWOLFScore', 'duration']
    for col in numericColumns:
        df[col] = pd.to_numeric(df[col])
        
    df.set_index('date', inplace=True)
    
    return df


def get_workout_event_lap(workoutTags):
    dicts = []
    for workoutTag in workoutTags:
        for child in workoutTag.findall("WorkoutEvent[@type='HKWorkoutEventTypeLap']"):
            recordDict = {}
            for k, v in child.attrib.items():
                if k in ['type']: continue
                recordDict[k] = v

                for entry in child.findall('MetadataEntry'):
                    k, v = entry.attrib['key'], entry.attrib['value']
                    recordDict[k] = v

            dicts.append(recordDict)

    df = pd.DataFrame(dicts)
    timeColumns = ['date']
    for col in timeColumns:
        df[col] = pd.to_datetime(df[col])
    numericColumns = ['HKSWOLFScore', 'duration', 'HKSwimmingStrokeStyle']
    for col in numericColumns:
        df[col] = pd.to_numeric(df[col])
        
    df.set_index('date', inplace=True)
    
    return df


def format_workout_time(tdelta):
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:0>2}:{minutes:0>2}:{seconds:0>2}"


def plot(i, swimmingData):
    directory = swimmingData['directory']
    distanceSwimming = swimmingData['distanceSwimming']
    heartRate = swimmingData['heartRate']
    swimmingStrokeCount = swimmingData['swimmingStrokeCount']
    workoutSummary = swimmingData['workoutSummary']
    workoutEventSegment = swimmingData['workoutEventSegment']
    workoutEventLap = swimmingData['workoutEventLap']

    date = workoutSummary.iloc[i].name.strftime('%Y-%m-%d')
    distance = int(workoutSummary.iloc[i].DistanceSwimming_sum)
    workoutTime = workoutSummary.iloc[i].endDate - workoutSummary.iloc[i].startDate
    workoutTimeFormatted = format_workout_time(workoutTime)

    heartRateAverage = int(workoutSummary.iloc[i].HeartRate_average)
    mydf = swimmingStrokeCount[date]
    strt = mydf.startDate.min()
    end = mydf.endDate.max()
    title = f'{date}: {distance:d}m, {workoutTimeFormatted}, Avg {heartRateAverage}bpm'
    filename = os.path.join(directory, f'{date} {distance:d}m.png')
    print(f'{i}, {title}, {strt}, {end}')

    mydf2 = heartRate[date][strt.strftime('%Y-%m-%d %H:%M:%S') : end.strftime('%Y-%m-%d %H:%M:%S')]
    mydf3 = workoutEventLap[date][strt.strftime('%Y-%m-%d %H:%M:%S') : end.strftime('%Y-%m-%d %H:%M:%S')]
    lap = mydf3['duration'].apply(lambda x: pd.Timedelta(x, 'min')).dt.total_seconds()
    mydf4 = workoutEventSegment[date][(strt-pd.Timedelta(100, 'sec')).strftime('%Y-%m-%d %H:%M:%S') : end.strftime('%Y-%m-%d %H:%M:%S')]


    fig = plt.figure(figsize=(16, 8), facecolor='white', constrained_layout=True)
    gs = GridSpec(2, 1, height_ratios=[4, 1], figure=fig)

    ax = fig.add_subplot(gs[0])
    ax.plot((mydf2['startDate'] - strt).dt.total_seconds()/60., mydf2['value']
        , '.', color='tab:blue')

    for index, row in mydf3.iterrows():
        ax.axvspan((index-strt).total_seconds()/60., (index-strt).total_seconds()/60.+row.duration, facecolor='tab:blue', alpha=0.1)

    ax.barh(75, width=mydf4['duration'], left=(mydf4.index - strt).total_seconds()/60., color='tab:blue', alpha=0.3, height=4)

    ax2 = ax.twinx()
    ax2.plot(((mydf3.index - strt).total_seconds() + lap)/60., lap, 'o', color='tab:orange')
    #ax2.set_ylim(0, 40)

    xticks = np.linspace(0, 30, 11)
    xlim = (0, 30)

    ax.grid()
    ax.set_xlabel('Time [min]')
    ax.set_xlim(xlim)
    ax.set_xticks(xticks)
    ax.set_ylabel('Heart Rate [bpm]')
    ax.yaxis.label.set_color(color='tab:blue')
    ax.set_ylim(75, 185)
    ax.tick_params(direction="in")

    ax2.set_ylabel('25m Lap [sec]')
    ax.set_xlim(xlim)
    ax2.set_xticks(xticks)
    ax2.set_ylim(20, 40)
    ax2.yaxis.label.set_color(color='tab:orange')
    ax2.tick_params(direction="in")

    ax.set_title(title)
    

    #j = 1
    axs = fig.add_subplot(gs[1])
    axs.plot(((mydf['startDate'] - strt).dt.total_seconds() + lap)/60., mydf['value']
        , 'o', color='tab:green')

    for index, row in mydf3.iterrows():
        axs.axvspan((index-strt).total_seconds()/60., (index-strt).total_seconds()/60.+row.duration, facecolor='tab:blue', alpha=0.1)

    axs.grid()
    axs.set_xlabel('Time [min]')
    axs.set_xlim(xlim)
    axs.set_xticks(xticks)
    axs.set_ylabel('Stroke Count')
    axs.yaxis.label.set_color(color='tab:green')
    axs.set_ylim(6, 14) 
    axs.tick_params(direction="in")

    plt.savefig(filename, dpi=200)
    #plt.show()


def parse_export(exportFilename):
    root = get_et_root(exportFilename)

    distanceSwimming = get_record_by_type(root, 'HKQuantityTypeIdentifierDistanceSwimming')
    heartRate = get_record_by_type(root, 'HKQuantityTypeIdentifierHeartRate')
    swimmingStrokeCount = get_record_by_type(root, 'HKQuantityTypeIdentifierSwimmingStrokeCount')

    workoutTags = get_workout_tags(root)
    workoutSummary = get_workout_summary(workoutTags)
    workoutEventSegment = get_workout_event_segment(workoutTags)
    workoutEventLap = get_workout_event_lap(workoutTags)

    swimmingData = {
        'directory': os.path.dirname(exportFilename),
        'distanceSwimming': distanceSwimming,
        'heartRate': heartRate,
        'swimmingStrokeCount': swimmingStrokeCount,
        'workoutSummary': workoutSummary,
        'workoutEventSegment': workoutEventSegment,
        'workoutEventLap': workoutEventLap
    }

    return swimmingData

if __name__ == '__main__':
    if len(sys.argv) > 1:
        exportFilename = sys.argv[1]
    else:
        exportFilename = 'export.xml'

    swimmingData = parse_export(exportFilename)
    for i in range(len(swimmingData['workoutSummary'])):
        plot(i, swimmingData)
    
