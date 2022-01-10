import datetime
import multiprocessing as mp
import os
import socket
import time

import matplotlib.pyplot as plt
import mysql.connector
import pandas as pd
import requests
import scipy
import seaborn as sns
import simplejson
from dotenv import load_dotenv
from pycoingecko import CoinGeckoAPI

import binanceapi.spot_extended
import urls as u
from correlation_statistics import CorrelationStatistics as cs
from utilities import log_error

# load dotenv
load_dotenv()

cg = CoinGeckoAPI()

h_name = socket.gethostname()
host = str(socket.gethostbyname(h_name))
urls = u.Urls(host=host)

# Binance configurations
binance_key = os.environ.get("BINANCE_KEY")
binance_secret = os.environ.get("BINANCE_SECRET")

binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)


def show_change_at_3sds():
    constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
    pairs_per_coin_limit = int(constants['pairs_per_coin'])

    db = mysql.connector.connect(
        host=os.environ.get("MYSQL_DATABASE_HOST"),
        user=os.environ.get("MYSQL_DATABASE_USER"),
        password=os.environ.get("MYSQL_DATABASE_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE_DB")
    )

    query = f"with a as (SELECT *, max(timestamp) over (partition by coin) as most_recent, min(p) over \
     (partition by coin) as min_p FROM crypto_db.statistics)\
    Select * FROM a \
    where datapoints > 1000 \
    and timestamp = most_recent"

    df = pd.read_sql(query, db)
    fig2, ax = plt.subplots(figsize=(15, 15))

    if len(df) > 0:
        print(df)
        coins = df['coin']
        print(coins)

        regplot = sns.lineplot(
            x=df['minutes_forward'],
            y=df['change_at_3sd'],
            data=df,
            hue=coins,
            ax=ax
        )

        plt.title(f"Change at 3sd vs Minutes Forward by Coin")
        plt.xlabel("Minutes Forward")
        plt.ylabel("Change at 3sd")

        regplot.legend()

        timestamp = int(time.time() * 1000)
        timestamp_string = datetime.datetime.strftime(datetime.datetime.fromtimestamp(timestamp / 1000), "%Y-%m-%d %Hh-%Mm")

        plt.savefig("Charts/Correlations/Change_at_3sds_Combined_{0}.png".format(timestamp_string))

        plt.show()


