import argparse
import os
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
from models.seq_2_seq_model import create_model
from preprocess.gfs_preprocess import prepare_gfs_sequence_dataset, CREATED_AT_COLUMN_NAME
from preprocess.synop_preprocess import prepare_synop_dataset, normalize
import pandas as pd
import tqdm
import warnings
warnings.filterwarnings('ignore')

def get_oldest_gfs_date(gfs: dict):
    gfs.keys()
    gfs_dates = [datetime.strptime(date, '%Y-%m-%d-%HZ').date() for date in gfs.keys()]
    return min(gfs_dates)

def filter_gfs(gfs: dict, last_synop_date: datetime, gfs_time_diff: int, label_seqence_len: int):
    fitlered = {}
    for key in gfs.keys():
        gfs_crated_at = datetime.strptime(key, '%Y-%m-%d-%HZ')
        if gfs_crated_at < last_synop_date - timedelta(hours=gfs_time_diff + label_seqence_len):
            fitlered[key] = gfs[key]
    return fitlered


def convert_wind(single_gfs):
    single_gfs["velocity"] = np.sqrt(single_gfs["U-wind, m/s"] ** 2 + single_gfs["V-wind, m/s"] ** 2)
    single_gfs = single_gfs.drop(["U-wind, m/s", "V-wind, m/s"], axis=1)

    return single_gfs


def prepare_data(gfs_dir: str, synop_dir: str, start_seq: int, end_seq: int, gfs_past: int, gfs_future: int,
                 synop_length: int, train_split: int, column_name_label: str):
    synop_dataset = prepare_synop_dataset(synop_dir)
    gfs_dataset, gfs_hour_diff = prepare_gfs_sequence_dataset(gfs_dir, start_seq, end_seq, gfs_past, gfs_future)

    least_recent_date = get_oldest_gfs_date(gfs_dataset)
    recent_synop_date = synop_dataset["date"].max()

    synop_dataset = synop_dataset[
        synop_dataset["date"] >= pd.to_datetime(least_recent_date) - timedelta(hours=synop_length)]
    gfs_dataset = filter_gfs(gfs_dataset, recent_synop_date, gfs_hour_diff, start_seq + end_seq)
    synop_dataset_input = []
    gfs_dataset_input = []
    dataset_label = []

    print("Creating data set")
    for key in tqdm.tqdm(gfs_dataset.keys()):
        gfs_creation_date = datetime.strptime(key, '%Y-%m-%d-%HZ')
        single_gfs = gfs_dataset[key]
        single_gfs = convert_wind(single_gfs)
        for hour in range(gfs_hour_diff):
            try:
                synop_index = synop_dataset.index[synop_dataset['date'] == gfs_creation_date][0]
                synop_input_index = hour + synop_index - synop_length + 1
                synop_input = synop_dataset.loc[synop_input_index: synop_input_index + synop_length]

                label = synop_dataset.loc[hour + synop_index + start_seq: hour + synop_index + end_seq]

                synop_input = synop_input.drop(['date', 'year', 'day', 'month'], axis=1).values
                gfs_input = normalize(single_gfs.drop(['date'], axis=1).values)
                label = label[column_name_label].values

                synop_dataset_input.append(synop_input)
                gfs_dataset_input.append(gfs_input)

                dataset_label.append(label)
            except:
                pass
    return np.array(synop_dataset_input), np.array(gfs_dataset_input), np.array(dataset_label)

def plot_history(history):
    # summarize history for loss
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('model loss')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'test'], loc='upper left')
    plt.show()

def train_model(**kwargs):
    dataset_input, gfs_dataset_input, dataset_label = prepare_data(**kwargs)
    print("Dataset size: {}".format(np.shape(dataset_input))[0])
    print("Label format: {}".format(np.shape(dataset_label)))

    train_index = int(dataset_input.shape[0] * kwargs["train_split"])
    label_input = []
    for label in dataset_label:
        label = np.insert(label, 0, 0)
        label_input.append(label[:-1])
    x_train = [dataset_input[:train_index], gfs_dataset_input[:train_index], np.array(label_input)[:train_index]]
    x_valid = [dataset_input[train_index:], gfs_dataset_input[train_index:], np.array(label_input)[train_index:]]
    y_train = dataset_label[:train_index]
    y_label = dataset_label[train_index:]

    model = create_model(dataset_input, gfs_dataset_input, 0.001, dataset_label.shape[1])
    history = model.fit(x_train, y_train, epochs=10, batch_size=32, validation_data=(x_valid, y_label))
    plot_history(history)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--gfs_dir', help='GFS directory', default='preprocess/wind_and_temp')
    parser.add_argument('--synop_dir', help='SYNOP directory', default='preprocess/synop_data/135_data.csv')
    parser.add_argument('--train_split', help='Train split factor from 0 to 1', default=0.75, type=float)
    parser.add_argument('--start_seq', help='Hour shift for start predicted sequence', default=12, type=int)
    parser.add_argument('--end_seq', help='Hour shift for end predicted sequence', default=24, type=int)

    parser.add_argument('--gfs_past', help='Number of hours before sequence which will be taken into account',
                        default=6, type=int)
    parser.add_argument('--gfs_future', help='Number of hours after sequence which will be taken into account',
                        default=6, type=int)
    parser.add_argument('--synop_length', help='Hours for Synop sequence which will be taken into account',
                        default=12, type=int)
    parser.add_argument('--column_name_label', help='Describe which feature will be predicted',
                        default='velocity', type=str)
    args = parser.parse_args()
    train_model(**vars(args))
