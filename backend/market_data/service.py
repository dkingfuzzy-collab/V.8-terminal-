import time
from backend.market_data.providers import history
from backend.market_data.aggregator import CandleAggregator

class MarketDataService:
    def __init__(self,aggregator):
        self.aggregator=aggregator
        self.cache={}
        self.diagnostics={}
    async def bootstrap(self,symbol,timeframe,limit=300,force=False):
        key=(symbol,timeframe)
        if not force and key in self.cache and len(self.cache[key].get('candles',[]))>=10:
            return self.cache[key]
        rows,provider,error=await history(symbol,timeframe,limit)
        if rows:
            self.aggregator.seed(symbol,timeframe,rows)
            item={"symbol":symbol,"timeframe":timeframe,"candles":rows,"provider":provider,"mode":"market_data","error":None,"updated_at":time.time()}
        else:
            item={"symbol":symbol,"timeframe":timeframe,"candles":[],"provider":"none","mode":"unavailable","error":error,"updated_at":time.time()}
        self.cache[key]=item; self.diagnostics[f"{symbol}:{timeframe}"]=item
        return item
    def status(self): return {"sources":self.diagnostics,"cached_series":len(self.cache)}
