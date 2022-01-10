from enum import Enum


class OrderStatus(object):
    """
    Order Status
    """
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(Enum):
    """
    Order type
    """
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP_LOSS"


class RequestMethod(Enum):
    """
    Request methods
    """
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class Interval(Enum):
    """
    Interval for klines
    """
    MINUTE_1 = '1m'
    MINUTE_3 = '3m'
    MINUTE_5 = '5m'
    MINUTE_15 = '15m'
    MINUTE_30 = '30m'
    HOUR_1 = '1h'
    HOUR_2 = '2h'
    HOUR_4 = '4h'
    HOUR_6 = '6h'
    HOUR_8 = '8h'
    HOUR_12 = '12h'
    DAY_1 = '1d'
    DAY_3 = '3d'
    WEEK_1 = '1w'
    MONTH_1 = '1M'


class OrderSide(Enum):
    """
    order side
    """
    BUY = "BUY"
    SELL = "SELL"


class AccountType(Enum):
    """
    Spot, Futures or Margin
    """
    SPOT = 'SPOT'
    FUTURES = "FUTURES"
    MARGIN = "MARGIN"


class ErrorCode(Enum):
    """
    ErrorCodes for binance responses
    """
    UNKNOWN = -1000
    DISCONNECTED = -1001
    UNAUTHORIZED = -1002
    TOO_MANY_REQUESTS = -1003
    UNEXPECTED_RESP = -1006
    TIMEOUT = -1007
    INVALID_MESSAGE = -1013
    UNKNOWN_ORDER_COMPOSITION = -1014
    TOO_MANY_ORDERS = -1015
    SERVICE_SHUTTING_DOWN = -1016
    UNSUPPORTED_OPERATION = -1020
    INVALID_TIMESTAMP = -1021
    INVALID_SIGNATURE = -1022
    ILLEGAL_CHARS = -1100
    TOO_MANY_PARAMETERS = -1101
    MANDATORY_PARAM_EMPTY_OR_MALFORMED = -1102
    UNKNOWN_PARAM = -1103
    UNREAD_PARAMETERS = -1104
    PARAM_EMPTY = -1105
    PARAM_NOT_REQUIRED = -1106
    NO_DEPTH = -1112
    TIF_NOT_REQUIRED = -1114
    INVALID_TIF = -1115
    INVALID_ORDER_TYPE = -1116
    INVALID_SIDE = -1117
    EMPTY_NEW_CL_ORD_ID = -1118
    EMPTY_ORG_CL_ORD_ID = -1119
    BAD_INTERVAL = -1120
    BAD_SYMBOL = -1121
    INVALID_LISTEN_KEY = -1125
    MORE_THAN_XX_HOURS = -1127
    OPTIONAL_PARAMS_BAD_COMBO = -1128
    INVALID_PARAMETER = -1130
    BAD_API_ID = -2008
    DUPLICATE_API_KEY_DESC = -2009
    INSUFFICIENT_BALANCE = -2010
    CANCEL_ALL_FAIL = -2012
    NO_SUCH_ORDER = -2013
    BAD_API_KEY_FMT = -2014
    REJECTED_MBX_KEY = -2015
