import datetime
import os

import simplejson
from dotenv import load_dotenv
from flask import Flask, request
from flask_restful import Resource, Api
from flask_restful import reqparse
from flaskext.mysql import MySQL

import binanceapi.spot_extended

# load dotenv
load_dotenv()

mysql = MySQL()
app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = os.environ.get("MYSQL_DATABASE_USER")
app.config['MYSQL_DATABASE_PASSWORD'] = os.environ.get("MYSQL_DATABASE_PASSWORD")
app.config['MYSQL_DATABASE_DB'] = os.environ.get("MYSQL_DATABASE_DB")
app.config['MYSQL_DATABASE_HOST'] = os.environ.get("MYSQL_DATABASE_HOST")

# Binance configurations
binance_key = os.environ.get("BINANCE_KEY")
binance_secret = os.environ.get("BINANCE_SECRET")

mysql.init_app(app)

api = Api(app)


class Elo(Resource):
    """ Elo table endpoints to get and post data. SQL table used is
    `crypto_db`.`elo`. Get request queries data from SQL table and converts
    data to a dictionary """

    def get(self):
        try:
            _start_time = request.args.get('start_time')
            _end_time = request.args.get('end_time')
            _coin = request.args.get('coin')

            binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)
            today = datetime.datetime.utcfromtimestamp(binance_api.get_current_timestamp() / 1000).replace(second=0,
                                                                                                           microsecond=0)
            millis_in_min = 1000 * 60
            epoch = datetime.datetime.utcfromtimestamp(0)
            elo_start_time = int(((today - datetime.timedelta(minutes=60) - epoch).total_seconds() * 1000.0))

            if request.args.get('coin') is None and request.args.get('start_time') is None and request.args.get(
                    'end_time') is None:
                _start_time = elo_start_time
                get_query = "SELECT DISTINCT `coin`, `start_time`, `elo_rating`, `end_time` FROM `elo` WHERE `start_time` >= {0}".format(
                    _start_time)

            elif request.args.get('start_time') is None:
                _start_time = elo_start_time

            elif request.args.get('coin') is None:
                get_query = "SELECT DISTINCT `coin`, `start_time`, `elo_rating`, `end_time` \
                FROM `elo` WHERE `start_time` >= {0} AND `end_time` <= {1}".format(_start_time, _end_time)

            elif request.args.get('end_time') is None:
                get_query = "SELECT DISTINCT `coin`, `start_time`, `elo_rating`, `end_time` \
                FROM `elo` WHERE `coin` = {0} AND `start_time` >= {1}".format(_coin, _start_time)

            else:
                get_query = "SELECT DISTINCT `coin`, `start_time`, `elo_rating`, `end_time` \
                FROM `elo` WHERE `coin` = {0} AND `start_time` >= {1} AND \
                `end_time` <= {2}".format(_coin, _start_time, _end_time)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {}
                dict["coin"] = entry[0]
                dict["start_time"] = entry[1]
                dict["elo_rating"] = entry[2]
                dict["end_time"] = entry[3]
                dict_list.append(dict)
            # save_file_api(dict_list, "elo")
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}

    def post(self):
        try:
            # Parse the arguments
            parser = reqparse.RequestParser()
            parser.add_argument('coin', type=str, help='Cryptocurrency symbol')
            parser.add_argument('start_time', type=int, help='Start time of elo calculation')
            parser.add_argument('end_time', type=int, help='End time of elo calculation')
            parser.add_argument('elo_rating', type=float, help='Elo rating for cryptocurrency')

            args = parser.parse_args()

            _coin = args['coin']
            _start_time = args['start_time']
            _end_time = args['end_time']
            _elo_rating = args['elo_rating']

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('spInsertElo', (_coin, _start_time, _elo_rating, _end_time))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return {'statusCode': '200', 'message': 'Elo entry inserted'}
            else:
                return {'statusCode': '1000', 'message': str(data[0])}

        except Exception as e:
            return {'error': str(e)}


