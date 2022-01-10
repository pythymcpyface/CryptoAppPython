import os
from dotenv import load_dotenv

# load dotenv
load_dotenv()


class Urls(object):

    def __init__(self, host):
        if len(host) == 0 or host is None:
            host = os.environ.get("HOST")

        port = os.environ.get("PORT")

        # build base url from env vars
        base_url = f"http://{host}:{port}"

        # Define urls
        self.ELO = f"{base_url}/Elo"
        self.ELO_STATS = f"{base_url}/EloStats"
        self.CONSTANTS = f"{base_url}/Constants"
        self.VOL_DIFF = f"{base_url}/VolDiff"
        self.PRICE = f"{base_url}/Price"
        self.PRICE_STATS = f"{base_url}/PriceStats"
        self.STATISTICS = f"{base_url}/Statistics"
