from collections import defaultdict, deque

TIMEFRAME_SECONDS={"1m":60,"15m":900,"1h":3600,"4h":14400,"1d":86400}

class CandleAggregator:
    def __init__(self,max_history=500):
        self.candles=defaultdict(dict)
        self.history=defaultdict(lambda: defaultdict(lambda: deque(maxlen=max_history)))
        self.max_history=max_history

    def _bucket(self,ts,tf): return int(ts//TIMEFRAME_SECONDS[tf])*TIMEFRAME_SECONDS[tf]

    def update(self,symbol,price,ts):
        done=[]
        for tf in TIMEFRAME_SECONDS:
            start=self._bucket(ts,tf)
            c=self.candles[symbol].get(tf)
            if c is None or c["timestamp"]!=start:
                if c:
                    closed=c.copy(); self.history[symbol][tf].append(closed)
                    done.append({"timeframe":tf,"candle":closed})
                c={"timestamp":start,"open":price,"high":price,"low":price,"close":price}
                self.candles[symbol][tf]=c
            else:
                c["high"]=max(c["high"],price); c["low"]=min(c["low"],price); c["close"]=price
        return done

    def seed(self,symbol,timeframe,rows):
        if timeframe not in TIMEFRAME_SECONDS: raise ValueError("Unsupported timeframe")
        rows=sorted(rows,key=lambda x:x["timestamp"])[-self.max_history:]
        self.history[symbol][timeframe].clear()
        self.candles[symbol].pop(timeframe,None)
        for row in rows[:-1]: self.history[symbol][timeframe].append(dict(row))
        if rows: self.candles[symbol][timeframe]=dict(rows[-1])

    def snapshot(self,symbol,timeframe=None,include_current=True):
        if timeframe:
            if timeframe not in TIMEFRAME_SECONDS: return []
            rows=list(self.history[symbol][timeframe])
            if include_current and self.candles[symbol].get(timeframe): rows.append(self.candles[symbol][timeframe].copy())
            return rows
        return {tf:self.snapshot(symbol,tf,include_current) for tf in TIMEFRAME_SECONDS}