class EloStats(Resource):
    """ Elo statistics endpoint to get data from SQL table `crypto_db`.`elo` via
    view `crypto_db`.`elo_stats`. Get request queries data and converts
    data to a dictionary """

    def get(self):
        try:
            _start_time = request.args.get('start_time')
            _end_time = request.args.get('end_time')
            _coin = request.args.get('coin')

            binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)
            today = datetime.datetime.utcfromtimestamp(binance_api.get_current_timestamp() / 1000).replace(second=0,
                                                                                                           microsecond=0)
            millis_in_min = 1000 * 60
            epoch = datetime.datetime.utcfromtimestamp(0)
            elo_start_time = int(((today - datetime.timedelta(minutes=6000) - epoch).total_seconds() * 1000.0))

            if request.args.get('coin') is None and request.args.get('start_time') is None and request.args.get(
                    'end_time') is None:
                _start_time = elo_start_time
                get_query = "with `f` as (\
                            select * from elo_stats_2) \
                            select distinct	`f`.`coin`,\
                                    `f`.`start_time`,\
                                    `f`.`elo_rating`,\
                                    `f`.`end_time`,\
                                    `e`.`average_elo`,\
                                    `e`.`std_dev`,\
                                    `e`.`lower_limit`,\
                                    `e`.`upper_limit`,\
                                    `f`.`moving_average`\
                            from `f`\
                            join `elo_stats` `e`\
                            on `e`.`end_time` = `f`.`end_time`\
                            and `e`.`coin` = `f`.`coin`\
                            where `e`.`end_time` = \
                            (select `end_time` from `elo` order by `end_time` desc limit 1)\
                            and `f`.`start_time` >= {0}".format(_start_time)

            elif request.args.get('start_time') is None:
                _start_time = elo_start_time

            elif request.args.get('coin') is None:
                get_query = "with `f` as (\
                            select * from elo_stats_2) \
                            select distinct	`f`.`coin`,\
                                    `f`.`start_time`,\
                                    `f`.`elo_rating`,\
                                    `f`.`end_time`,\
                                    `e`.`average_elo`,\
                                    `e`.`std_dev`,\
                                    `e`.`lower_limit`,\
                                    `e`.`upper_limit`,\
                                    `f`.`moving_average`\
                            from `f`\
                            join `elo_stats` `e`\
                            on `e`.`end_time` = `f`.`end_time`\
                            and `e`.`coin` = `f`.`coin`\
                            where `e`.`end_time` = \
                            (select `end_time` from `elo` order by `end_time` desc limit 1)\
                             and `f`.`start_time` >= {0} \
                 AND `f`.`end_time` <= {1}".format(_start_time, _end_time)

            elif request.args.get('end_time') is None:
                get_query = "with `f` as (\
                            select * from elo_stats_2) \
                            select distinct	`f`.`coin`,\
                                    `f`.`start_time`,\
                                    `f`.`elo_rating`,\
                                    `f`.`end_time`,\
                                    `e`.`average_elo`,\
                                    `e`.`std_dev`,\
                                    `e`.`lower_limit`,\
                                    `e`.`upper_limit`,\
                                    `f`.`moving_average`\
                            from `f`\
                            join `elo_stats` `e`\
                            on `e`.`end_time` = `f`.`end_time`\
                            and `e`.`coin` = `f`.`coin`\
                            where `e`.`end_time` = \
                            (select `end_time` from `elo` order by `end_time` desc limit 1)\
                             and `f`.`coin` = {0} \
                 AND `f`.`start_time` >= {1}".format(_coin, _start_time)

            else:
                get_query = "SELECT DISTINCT `coin`, `start_time`, `elo_rating`,\
                 `end_time`, `average_elo`, `std_dev`, `lower_limit`, \
                 `upper_limit`, `moving_average` FROM `elo_stats` WHERE `coin` = {0} AND \
                 `start_time` >= {1} AND \
                `end_time` <= {2}".format(_coin, _start_time, _end_time)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {}
                dict["coin"] = entry[0]
                dict["start_time"] = entry[1]
                dict["elo_rating"] = entry[2]
                dict["end_time"] = entry[3]
                dict["average_elo"] = entry[4]
                dict["std_dev"] = entry[5]
                dict["lower_limit"] = entry[6]
                dict["upper_limit"] = entry[7]
                dict["moving_average"] = entry[8]
                dict_list.append(dict)
            # save_file_api(dict_list, "elo_stats")
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}


