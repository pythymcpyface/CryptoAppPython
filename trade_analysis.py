import datetime
import os
import socket
import time

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import simplejson
from dotenv import load_dotenv
from pycoingecko import CoinGeckoAPI

import binanceapi.spot_extended
import statistical_analysis as sa
import urls as u
from binanceapi.constant import Interval


def calculate_percent_change(df, row, column):
    for i in range(1, len(df.index)):

        if row.name - i >= 0:

            previous_row = df.loc[row.name - i, column]
            current_row = df.loc[row.name, column]

            difference = current_row - previous_row

            percent_change = 100 * difference / previous_row

            if difference != 0.0:
                return percent_change
        else:
            return 0.0


load_dotenv()

cg = CoinGeckoAPI()

# Binance configurations
binance_key = os.environ.get("BINANCE_KEY")
binance_secret = os.environ.get("BINANCE_SECRET")

h_name = socket.gethostname()
host = str(socket.gethostbyname(h_name))
urls = u.Urls(host=host)
binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)
constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
pairs_per_coin_limit = int(constants['pairs_per_coin'])
pairs = binance_api.get_pairs()
pairs_per_coin = binance_api.get_pairs_per_coin(pairs)
wanted_pairs = binance_api.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

pair_symbol_dict = {}

symbols = []

for pair in wanted_pairs:
    symbol = pair.replace("-", "")
    symbols.append(symbol)
    pair_symbol_dict[symbol] = pair

user_orders_list = []

for symbol in symbols:
    try:
        user_orders = binance_api.get_user_orders(start_time=1639123200000, symbol=symbol)

        print(user_orders)
        if len(user_orders) > 0 and type(user_orders[1]) != int:
            user_orders_list.append(user_orders)

    except Exception as e:
        print(f"Error for {symbol}: {e}")
        user_orders_list.append([])

print(user_orders_list)

df = pd.DataFrame(columns=range(18))

if len(user_orders_list) > 0:

    for user_orders in user_orders_list:
        for user_order in user_orders:
            df.columns = user_order.keys()
            _df = pd.DataFrame(user_order, index=[0])

            df = pd.concat([df, _df], sort=False)

    df = df.sort_values('time')

df = df.reset_index()
pair_symbol_dict = sa.create_pair_symbol_dict()
df['pair'] = df.apply(lambda row: sa.convert_symbol_to_pair(df.loc[row.name, 'symbol'], pair_symbol_dict), axis=1)
df['baseAsset'] = df.apply(lambda row: df.loc[row.name, 'pair'][:df.loc[row.name, 'pair'].find("-")], axis=1)
df['priceUsd'] = df.apply(lambda row: binance_api.get_kline(f"{df.loc[row.name, 'baseAsset']}USDT", Interval.MINUTE_1,
                                                            df.loc[row.name, 'time'] - (60 * 1000),
                                                            df.loc[row.name, 'time'])[0][4], axis=1)
df['valueUsd'] = df.apply(lambda row: float(df.loc[row.name, 'origQty']) * float(df.loc[row.name, 'priceUsd']), axis=1)
df['date'] = df.apply(
    lambda row: datetime.datetime.strftime(datetime.datetime.fromtimestamp(int(df.loc[row.name, 'time']) / 1000),
                                           "%d-%m-%Y"), axis=1)
df['datetime'] = df.apply(
    lambda row: datetime.datetime.strftime(datetime.datetime.fromtimestamp(int(df.loc[row.name, 'time']) / 1000),
                                           "%d-%m-%Y %Hh:%Mm"), axis=1)
df['valueUsd%Change'] = df.apply(lambda row: calculate_percent_change(df, row, 'valueUsd'), axis=1)
df['cumulativeValueUsd%Change'] = df.apply(lambda row: (
        100 * (df.loc[row.name, 'valueUsd'] - df.loc[0, 'valueUsd']) /
        df.loc[0, 'valueUsd']), axis=1)
df['marketCapUsd'] = df.apply(lambda row: sa.get_market_cap(df, row), axis=1)
df['marketCapUsd'] = df.apply(lambda row: sa.replace_column_zeroes(df, row, 'marketCapUsd'), axis=1)
df['marketCapUsd%Change'] = df.apply(lambda row: calculate_percent_change(df, row, 'marketCapUsd'), axis=1)
df['cumulativeMarketCapUsd%Change'] = df.apply(lambda row: (
        100 * (df.loc[row.name, 'marketCapUsd'] - df.loc[0, 'marketCapUsd']) /
        df.loc[0, 'marketCapUsd']), axis=1)

average_percent_change = df['valueUsd%Change'].mean()
start_time = df['time'].min()
end_time = time.time() * 1000
milliseconds = end_time - start_time
days = milliseconds / (24 * 60 * 60 * 1000)
number_of_trades = df['time'].count() / 2
trades_per_day = number_of_trades / days

total_holdings = binance_api.get_total_holdings(pairs_per_coin_limit)

print(df)

fig, ax1 = plt.subplots()
# ax2 = ax1.twinx()
sns.set_palette("bright")
sns.lineplot(x=df['datetime'], y=df['cumulativeValueUsd%Change'], data=df, ax=ax1, color='g')
sns.lineplot(x=df['datetime'], y=df['valueUsd%Change'], data=df, ax=ax1, color='b')
sns.lineplot(x=df['datetime'], y=df['cumulativeMarketCapUsd%Change'], data=df, ax=ax1, color='r')

plt.legend()

projected_day = total_holdings * ((100 + average_percent_change) / 100) ** trades_per_day
projected_year = total_holdings * ((100 + average_percent_change) / 100) ** (trades_per_day * 365)

plt.title(
    "Current holdings = \${0:.2f},\nProjection after one day = \${1:.2f},\nProjection after one year = \${2:.2f}".format(
        total_holdings, projected_day, projected_year))

fig.canvas.draw()
plt.show()
