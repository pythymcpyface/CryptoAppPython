import csv
import datetime
import logging
import pickle

from binanceapi.constant import OrderSide, OrderType


def save_file_api(dict_list, api_type):
    """ Saves the response data from binance api in a .csv file """

    now = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %Hh-%Mm")
    keys = dict_list[0].keys()
    with open('Api_Response_{0}_{1}.csv'.format(api_type, now), 'w', newline='') as file:
        dict_writer = csv.DictWriter(file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(dict_list)


def save_file_trade(current_coin_holdings: float, symbol: str, order_side: OrderSide, order_type: OrderType,
                    quantity: float, price: float, reason: str):
    """ Saves the trade information in a .txt file """

    now = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %Hh-%Mm")
    file = open("Logs/Order_Log.txt", "a")
    file.write(
        f"Placed order {now}: "
        f"holding = {current_coin_holdings}, "
        f"symbol = {symbol}, "
        f"side = {order_side}, "
        f"type = {order_type}, "
        f"qty = {quantity}, "
        f"price = {price}, "
        f"reason = {reason}\n"
    )


def save_file_error(binance_code: int, binance_reason: str, response_code: int, response_reason: str):
    """ Saves the error information in a .txt file """

    now = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %Hh-%Mm")
    file = open("Logs/Order_Log.txt", "a")
    file.write(
        f"Error returned {now}: "
        f"Binance code = {binance_code}, "
        f"Binance reason = {binance_reason}, "
        f"Response code = {response_code}, "
        f"Response reason = {response_reason}\n"
    )

    print(f"Error logged: "
          f"Error returned {now}: "
          f"Binance code = {binance_code}, "
          f"Binance reason = {binance_reason}, "
          f"Response code = {response_code}, "
          f"Response reason = {response_reason}")


def log_error(error_message):
    logging.basicConfig(filename='Logs/Error_Log.log',
                        level=logging.DEBUG,
                        format='%(asctime)s %(message)s',
                        datefmt='%Y-%m-%d %Hh-%Mm-%Ss')
    logging.debug(f"{error_message}\n")
