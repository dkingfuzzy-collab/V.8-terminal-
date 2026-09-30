def analyze(candles, atr=0.0):
    if not candles: return {"name":"Displacement","direction":"NEUTRAL","score":0,"reason":"Insufficient candles"}
    c=candles[-1]; rng=c["high"]-c["low"]
    threshold=max(atr*1.2, 1e-9)
    if rng>=threshold:
        if c["close"]>c["open"]: return {"name":"Displacement","direction":"BUY","score":20,"reason":"Bullish displacement candle"}
        if c["close"]<c["open"]: return {"name":"Displacement","direction":"SELL","score":20,"reason":"Bearish displacement candle"}
    return {"name":"Displacement","direction":"NEUTRAL","score":0,"reason":"No displacement"}
