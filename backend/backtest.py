from dataclasses import asdict
from backend.analysis.mtf_engine import analyze_mtf
from backend.engine.confluence import ConfluenceEngine
from backend.setup.generator import generate_setup
from backend.paper.engine import Tracker, Setup, wilson_interval


def _prefix(rows, ts):
    return [x for x in rows if float(x.get('timestamp',0)) <= float(ts)]


def _atr(candles, n=14):
    if len(candles)<2: return 0.0
    trs=[]
    for i in range(1,len(candles)):
        h,l,pc=float(candles[i]['high']),float(candles[i]['low']),float(candles[i-1]['close'])
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs[-n:])/min(n,len(trs)) if trs else 0.0


def run_backtest(symbol, candles_by_tf, min_score=60, max_setups=500):
    bars15=sorted(candles_by_tf.get('15m',[]), key=lambda x:x.get('timestamp',0))
    tracker=Tracker(); confluence=ConfluenceEngine(threshold=min_score); generated=0
    closed_ids=set(); ambiguous=0
    for i in range(30,len(bars15)-1):
        current=bars15[i]; ts=float(current.get('timestamp',i))
        mtf={tf:_prefix(candles_by_tf.get(tf,[]),ts) for tf in ('1d','4h','1h','15m')}
        mtf_result=analyze_mtf(symbol,mtf)
        c=confluence.evaluate(mtf['15m'],_atr(mtf['15m']),mtf_result)
        if not c['qualified'] or c['direction']=='NEUTRAL' or generated>=max_setups: continue
        try:
            g=generate_setup(symbol=symbol,candles=mtf['15m'],direction=c['direction'],score=c['score'],aligned_bots=c['aligned_bots'],qualified=True,atr=_atr(mtf['15m']),timeframe='15m')
        except ValueError: continue
        s=Setup(setup_id=g.setup_id,symbol=symbol,direction=g.direction,entry=g.entry,sl=g.sl,tp1=g.tp1,tp2=g.tp2,tp3=g.tp3,score=g.score,timeframe='15m',taken=False)
        tracker.add(s); generated+=1
        # Evaluate only candles after signal candle; no future candle is used to create the signal.
        for future in bars15[i+1:]:
            h,l=float(future['high']),float(future['low'])
            if s.direction=='BUY':
                hit_sl=l<=s.sl; hit_tp=h>=s.tp3
            else:
                hit_sl=h>=s.sl; hit_tp=l<=s.tp3
            if hit_sl and hit_tp:
                s.outcome='AMBIGUOUS'; ambiguous+=1; break
            if hit_sl:
                tracker.update(s.setup_id,s.sl); break
            if hit_tp:
                tracker.update(s.setup_id,s.tp3); break
            # Track MFE/MAE with close only; final outcome is threshold based.
            tracker.update(s.setup_id,float(future['close']))
            if s.outcome in {'LOSS','PROFIT'}: break
    rows=tracker.all(); closed=[x for x in rows if x['outcome'] in {'LOSS','PROFIT'}]
    wins=sum(x['outcome']=='PROFIT' for x in closed); losses=sum(x['outcome']=='LOSS' for x in closed)
    return {
        'mode':'paper_only','symbol':symbol,'setups_generated':generated,'closed_setups':len(closed),'wins':wins,'losses':losses,
        'profitability_probability_percent':round(100*wins/len(closed),2) if len(closed)>=10 else None,
        'confidence_interval_95_percent':wilson_interval(wins,len(closed)) if len(closed)>=10 else None,
        'insufficient_history':len(closed)<10,'minimum_sample_recommended':10,'ambiguous_setups':ambiguous,
        'setups':rows,
        'note':'Chronological replay using only candles available at each signal time. This is a research backtest, not a forecast or guarantee.'
    }
