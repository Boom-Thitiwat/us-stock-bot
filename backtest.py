from backtesting import Backtest, Strategy
from backtesting.lib import crossover

import yfinance as yf
import pandas as pd

# =====================
# DOWNLOAD DATA
# =====================
df = yf.download(
    "AAPL",
    start="2023-01-01",
    end="2025-01-01"
)

df.columns = df.columns.droplevel(1)

# =====================
# EMA STRATEGY
# =====================
class EmaCross(Strategy):

    n1 = 9
    n2 = 21

    def init(self):

        close = self.data.Close

        self.ema1 = self.I(
            lambda x: pd.Series(x).ewm(span=self.n1).mean(),
            close
        )

        self.ema2 = self.I(
            lambda x: pd.Series(x).ewm(span=self.n2).mean(),
            close
        )

    def next(self):

        if crossover(self.ema1, self.ema2):
            self.buy()

        elif crossover(self.ema2, self.ema1):
            self.sell()

# =====================
# RUN BACKTEST
# =====================
bt = Backtest(
    df,
    EmaCross,
    cash=10000,
    commission=.002
)

stats = bt.run()

print(stats)

bt.plot()