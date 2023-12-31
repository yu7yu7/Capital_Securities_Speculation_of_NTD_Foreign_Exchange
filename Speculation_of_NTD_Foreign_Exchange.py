# -*- coding: utf-8 -*-
"""Untitled6.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1TfXHLD650L3ag-v_ycCelinHLPkVq8wY
"""

import pandas as pd
import numpy as np
import datetime

from sklearn.linear_model import LinearRegression
import pywt

import matplotlib.pyplot as plt

import os
from tqdm import tqdm
import time
import warnings
warnings.filterwarnings("ignore")


# #Transforming the data format into 5S-interval
def transform_data(df, dates, interval="1S"):
    df = df.groupby([df.index, "Type"]).mean().reset_index()
    df = df.pivot(index="Dates", columns="Type", values="Price")

    bid_df = df["BEST_BID"]
    ask_df = df["BEST_ASK"]
    trade_df = df["TRADE"]

    result_dfs = []
    for date in dates:
        start_time = datetime.datetime.combine(
            date, datetime.datetime.min.time()
        ) + datetime.timedelta(hours=9)
        end_time = datetime.datetime.combine(
            date, datetime.datetime.min.time()
        ) + datetime.timedelta(hours=16, minutes=1)

        bid_df_day = bid_df.loc[start_time:end_time].resample(interval).last().ffill()
        ask_df_day = ask_df.loc[start_time:end_time].resample(interval).last().ffill()
        trade_df_day = (
            trade_df.loc[start_time:end_time].resample(interval).last().ffill()
        )

        result_df = pd.concat([bid_df_day, ask_df_day, trade_df_day], axis=1)
        result_df.columns = ["BID", "ASK", "TRADE"]

        result_df["MID"] = (result_df["BID"] + result_df["ASK"]) / 2
        result_df = result_df[["BID", "MID", "ASK", "TRADE"]]

        result_dfs.append(result_df)

    final_df = pd.concat(result_dfs)

    return final_df


# Define a function to replace values with NaN during a specific time interval
def replace_with_nan(df):
    mask = (df.index.time > datetime.time(12, 0)) & (
        df.index.time < datetime.time(14, 0)
    )
    df.loc[mask] = np.nan
    return df


def calculate_returns(df):
    # Calculate the percentage change (returns)
    df_returns = df.pct_change()

    # Drop any NA values generated by the pct_change function
    df_returns = df_returns.dropna()

    return df_returns


def align_dataframes(*dfs):
    # Find the intersection of all indices
    common_index = dfs[0].index
    for df in dfs[1:]:
        common_index = common_index.intersection(df.index)

    # Reindex all dataframes with the common index
    return [df.reindex(common_index) for df in dfs]

def wavelet_denoise(data, wavelet, level):
    # Remember the original data length
    original_length = len(data)

    # Ensure the data length is even
    if len(data) % 2:
        data = np.pad(data, (0, 1), 'edge')

    # Decompose to get wavelet coefficients
    coeff = pywt.wavedec(data, wavelet, mode="per", level=level)

    # Calculate sigma for threshold as defined in
    # Donoho and Johnstone 1994, p. 12
    sigma = (1/0.6745) * np.median(np.abs(coeff[-level] - np.median(coeff[-level])))

    # Calculate universal threshold
    uthresh = sigma * np.sqrt(2*np.log(len(data)))
    coeff = list(map(lambda x: pywt.threshold(x, value=uthresh, mode="soft"), coeff))

    # Reconstruct the signal using the thresholded coefficients
    denoised_data = pywt.waverec(coeff, wavelet, mode="per")

    # Truncate back to the original length if necessary
    if original_length != len(denoised_data):
        denoised_data = denoised_data[:original_length]

    return denoised_data

def colorize(row):
    if (row["New Accuracy"] == Acc_table.min().min()):
        return ['color: green', 'color: black']
    elif  (row["Previous Accuracy"] == Acc_table.min().min()):
        return ['color: black', 'color: green']
    elif row["New Accuracy"] < row["Previous Accuracy"]:
        return ['color: blue', 'color: black']
    else:
        return ['color: black', 'color: blue']

