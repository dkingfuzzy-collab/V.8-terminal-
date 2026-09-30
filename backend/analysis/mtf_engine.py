from statistics import mean

TF_ORDER = ["1d", "4h", "1h", "15m"]

def _state(bars, lookback=30):
    if len(bars) < 10: return "INSUFFICIENT"
    x=bars[-min(lookback,len(bars)):]; mid=max(1,len(x)//2)
    hi0=max(b["high"] for b in x[:mid]); hi1=max(b["high"] for b in x[mid:])
    lo0=min(b["low"] for b in x[:mid]); lo1=min(b["low"] for b in x[mid:])
    if hi1>hi0 and lo1>=lo0: return "BULLISH"
    if hi1<hi0 and lo1<=lo0: return "BEARISH"
    return "NEUTRAL"

def _sweep(bars, lookback=6):
    if len(bars)<lookback+1: return {"bullish":False,"bearish":False}
    x=bars[-1]; p=bars[-lookback-1:-1]; ph=max(v["high"] for v in p); pl=min(v["low"] for v in p)
    return {"bullish":x["low"]<pl and x["close"]>pl,"bearish":x["high"]>ph and x["close"]<ph}

def _displacement(bars, factor=1.3):
    if len(bars)<10: return {"bullish":False,"bearish":False}
    x=bars[-1]; avg=mean(v["high"]-v["low"] for v in bars[-10:-1]); body=abs(x["close"]-x["open"]); strong=avg>0 and body>=factor*avg
    return {"bullish":strong and x["close"]>x["open"],"bearish":strong and x["close"]<x["open"]}

def _fvg(bars):
    if len(bars)<3: return {"bullish":False,"bearish":False}
    a,c=bars[-3],bars[-1]
    return {"bullish":c["low"]>a["high"],"bearish":c["high"]<a["low"]}

def analyze_timeframe(bars):
    return {"state":_state(bars),"sweep":_sweep(bars),"displacement":_displacement(bars),"fvg":_fvg(bars)}

def analyze_mtf(symbol, candles):
    a={tf:analyze_timeframe(candles.get(tf,[])) for tf in TF_ORDER}
    bull_context=a["1d"]["state"]=="BULLISH" and a["4h"]["state"] in {"BULLISH","NEUTRAL"}
    bear_context=a["1d"]["state"]=="BEARISH" and a["4h"]["state"] in {"BEARISH","NEUTRAL"}
    bull_reasons=[]; bear_reasons=[]
    for tf in TF_ORDER:
        if a[tf]["sweep"]["bullish"]: bull_reasons.append(f"{tf} liquidity sweep")
        if a[tf]["displacement"]["bullish"]: bull_reasons.append(f"{tf} bullish displacement")
        if a[tf]["fvg"]["bullish"]: bull_reasons.append(f"{tf} bullish FVG")
        if a[tf]["sweep"]["bearish"]: bear_reasons.append(f"{tf} liquidity sweep")
        if a[tf]["displacement"]["bearish"]: bear_reasons.append(f"{tf} bearish displacement")
        if a[tf]["fvg"]["bearish"]: bear_reasons.append(f"{tf} bearish FVG")
    bull=a["15m"]["state"] in {"BULLISH","NEUTRAL"} and bull_context and bool(bull_reasons)
    bear=a["15m"]["state"] in {"BEARISH","NEUTRAL"} and bear_context and bool(bear_reasons)
    score_b=min(10,2*int(a["1d"]["state"]=="BULLISH")+2*int(a["4h"]["state"]=="BULLISH")+int(a["1h"]["state"]=="BULLISH")+2*int(a["15m"]["sweep"]["bullish"])+2*int(a["15m"]["displacement"]["bullish"])+int(a["15m"]["fvg"]["bullish"]))
    score_s=min(10,2*int(a["1d"]["state"]=="BEARISH")+2*int(a["4h"]["state"]=="BEARISH")+int(a["1h"]["state"]=="BEARISH")+2*int(a["15m"]["sweep"]["bearish"])+2*int(a["15m"]["displacement"]["bearish"])+int(a["15m"]["fvg"]["bearish"]))
    if bull and score_b>=5 and score_b>=score_s: signal="BUY_PAPER"
    elif bear and score_s>=5: signal="SELL_PAPER"
    else: signal="NO_SETUP"
    score=score_b if signal=="BUY_PAPER" else score_s if signal=="SELL_PAPER" else max(score_b,score_s)
    return {"symbol":symbol,"mode":"paper_only","timeframes":a,"signal":signal,"confluence_score":score,"bullish_reasons":bull_reasons,"bearish_reasons":bear_reasons}
