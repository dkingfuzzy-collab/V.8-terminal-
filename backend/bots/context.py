def analyze(mtf):
    # Accept either a direct direction or the MTF engine signal.
    if not isinstance(mtf, dict):
        d="NEUTRAL"
    else:
        d=mtf.get("direction", "NEUTRAL")
        if d not in ("BUY", "SELL"):
            signal=mtf.get("signal", "")
            d="BUY" if signal in ("BUY_PAPER", "BUY") else "SELL" if signal in ("SELL_PAPER", "SELL") else "NEUTRAL"
    return {"name":"ICT/SMC Context","direction":d,"score":20 if d in ("BUY","SELL") else 0,
            "reason":"Higher-timeframe context agrees" if d!="NEUTRAL" else "No aligned HTF context"}