def get_pred_path(date, time, model, window):
    y_pred = model.predict(df[(df.index.date == date) & (df.index.time <= time)][["CMPN"]]) # Fit

    y_pred = pd.DataFrame(y_pred, index = df[(df.index.date == date) & (df.index.time <= time)].index, columns = ["Prediction"])
    y_pred = y_pred.ewm(span=window).mean()
    real_closing = df[(df.index.date == date) & (df.index.time == datetime.time(12, 0))]["TPFT"].values[0]
    est_closing = y_pred[(y_pred.index.date == date) & (y_pred.index.time == datetime.time(12, 0))]["Prediction"].values[0]
    y_pred = y_pred - est_closing + real_closing # Shift

    return y_pred

path = "./Dataset"
files = [f for f in os.listdir(path) if f.endswith(".txt")]
print(f"Found files in the main folder: {files}")

dic = {}
for file_path in files:
    if file_path == "BNTD_1201_0526.txt":
        df = pd.read_csv("./Dataset/BNTD_1201_0526.txt", sep=",", skiprows=2)
        df["Dates"] = pd.to_datetime(
            df["Dates"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )
    else:
        df = pd.read_csv(path + "/" + file_path, sep="\t", skiprows=2)
        df["Dates"] = pd.to_datetime(
            df["Dates"], format="%Y/%m/%d %p %I:%M:%S", errors="coerce"
        )

    df.dropna(subset=["Dates"], inplace=True)

    df.set_index("Dates", inplace=True)
    dic[file_path] = df
    print(file_path + " loaded.")

# Set time interval
time_interval = "1S"

# create empty DataFrames for each category
df_TPFT = pd.DataFrame()
df_CMPN = pd.DataFrame()

# iterate through dictionary keys
for key in dic.keys():
    # determine category
    category = key.split("_")[0]
    # concatenate DataFrame to appropriate category
    if category == "TPFT":
        df_TPFT = pd.concat([df_TPFT, dic[key]])
    elif category == "CMPN":
        df_CMPN = pd.concat([df_CMPN, dic[key]])

# Now df_COFX, df_REGN, df_TPFT, df_CMPN, and df_BGN each contain all the data from the respective category across all dates
df_TPFT = df_TPFT.sort_index()
df_CMPN = df_CMPN.sort_index()
display(f"TPFT Length: {len(df_TPFT)}, CMPN Length: {len(df_CMPN)}")

# Formatting the data type as float
df_TPFT["Price"] = df_TPFT["Price"].astype(float)
df_CMPN["Price"] = df_CMPN["Price"].astype(float)

# Create dates overlapping
unique_TPFT_dates = set(pd.unique(df_TPFT.index.date))
unique_CMPN_dates = set(pd.unique(df_CMPN.index.date))

# Get the unique dates that are only in TPFT and not in the others
unique_to_TPFT = (
    unique_TPFT_dates
    - unique_CMPN_dates
)



# Get the unique dates that are only in CMPN and not in the others
unique_to_CMPN = (
    unique_CMPN_dates
    - unique_TPFT_dates
)


# If you want the dates that are in all dataframes
dates = (
    unique_TPFT_dates
    & unique_CMPN_dates
)

dates = list(dates)
dates.remove(datetime.date(2023, 4, 18))
dates = sorted(dates)

# Now, apply the function to your dataframes
df_TPFT = transform_data(df_TPFT, dates, time_interval)
df_CMPN = transform_data(df_CMPN, dates, time_interval)


# Now df_COFX, df_REGN, df_TPFT, df_CMPN, and df_BGN each contain all the data from the respective category across all dates
df_TPFT = df_TPFT.sort_index()
df_CMPN = df_CMPN.sort_index()

# Drop Nan
df_TPFT = df_TPFT.dropna(subset=["MID"])
df_CMPN = df_CMPN.dropna(subset=["MID"])

# Transform to BP format
df_TPFT_BP = calculate_returns(df_TPFT)
df_CMPN_BP = calculate_returns(df_CMPN)

# Reformatting in same shape
df_TPFT, df_CMPN = align_dataframes(
    df_TPFT, df_CMPN
)
df_TPFT_BP, df_CMPN_BP = align_dataframes(
    df_TPFT_BP, df_CMPN_BP
)
print(df_TPFT.shape, df_CMPN.shape)

# Restore the fact that TPFT is not being traded between 12 and 14 every day
df_TPFT = replace_with_nan(df_TPFT)
df_TPFT_BP = replace_with_nan(df_TPFT_BP)

df_est = pd.DataFrame()
df_est = pd.concat([df_est, dic["BNTD_1201_0526.txt"]])
df_est = df_est.sort_index()
df_est["Price"] = df_est["Price"].astype(float)
df_est = transform_data(df_est, dates, time_interval)
df_est = df_est.sort_index()
df_est = df_est.dropna(subset=["MID"])
df_est_BP = calculate_returns(df_est)

df = df_CMPN['MID'].loc[df_CMPN.index.date == datetime.date(2023, 3, 13)]

plt.figure(figsize = (20, 5))
plt.title(f"NYSE NTD Foreign Exchange of {datetime.date(2023, 3, 13)}")
plt.plot(df, "-", label = "Actual Path")
plt.xlabel("Time")
plt.ylabel("Price")
plt.legend()
plt.show()

#　Real time imitation
# Linear Regression + Wavelet Signal Denoiser + Shifting
chosen_date = datetime.date(2023, 3, 13)
X_record = np.array([])
y_record = np.array([])
model = LinearRegression()
time_record = []

df = pd.DataFrame({"TPFT": df_TPFT["MID"],
                "CMPN": df_CMPN["MID"]})

for date_idx in tqdm(df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, desc="Processing", unit="rows"):
    start = time.time()

    TPFT_new_input = df[df.index == date_idx]["TPFT"].values[0]
    CMPN_new_input = df[df.index == date_idx]["CMPN"].values[0]
    X_record = np.append(X_record, [CMPN_new_input])

    if date_idx.time() <= datetime.time(12, 0): # Storing all training sets
        y_record = np.append(y_record, [TPFT_new_input])

    if date_idx.time() == datetime.time(12, 0): # Fit and get Parameters ONLY ONCE!
        real_closing = TPFT_new_input
        X_record = X_record.reshape(-1, 1)
        model.fit(X_record, y_record)
        y_pred = model.predict(X_record)
        X_record = X_record.reshape(-1)
        index_of_12 = len(X_record) - 1

    if (date_idx.time() > datetime.time(12, 0)) & (date_idx.time() <= datetime.time(14, 0)):
        # Fit, Denoise and Shift
        y_pred = np.append(y_pred, model.predict([[CMPN_new_input]])) # Fit
        smoothed_y_pred = wavelet_denoise(y_pred, wavelet="db8", level=37) # Denoise
        est_closing = smoothed_y_pred[index_of_12]
        smoothed_y_pred = smoothed_y_pred - (est_closing - real_closing) # Shift

    end = time.time()
    time_record.append(end - start)

smoothed_y_pred = pd.DataFrame(smoothed_y_pred, index = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, columns = ['Prediction'])

plt.figure(figsize = (20, 5))
plt.title(f"TPFT Estimation of {chosen_date}")
plt.plot(smoothed_y_pred[(smoothed_y_pred.index.time > datetime.time(12, 0)) & (smoothed_y_pred.index.time <= datetime.time(14, 0))], "-", label = "Prediction Path")
plt.plot(df[( df.index.date == chosen_date)]["TPFT"], "-", label = "Actual Path")
plt.annotate(f'Value at 12:00: {df[( df.index.date == chosen_date) & (df.index.time == datetime.time(14, 0))]["TPFT"].values[0]}', (datetime.datetime.combine(chosen_date, datetime.time(14, 0)), df[( df.index.date == chosen_date) & (df.index.time == datetime.time(14, 0))]["TPFT"].values[0]), textcoords="offset points", xytext=(0,10), ha='center')
plt.annotate(f'Estimation at 14:00: {smoothed_y_pred[smoothed_y_pred.index.time == datetime.time(14, 0)].values[0][0]}', (datetime.datetime.combine(chosen_date, datetime.time(14, 0)),smoothed_y_pred[smoothed_y_pred.index.time == datetime.time(14, 0)].values[0][0]), textcoords="offset points", xytext=(0, -10), ha='center')
plt.xlabel("Time")
plt.ylabel("Price")
plt.legend()
plt.show()

plt.figure(figsize = (20, 5))
plt.title("Time Spent")
plt.plot(df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, time_record, "o")
plt.xlabel("Time")
plt.ylabel("Timespent")
plt.show()

# Performance
# Linear Regression + EMA100 + Shifting
chosen_date = datetime.date(2023, 3, 13)
X_record = np.array([])
y_record = np.array([])
model = LinearRegression()
time_record = []

df = pd.DataFrame({"TPFT": df_TPFT["MID"],
                "CMPN": df_CMPN["MID"]})

for date_idx in tqdm(df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, desc="Processing", unit="rows"):
    start = time.time()

    TPFT_new_input = df[df.index == date_idx]["TPFT"].values[0]
    CMPN_new_input = df[df.index == date_idx]["CMPN"].values[0]
    X_record = np.append(X_record, [CMPN_new_input])

    if date_idx.time() <= datetime.time(12, 0): # Storing all training sets
        y_record = np.append(y_record, [TPFT_new_input])

    if date_idx.time() == datetime.time(12, 0): # Fit and get Parameters ONLY ONCE!
        real_closing = TPFT_new_input
        X_record = X_record.reshape(-1, 1)
        model.fit(X_record, y_record)
        y_pred = model.predict(X_record)
        X_record = X_record.reshape(-1)
        index_of_12 = len(X_record) - 1

    if (date_idx.time() > datetime.time(12, 0)) & (date_idx.time() <= datetime.time(14, 0)):
        # Fit, Denoise and Shift
        y_pred = np.append(y_pred, model.predict([[CMPN_new_input]])) # Fit


        # Convert the numpy array to pandas Series
        y_pred_series = pd.Series(y_pred)

        # Calculate the Exponential Moving Average
        smoothed_y_pred = y_pred_series.ewm(span=37, adjust=False).mean().values

        est_closing = smoothed_y_pred[index_of_12]
        smoothed_y_pred = smoothed_y_pred - (est_closing - real_closing) # Shift

    end = time.time()
    time_record.append(end - start)

smoothed_y_pred = pd.DataFrame(smoothed_y_pred, index = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, columns = ['Prediction'])

plt.figure(figsize = (20, 5))
plt.title(f"TPFT Estimation of {chosen_date}")
plt.plot(smoothed_y_pred[(smoothed_y_pred.index.time > datetime.time(12, 0)) & (smoothed_y_pred.index.time <= datetime.time(14, 0))], "-", label = "Prediction Path")
plt.plot(df[( df.index.date == chosen_date)]["TPFT"], "-", label = "Actual Path")
plt.annotate(f'Value at 12:00: {df[( df.index.date == chosen_date) & (df.index.time == datetime.time(14, 0))]["TPFT"].values[0]}', (datetime.datetime.combine(chosen_date, datetime.time(14, 0)), df[( df.index.date == chosen_date) & (df.index.time == datetime.time(14, 0))]["TPFT"].values[0]), textcoords="offset points", xytext=(0,10), ha='center')
plt.annotate(f'Estimation at 14:00: {smoothed_y_pred[smoothed_y_pred.index.time == datetime.time(14, 0)].values[0][0]}', (datetime.datetime.combine(chosen_date, datetime.time(14, 0)),smoothed_y_pred[smoothed_y_pred.index.time == datetime.time(14, 0)].values[0][0]), textcoords="offset points", xytext=(0, -10), ha='center')
plt.xlabel("Time")
plt.ylabel("Price")
plt.legend()
plt.show()

plt.figure(figsize = (20, 5))
plt.title("Time Spent")
plt.plot(df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(14, 0))].index, time_record, "o")
plt.xlabel("Time")
plt.ylabel("Timespent")
plt.show()

