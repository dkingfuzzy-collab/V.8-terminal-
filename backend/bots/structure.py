def analyze(candles):
    if len(candles)<6: return {"name":"Structure","direction":"NEUTRAL","score":0,"reason":"Insufficient candles"}
    recent=candles[-4:]; prev=candles[-6:-2]
    rh=max(x["high"] for x in recent); rl=min(x["low"] for x in recent)
    ph=max(x["high"] for x in prev); pl=min(x["low"] for x in prev)
    if rh>ph and rl>pl: d="BUY"; s=20; r="Higher highs and higher lows"
    elif rh<ph and rl<pl: d="SELL"; s=20; r="Lower highs and lower lows"
    else: d="NEUTRAL"; s=0; r="Mixed structure"
    return {"name":"Structure","direction":d,"score":s,"reason":r}