class Constants(Resource):
    """ Constants endpoint to get the most recent set of constants from SQL
    table `crypto_db`.`constants`. Get request queries data and converts
    data to a dictionary. Retrieving constants live from an SQL table means
    it's easier to configure the program without restarting it """

    def get(self):
        try:
            get_query = "SELECT `standard_deviations`, `minutes`,               \
            `percent_change`, `pairs_per_coin`, `moving_average_n` FROM `constants` order by `idconstants`    \
            desc limit 1"

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {}
                dict["standard_deviations"] = float(entry[0])
                dict["minutes"] = int(entry[1])
                dict["percent_change"] = float(entry[2])
                dict["pairs_per_coin"] = int(entry[3])
                dict["moving_average_n"] = int(entry[4])
                dict_list.append(dict)
            return simplejson.loads(simplejson.dumps(dict_list[0]))

        except Exception as e:
            return {'error': str(e)}


class StatisticsTest(Resource):
    """ Statistics endpoint to get data from SQL table
        `crypto_db`.`statistics` which holds graphical analysis
        data for each coin relating Elo rating to price change as
        calculated from the statistical_analysis tool. Get
        request queries data and converts data to a dictionary """

    def get(self):
        try:
            _coin = request.args.get('coin')

            get_query = f"SELECT `coin`, `minutes_forward`, `slope`, `intercept`, `r`, `p`, `std_err`,  \
                            `change_at_3sd` FROM `statistics_test` WHERE `coin` = '{0}'".format(_coin)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {"coin": entry[0], "minutes_forward": entry[1], "slope": entry[2], "intercept": entry[3],
                        "r_value": entry[4], "p_value": entry[5], "std_err": entry[6], "change_at_3sd": entry[7]}
                dict_list.append(dict)
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}

    def post(self):
        try:
            # Parse the arguments
            parser = reqparse.RequestParser()
            parser.add_argument('coin', type=str, help='Coin to get stats of')
            parser.add_argument('minutes_forward', type=str, help='Minutes shifted forward to get price change')
            parser.add_argument('slope', type=float, help='Slope of chart data at minutes forward')
            parser.add_argument('intercept', type=float, help='Intercept of chart data at minutes forward')
            parser.add_argument('r_value', type=float, help='Coefficient of correlation: -1 = negative, 1 = positive')
            parser.add_argument('p_value', type=float, help='Strength of correlation: 0 = random, 1 = correlation')
            parser.add_argument('std_err', type=float, help='Uncertainty in slope')
            parser.add_argument('change_at_3sd', type=float, help='Change of price at minutes forward if Elo was +3sd')

            args = parser.parse_args()

            _coin = args['coin']
            _minutes_forward = args['minutes_forward']
            _slope = args['slope']
            _intercept = args['intercept']
            _r_value = args['r_value']
            _p_value = args['p_value']
            _std_err = args['std_err']
            _change_at_3sd = args['change_at_3sd']

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('spInsertStatisticsTest', (_coin, _minutes_forward,
                                                   _slope, _intercept, _r_value,
                                                   _p_value, _std_err, _change_at_3sd))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return {'statusCode': '200', 'message': 'Statistics entry inserted'}
            else:
                return {'statusCode': '1000', 'message': str(data[0])}

        except Exception as e:
            return {'error': str(e)}