# See performance
def get_pred_path(date, time, model, window):
    y_pred = model.predict(df[(df.index.date == date) & (df.index.time <= time)][["CMPN"]]) # Fit

    y_pred = pd.DataFrame(y_pred, index = df[(df.index.date == date) & (df.index.time <= time)].index, columns = ["Prediction"])
    y_pred = y_pred.ewm(span=window).mean()
    real_closing = df[(df.index.date == date) & (df.index.time == datetime.time(12, 0))]["TPFT"].values[0]
    est_closing = y_pred[(y_pred.index.date == date) & (y_pred.index.time == datetime.time(12, 0))]["Prediction"].values[0]
    y_pred = y_pred - est_closing + real_closing # Shift

    return y_pred

# Variables Setting
model = LinearRegression()
df = pd.DataFrame({
    "TPFT": df_TPFT["MID"],
    "CMPN": df_CMPN["MID"]
})
accuracy_of_1215 = 0
accuracy_of_1230 = 0
accuracy_of_1245 = 0
accuracy_of_1300 = 0
accuracy_of_1315 = 0
accuracy_of_1330 = 0
accuracy_of_1345 = 0

accuracy_of_1215_their = 0
accuracy_of_1230_their = 0
accuracy_of_1245_their = 0
accuracy_of_1300_their = 0
accuracy_of_1315_their = 0
accuracy_of_1330_their = 0
accuracy_of_1345_their = 0

