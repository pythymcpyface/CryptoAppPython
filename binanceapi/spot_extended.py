import datetime
import socket
import time

import numpy as np
import requests
import simplejson

import binanceapi.spot
import urls as u
from binanceapi.binance_response import BinanceResponse
from binanceapi.constant import RequestMethod, OrderSide, OrderType, Interval, AccountType
from utilities import save_file_trade, save_file_error, log_error


class BinanceSpotExtendedHttp(binanceapi.spot.BinanceSpotHttp):

    def __init__(self, api_key, secret, host=None, timeout=60, try_counts=3):
        super().__init__(api_key, secret, host, timeout, try_counts)

    def get_pairs(self):
        path = "/api/v3/exchangeInfo"
        pairs = np.array([])

        exchange_info = self.request(req_method=RequestMethod.GET, path=path)

        for symbol_info in exchange_info['symbols']:
            if symbol_info['status'] == 'TRADING':
                base_asset = symbol_info['baseAsset']
                quote_asset = symbol_info['quoteAsset']
                pair = "{0}-{1}".format(base_asset, quote_asset)
                pairs = np.append(pairs, pair)

        return pairs

    def get_symbols(self):
        path = "/api/v3/exchangeInfo"
        symbols = np.array([])

        exchange_info = self.request(req_method=RequestMethod.GET, path=path)

        for symbol_info in exchange_info['symbols']:
            if symbol_info['status'] == 'TRADING':
                symbols = np.append(symbols, symbol_info['symbol'])

        return symbols

    def get_pairs_per_coin(self, pairs):
        """ Gets the number of pairs each coin trades with. More pairs means a
        more accurate final Elo rating """

        pairs_per_coin = {}

        coin_arr = np.array([])

        for pair in pairs:
            coin1 = pair.split("-")[0]
            coin2 = pair.split("-")[1]
            coin_arr = np.append(coin_arr, coin1)
            coin_arr = np.append(coin_arr, coin2)

        for coin in coin_arr:
            coin_count = 0
            for pair in pairs:
                if pair.find(coin) >= 0:
                    coin_count += 1
            pairs_per_coin[coin] = coin_count

        return pairs_per_coin

    def get_wanted_pairs(self, pairs_per_coin, limit):
        """ Returns the pairs available from the exchange which use coins that
        have a number of pairs they trade with higher than that decided in the
        'limit' """

        wanted_coins = np.array([])
        wanted_pairs = np.array([])

        symbols = self.get_symbols()

        for coin in pairs_per_coin:
            if pairs_per_coin[coin] >= limit:
                wanted_coins = np.append(wanted_coins, coin)

        for coin_a in wanted_coins:
            for coin_b in wanted_coins:
                if coin_a + coin_b in symbols:
                    wanted_pairs = np.append(wanted_pairs, "{0}-{1}".format(coin_a, coin_b))

        return wanted_pairs

    def get_wanted_coins(self, limit):
        """ Wanted_coins list is created by getting all trading
        pairs from the binance info api and then appending each coin in the pair
        distinctly to a list as long as it trades with at least x number of other
        coins. Using a minimum trading pairs value means that the elo rating
        calculation is more accurate """

        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_coins = np.array([])

        for coin in pairs_per_coin:
            if pairs_per_coin[coin] >= limit:
                wanted_coins = np.append(wanted_coins, coin)

        return wanted_coins

    def request_extended(self, req_method: RequestMethod, path: str, requery_dict=None, verify=False):
        url = self.host + path

        if verify:
            query_str = self._sign(requery_dict)
            url += '?' + query_str
        elif requery_dict:
            url += '?' + self.build_parameters(requery_dict)
        headers = {"X-MBX-APIKEY": self.api_key}

        for i in range(0, self.try_counts):
            try:
                response = requests.request(req_method.value, url=url, headers=headers, timeout=self.timeout)
                if response.status_code in (429, 418):
                    log_error(BinanceResponse(response.json()['code'], response.json()['msg'], response.status_code,
                                              response.reason))
                    retry_after = int(response.headers["Retry-After"])
                    if retry_after is not None:
                        time.sleep(retry_after)
                    else:
                        time.sleep(60)
                elif response.status_code == 200:
                    return BinanceResponse(0, response.json(), response.status_code, response.reason)
                else:
                    return BinanceResponse(response.json()['code'], response.json()['msg'], response.status_code,
                                           response.reason)
            except Exception as error:
                log_error(error)
                print(f"Path:{path}, Error: {error}")

    def limit_sell_coin(self, symbols, current_coin, initial_price, expected_percent_change):
        """ Place a limit order to sell the current coin """

        symbol = f"{current_coin}USDT"
        flipped_flag = False
        current_coin_holdings = self.get_holdings(current_coin)
        stop_price = initial_price * (1 - (2 / 100))

        try:
            if symbol in symbols:
                # Symbol will probably always be correct here
                # Calculate the expected price based on the percent change from statistical analysis
                sell_price = initial_price * (1 + (expected_percent_change / 100))
                quantity_possible = round(float(current_coin_holdings * sell_price), 8)
                reason = f"Placing limit sell order for {symbol} at expected price of {sell_price}"

                self.place_order(
                    current_coin,
                    symbol=symbol,
                    order_side=OrderSide.SELL,
                    order_type=OrderType.STOP,
                    quantity=quantity_possible,
                    price=sell_price,
                    flipped=flipped_flag,
                    reason=reason,
                    stop_price=stop_price
                )

            elif symbol not in symbols:
                # Calculate the expected price based on the percent change from statistical analysis
                symbol = f"USDT{current_coin}"
                flipped_flag = True
                sell_price = initial_price * (1 - (expected_percent_change / 100))
                quantity_possible = round(current_coin_holdings, 8)
                reason = f"Placing limit sell order for {symbol} at expected price of {sell_price}"

                self.place_order(
                    current_coin,
                    symbol=symbol,
                    order_side=OrderSide.BUY,
                    order_type=OrderType.STOP,
                    quantity=quantity_possible,
                    price=sell_price,
                    flipped=flipped_flag,
                    reason=reason,
                    stop_price=stop_price
                )

        except Exception as e:
            log_error(e)

    def cancel_all_open_orders(self):
        # Get the ip address
        h_name = socket.gethostname()
        host = str(socket.gethostbyname(h_name))
        urls = u.Urls(host=host)
        constants = simplejson.loads(requests.get(url=urls.CONSTANTS).text)
        pairs_per_coin_limit = constants['pairs_per_coin']
        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        symbols = self.get_wanted_pairs(pairs_per_coin, pairs_per_coin_limit)

        for symbol in symbols:
            try:
                self.cancel_open_orders(symbol)
            except Exception as e:
                log_error(e)

    def market_buy_new_coin(self, symbols, current_coin, coin, reason, expected_percent_change):
        """ Place a market order for a coin """

        # Cancel all open orders first
        self.cancel_all_open_orders()

        symbol = "{0}{1}".format(current_coin, coin)
        flipped_flag = False

        # Get the quantity of the current coin which is held
        current_coin_holdings = self.get_holdings(current_coin)

        print("Symbol: {0}, Holdings: {1}".format(symbol, current_coin_holdings))

        if symbol not in symbols:
            # If symbol is not correct, then swap the coins in the symbol format
            print("symbol {0} not in symbols".format(symbol))
            symbol = "{0}{1}".format(coin, current_coin)
            flipped_flag = True

            if symbol in symbols:
                # Get this pair's price
                print("symbol {0} in symbols".format(symbol))
                coin_to_current_coin_price = round(float(self.get_latest_price(symbol=symbol)['price']), 8)
                quantity_possible = round(current_coin_holdings, 8)

                print("Price: {0}, Qty possible: {1}".format(coin_to_current_coin_price, quantity_possible))
                self.place_order(
                    current_coin,
                    symbol=symbol,
                    order_side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity_possible,
                    price=coin_to_current_coin_price,
                    flipped=flipped_flag,
                    reason=reason
                )

                # Wait 20 seconds to ensure coin is bought
                time.sleep(20)

                # Then place limit order to sell again
                self.limit_sell_coin(symbols, coin, coin_to_current_coin_price, expected_percent_change)
            else:
                print("Symbol {0} not valid for trading".format(symbol))
                raise Exception("Symbol {0} not valid for trading".format(symbol))

        else:
            print("symbol {0} in symbols".format(symbol))
            current_coin_to_coin_price = round(float(self.get_latest_price(symbol=symbol)['price']), 8)
            quantity_possible = round(float(current_coin_holdings * current_coin_to_coin_price), 8)
            print("Price: {0}, Qty possible: {1}".format(current_coin_to_coin_price, quantity_possible))
            self.place_order(
                current_coin,
                symbol=symbol,
                order_side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity_possible,
                price=current_coin_to_coin_price,
                flipped=flipped_flag,
                reason=reason
            )

            # Wait 20 seconds to ensure coin is bought
            time.sleep(20)

            # Then place limit order to sell again
            self.limit_sell_coin(symbols, coin, current_coin_to_coin_price, expected_percent_change)

    def market_buy_new_coin_invalid_symbol(self, symbols, current_coin, coin, reason, expected_percent_change):
        self.market_buy_new_coin(symbols, current_coin, "USDT", reason, expected_percent_change)
        time.sleep(20)
        self.market_buy_new_coin(symbols, "USDT", coin, reason, expected_percent_change)

    def place_order(self, current_coin: str, symbol: str, order_side: OrderSide, order_type: OrderType,
                    quantity: float,
                    price: float, flipped: bool, reason: str,
                    client_order_id: str = None, time_inforce="GTC", stop_price=0):
        """

        :param symbol: 交易对名称
        :param order_side: 买或者卖， BUY or SELL
        :param order_type: 订单类型 LIMIT or other order type.
        :param quantity: 数量
        :param price: 价格
        :param client_order_id: 用户的订单ID
        :param time_inforce:
        :param stop_price:
        :return:
        """

        path = '/api/v3/order'

        if client_order_id is None:
            client_order_id = self.get_client_order_id()

        current_coin_holdings = self.get_holdings(current_coin)

        price = round(float(self.get_latest_price(symbol=symbol)['price']), 8)

        if flipped:
            quantity = round(current_coin_holdings, 8)
        else:
            quantity = round((current_coin_holdings * price), 8)

        for i in range(1, 10):

            print("Placing {0} {1} order for {2} with {3} at price {4}".format(order_side, symbol, quantity,
                                                                               current_coin_holdings, price))

            save_file_trade(current_coin_holdings, symbol, order_side, order_type, quantity, price, reason)

            params = {
                "symbol": symbol,
                "side": order_side.value,
                "type": order_type.value,
                "quoteOrderQty": quantity,
                "price": price,
                "recvWindow": self.recv_window,
                "timestamp": self.get_current_timestamp(),
                "newClientOrderId": client_order_id
            }

            if order_type == OrderType.LIMIT:
                params['timeInForce'] = time_inforce

            if order_type == OrderType.MARKET:
                if params.get('price'):
                    del params['price']

            if order_type == OrderType.STOP:
                if stop_price > 0:
                    params["stopPrice"] = stop_price
                else:
                    raise ValueError("stopPrice must greater than 0")

            order = self.request_extended(RequestMethod.POST, path=path, requery_dict=params, verify=True)

            if order.response_code == 200:
                return order.binance_reason
            else:
                save_file_error(order.binance_code, order.binance_reason, order.response_code, order.response_reason)
                # Reduce quantity by 0.1% and retry
                quantity = round(quantity * (1 - (i / 1000)), 8)

    def place_order_test(self, current_coin: str, symbol: str, order_side: OrderSide, order_type: OrderType,
                         quantity: float,
                         price: float, flipped: bool, reason: str,
                         client_order_id: str = None, time_inforce="GTC", stop_price=0):
        """

        :param symbol: 交易对名称
        :param order_side: 买或者卖， BUY or SELL
        :param order_type: 订单类型 LIMIT or other order type.
        :param quantity: 数量
        :param price: 价格
        :param client_order_id: 用户的订单ID
        :param time_inforce:
        :param stop_price:
        :return:
        """

        path = '/api/v3/order/test'

        if client_order_id is None:
            client_order_id = self.get_client_order_id()

        current_coin_holdings = self.get_holdings(current_coin)

        price = round(float(self.get_latest_price(symbol=symbol)['price']), 8)

        if flipped:
            quantity = round(current_coin_holdings, 8)
        else:
            quantity = round((current_coin_holdings * price), 8)

        print("Placing {0} {1} order for {2} with {3} at price {4}".format(order_side, symbol, quantity,
                                                                           current_coin_holdings, price))

        save_file_trade(current_coin_holdings, symbol, order_side, order_type, quantity, price, reason)

        params = {
            "symbol": symbol,
            "side": order_side.value,
            "type": order_type.value,
            "quoteOrderQty": quantity,
            "price": price,
            "recvWindow": self.recv_window,
            "timestamp": self.get_current_timestamp(),
            "newClientOrderId": client_order_id
        }

        if order_type == OrderType.LIMIT:
            params['timeInForce'] = time_inforce

        if order_type == OrderType.MARKET:
            if params.get('price'):
                del params['price']

        if order_type == OrderType.STOP:
            if stop_price > 0:
                params["stopPrice"] = stop_price
            else:
                raise ValueError("stopPrice must greater than 0")

        order = self.request_extended(RequestMethod.POST, path=path, requery_dict=params, verify=True)

        if order.response_code == 200:
            return order.binance_reason
        else:
            save_file_error(order.binance_code, order.binance_reason, order.response_code, order.response_reason)

    def get_user_trades(self, symbol, start_time=1609459200000):

        path = "/api/v3/myTrades"
        params = {"startTime": start_time,
                  "timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window,
                  "symbol": symbol
                  }
        return self.request(RequestMethod.GET, path, params, verify=True)

    def get_user_orders(self, start_time, symbol):

        path = "/api/v3/allOrders"
        params = {"startTime": start_time,
                  "timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window,
                  "symbol": symbol
                  }
        return self.request(RequestMethod.GET, path, params, verify=True)

    def get_latest_trade(self, pairs_per_coin_limit):
        current_coin = self.get_current_coin(pairs_per_coin_limit)
        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_pairs = self.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

        user_trades_list = []
        for pair in wanted_pairs:
            if pair.find(current_coin) >= 0:
                symbol = pair.replace("-", "")
                try:
                    user_trades = sorted(self.get_user_trades(symbol=symbol), key=lambda d: d['time'])
                except Exception as e:
                    log_error(e)
                    print("Error getting last trade ", e)
                    user_trades = []

                if len(user_trades) > 0:
                    user_trades_list.append(user_trades[-1])

        return sorted(user_trades_list, key=lambda d: d['time'])[-1]

    def get_holdings(self, coin):
        """ Returns the quantity held of a specific coin """
        assets = self.get_account_info()['balances']

        if assets is None:
            holdings = 0.0
        else:
            holdings = round(float([d['free'] for d in assets if d["asset"] == coin][0]), 8)

        return holdings

    def get_total_holdings(self, pairs_per_coin_limit):
        """ Returns the total value in USDT of account """

        holdings_dict = {}
        symbols = np.array([])

        assets = self.get_account_info()['balances']

        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_pairs = self.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

        for pair in wanted_pairs:
            symbol = pair.replace("-", "")
            symbols = np.append(symbols, symbol)

        for asset in assets:
            coin = asset['asset']
            if coin == "USDT":
                value_in_usdt = round(float(asset['free']), 8)
            else:
                symbol = "{0}{1}".format(coin, "USDT")
                holdings = round(float(asset['free']), 8)

                if symbol not in symbols:
                    symbol = "{0}{1}".format("USDT", coin)

                    if symbol not in symbols:
                        value_in_usdt = 0.0

                    else:
                        value_in_usdt = round(1 / (float(self.get_latest_price(symbol=symbol)['price'])), 8) * holdings

                else:
                    value_in_usdt = round(float(self.get_latest_price(symbol=symbol)['price']), 8) * holdings

            holdings_dict[coin] = value_in_usdt

        return sum(holdings_dict.values())

    def get_latest_price(self, symbol):
        """
        :param symbol: 获取最新的价格.
        :return: {'symbol': 'BTCUSDT', 'price': '9168.90000000'}

        """
        path = "/api/v3/ticker/price"
        query_dict = {"symbol": symbol}

        price = self.request_extended(RequestMethod.GET, path, query_dict)

        if price.response_code == 200:
            return price.binance_reason
        else:
            return {'price': 0.0}

    def get_current_coin(self, pairs_per_coin_limit):
        """ Returns the coin which has the highest value held in USDT """

        holdings_dict = {}
        symbols = np.array([])

        assets = self.get_account_info()['balances']

        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_pairs = self.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

        for pair in wanted_pairs:
            symbol = pair.replace("-", "")
            symbols = np.append(symbols, symbol)

        for asset in assets:
            coin = asset['asset']
            if coin == "USDT":
                value_in_usdt = round(float(asset['free']), 8)
            else:
                symbol = "{0}{1}".format(coin, "USDT")
                holdings = round(float(asset['free']), 8)

                if symbol not in symbols:
                    symbol = "{0}{1}".format("USDT", coin)

                    if symbol not in symbols:
                        value_in_usdt = 0.0

                    else:
                        value_in_usdt = round(1 / (float(self.get_latest_price(symbol=symbol)['price'])), 8) * holdings

                else:
                    value_in_usdt = round(float(self.get_latest_price(symbol=symbol)['price']), 8) * holdings

            holdings_dict[coin] = value_in_usdt

        current_coin = max(zip(holdings_dict.values(), holdings_dict.keys()))[1]

        return current_coin

    def get_agg_trades(self, pair, start_time, end_time, limit=500):
        """
        Returns aggregate trades in the form of kLine for a pair between time
        interval
        :param pair: The trading pair
        :param start_time: Beginning of aggregate trade
        :param end_time: End of aggregate trade time
        :param limit: Data to return
        """
        path = "/api/v3/aggTrades"
        params = {"symbol": pair.replace('-', ""),
                  "startTime": start_time,
                  "endTime": end_time,
                  "limit": limit
                  }
        # print(f"params = {params}, {self.request(RequestMethod.GET, path, params)}")
        return self.request(RequestMethod.GET, path, params)

    def get_account_snapshot(self, account_type: AccountType, start_time: int, end_time: int):

        path = "/sapi/v1/accountSnapshot"

        params = {"type": account_type,
                  "startTime": start_time,
                  "endTime": end_time,
                  "recvWindow": self.recv_window,
                  "timestamp": self.get_current_timestamp()
                  }

        return self.request(RequestMethod.GET, path, params, verify=True)

    def get_vol_diffs(self, minutes, interval_in_minutes, pairs_per_coin_limit):
        """ Gets the volume differences for a 'wanted coins' between a time
        interval """

        today = datetime.datetime.utcfromtimestamp(self.get_current_timestamp() / 1000).replace(second=0, microsecond=0)
        epoch = datetime.datetime.utcfromtimestamp(0)
        start_time = int(((today - datetime.timedelta(minutes=minutes) - epoch).total_seconds() * 1000.0))

        millis_in_min = 1000 * 60

        vol_diff_list = []
        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_pairs = self.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

        for minute in range(int(minutes / interval_in_minutes)):

            for pair in wanted_pairs:

                end_time = int(start_time + (millis_in_min * interval_in_minutes))

                try:
                    trade_data = self.get_agg_trades(pair, start_time, end_time, 100)
                except Exception as e:
                    log_error(e)
                    print(f"Error in vol_diffs {e}")
                    time.sleep(millis_in_min)
                    trade_data = self.get_agg_trades(pair, start_time, end_time, 1000)

                buy_volume = 0
                sell_volume = 0

                for trade_entry in trade_data:
                    if trade_entry['m']:
                        buy_volume += np.double(trade_entry['q'])

                    elif not trade_entry['m']:
                        sell_volume += np.double(trade_entry['q'])

                volume_diff = buy_volume - sell_volume

                vol_diff_object = {
                    "pair": pair,
                    "start_time": start_time,
                    "end_time": end_time,
                    "vol_diff": volume_diff
                }

                vol_diff_list = np.append(vol_diff_list, vol_diff_object)

            start_time += millis_in_min * interval_in_minutes

        return vol_diff_list

    def convert_vol_diffs_to_pair_dict(self, vol_diff_list):
        """ Converts the volume difference dictionary from 'get_vol_diffs'
        method into a pair_dict so that it can be converted into Elo ratings.
        This is legacy from the original code and works correctly so made
        sense to continue the pair_dict -> Elo conversion """
        pair_dict = {}
        times = self.getTimes(vol_diff_list)
        pair_dict['timestamps'] = times

        for vol_diff_entry in vol_diff_list:
            pair = vol_diff_entry['pair']
            start_time = vol_diff_entry['start_time']
            end_time = vol_diff_entry['end_time']
            vol_diff = vol_diff_entry['vol_diff']

            if pair is not None and start_time is not None and end_time is not None and vol_diff is not None:

                if pair not in pair_dict:
                    pair_dict[pair] = np.full((len(times)), 0.0)

                for timestamp in pair_dict['timestamps']:
                    position = np.where(pair_dict['timestamps'] == timestamp)[0]

                    if end_time == timestamp:
                        pair_dict[pair][position] = vol_diff

        return pair_dict

    def get_prices(self, quote_pair, minutes, interval_in_minutes, pairs_per_coin_limit):
        """ Gets prices for a set of trading pairs between two timestamps with
        given interval """

        interval = self.get_interval(interval_in_minutes)

        today = datetime.datetime.utcfromtimestamp(self.get_current_timestamp() / 1000).replace(second=0, microsecond=0)
        millis_in_min = 1000 * 60
        epoch = datetime.datetime.utcfromtimestamp(0)
        start_time = int(((today - datetime.timedelta(minutes=minutes)) - epoch).total_seconds() * 1000.0)
        end_time = int(start_time + (millis_in_min * minutes))

        price_dict = {}
        price_list = np.array([])
        price_dict['timestamps'] = np.array([])
        iteration = 0

        pairs = self.get_pairs()
        pairs_per_coin = self.get_pairs_per_coin(pairs)
        wanted_pairs = self.get_wanted_pairs(pairs_per_coin, limit=pairs_per_coin_limit)

        for pair in wanted_pairs:
            if (pair.find("-") >= 0) and ((pair.split("-")[1]).upper() == quote_pair.upper()):
                price_dict[pair] = np.array([])
                symbol = pair.replace("-", "")

                kline = self.get_kline(symbol, interval, start_time, end_time)

                for i in range(len(kline)):
                    timestamp = datetime.datetime.utcfromtimestamp(kline[i][0] / 1000)
                    open_time = kline[i][0]
                    close_time = kline[i][6]
                    open_price = kline[i][1]
                    close_price = kline[i][4]
                    price_dict[pair] = np.append(price_dict[pair], close_price)

                    price_list_entry = {
                        "pair": pair,
                        "start_time": open_time,
                        "end_time": close_time,
                        "open_price": open_price,
                        "close_price": close_price
                    }

                    price_list = np.append(price_list, price_list_entry)
                    if iteration == 0:
                        price_dict['timestamps'] = np.append(price_dict['timestamps'], timestamp)

                iteration += 1

        return price_list

    def getTimes(self, vol_diff_list):
        """ Gets the set of start times from the volume differences """
        times = np.array([])
        for vol_diff in vol_diff_list:
            time = vol_diff['end_time']
            if len(np.where(times == time)[0]) == 0 and time is not None:
                times = np.append(times, time)

        return np.sort(times)

    def getPairs(self, vol_diff_list):
        """ Gets the set of pairs from the volume differences """
        pairs = np.array([])
        for vol_diff in vol_diff_list:
            pair = vol_diff['pair']
            if len(np.where(pairs == pair)[0]) == 0 and pair is not None:
                pairs = np.append(pairs, pair)

        return pairs

    def get_interval(self, interval_in_minutes):
        """ Converts an integer in minutes into an Interval enum """

        if interval_in_minutes == 1:
            return Interval.MINUTE_1
        elif interval_in_minutes == 3:
            return Interval.MINUTE_3
        elif interval_in_minutes == 5:
            return Interval.MINUTE_5
        elif interval_in_minutes == 10:
            return Interval.MINUTE_10
        elif interval_in_minutes == 15:
            return Interval.MINUTE_15
        elif interval_in_minutes == 30:
            return Interval.MINUTE_30
        elif interval_in_minutes == 60:
            return Interval.HOUR_1
        elif interval_in_minutes == 120:
            return Interval.HOUR_2
