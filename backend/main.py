import os, asyncio, time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.market_data.aggregator import CandleAggregator
from backend.market_data.service import MarketDataService
from backend.market_data.providers import public_crypto_stream
from backend.analysis.mtf_engine import analyze_mtf
from backend.analysis.poi import analyze_poi
from backend.engine.confluence import ConfluenceEngine
from backend.setup.generator import generate_setup
from backend.paper.engine import Tracker, Setup, stats, profitability_estimate
from backend.backtest import run_backtest
from backend.auth import init_db, authenticate, create_session, get_user, revoke

ROOT=Path(__file__).resolve().parents[1]
FRONTEND=ROOT/'frontend'
app=FastAPI(title='Dickson Bot V8 Paper Research Terminal',version='8.0')
allowed_origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','*').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=allowed_origins,allow_methods=['GET','POST','OPTIONS'],allow_headers=['*'],allow_credentials=True)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'; response.headers['X-Frame-Options']='DENY'; response.headers['Referrer-Policy']='same-origin'; response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        return response
app.add_middleware(SecurityHeadersMiddleware)

agg=CandleAggregator(max_history=1000); market=MarketDataService(agg); tracker=Tracker(); confluence=ConfluenceEngine(threshold=60); clients=set(); feed_task=None

def token_from_request(request): return request.cookies.get('session')
def current_user(request:Request):
    u=get_user(token_from_request(request))
    if not u: raise HTTPException(401,'Authentication required')
    return u

def atr_estimate(rows):
    if len(rows)<2:return 0.0
    t=rows[-15:]; vals=[]
    for i in range(1,len(t)): vals.append(max(t[i]['high']-t[i]['low'],abs(t[i]['high']-t[i-1]['close']),abs(t[i]['low']-t[i-1]['close'])))
    return sum(vals)/len(vals) if vals else 0.0

@app.on_event('startup')
async def startup(): init_db()
@app.on_event('shutdown')
async def shutdown():
    global feed_task
    if feed_task: feed_task.cancel(); await asyncio.gather(feed_task,return_exceptions=True)

@app.get('/')
def root(): return FileResponse(FRONTEND/'index.html')
@app.get('/manifest.json')
def manifest(): return FileResponse(FRONTEND/'manifest.json',media_type='application/manifest+json')
@app.get('/service-worker.js')
def sw(): return FileResponse(FRONTEND/'service-worker.js',media_type='application/javascript')

@app.get('/api/health')
def health():
    return {'status':'ok','version':'V8.0','mode':'paper_only','authentication':'enabled','scanner':'enabled','market_data':'multi_provider','diagnostics':'enabled','database':'sqlite'}

@app.post('/api/auth/login')
def login(payload:dict,response:Response):
    u=authenticate(payload.get('username',''),payload.get('password',''))
    if not u: raise HTTPException(401,'Invalid credentials')
    token=create_session(u['id']); response.set_cookie('session',token,httponly=True,samesite='lax',secure=os.getenv('COOKIE_SECURE','false').lower()=='true',max_age=86400,path='/')
    return {'authenticated':True,'username':u['username'],'role':u['role']}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response):
    revoke(token_from_request(request)); response.delete_cookie('session',path='/'); return {'authenticated':False}
@app.get('/api/auth/me')
def me(user=Depends(current_user)): return {'authenticated':True,'username':user['username'],'role':user['role']}

@app.get('/api/market/bootstrap/{symbol}/{timeframe}')
async def bootstrap(symbol:str,timeframe:str,force:int=0,user=Depends(current_user)):
    return await market.bootstrap(symbol.upper(),timeframe,300,bool(force))
@app.get('/api/market/status')
def market_status(user=Depends(current_user)): return market.status()
@app.get('/api/candles/{symbol}/{timeframe}')
async def candles(symbol:str,timeframe:str,user=Depends(current_user)):
    item=await market.bootstrap(symbol.upper(),timeframe,300)
    return item

async def scan_symbol(symbol,timeframe='15m'):
    symbol=symbol.upper(); data={}
    for tf in ('1d','4h','1h','15m'):
        data[tf]=(await market.bootstrap(symbol,tf,300))['candles']
    rows=data[timeframe]
    atr=atr_estimate(rows); mtf=analyze_mtf(symbol,data); c=confluence.evaluate(rows,atr,mtf)
    setup=None; p=profitability_estimate(tracker.items.values(),symbol=symbol,timeframe=timeframe,direction=c['direction'] if c['direction']!='NEUTRAL' else None,score=c['score'])
    if c['qualified'] and c['direction']!='NEUTRAL':
        try:
            s=generate_setup(symbol=symbol,candles=rows,direction=c['direction'],score=c['score'],aligned_bots=c['aligned_bots'],qualified=True,atr=atr,timeframe=timeframe)
            s.reasons=[b['reason'] for b in c['bots'] if b['direction']==c['direction']]; setup=s.as_dict()
        except Exception as e: setup={'error':str(e)}
    return {'symbol':symbol,'timeframe':timeframe,'mtf':mtf,'confluence':c,'setup':setup,'profitability':p,'candles':len(rows),'source':{tf:(await market.bootstrap(symbol,tf,300))['provider'] for tf in ('1d','4h','1h','15m')},'paper_only':True}

@app.post('/api/scanner/scan')
async def scanner_scan(payload:dict,user=Depends(current_user)):
    symbols=payload.get('symbols') or ['XAUUSD','XAGUSD','BTCUSD','EURUSD','GBPUSD']; tf=payload.get('timeframe','15m')
    results=[]
    for s in symbols[:10]: results.append(await scan_symbol(s,tf))
    return {'mode':'paper_only','timeframe':tf,'results':results,'generated_at':time.time()}