day_count = 0

window = 37

# Dataset Setting
for chosen_date in tqdm(dates, desc="Processing", unit="rows"):

    day_count += 1

    X_train = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(12, 0))][["CMPN"]]
    y_train = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(12, 0))]["TPFT"]

    # Fit
    model.fit(X_train, y_train)

    # Get Prediction Path
    y_pred_1215_path = get_pred_path(chosen_date, datetime.time(12, 15), model, window)
    y_pred_1230_path = get_pred_path(chosen_date, datetime.time(12, 30), model, window)
    y_pred_1245_path = get_pred_path(chosen_date, datetime.time(12, 45), model, window)
    y_pred_1300_path = get_pred_path(chosen_date, datetime.time(13, 00), model, window)
    y_pred_1315_path = get_pred_path(chosen_date, datetime.time(13, 15), model, window)
    y_pred_1330_path = get_pred_path(chosen_date, datetime.time(13, 30), model, window)
    y_pred_1345_path = get_pred_path(chosen_date, datetime.time(13, 45), model, window)

    # Get Prediction Spot
    y_pred_1215 = y_pred_1215_path.loc[y_pred_1215_path.index[-1]].values[0]
    y_pred_1230 = y_pred_1230_path.loc[y_pred_1230_path.index[-1]].values[0]
    y_pred_1245 = y_pred_1245_path.loc[y_pred_1245_path.index[-1]].values[0]
    y_pred_1300 = y_pred_1300_path.loc[y_pred_1300_path.index[-1]].values[0]
    y_pred_1315 = y_pred_1315_path.loc[y_pred_1315_path.index[-1]].values[0]
    y_pred_1330 = y_pred_1330_path.loc[y_pred_1330_path.index[-1]].values[0]
    y_pred_1345 = y_pred_1345_path.loc[y_pred_1345_path.index[-1]].values[0]

    # Get Previous Prediction Spot
    y_pred_1215_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 15))]["MID"].values[0]
    y_pred_1230_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 30))]["MID"].values[0]
    y_pred_1245_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 45))]["MID"].values[0]
    y_pred_1300_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 00))]["MID"].values[0]
    y_pred_1315_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 15))]["MID"].values[0]
    y_pred_1330_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 30))]["MID"].values[0]
    y_pred_1345_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 45))]["MID"].values[0]

    # Get Prediction Target
    y_at_15 = df[(df.index.date == chosen_date) & (df.index.time == datetime.time(15, 0))]["TPFT"].values[0]

    # Get Accuracies
    accuracy_of_1215 += np.abs(y_at_15 - y_pred_1215)
    accuracy_of_1230 += np.abs(y_at_15 - y_pred_1230)
    accuracy_of_1245 += np.abs(y_at_15 - y_pred_1245)
    accuracy_of_1300 += np.abs(y_at_15 - y_pred_1300)
    accuracy_of_1315 += np.abs(y_at_15 - y_pred_1315)
    accuracy_of_1330 += np.abs(y_at_15 - y_pred_1330)
    accuracy_of_1345 += np.abs(y_at_15 - y_pred_1345)

    # Get Previous Accuracies
    accuracy_of_1215_their += np.abs(y_at_15 - y_pred_1215_their)
    accuracy_of_1230_their += np.abs(y_at_15 - y_pred_1230_their)
    accuracy_of_1245_their += np.abs(y_at_15 - y_pred_1245_their)
    accuracy_of_1300_their += np.abs(y_at_15 - y_pred_1300_their)
    accuracy_of_1315_their += np.abs(y_at_15 - y_pred_1315_their)
    accuracy_of_1330_their += np.abs(y_at_15 - y_pred_1330_their)
    accuracy_of_1345_their += np.abs(y_at_15 - y_pred_1345_their)


