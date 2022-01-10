from dataclasses import dataclass


@dataclass
class BinanceResponse:
    binance_code: int
    binance_reason: str
    response_code: int
    response_reason: str
