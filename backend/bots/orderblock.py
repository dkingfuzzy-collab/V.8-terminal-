def detect_order_blocks(bars,lookback=60):
    if len(bars)<5:return []
    x=bars[-min(len(bars),lookback):]; zones=[]
    for i in range(1,len(x)-1):
        cur,nxt=x[i],x[i+1]; avg=sum(abs(b['close']-b['open']) for b in x[max(0,i-8):i])/max(1,min(8,i)); body=abs(nxt['close']-nxt['open'])
        if cur['close']<cur['open'] and nxt['close']>nxt['open'] and body>=1.3*max(avg,1e-12) and nxt['close']>cur['high']:
            zones.append({'type':'bullish_order_block','low':cur['low'],'high':cur['open'],'index':i})
        if cur['close']>cur['open'] and nxt['close']<nxt['open'] and body>=1.3*max(avg,1e-12) and nxt['close']<cur['low']:
            zones.append({'type':'bearish_order_block','low':cur['open'],'high':cur['high'],'index':i})
    return zones[-5:]
def order_block_poi(bars):
    zs=detect_order_blocks(bars)
    if not zs:return {'zones':[],'active_poi':None}
    price=bars[-1]['close']; out=[]
    for z in zs:
        inside=z['low']<=price<=z['high']; zz=dict(z); zz.update(active=inside,distance=0 if inside else min(abs(price-z['low']),abs(price-z['high']))); out.append(zz)
    out.sort(key=lambda z:(not z['active'],z['distance'])); return {'zones':out,'active_poi':out[0] if out else None}
