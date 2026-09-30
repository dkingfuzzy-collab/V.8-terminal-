from backend.bots.structure import analyze as structure
from backend.bots.liquidity import analyze as liquidity
from backend.bots.fvg import analyze as fvg
from backend.bots.displacement import analyze as displacement
from backend.bots.context import analyze as context

class ConfluenceEngine:
    def __init__(self, threshold=60):
        self.threshold=threshold
    def evaluate(self, candles, atr=0.0, mtf_context=None):
        results=[structure(candles), liquidity(candles,atr), fvg(candles,max(atr*0.25,0.0)), displacement(candles,atr), context(mtf_context or {})]
        votes={"BUY":0,"SELL":0}
        for r in results:
            if r["direction"] in votes: votes[r["direction"]]+=r["score"]
        direction=max(votes,key=votes.get)
        score=votes[direction]
        aligned=sum(1 for r in results if r["direction"]==direction)
        return {"direction":direction if score>=self.threshold else "NEUTRAL",
                "score":score,"aligned_bots":aligned,"total_bots":len(results),
                "qualified":score>=self.threshold and aligned>=3,
                "bots":results}
