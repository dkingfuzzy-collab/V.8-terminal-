from dataclasses import dataclass, asdict
from collections import defaultdict
from math import sqrt
import os, sqlite3, time
from pathlib import Path

DB_PATH = Path(os.getenv('PAPER_DB_PATH', str(Path(__file__).resolve().parent.parent/'data'/'paper.db')))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def _init_db():
    with _db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS paper_setups(
            setup_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, direction TEXT NOT NULL,
            entry REAL NOT NULL, sl REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL, tp3 REAL NOT NULL,
            score INTEGER NOT NULL, timeframe TEXT NOT NULL, taken INTEGER NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL DEFAULT 'OPEN', mfe REAL NOT NULL DEFAULT 0, mae REAL NOT NULL DEFAULT 0,
            r_multiple REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
        c.commit()

@dataclass
class Setup:
    setup_id:str; symbol:str; direction:str; entry:float; sl:float; tp1:float; tp2:float; tp3:float; score:int
    timeframe:str="15m"; taken:bool=False; outcome:str="OPEN"; mfe:float=0; mae:float=0; r_multiple:float=0

class Tracker:
    def __init__(self):
        _init_db(); self.items={}; self._load()
    def _load(self):
        with _db() as c:
            for r in c.execute('SELECT * FROM paper_setups ORDER BY created_at'):
                self.items[r['setup_id']]=Setup(r['setup_id'],r['symbol'],r['direction'],r['entry'],r['sl'],r['tp1'],r['tp2'],r['tp3'],r['score'],r['timeframe'],bool(r['taken']),r['outcome'],r['mfe'],r['mae'],r['r_multiple'])
    def _save(self,s):
        now=time.time()
        with _db() as c:
            c.execute('''INSERT INTO paper_setups VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(setup_id) DO UPDATE SET symbol=excluded.symbol,direction=excluded.direction,
                entry=excluded.entry,sl=excluded.sl,tp1=excluded.tp1,tp2=excluded.tp2,tp3=excluded.tp3,
                score=excluded.score,timeframe=excluded.timeframe,taken=excluded.taken,outcome=excluded.outcome,
                mfe=excluded.mfe,mae=excluded.mae,r_multiple=excluded.r_multiple,updated_at=excluded.updated_at''',
                (s.setup_id,s.symbol,s.direction,s.entry,s.sl,s.tp1,s.tp2,s.tp3,s.score,s.timeframe,int(s.taken),s.outcome,s.mfe,s.mae,s.r_multiple,now,now))
            c.commit()
    def add(self,s): self.items[s.setup_id]=s; self._save(s)
    def mark_taken(self,i,taken=True):
        s=self.items.get(i)
        if not s: return None
        s.taken=bool(taken); self._save(s); return asdict(s)
    def update(self,i,p):
        s=self.items.get(i)
        if not s or s.outcome in {"LOSS","PROFIT"}: return None
        risk=abs(s.entry-s.sl) or 1e-12
        if s.direction.upper()=="BUY":
            s.mfe=max(s.mfe,p-s.entry); s.mae=max(s.mae,s.entry-p)
            if p<=s.sl: s.outcome="LOSS"; s.r_multiple=-1
            elif p>=s.tp3: s.outcome="PROFIT"; s.r_multiple=abs(s.tp3-s.entry)/risk
            elif p>=s.tp2: s.outcome="TP2"
            elif p>=s.tp1: s.outcome="TP1"
        else:
            s.mfe=max(s.mfe,s.entry-p); s.mae=max(s.mae,p-s.entry)
            if p>=s.sl: s.outcome="LOSS"; s.r_multiple=-1
            elif p<=s.tp3: s.outcome="PROFIT"; s.r_multiple=abs(s.tp3-s.entry)/risk
            elif p<=s.tp2: s.outcome="TP2"
            elif p<=s.tp1: s.outcome="TP1"
        self._save(s); return asdict(s)
    def all(self): return [asdict(x) for x in self.items.values()]

def _rate(wins,total): return round(100*wins/total,2) if total else None
def _row(x):
    return asdict(x) if hasattr(x, '__dataclass_fields__') else x

def _rows(items): return [_row(x) for x in items]
def _closed(rows): return [x for x in rows if x["outcome"] in {"LOSS","PROFIT"}]
def _probability_for(rows):
    rows=_rows(rows); closed=_closed(rows); wins=sum(x["outcome"]=="PROFIT" for x in closed); return _rate(wins,len(closed)),len(closed),wins

def wilson_interval(wins,total,z=1.959963984540054):
    if not total: return None
    p=wins/total; den=1+z*z/total; centre=(p+z*z/(2*total))/den
    margin=z*sqrt((p*(1-p)+z*z/(4*total))/total)/den
    return [round(100*(centre-margin),2),round(100*(centre+margin),2)]

def profitability_estimate(items,symbol=None,timeframe=None,direction=None,score=None):
    rows=_rows(items)
    if symbol: rows=[x for x in rows if x["symbol"]==symbol]
    if timeframe: rows=[x for x in rows if x.get("timeframe")==timeframe]
    if direction: rows=[x for x in rows if x["direction"].upper()==direction.upper()]
    scoped=rows; basis="historical paper outcomes"
    if score is not None:
        lo=(int(score)//10)*10; hi=lo+9; bucket=[x for x in rows if lo<=int(x.get("score",0))<=hi]
        if len(_closed(bucket))>=10: scoped=bucket; basis=f"historical paper outcomes, score bucket {lo}-{hi}"
    prob,n,w=_probability_for(scoped)
    if n<10: return {"profitability_probability_percent":None,"sample_size":n,"profitable_setups":w,"basis":"insufficient historical sample","minimum_sample_recommended":10,"confidence_interval_95_percent":None,"is_predictive_guarantee":False}
    return {"profitability_probability_percent":prob,"sample_size":n,"profitable_setups":w,"basis":basis,"minimum_sample_recommended":10,"confidence_interval_95_percent":wilson_interval(w,n),"is_predictive_guarantee":False}

def stats(items):
    items=_rows(items); closed=_closed(items); wins=sum(x["outcome"]=="PROFIT" for x in closed); losses=len(closed)-wins
    taken=[x for x in items if x["taken"]]; missed=[x for x in items if not x["taken"]]
    by_symbol=defaultdict(list); by_direction=defaultdict(list); by_score=defaultdict(list); by_tf=defaultdict(list)
    for x in items:
        by_symbol[x["symbol"]].append(x); by_direction[x["direction"]].append(x); by_score[(int(x.get("score",0))//10)*10].append(x); by_tf[x.get('timeframe','15m')].append(x)
    def group(v):
        p,n,w=_probability_for(v); return {"profitability_probability_percent":p if n>=10 else None,"sample_size":n,"profitable_setups":w,"confidence_interval_95_percent":wilson_interval(w,n) if n>=10 else None}
    return {"total_setups":len(items),"taken":len(taken),"missed":len(missed),"closed":len(closed),"open":len(items)-len(closed),"wins":wins,"losses":losses,
        "win_rate_closed_percent":_rate(wins,len(closed)),"profitability_probability_percent":_rate(wins,len(closed)) if len(closed)>=10 else None,
        "profitability_confidence_interval_95_percent":wilson_interval(wins,len(closed)) if len(closed)>=10 else None,
        "tp1_hits":sum(x["outcome"] in {"TP1","TP2","PROFIT"} for x in items),"tp2_hits":sum(x["outcome"] in {"TP2","PROFIT"} for x in items),"tp3_hits":sum(x["outcome"]=="PROFIT" for x in items),
        "avg_r_closed":round(sum(x["r_multiple"] for x in closed)/len(closed),3) if closed else None,
        "symbol_profitability":{k:group(v) for k,v in by_symbol.items()},"direction_profitability":{k:group(v) for k,v in by_direction.items()},"score_bucket_profitability":{str(k):group(v) for k,v in sorted(by_score.items())},"timeframe_profitability":{k:group(v) for k,v in by_tf.items()},
        "note":"Rates are empirical paper/backtest statistics. A 95% interval shows sampling uncertainty; neither is a guarantee of future performance."}