@app.post('/api/dashboard/analyze')
def dashboard_analyze(payload:dict,user=Depends(current_user)):
    candles=payload.get('candles',[]); atr=float(payload.get('atr',0.0)); mtf=payload.get('mtf_context',{})
    c=confluence.evaluate(candles,atr,mtf); p=analyze_poi(payload.get('poi_candles',{})); return {'confluence':c,'poi':p,'mode':'paper_only'}
@app.post('/api/analysis/mtf')
def mtf(x:dict,user=Depends(current_user)): return analyze_mtf(x.get('symbol','UNKNOWN'),x.get('candles',{}))
@app.post('/api/analysis/poi')
def poi(x:dict,user=Depends(current_user)): return analyze_poi(x.get('candles',{}))
@app.post('/api/confluence/evaluate')
def confluence_evaluate(payload:dict,user=Depends(current_user)): return confluence.evaluate(payload.get('candles',[]),float(payload.get('atr',0.0)),payload.get('mtf_context',{}))

@app.post('/api/setup/generate')
def setup_generate(payload:dict,user=Depends(current_user)):
    c=confluence.evaluate(payload.get('candles',[]),float(payload.get('atr',0.0)),payload.get('mtf_context',{}))
    if not c['qualified'] or c['direction']=='NEUTRAL': return {'qualified':False,'confluence':c,'setup':None,'mode':'paper_only'}
    s=generate_setup(symbol=payload['symbol'],candles=payload['candles'],direction=c['direction'],score=c['score'],aligned_bots=c['aligned_bots'],qualified=True,atr=float(payload.get('atr',0.0)),timeframe=payload.get('timeframe','15m'))
    s.reasons=[b['reason'] for b in c['bots'] if b['direction']==c['direction']]
    paper=Setup(setup_id=s.setup_id,symbol=s.symbol,direction=s.direction,entry=s.entry,sl=s.sl,tp1=s.tp1,tp2=s.tp2,tp3=s.tp3,score=s.score,timeframe=s.timeframe); tracker.add(paper)
    result=s.as_dict(); result['profitability_estimate']=profitability_estimate(tracker.items.values(),symbol=s.symbol,timeframe=s.timeframe,direction=s.direction,score=s.score); return {'qualified':True,'confluence':c,'setup':result,'mode':'paper_only'}

@app.post('/api/paper/setup')
def paper_setup(x:dict,user=Depends(current_user)): s=Setup(**x); tracker.add(s); return s.__dict__
@app.post('/api/paper/{setup_id}/price')
def paper_price(setup_id:str,x:dict,user=Depends(current_user)): return tracker.update(setup_id,float(x['price']))
@app.post('/api/paper/{setup_id}/taken')
def paper_taken(setup_id:str,x:dict,user=Depends(current_user)): return tracker.mark_taken(setup_id,bool(x.get('taken',True)))
@app.get('/api/paper/setups')
def paper_setups(user=Depends(current_user)): return tracker.all()
@app.get('/api/paper/statistics')
def paper_statistics(user=Depends(current_user)): return stats(tracker.items.values())
@app.get('/api/paper/analytics')
def paper_analytics(user=Depends(current_user)): return stats(tracker.items.values())
@app.post('/api/setup/profitability')
def setup_profitability(payload:dict,user=Depends(current_user)): return profitability_estimate(tracker.items.values(),symbol=payload.get('symbol'),timeframe=payload.get('timeframe'),direction=payload.get('direction'),score=payload.get('score'))
@app.post('/api/backtest/run')
def backtest_run(payload:dict,user=Depends(current_user)): return run_backtest(payload.get('symbol','UNKNOWN'),payload.get('candles',{}),int(payload.get('min_score',60)),int(payload.get('max_setups',500)))

@app.get('/api/diagnostics')
def diagnostics(user=Depends(current_user)):
    return {'health':'ok','paper_only':True,'auth_password_configured':bool(os.getenv('ADMIN_PASSWORD')),'providers':market.status(),'environment':{'auto_bootstrap':'lazy','twelve_data_configured':bool(os.getenv('TWELVE_DATA_API_KEY'))},'next_step':'Use /api/market/bootstrap or Scanner Refresh to load candles.'}

async def _crypto_loop():
    while True:
        try:
            async for tick in public_crypto_stream():
                for completed in agg.update(tick['symbol'],tick['price'],tick['timestamp']):
                    for ws in list(clients):
                        try: await ws.send_json({'type':'candle_completed','symbol':tick['symbol'],'candle':completed})
                        except Exception: clients.discard(ws)
        except asyncio.CancelledError: raise
        except Exception:
            await asyncio.sleep(10)

@app.post('/api/feed/start')
async def feed_start(user=Depends(current_user)):
    global feed_task
    if feed_task is None or feed_task.done(): feed_task=asyncio.create_task(_crypto_loop())
    return {'status':'starting','mode':'paper_only','provider':'coinbase_public_market_data'}
@app.post('/api/feed/stop')
async def feed_stop(user=Depends(current_user)):
    global feed_task
    if feed_task: feed_task.cancel(); await asyncio.gather(feed_task,return_exceptions=True); feed_task=None
    return {'status':'stopped','mode':'paper_only'}
@app.websocket('/ws/market')
async def market_ws(ws:WebSocket):
    if not get_user(ws.cookies.get('session')): await ws.close(code=1008); return
    await ws.accept(); clients.add(ws)
    try:
        while True: await ws.receive_text()
    except (WebSocketDisconnect,Exception): clients.discard(ws)

@app.post('/api/candle/tick')
def tick(x:dict,user=Depends(current_user)):
    return agg.update(x['symbol'],float(x['price']),float(x.get('timestamp',time.time())))