def analyse():

    while True:

        timestamp = int(time.time() * 1000)
        timestamp_string = datetime.datetime.strftime(datetime.datetime.fromtimestamp(timestamp / 1000), "%Y-%m-%d %Hh-%Mm")

        constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
        pairs_per_coin_limit = int(constants['pairs_per_coin'])

        db = mysql.connector.connect(
            host=os.environ.get("MYSQL_DATABASE_HOST"),
            user=os.environ.get("MYSQL_DATABASE_USER"),
            password=os.environ.get("MYSQL_DATABASE_PASSWORD"),
            database=os.environ.get("MYSQL_DATABASE_DB")
        )

        # try:
        #     coins = binance_api.get_wanted_coins(pairs_per_coin_limit)
        # except Exception as e:
        #     print("Error:", e)
        df = pd.read_sql("Select DISTINCT coin from crypto_db.statistics", db)
        print(df)
        coins = df['coin']

        rows = int(constants['moving_average_n'])

        print("Starting stats worker")

        for coin in coins:
            print(coin)
            for minute in range(2, 63):
                print(minute)
                _df = pd.DataFrame([])

                try:
                    query = f"SELECT a.coin, a.elo_rating, a.x_point_moving_average \
                    as x_point_moving_average_rating, \
                    (a.elo_rating - a.average_elo) / a.std_dev as elo_deviations,\
                            avg((a.elo_rating - a.average_elo) / a.std_dev) OVER (PARTITION \
                    BY a.coin ORDER BY a.end_time DESC ROWS BETWEEN {rows - 1} \
                    PRECEDING AND CURRENT ROW) AS \
                    `x_point_moving_average_deviations`,\
                    a.end_time as original_time,\
                    a.close_price as original_price,\
                    b.close_price as projected_price,\
                    (b.close_price * 100 / a.close_price) - 100 as \
                    price_change_percent,\
                    b.end_time as projected_time,\
                    (b.end_time - a.end_time) / 60000 as minutes_forward\
                    FROM crypto_db.price_elo_stats a\
                    join crypto_db.price_elo_stats b\
                    on (a.end_time + (60000 * {minute})) = b.end_time\
                    where a.coin = '{coin}'\
                    and b.coin = '{coin}'\
                    order by a.end_time desc"

                    # print(query)

                    df = pd.read_sql(query, db)

                    # print(df)

                    x_array = df['x_point_moving_average_deviations'].to_numpy()
                    y_array = df['price_change_percent'].to_numpy()

                    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(x_array, y_array)
                    change_at_3sd = (3 * slope) + intercept
                    datapoints = int(x_array.size)
                    stats = {
                        'coin': coin,
                        'minutes_forward': minute,
                        'slope': slope,
                        'intercept': intercept,
                        'r_value': r_value,
                        'p_value': p_value,
                        'std_err': std_err,
                        'change_at_3sd': change_at_3sd,
                        'datapoints': datapoints,
                        'timestamp': timestamp
                    }

                except Exception as e:
                    log_error(e)

        for coin in coins:
            print(coin)
            strongest_minute = read_coin_stats(coin).strongest_minute
            print(strongest_minute)

            fig2, ax = plt.subplots(figsize=(15, 15))

            query = f"SELECT a.coin, a.elo_rating, a.x_point_moving_average \
                                as x_point_moving_average_rating, \
                                (a.elo_rating - a.average_elo) / a.std_dev as elo_deviations,\
                                        avg((a.elo_rating - a.average_elo) / a.std_dev) OVER (PARTITION \
                                BY a.coin ORDER BY a.end_time DESC ROWS BETWEEN {rows - 1} \
                                PRECEDING AND CURRENT ROW) AS \
                                `x_point_moving_average_deviations`,\
                                a.end_time as original_time,\
                                a.close_price as original_price,\
                                b.close_price as projected_price,\
                                (b.close_price * 100 / a.close_price) - 100 as \
                                price_change_percent,\
                                b.end_time as projected_time,\
                                (b.end_time - a.end_time) / 60000 as minutes_forward\
                                FROM crypto_db.price_elo_stats a\
                                join crypto_db.price_elo_stats b\
                                on (a.end_time + (60000 * {strongest_minute})) = b.end_time\
                                where a.coin = '{coin}'\
                                and b.coin = '{coin}'\
                                order by a.end_time desc"

            # print(query)

            df = pd.read_sql(query, db)

            if len(df) > 0:

                # print(df)

                x_array = df['x_point_moving_average_deviations'].to_numpy()
                y_array = df['price_change_percent'].to_numpy()
                datapoints = x_array.size

                slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(x_array, y_array)
                change_at_3sd = (3 * slope) + intercept

                regplot = sns.regplot(
                    x=df['x_point_moving_average_deviations'],
                    y=df['price_change_percent'],
                    data=df,
                    line_kws={
                        'label': "ΔPrice(%) = {0:.2E}*(Elo-μ)/σ + {1:.2E},\nr = {2:.2E}, p = {3:.2E}, @3sd = {4:.2f}%".format(
                            slope,
                            intercept,
                            r_value,
                            p_value,
                            change_at_3sd)}
                )
                plt.title("{0} at {1} with {2} datapoints".format(coin, timestamp_string, datapoints))
                plt.xlabel('{0} Point Moving Average Elo Rating Deviations at Time t0'.format(rows))
                plt.ylabel('Price Change % {0} Minutes After t0 /USDT'.format(strongest_minute))
                ax.set_xlim(-3, 3)
                ax.set_ylim(-1.5, 1.5)

                regplot.legend()

                plt.savefig("Charts/Correlations/Correlation_Chart_Test_{1}_Point_Moving_Average_{0}.png".format(coin, rows))

        print('Ending stats worker')


