def analyze(candles, min_gap=0.0):
    if len(candles)<3: return {"name":"FVG","direction":"NEUTRAL","score":0,"reason":"Insufficient candles"}
    a,b,c=candles[-3],candles[-2],candles[-1]
    if c["low"] > a["high"]+min_gap:
        return {"name":"FVG","direction":"BUY","score":20,"score_raw":20,"reason":"Bullish three-candle imbalance"}
    if c["high"] < a["low"]-min_gap:
        return {"name":"FVG","direction":"SELL","score":20,"score_raw":20,"reason":"Bearish three-candle imbalance"}
    return {"name":"FVG","direction":"NEUTRAL","score":0,"reason":"No qualifying FVG"}
