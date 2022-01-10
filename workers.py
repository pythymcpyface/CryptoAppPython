import multiprocessing as mp
import socket
import time

import numpy as np
import requests
import simplejson

import elo
import urls as u
from binanceapi import spot_extended
from binanceapi.constant import Interval
from statistical_analysis import get_strongly_correlated_coins, read_coin_stats
from utilities import log_error


def bot_worker(binance_key, binance_secret):
    """ Gets the current coin from Binance i.e. the one with the most value and
        checks if its value against USDT has increased by x% since either the time
        it was bought or 5 minutes before the bot was started. If it has
        increased by x% then the bot sells it back into USDT. USDT is used in this
        sense because it is a likely fiat currency to ultimately withdraw into.
        The Elo rating of each coin in the SQL table `crypto`.`db`.`elo` (posted by
        the elo_worker) is taken via the `crypto_db`.`elo_stats` view. This view
        takes the data for each interval in the `crypto`.`db`.`elo` table, averages
        it across the entire interval, calculates the standard deviation across each
        interval and then calculates the upper and lower limits using the standard
        deviation multiplied by a constant (defined in the constants table) as
        explained in the elo_worker.
        With the elo data the bot checks if any coin has a rating higher or lower
        than the upper or lower limit respectively indicating popularity or
        unpopularity. With this information it will then attempt to buy or sell that
        coin. Once a trade has occured a timer is set and the bot checks at the
        beginning of each loop if the coin's value against USDT has gone above x% as
        described above """

    # Instantiate Binance api
    binance_api = spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)

    symbol_dicts = binance_api.get_exchange_info()['symbols']
    symbols = [symbol_dict['symbol'] for symbol_dict in symbol_dicts]

    while True:
        # Loops every y minutes to get the current_coin and Elo data then check
        # if any other coin has an Elo rating higher or lower than the
        # statistical limit

        # Elo stats data always uses the minutes constant in the SQL table
        # because it is coded into the SQL query itself
        try:
            print("Starting bot worker")

            # Get the ip address
            h_name = socket.gethostname()
            host = str(socket.gethostbyname(h_name))
            urls = u.Urls(host=host)

            # Get a list of only the coins which have a good statistical correlation
            strongly_correlated_coins = get_strongly_correlated_coins()

            # Gets the constants every loop
            constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
            pairs_per_coin_limit = constants['pairs_per_coin']

            # Get the latest trade
            latest_trade = binance_api.get_latest_trade(pairs_per_coin_limit)
            trade_time = latest_trade['time']

            # Get the user's current coin
            current_coin = binance_api.get_current_coin(pairs_per_coin_limit)
            now = time.time() * 1000

            # New minutes value is calculated each loop based off last trade
            minutes = int((now - trade_time) / 60000)

            # TODO: Update to use base asset from constants table instead?

            # if current_coin in strongly_correlated_coins:
            #     # Get the last entry from the price change (it's ordered ascending so
            #     # the last one is the earliest entry and gives the percent change since
            #     # x minutes ago)
            #     # Returns the change in price as a percent of price at x minutes ago
            #     # of the current coin if it is not USDT
            #
            #     try:
            #         pair="{0}-USDT".format(current_coin)
            #         end_time = int(trade_time)
            #         start_time = int(trade_time - (60 * 1000))
            #         # print(f"pair = {pair}, end_time = {trade_time}, start_time = {trade_time - (60 * 1000)}")
            #         initial_current_coin_usdt_price = float(binance_api.get_kline(
            #             symbol="{0}USDT".format(current_coin),
            #             interval=Interval.MINUTE_1,
            #             end_time=end_time,
            #             start_time=start_time
            #         )[0][4])
            #         current_coin_usdt_price = float(
            #             binance_api.get_latest_price("{0}USDT".format(current_coin))['price'])
            #         current_coin_price_percent_change = (100 * current_coin_usdt_price / initial_current_coin_usdt_price) - 100
            #         # print(f"current_coin_price_percent_change = {current_coin_price_percent_change}")
            #     except Exception as e:
            #         log_error(f"Failed to get price change due to: {e}")
            #         price_stats = simplejson.loads(requests.get(
            #             url=urls.PRICE_STATS,
            #             params={'pair': current_coin, 'minutes': minutes}
            #         ).text)[-1]
            #         initial_current_coin_usdt_price = 0.0
            #         current_coin_usdt_price = 0.0
            #         current_coin_price_percent_change = price_stats['price_change_percent']
            #
            #     #  Get expected percent change based on statistics or constants table
            #     try:
            #         percent_change = read_coin_stats(current_coin).change_at_3sd
            #         # print(f"percent_change = {percent_change}")
            #     except Exception as e:
            #         log_error(e)
            #         percent_change = constants['percent_change']
            #
            #     if current_coin_price_percent_change > percent_change:
            #         # If the percent change since x minutes ago is above y% as
            #         # defined in the constants table then sell the coin into USDT
            #         reason = f"Price percent change for {current_coin} is {current_coin_price_percent_change}" \
            #                  f" which is above limit of {percent_change}, initial price was {initial_current_coin_usdt_price}, current price is {current_coin_usdt_price}"
            #         try:
            #             binance_api.market_buy_new_coin(symbols, current_coin, "USDT", reason)
            #         except Exception as e:
            #             log_error(e)
            #             # print("Error in price stats: {0}".format(e))

            # Get the Elo ratings for each coin for the last time interval
            elo_stats = simplejson.loads(requests.get(url=urls.ELO_STATS).text)
            # print(f"elo_stats = {elo_stats}")

            if len(elo_stats) > 0:
                for elo_stats_entry in elo_stats:
                    # Loop through each coin and check its Elo rating
                    try:
                        coin = elo_stats_entry["coin"]

                        if coin in strongly_correlated_coins:
                            elo_rating = elo_stats_entry["moving_average"]
                            lower_limit = elo_stats_entry["lower_limit"]
                            upper_limit = elo_stats_entry["upper_limit"]

                            # Returns the change in price as a percent of price at
                            # x minutes ago for the coin in the loop
                            try:
                                end_time = int(trade_time)
                                start_time = int(trade_time - (60 * 1000))
                                initial_coin_usdt_price = float(binance_api.get_kline(
                                    symbol="{0}USDT".format(coin),
                                    interval=Interval.MINUTE_1,
                                    end_time=end_time,
                                    start_time=start_time
                                )[0][4])
                                coin_usdt_price = float(binance_api.get_latest_price("{0}USDT".format(coin))['price'])
                                coin_price_percent_change = (100 * coin_usdt_price / initial_coin_usdt_price) - 100
                            except Exception as e:
                                log_error(f"Failed to get price change due to: {e}")
                                price_stats = simplejson.loads(requests.get(
                                    url=urls.PRICE_STATS,
                                    params={'pair': coin, 'minutes': minutes}
                                ).text)[-1]
                                initial_coin_usdt_price = 0.0
                                coin_usdt_price = 0.0
                                coin_price_percent_change = price_stats['price_change_percent']

                            #  Get expected percent change based on statistics or constants table
                            try:
                                percent_change = read_coin_stats(coin).change_at_3sd
                            except Exception as e:
                                print(e)
                                log_error(e)
                                percent_change = constants['percent_change']

                            print(
                                "Elo: {0:.2f}, Elo Limits: {1:.2f}-{2:.2f}, Coin: {3}, Initial Price: ${4:.2f}, Current Price: ${5:.2f}, Price Change: {6:.3f}%, "
                                "Price Limit: {7:.3f}% Current Coin: {8}".format(
                                    elo_rating, lower_limit, upper_limit, coin, initial_coin_usdt_price,
                                    coin_usdt_price, coin_price_percent_change, percent_change,
                                    current_coin))

                            if elo_rating > upper_limit and coin != current_coin:
                                # Elo rating of this coin is above limit and is
                                # therefore popular, increase in value expected
                                reason = f"Elo rating for {coin} is {elo_rating} which is above upper limit " \
                                         f"of {upper_limit}"
                                print(reason)

                                try:
                                    # Buy this coin by selling the currently held coin
                                    binance_api.market_buy_new_coin(symbols, current_coin, coin, reason, percent_change)
                                    break

                                except Exception as e:
                                    log_error(e)
                                    # An error occurred, potentially because there is
                                    # no trading pair between the currently held coin
                                    # and the coin with the high rating
                                    print("Error in trading above rating: {0}".format(e))

                                    try:
                                        # Try selling the currently held coin into USDT,
                                        # then the USDT into the coin with the high
                                        # rating. Most coins trade with USDT
                                        binance_api.market_buy_new_coin_invalid_symbol(symbols, current_coin, coin, reason, percent_change)
                                        break

                                    except Exception as e:
                                        log_error(e)
                                        print("Error in trading above rating: {0}".format(e))

                            elif elo_rating < lower_limit and coin == current_coin:
                                # Elo rating of the currently held coin is below limit
                                # and is therefore unpopular, decrease in value expected
                                reason = f"Elo rating for {current_coin} is {elo_rating} which is below lower " \
                                         f"limit of {lower_limit}"
                                print(reason)

                                try:
                                    # Sell currently held coin into USDT
                                    binance_api.market_buy_new_coin(symbols, current_coin, "USDT", reason, percent_change)
                                    break

                                except Exception as e:
                                    log_error(e)
                                    print("Error in trading below rating: {0}".format(e))

                    except Exception as e:
                        log_error(e)
                        print("Error in trading: {0}".format(e))

                # Wait some time but not necessarily the x minutes defined in the
                # constants table because this for loop takes a while to complete

        except Exception as e:
            log_error(e)
            print("Error in bot worker: {0}".format(e))

        # Get the ip address
        h_name = socket.gethostname()
        host = str(socket.gethostbyname(h_name))
        urls = u.Urls(host=host)

        # Gets constants each loop so it can be editted live
        constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
        time.sleep(60 * (constants['minutes']))

        print("Ending bot worker")