class Statistics(Resource):
    """ Statistics endpoint to get data from SQL table
    `crypto_db`.`statistics` which holds graphical analysis
    data for each coin relating Elo rating to price change as
    calculated from the statistical_analysis tool. Get
    request queries data and converts data to a dictionary """

    def get(self):
        try:
            _coin = request.args.get('coin')

            get_query = f"SELECT `coin`, `minutes_forward`, `slope`, `intercept`, `r`, `p`, `std_err`,  \
                        `change_at_3sd` FROM `statistics` WHERE `coin` = '{0}'".format(_coin)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {"coin": entry[0], "minutes_forward": entry[1], "slope": entry[2], "intercept": entry[3],
                        "r_value": entry[4], "p_value": entry[5], "std_err": entry[6], "change_at_3sd": entry[7],
                        "datapoints": entry[8], "timestamp": entry[9]}
                dict_list.append(dict)
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}

    def post(self):
        try:
            # Parse the arguments
            parser = reqparse.RequestParser()
            parser.add_argument('coin', type=str, help='Coin to get stats of')
            parser.add_argument('minutes_forward', type=str, help='Minutes shifted forward to get price change')
            parser.add_argument('slope', type=float, help='Slope of chart data at minutes forward')
            parser.add_argument('intercept', type=float, help='Intercept of chart data at minutes forward')
            parser.add_argument('r_value', type=float, help='Coefficient of correlation: -1 = negative, 1 = positive')
            parser.add_argument('p_value', type=float, help='Strength of correlation: 0 = random, 1 = correlation')
            parser.add_argument('std_err', type=float, help='Uncertainty in slope')
            parser.add_argument('change_at_3sd', type=float, help='Change of price at minutes forward if Elo was +3sd')
            parser.add_argument('datapoints', type=int, help='Number of datapoints to make statistics')
            parser.add_argument('timestamp', type=int, help='Timestamp of entry')

            args = parser.parse_args()

            _coin = args['coin']
            _minutes_forward = args['minutes_forward']
            _slope = args['slope']
            _intercept = args['intercept']
            _r_value = args['r_value']
            _p_value = args['p_value']
            _std_err = args['std_err']
            _change_at_3sd = args['change_at_3sd']
            _datapoints = args['datapoints']
            _timestamp = args['timestamp']

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('spInsertStatistics', (_coin, _minutes_forward,
                                                   _slope, _intercept, _r_value,
                                                   _p_value, _std_err, _change_at_3sd,
                                                   _datapoints, _timestamp))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return {'statusCode': '200', 'message': 'Statistics entry inserted'}
            else:
                return {'statusCode': '1000', 'message': str(data[0])}

        except Exception as e:
            return {'error': str(e)}


class VolDiff(Resource):
    """ Volume difference endpoint to get data from SQL table
    `crypto_db`.`vol_diff`. Get request queries data and converts data to a
    dictionary """

    def get(self):
        try:
            _end_time = request.args.get('end_time')
            _start_time = request.args.get('start_time')
            _pair = request.args.get('pair')

            binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)
            today = datetime.datetime.utcfromtimestamp(binance_api.get_current_timestamp() / 1000).replace(second=0,
                                                                                                           microsecond=0)
            millis_in_min = 1000 * 60
            epoch = datetime.datetime.utcfromtimestamp(0)
            vol_diff_start_time = int(((today - datetime.timedelta(minutes=60) - epoch).total_seconds() * 1000.0))

            if request.args.get('pair') is None and request.args.get('start_time') is None and request.args.get(
                    'end_time') is None:
                _start_time = vol_diff_start_time
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `vol_diff` FROM `vol_diff` WHERE `start_time` >= {0}".format(
                    _start_time)

            elif request.args.get('start_time') is None:
                _start_time = vol_diff_start_time

            elif request.args.get('pair') is None:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `vol_diff` \
                FROM `vol_diff` WHERE `start_time` >= {0} AND `end_time` <= {1}".format(_start_time, _end_time)

            elif request.args.get('end_time') is None:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `vol_diff` \
                FROM `vol_diff` WHERE `pair` = {0} AND `start_time` >= {1}".format(_pair, _start_time)

            else:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `vol_diff` \
                FROM `vol_diff` WHERE `pair` = {0} AND `start_time` >= {1} AND \
                `end_time` <= {2}".format(_pair, _start_time, _end_time)

            # print(get_query)
            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            # print(json_data)
            dict_list = []
            for entry in json_data:
                dict = {}
                dict["pair"] = entry[0]
                dict["start_time"] = entry[1]
                dict["end_time"] = entry[2]
                dict["vol_diff"] = entry[3]
                dict_list.append(dict)
            # save_file_api(dict_list, "vol_diff")
            # print(dict_list)
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}

    def post(self):
        try:
            # Parse the arguments
            parser = reqparse.RequestParser()
            parser.add_argument('pair', type=str, help='Trading pair')
            parser.add_argument('start_time', type=int, help='Start time of vol diff calculation')
            parser.add_argument('end_time', type=int, help='End time of vol diff calculation')
            parser.add_argument('vol_diff', type=float, help='Volume difference between pair')

            args = parser.parse_args()

            _pair = args['pair']
            _start_time = args['start_time']
            _end_time = args['end_time']
            _vol_diff = args['vol_diff']

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('spInsertVolDiff', (_pair, _start_time, _end_time, _vol_diff))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return {'statusCode': '200', 'message': 'VolDiff entry inserted'}
            else:
                return {'statusCode': '1000', 'message': str(data[0])}

        except Exception as e:
            return {'error': str(e)}


