import os, json, time
from typing import Any
import httpx
import websockets

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
COINBASE = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
TWELVE = "https://api.twelvedata.com/time_series"

SYMBOL_MAP = {
    "BTCUSD": "BTC-USD",
    "BTC/USDT": "BTC-USD",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "XAUUSD": "XAUUSD=X",
    "XAGUSD": "XAGUSD=X",
}
INTERVALS = {"1m":"1m","15m":"15m","1h":"1h","4h":"1h","1d":"1d"}

def _norm(rows):
    out=[]
    for r in rows or []:
        try:
            if isinstance(r, dict):
                ts=float(r.get("timestamp", r.get("datetime", time.time())))
                o,h,l,c=map(float,(r["open"],r["high"],r["low"],r["close"]))
            else:
                ts=float(r[0]); o,h,l,c=map(float,r[1:5])
            out.append({"timestamp":ts,"open":o,"high":h,"low":l,"close":c})
        except (KeyError,TypeError,ValueError,IndexError):
            continue
    out.sort(key=lambda x:x["timestamp"])
    return out

async def yahoo_history(symbol:str,timeframe:str,limit:int=300):
    ticker=SYMBOL_MAP.get(symbol,symbol)
    interval=INTERVALS.get(timeframe,timeframe)
    period1=int(time.time()-90*86400) if timeframe in {"15m","1h","4h"} else int(time.time()-730*86400)
    if timeframe=="1m": period1=int(time.time()-7*86400)
    params={"period1":period1,"period2":int(time.time()),"interval":interval,"events":"history","includeAdjustedClose":"true"}
    async with httpx.AsyncClient(timeout=12,headers={"User-Agent":"Mozilla/5.0"}) as client:
        r=await client.get(YAHOO.format(symbol=ticker),params=params); r.raise_for_status(); j=r.json()
    result=(j.get("chart") or {}).get("result") or []
    if not result: raise RuntimeError("Yahoo returned no chart data")
    q=(result[0].get("indicators") or {}).get("quote") or []
    if not q: raise RuntimeError("Yahoo returned no quote data")
    ts=result[0].get("timestamp") or []
    rows=[]
    for i,t in enumerate(ts):
        try:
            o,h,l,c=[q[0][k][i] for k in ("open","high","low","close")]
            if None not in (o,h,l,c): rows.append({"timestamp":float(t),"open":float(o),"high":float(h),"low":float(l),"close":float(c)})
        except (IndexError,TypeError,KeyError): pass
    if timeframe=="4h": rows=_resample(rows,4*3600)
    return rows[-limit:]

async def coinbase_history(symbol:str,timeframe:str,limit:int=300):
    seconds={"1m":60,"15m":900,"1h":3600,"4h":3600,"1d":86400}.get(timeframe,900)
    gran=seconds
    end=time.time(); start=end-gran*min(limit,300)
    async with httpx.AsyncClient(timeout=12,headers={"User-Agent":"DicksonBot/8"}) as client:
        r=await client.get(COINBASE,params={"granularity":gran,"start":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(start)),"end":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(end))})
        r.raise_for_status(); rows=r.json()
    # Coinbase rows are [time, low, high, open, close, volume]
    out=[{"timestamp":float(x[0]),"open":float(x[3]),"high":float(x[2]),"low":float(x[1]),"close":float(x[4])} for x in rows]
    out.sort(key=lambda x:x["timestamp"])
    if timeframe=="4h": out=_resample(out,4*3600)
    return out[-limit:]

def _resample(rows,seconds):
    if not rows:return []
    out=[]; current=None
    for r in rows:
        bucket=int(r["timestamp"]//seconds)*seconds
        if current is None or current["timestamp"]!=bucket:
            if current: out.append(current)
            current={"timestamp":bucket,"open":r["open"],"high":r["high"],"low":r["low"],"close":r["close"]}
        else:
            current["high"]=max(current["high"],r["high"]); current["low"]=min(current["low"],r["low"]); current["close"]=r["close"]
    if current:out.append(current)
    return out

async def twelve_history(symbol:str,timeframe:str,limit:int=300):
    key=os.getenv("TWELVE_DATA_API_KEY")
    if not key: raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
    td_symbol={"XAUUSD":"XAU/USD","XAGUSD":"XAG/USD","EURUSD":"EUR/USD","GBPUSD":"GBP/USD","BTCUSD":"BTC/USD"}.get(symbol,symbol)
    interval={"1m":"1min","15m":"15min","1h":"1h","4h":"4h","1d":"1day"}.get(timeframe,"15min")
    async with httpx.AsyncClient(timeout=12) as client:
        r=await client.get(TWELVE,params={"symbol":td_symbol,"interval":interval,"outputsize":limit,"apikey":key,"order":"ASC"}); r.raise_for_status(); j=r.json()
    if j.get("status")=="error": raise RuntimeError(j.get("message","Twelve Data error"))
    return _norm(j.get("values",[]))[-limit:]

async def history(symbol,timeframe,limit=300):
    errors=[]
    providers=[]
    if os.getenv("TWELVE_DATA_API_KEY"): providers.append(("twelve_data",twelve_history))
    if symbol=="BTCUSD": providers.extend([("coinbase",coinbase_history), ("yahoo",yahoo_history)])
    else: providers.append(("yahoo",yahoo_history))
    for name,fn in providers:
        try:
            rows=await fn(symbol,timeframe,limit)
            if len(rows)>=10:return rows,name,None
            errors.append(f"{name}: only {len(rows)} candles")
        except Exception as e: errors.append(f"{name}: {type(e).__name__}: {e}")
    return [],"none","; ".join(errors) if errors else "No provider configured"

async def public_crypto_stream():
    uri="wss://ws-feed.exchange.coinbase.com"
    async with websockets.connect(uri,ping_interval=20,ping_timeout=20) as ws:
        await ws.send(json.dumps({"type":"subscribe","product_ids":["BTC-USD"],"channels":["ticker"]}))
        async for raw in ws:
            msg=json.loads(raw)
            if msg.get("type")=="ticker" and msg.get("price"):
                yield {"provider":"coinbase","symbol":"BTCUSD","price":float(msg["price"]),"timestamp":time.time()}
