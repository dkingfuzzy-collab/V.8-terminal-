from dataclasses import dataclass, asdict
from typing import Any
import uuid

@dataclass
class GeneratedSetup:
    setup_id: str
    symbol: str
    direction: str
    timeframe: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    risk_distance: float
    rr_tp1: float
    rr_tp2: float
    rr_tp3: float
    score: int
    aligned_bots: int
    qualified: bool
    reasons: list[str]
    invalidation: str
    mode: str = "paper_only"

    def as_dict(self):
        return asdict(self)


def _latest_close(candles: list[dict[str, Any]]) -> float:
    if not candles:
        raise ValueError("At least one candle is required")
    return float(candles[-1]["close"])


def generate_setup(*, symbol: str, candles: list[dict[str, Any]], direction: str,
                   score: int, aligned_bots: int, qualified: bool,
                   atr: float = 0.0, timeframe: str = "15m",
                   min_rr: float = 1.0, setup_id: str | None = None) -> GeneratedSetup:
    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if not candles:
        raise ValueError("candles cannot be empty")

    entry = _latest_close(candles)
    highs = [float(c["high"]) for c in candles[-20:]]
    lows = [float(c["low"]) for c in candles[-20:]]
    recent_high = max(highs)
    recent_low = min(lows)
    atr = max(float(atr), 0.0)

    # Deterministic paper-model invalidation: use recent structure plus ATR padding.
    if direction == "BUY":
        structural_sl = recent_low
        padding = max(atr * 0.20, abs(entry) * 0.0001)
        sl = min(structural_sl - padding, entry - max(atr, abs(entry) * 0.0005))
        risk = entry - sl
        if risk <= 0:
            raise ValueError("Unable to construct a positive BUY risk distance")
        tp1, tp2, tp3 = entry + risk * max(min_rr, 1.0), entry + risk * 2.0, entry + risk * 3.0
        invalidation = "Paper BUY setup invalidates if price reaches SL before a TP3 close."
    else:
        structural_sl = recent_high
        padding = max(atr * 0.20, abs(entry) * 0.0001)
        sl = max(structural_sl + padding, entry + max(atr, abs(entry) * 0.0005))
        risk = sl - entry
        if risk <= 0:
            raise ValueError("Unable to construct a positive SELL risk distance")
        tp1, tp2, tp3 = entry - risk * max(min_rr, 1.0), entry - risk * 2.0, entry - risk * 3.0
        invalidation = "Paper SELL setup invalidates if price reaches SL before a TP3 close."

    return GeneratedSetup(
        setup_id=setup_id or f"PAPER-{uuid.uuid4().hex[:12].upper()}",
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        risk_distance=risk,
        rr_tp1=abs(tp1-entry)/risk,
        rr_tp2=abs(tp2-entry)/risk,
        rr_tp3=abs(tp3-entry)/risk,
        score=int(score),
        aligned_bots=int(aligned_bots),
        qualified=bool(qualified),
        reasons=[],
        invalidation=invalidation,
    )
