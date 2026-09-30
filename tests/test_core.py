import sys, pathlib
from backend.market_data.aggregator import CandleAggregator
from backend.engine.confluence import ConfluenceEngine

def bars(n=80,base=100):
    out=[]
    for i in range(n):
        o=base+i*0.1; c=o+0.05; out.append({'timestamp':i*60,'open':o,'high':c+0.1,'low':o-0.05,'close':c})
    return out

def test_aggregation():
    a=CandleAggregator();
    for i in range(100): a.update('XAUUSD',100+i*0.01,i*60)
    assert len(a.snapshot('XAUUSD','1m'))>1
    assert len(a.snapshot('XAUUSD','15m'))>=2

def test_confluence_shape():
    c=ConfluenceEngine().evaluate(bars(),0.15,{"signal":"BUY_PAPER"})
    assert 'bots' in c and len(c['bots'])==5
    assert c['direction'] in {'BUY','SELL','NEUTRAL'}