def elo_worker(binance_key, binance_secret):
    """ Takes the trade volume data for each pair in the 'wanted_coins list'.
        Pairs are calculated by concatenating every coin in the list against every
        other coin. Volume difference is calculated by comparing the volumes traded
        in each pair. The get_vol_diffs method calculates this for the time between
        *now* and y minutes ago with interval of z minutes (usually will be the
        same as y). This data is then posted to the SQL table
        `crypto`.`db`.`vol_diff`.
        A higher volume than the other coin means higher popularity
        meaning that this coin effectively 'won' the pair while the other coin
        'lost'. It is possible to then apply a 1v1 gaming rating to this result,
        namely the 'Elo' rating system. Applying this across all pairs across each
        time interval means it is possible to compare all coins in the system
        against each other in a normal distribution - higher rating = higher
        popularity and vice versa. It also means that it is possible to apply
        statistical analysis to the distribution of ratings, namely averages (m) and
        standard deviations (SD). By definition in the Elo system 1500 is always the
        average. A rating of m + 3*SD (and vice versa m - 3*SD) has a 97.6% chance
        of occuring naturally, therefore it can said to be statistically
        significant. Plotting the progression of ratings for all coins across each
        interval means it is possible to pinpoint when a coin has become popular or
        unpopular to the point of statistical significance and this can be used to
        monitor which coins to buy or sell. The method of comparing each coin
        simultaneously also gives us the insight into the whole system of
        cryptocurrencies rather than a single pair like with most trading
        indicators. The Elo rating for each coin at each interval is calculated in
        the get_elos method and posted to the SQL table `crypto`.`db`.`elo` """

    binance_api = spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)

    # Instantiate Elo class object
    _elo = elo

    while True:
        print("Starting elo worker")
        # Loop every y minutes to gather vol_diff data then apply elo ratings,
        # then posts this to SQL

        # Get the ip address
        h_name = socket.gethostname()
        host = str(socket.gethostbyname(h_name))
        urls = u.Urls(host=host)

        # Gets constants each loop so it can be editted live
        constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
        minutes = constants['minutes']
        pairs_per_coin_limit = constants['pairs_per_coin']

        try:
            # Get the volume differences for each pair
            vol_diffs = binance_api.get_vol_diffs(minutes, minutes, pairs_per_coin_limit)

            # Put data in table
            for vol_diff_entry in vol_diffs:
                requests.post(url=urls.VOL_DIFF, data=vol_diff_entry)

            # Retrieve the data back
            all_vol_diffs = simplejson.loads(requests.get(
                url=urls.VOL_DIFF,
                # params = {"start_time": start_time, "end_time": end_time}
            ).text)

            # If there is data then calculate Elo ratings
            if len(all_vol_diffs) > 0:
                # Pair dict is just a legacy method of calculating Elo ratings, don't want to touch as it works
                pair_dict = binance_api.convert_vol_diffs_to_pair_dict(all_vol_diffs)
                elos = _elo.get_elos(pair_dict)

                # Retrieve all Elo data
                all_elos = simplejson.loads(requests.get(
                    url=urls.ELO
                ).text)

                elo_coin_time_dict = {}

                # Build dictionary containing all the coin:end_times
                for elo_entry in all_elos:
                    elo_coin = elo_entry['coin']
                    elo_end_time = elo_entry['end_time']

                    if elo_coin not in elo_coin_time_dict:
                        elo_coin_time_dict[elo_coin] = np.array([])

                    elo_coin_time_dict[elo_coin] = np.append(elo_coin_time_dict[elo_coin], elo_end_time)

                # Check if coin end_time is already in table and if it isn't, post it
                for elo_entry in elos:
                    new_elo_coin = elo_entry['coin']
                    new_elo_end_time = elo_entry['end_time']

                    try:
                        if (len(np.where(elo_coin_time_dict[new_elo_coin] == new_elo_end_time)[0]) == 0) or (
                                new_elo_coin not in elo_coin_time_dict):
                            # This end_time for this coin is not in the table so post it into table
                            requests.post(
                                url=urls.ELO,
                                data=elo_entry)

                    except Exception as e:
                        print(e)
                        log_error(e)
                        requests.post(
                            url=urls.ELO,
                            data=elo_entry)

        except Exception as e:
            log_error(e)
            print("Error in elo worker: {0}".format(e))

        time.sleep(60 * minutes)

        print("Ending elo worker")