class PriceStats(Resource):
    """ Price statistics endpoint to get data from SQL table
    `crypto_db`.`price_stats`. Get request queries data and converts data to a
    dictionary """

    def get(self):
        try:
            _pair = request.args.get('pair')
            _minutes = request.args.get('minutes')

            get_query = "WITH B AS (                                        \
	WITH A AS (                                                            \
		SELECT `pair`,                                                        \
				`start_time`,                                                   \
				`end_time`,                                                     \
				`open_price`,                                                   \
				`close_price`,                                                  \
				(SELECT `close_price`                                           \
				FROM `crypto_db`.`price`                                        \
				WHERE `pair` = \"{0}-USDT\"                                     \
				ORDER BY `end_time` DESC                                        \
				LIMIT 1) AS `current_price`                                     \
		FROM `crypto_db`.`price`                                                  \
		WHERE `pair` = \"{0}-USDT\"                                           \
		ORDER BY `end_time` DESC)                                             \
                                                                            \
	SELECT 	`pair`,                                                            \
			`start_time`,                                                    \
			`end_time`,                                                      \
			`open_price`,                                                    \
			`close_price` AS `original_price`,                                 \
			`current_price`,                                                     \
			(100 / `close_price`) * (`current_price` - `close_price`) as     \
            `price_change_percent`,                                             \
			(round((unix_timestamp(curtime(4)) * 1000),0) - `end_time`) /    \
            60000 as `minutes_ago`                                              \
	FROM A)                                                                    \
                                                                                \
SELECT 	`pair`,                                                                \
		`start_time`,                                                         \
		`end_time`,                                                           \
		`original_price`,                                    \
		`current_price`,                                                      \
        `price_change_percent`,                                                 \
        `minutes_ago`                                                           \
FROM B                                                                          \
WHERE `minutes_ago` <= {1}                                                      \
ORDER BY `end_time` ASC                                                         \
LIMIT 1".format(_pair, _minutes)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            if len(json_data) > 0:
                for entry in json_data:
                    dict = {}
                    dict["pair"] = entry[0]
                    dict["start_time"] = entry[1]
                    dict["end_time"] = entry[2]
                    dict["original_price"] = entry[3]
                    dict["current_price"] = entry[4]
                    dict["price_change_percent"] = entry[5]
                    dict["minutes_ago"] = entry[6]
                    dict_list.append(dict)
                # save_file_api(dict_list, "price_stats")
                # print(dict_list)
                return simplejson.loads(simplejson.dumps(dict_list))
            else:
                return json_data

        except Exception as e:
            print("Error: {0}".format(e))
            return {'error': str(e)}