Acc_table = pd.DataFrame({
    '12:15': [accuracy_of_1215/day_count, accuracy_of_1215_their/day_count],
    '12:30': [accuracy_of_1230/day_count, accuracy_of_1230_their/day_count],
    '12:45': [accuracy_of_1245/day_count, accuracy_of_1245_their/day_count],
    '13:00': [accuracy_of_1300/day_count, accuracy_of_1300_their/day_count],
    '13:15': [accuracy_of_1315/day_count, accuracy_of_1315_their/day_count],
    '13:30': [accuracy_of_1330/day_count, accuracy_of_1330_their/day_count],
    '13:45': [accuracy_of_1345/day_count, accuracy_of_1345_their/day_count]}, index= ["New Accuracy", "Previous Accuracy"])

Acc_table = Acc_table.transpose()
Acc_table.style.apply(colorize, axis=1)

# Linear Regression + Wavelet Signal Denoiser + Shifting
def get_pred_path(date, time, model):
    y_pred = model.predict(df[(df.index.date == date) & (df.index.time <= time)][["CMPN"]]) # Fit
    y_pred = wavelet_denoise(y_pred, wavelet="db8", level=37) # Denoise
    y_pred = pd.DataFrame(y_pred, index = df[(df.index.date == date) & (df.index.time <= time)].index, columns = ["Prediction"])
    real_closing = df[(df.index.date == date) & (df.index.time == datetime.time(12, 0))]["TPFT"].values[0]
    est_closing = y_pred[(y_pred.index.date == date) & (y_pred.index.time == datetime.time(12, 0))]["Prediction"].values[0]
    y_pred = y_pred - est_closing + real_closing # Shift

    return y_pred