def price_worker(binance_key, binance_secret):
    """ Takes the prices for each coin in the 'wanted_coins list' against
    a base asset. Only gets the prices from *now* to y minutes
    ago where y is the second argument in the method get_prices. The third
    argument is the interval to break the price response up into between the
    date ranges. Once the price data has been received, this worker then posts
    them to the SQL database `crypto`.`db`.`price` and waits y minutes before
    looping """

    binance_api = spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)

    while True:
        # Loops every y minutes to get price data from binance then post to SQL

        # Get the ip address
        h_name = socket.gethostname()
        host = str(socket.gethostbyname(h_name))
        urls = u.Urls(host=host)

        # Gets constants each loop so it can be editted live
        constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
        minutes = constants['minutes']
        pairs_per_coin_limit = constants['pairs_per_coin']

        try:
            print("Starting price worker")
            # TODO: Implement base asset and trading pairs from constants table
            # Calculate prices for all coins against base
            prices = binance_api.get_prices("USDT", minutes, minutes, pairs_per_coin_limit)

            # Retrieve all price data
            all_prices = simplejson.loads(requests.get(
                url=urls.PRICE
            ).text)

            price_pair_time_dict = {}

            # Build dictionary containing all the pair:end_times
            for price_entry in all_prices:
                price_pair = price_entry['pair']
                price_end_time = price_entry['end_time']

                if price_pair not in price_pair_time_dict:
                    price_pair_time_dict[price_pair] = np.array([])

                price_pair_time_dict[price_pair] = np.append(price_pair_time_dict[price_pair], price_end_time)

            # Check if pair end_time is already in table and if it isn't, post it
            for price_entry in prices:
                new_price_pair = price_entry['pair']
                new_price_end_time = price_entry['end_time']

                try:

                    if (len(np.where(price_pair_time_dict[new_price_pair] == new_price_end_time)[0]) == 0) or (
                            new_price_pair not in price_pair_time_dict):
                        # This end_time for this pair is not in the table so post it into table
                        requests.post(
                            url=urls.PRICE,
                            data=price_entry)

                except Exception as e:
                    print(e)
                    log_error(e)
                    requests.post(
                        url=urls.PRICE,
                        data=price_entry)

        except Exception as e:
            log_error(e)
            print("Error in price worker: {0}".format(e))

        time.sleep(60 * minutes)

        print("Ending price worker")


def multiprocess_workers(binance_key, binance_secret):
    if __name__ == 'workers':
        p1 = mp.Process(target=elo_worker, args=(binance_key, binance_secret))
        p2 = mp.Process(target=price_worker, args=(binance_key, binance_secret))
        p3 = mp.Process(target=bot_worker, args=(binance_key, binance_secret))

        p1.start()
        p2.start()
        p3.start()