class Price(Resource):
    """ Price endpoint to get data from SQL table `crypto_db`.`price`. Get
    request queries data and converts data to a dictionary """

    def get(self):
        try:
            _start_time = request.args.get('start_time')
            _end_time = request.args.get('end_time')
            _pair = request.args.get('pair')

            binance_api = binanceapi.spot_extended.BinanceSpotExtendedHttp(api_key=binance_key, secret=binance_secret)
            today = datetime.datetime.utcfromtimestamp(binance_api.get_current_timestamp() / 1000).replace(second=0,
                                                                                                           microsecond=0)
            millis_in_min = 1000 * 60
            epoch = datetime.datetime.utcfromtimestamp(0)
            price_start_time = int(((today - datetime.timedelta(minutes=60) - epoch).total_seconds() * 1000.0))

            if request.args.get('pair') is None and request.args.get('start_time') is None and request.args.get(
                    'end_time') is None:
                _start_time = price_start_time
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `open_price`, `close_price` FROM `price` WHERE `start_time` >= {0}".format(
                    _start_time)

            elif request.args.get('start_time') is None:
                _start_time = price_start_time

            elif request.args.get('pair') is None:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `open_price`, `close_price` \
                FROM `price` WHERE `start_time` >= {0} AND `end_time` <= {1}".format(_start_time, _end_time)

            elif request.args.get('end_time') is None:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `open_price`, `close_price` \
                FROM `price` WHERE `pair` = {0} AND `start_time` >= {1}".format(_pair, _start_time)

            else:
                get_query = "SELECT DISTINCT `pair`, `start_time`, `end_time`, `open_price`, `close_price` \
                FROM `price` WHERE `pair` = {0} AND `start_time` >= {1} AND \
                `end_time` <= {2}".format(_pair, _start_time, _end_time)

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute(get_query)
            data = cursor.fetchall()
            json_data = simplejson.loads(simplejson.dumps(data))
            dict_list = []
            for entry in json_data:
                dict = {}
                dict["pair"] = entry[0]
                dict["start_time"] = entry[1]
                dict["end_time"] = entry[2]
                dict["open_price"] = entry[3]
                dict["close_price"] = entry[4]
                dict_list.append(dict)
            # save_file_api(dict_list, "price")
            return simplejson.loads(simplejson.dumps(dict_list))

        except Exception as e:
            return {'error': str(e)}

    def post(self):
        try:
            # Parse the arguments
            parser = reqparse.RequestParser()
            parser.add_argument('pair', type=str, help='Trading pair')
            parser.add_argument('start_time', type=int, help='Start time of price window')
            parser.add_argument('end_time', type=int, help='End time of price window')
            parser.add_argument('open_price', type=float, help='Price at start time')
            parser.add_argument('close_price', type=float, help='Price at close time')

            args = parser.parse_args()

            _pair = args['pair']
            _start_time = args['start_time']
            _end_time = args['end_time']
            _open_price = args['open_price']
            _close_price = args['close_price']

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('spInsertPrice', (_pair, _start_time, _end_time, _open_price, _close_price))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return {'statusCode': '200', 'message': 'Price entry inserted'}
            else:
                return {'statusCode': '1000', 'message': str(data[0])}

        except Exception as e:
            return {'error': str(e)}


# Assign endpoints
api.add_resource(VolDiff, '/VolDiff')
api.add_resource(Elo, '/Elo')
api.add_resource(EloStats, '/EloStats')
api.add_resource(Price, '/Price')
api.add_resource(PriceStats, '/PriceStats')
api.add_resource(Constants, '/Constants')
api.add_resource(Statistics, '/Statistics')
api.add_resource(StatisticsTest, '/StatisticsTest')

# def run_server(host, port, debug, threaded):
app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

# def multiprocess_server(port):
#     if __name__ == 'server':
#         p1 = mp.Process(target=run_server, args=('0.0.0.0', port, False, True))
#         p1.start()
