from backend.bots.orderblock import order_block_poi
def analyze_poi(candles):
    return {'timeframes':{tf:order_block_poi(b) for tf,b in candles.items() if b},'mode':'paper_only','note':'Heuristic Order Block/POI detection; validate historically.'}