# Variables Setting
model = LinearRegression()
df = pd.DataFrame({
    "TPFT": df_TPFT["MID"],
    "CMPN": df_CMPN["MID"]
})
accuracy_of_1215 = 0
accuracy_of_1230 = 0
accuracy_of_1245 = 0
accuracy_of_1300 = 0
accuracy_of_1315 = 0
accuracy_of_1330 = 0
accuracy_of_1345 = 0

accuracy_of_1215_their = 0
accuracy_of_1230_their = 0
accuracy_of_1245_their = 0
accuracy_of_1300_their = 0
accuracy_of_1315_their = 0
accuracy_of_1330_their = 0
accuracy_of_1345_their = 0

day_count = 0

# Dataset Setting
for chosen_date in tqdm(dates, desc="Processing", unit="rows"):

    day_count += 1

    X_train = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(12, 0))][["CMPN"]]
    y_train = df[(df.index.date == chosen_date) & (df.index.time <= datetime.time(12, 0))]["TPFT"]

    # Fit
    model.fit(X_train, y_train)

    # Get Prediction Path
    y_pred_1215_path = get_pred_path(chosen_date, datetime.time(12, 15), model)
    y_pred_1230_path = get_pred_path(chosen_date, datetime.time(12, 30), model)
    y_pred_1245_path = get_pred_path(chosen_date, datetime.time(12, 45), model)
    y_pred_1300_path = get_pred_path(chosen_date, datetime.time(13, 00), model)
    y_pred_1315_path = get_pred_path(chosen_date, datetime.time(13, 15), model)
    y_pred_1330_path = get_pred_path(chosen_date, datetime.time(13, 30), model)
    y_pred_1345_path = get_pred_path(chosen_date, datetime.time(13, 45), model)

    # Get Prediction Spot
    y_pred_1215 = y_pred_1215_path.loc[y_pred_1215_path.index[-1]].values[0]
    y_pred_1230 = y_pred_1230_path.loc[y_pred_1230_path.index[-1]].values[0]
    y_pred_1245 = y_pred_1245_path.loc[y_pred_1245_path.index[-1]].values[0]
    y_pred_1300 = y_pred_1300_path.loc[y_pred_1300_path.index[-1]].values[0]
    y_pred_1315 = y_pred_1315_path.loc[y_pred_1315_path.index[-1]].values[0]
    y_pred_1330 = y_pred_1330_path.loc[y_pred_1330_path.index[-1]].values[0]
    y_pred_1345 = y_pred_1345_path.loc[y_pred_1345_path.index[-1]].values[0]

    # Get Previous Prediction Spot
    y_pred_1215_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 15))]["MID"].values[0]
    y_pred_1230_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 30))]["MID"].values[0]
    y_pred_1245_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(12, 45))]["MID"].values[0]
    y_pred_1300_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 00))]["MID"].values[0]
    y_pred_1315_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 15))]["MID"].values[0]
    y_pred_1330_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 30))]["MID"].values[0]
    y_pred_1345_their = df_est[(df_est.index.date == chosen_date) & (df_est.index.time == datetime.time(13, 45))]["MID"].values[0]

    # Get Prediction Target
    y_at_15 = df[(df.index.date == chosen_date) & (df.index.time == datetime.time(15, 0))]["TPFT"].values[0]

    # Get Accuracies
    accuracy_of_1215 += np.abs(y_at_15 - y_pred_1215)
    accuracy_of_1230 += np.abs(y_at_15 - y_pred_1230)
    accuracy_of_1245 += np.abs(y_at_15 - y_pred_1245)
    accuracy_of_1300 += np.abs(y_at_15 - y_pred_1300)
    accuracy_of_1315 += np.abs(y_at_15 - y_pred_1315)
    accuracy_of_1330 += np.abs(y_at_15 - y_pred_1330)
    accuracy_of_1345 += np.abs(y_at_15 - y_pred_1345)

    # Get Previous Accuracies
    accuracy_of_1215_their += np.abs(y_at_15 - y_pred_1215_their)
    accuracy_of_1230_their += np.abs(y_at_15 - y_pred_1230_their)
    accuracy_of_1245_their += np.abs(y_at_15 - y_pred_1245_their)
    accuracy_of_1300_their += np.abs(y_at_15 - y_pred_1300_their)
    accuracy_of_1315_their += np.abs(y_at_15 - y_pred_1315_their)
    accuracy_of_1330_their += np.abs(y_at_15 - y_pred_1330_their)
    accuracy_of_1345_their += np.abs(y_at_15 - y_pred_1345_their)


Acc_table = pd.DataFrame({
    '12:15': [accuracy_of_1215/day_count, accuracy_of_1215_their/day_count],
    '12:30': [accuracy_of_1230/day_count, accuracy_of_1230_their/day_count],
    '12:45': [accuracy_of_1245/day_count, accuracy_of_1245_their/day_count],
    '13:00': [accuracy_of_1300/day_count, accuracy_of_1300_their/day_count],
    '13:15': [accuracy_of_1315/day_count, accuracy_of_1315_their/day_count],
    '13:30': [accuracy_of_1330/day_count, accuracy_of_1330_their/day_count],
    '13:45': [accuracy_of_1345/day_count, accuracy_of_1345_their/day_count]}, index= ["New Accuracy", "Previous Accuracy"])

Acc_table = Acc_table.transpose()
Acc_table.style.apply(colorize, axis=1)