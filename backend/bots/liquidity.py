def analyze(candles, atr=0.0):
    if len(candles)<5: return {"name":"Liquidity Sweep","direction":"NEUTRAL","score":0,"reason":"Insufficient candles"}
    a,b=candles[-2],candles[-1]
    prior_high=max(x["high"] for x in candles[-5:-2]); prior_low=min(x["low"] for x in candles[-5:-2])
    buffer=max(atr*0.1, 1e-9)
    if a["low"] < prior_low-buffer and b["close"] > prior_low:
        return {"name":"Liquidity Sweep","direction":"BUY","score":20,"reason":"Sell-side liquidity sweep and reclaim"}
    if a["high"] > prior_high+buffer and b["close"] < prior_high:
        return {"name":"Liquidity Sweep","direction":"SELL","score":20,"reason":"Buy-side liquidity sweep and rejection"}
    return {"name":"Liquidity Sweep","direction":"NEUTRAL","score":0,"reason":"No confirmed sweep"}