def read_coin_stats(coin):
    db = mysql.connector.connect(
        host=os.environ.get("MYSQL_DATABASE_HOST"),
        user=os.environ.get("MYSQL_DATABASE_USER"),
        password=os.environ.get("MYSQL_DATABASE_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE_DB")
    )

    query = f"  with `a` as (SELECT *, min(`p`) OVER(PARTITION BY `coin`) as `min_p` from `statistics`) \
                select * from `a`\
                where `min_p` = `p`\
                and `coin` = '{coin}'"

    df = pd.read_sql(query, db)

    coin_stats = df.to_dict()

    # print(f"stats for {coin}:", coin_stats)

    if len(df) == 0:
        return cs(coin, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    else:
        return cs(
            coin=coin_stats['coin'][0],
            strongest_minute=coin_stats['minutes_forward'][0],
            slope=coin_stats['slope'][0],
            intercept=coin_stats['intercept'][0],
            r_value=coin_stats['r'][0],
            p_value=coin_stats['p'][0],
            std_err=coin_stats['std_err'][0],
            change_at_3sd=coin_stats['change_at_3sd'][0],
            datapoints=coin_stats['datapoints'][0],
            timestamp=coin_stats['timestamp'][0]
        )


def get_strongly_correlated_coins():
    constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
    pairs_per_coin_limit = int(constants['pairs_per_coin'])
    wanted_coins = binance_api.get_wanted_coins(pairs_per_coin_limit)

    strongly_correlated_coins = []
    for wanted_coin in wanted_coins:
        try:
            if read_coin_stats(wanted_coin).change_at_3sd > 0.1:
                strongly_correlated_coins.append(read_coin_stats(wanted_coin).coin)

        except Exception as e:
            print(e)
            log_error(e)
            continue

    return strongly_correlated_coins


def get_market_cap(df, row):
    date = df.loc[row.name, 'date']
    strongly_correlated_coins = get_strongly_correlated_coins()

    if row.name > 0:
        previous_date = df.loc[row.name - 1, 'date']
    else:
        previous_date = date

    if date != previous_date or row.name == 0:
        try:
            cg_coins = cg.get_coins()
            # print(cg_coins)
        except Exception as e:
            log_error(e)
            time.sleep(120)
            cg_coins = cg.get_coins()
            time.sleep(120)

        id_dicts = [{'symbol': coin['symbol'], 'id': coin['id']} for coin in cg_coins if
                    coin['symbol'].upper() in strongly_correlated_coins]
        market_data_list = []

        for id_dict in id_dicts:
            try:
                market_data = cg.get_coin_history_by_id(id_dict['id'], date)
                market_data_list.append(market_data)
            except Exception as e:
                log_error(e)
                time.sleep(120)
                market_data_list.append(cg.get_coin_history_by_id(id_dict['id'], date))
                time.sleep(120)

        market_cap_list = [{'symbol': market['symbol'], 'market_cap_usd': market['market_data']['market_cap']['usd']}
                           for
                           market in market_data_list]
        total_market_cap = sum([market_cap['market_cap_usd'] for market_cap in market_cap_list])

        return total_market_cap

    else:
        return 0.0


def replace_column_zeroes(df, row, column):
    for i in range(len(df)):
        # print("Replacing 0's, i =", i)
        # print("Replacing 0's, current =", df.loc[row.name, column])
        if df.loc[row.name, column] == 0 and row.name - i >= 0:
            # print("Replacing 0's, previous =", df.loc[row.name - i, column])
            if df.loc[row.name - i, column] != 0:
                return df.loc[row.name - i, column]

        else:
            return df.loc[row.name, column]


def create_pair_symbol_dict():
    constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
    pairs_per_coin_limit = int(constants['pairs_per_coin'])
    pairs = binance_api.get_pairs()
    pairs_per_coin = binance_api.get_pairs_per_coin(pairs)
    wanted_pairs = binance_api.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)
    pair_symbol_dict = {}

    for pair in wanted_pairs:
        symbol = pair.replace("-", "")
        pair_symbol_dict[symbol] = pair

    return pair_symbol_dict


def convert_symbol_to_pair(symbol, pair_symbol_dict):
    return pair_symbol_dict[symbol]


def multiprocess_statistical_analysis():
    if __name__ == 'statistical_analysis':
        p4 = mp.Process(target=analyse)
        p4.start()
