import os

from dotenv import load_dotenv

import statistical_analysis
import workers

# load dotenv
load_dotenv()

# Binance configurations
binance_key = os.environ.get("BINANCE_KEY")
binance_secret = os.environ.get("BINANCE_SECRET")
port = os.environ.get("PORT")

# Begin main loop
if __name__ == '__main__':
    # server.multiprocess_server(port)
    workers.multiprocess_workers(binance_key, binance_secret)
    # statistical_analysis.multiprocess_statistical_analysis()
