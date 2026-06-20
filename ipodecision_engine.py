import math
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple, Union


class IPODecisionEngine:
    """Implementation of the DecodeLabs systematic trading engine framework.

    Processes raw OHLCV streams, computes Wick-to-Body ratios, tracks
    structural Support/Resistance boundaries, tracks 50/200 EMAs, computes
    RSI indicators, and executes mechanical circuit breakers.
    """

    def __init__(
        self,
        daily_loss_limit: float,
        support_level: float,
        resistance_level: float,
        tolerance_pct: float = 0.005,
    ):
        # Risk Parameters
        self.daily_loss_limit = daily_loss_limit
        self.current_daily_drawdown = 0.0
        self.consecutive_losses = 0
        self.system_status = "IDLE"  # IDLE, EXECUTE, or HARD_LOCK

        # Structural Boundaries
        self.support_level = support_level
        self.resistance_level = resistance_level
        self.tolerance_pct = tolerance_pct

        # Multi-period History for EMAs and RSI calculations
        self.close_prices: List[float] = []
        self.gains: List[float] = []
        self.losses: List[float] = []

        # Tracking state
        self.ema_50: Optional[float] = None
        self.ema_200: Optional[float] = None

    # =========================================================================
    # 1. INPUT LAYER: Raw Data Processing & Candle Microstructure Mechanics
    # =========================================================================

    def calculate_wick_to_body_ratio(
        self, open_p: float, high: float, low: float, close_p: float
    ) -> float:
        """Quantifies price rejection using the Rwb formula (Page 7).

        Formula: Rwb = [(High - max(Open, Close)) + (min(Open, Close) - Low)] /

        |Open - Close|
        """
        body = abs(open_p - close_p)
        upper_wick = high - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low
        total_wick = upper_wick + lower_wick

        # Handle Marubozu or near-zero bodies to avoid DivisionByZero errors
        if body < 1e-8:
            return total_wick / 1e-8
        return total_wick / body

    # =========================================================================
    # 2. PROCESS LAYER: Technical Filtering & Smoothing
    # =========================================================================

    def update_indicators(self, close_p: float, period_rsi: int = 14) -> None:
        """Applies exponential trend smoothing updates and RSI filters (Pages 9
        & 11).
        """
        self.close_prices.append(close_p)

        # ---- Exponential Moving Average (EMA) Calculation ----
        # α = 2 / (N + 1)
        if len(self.close_prices) >= 50:
            if self.ema_50 is None:
                self.ema_50 = sum(self.close_prices[-50:]) / 50
            else:
                alpha_50 = 2.0 / (50 + 1)
                self.ema_50 = (close_p * alpha_50) + (
                    self.ema_50 * (1.0 - alpha_50)
                )

        if len(self.close_prices) >= 200:
            if self.ema_200 is None:
                self.ema_200 = sum(self.close_prices[-200:]) / 200
            else:
                alpha_200 = 2.0 / (200 + 1)
                self.ema_200 = (close_p * alpha_200) + (
                    self.ema_200 * (1.0 - alpha_200)
                )

        # ---- Relative Strength Index (RSI) Calculation ----
        if len(self.close_prices) > 1:
            delta = self.close_prices[-1] - self.close_prices[-2]
            self.gains.append(max(delta, 0.0))
            self.losses.append(max(-delta, 0.0))

    def get_rsi(self, period: int = 14) -> Optional[float]:
        """Calculates standard Wilder's RSI value over a set sliding lookback
        period.
        """
        if len(self.gains) < period:
            return None

        # Wilders smoothing mechanism initialization
        avg_gain = sum(self.gains[:period]) / period
        avg_loss = sum(self.losses[:period]) / period

        for idx in range(period, len(self.gains)):
            avg_gain = (avg_gain * (period - 1) + self.gains[idx]) / period
            avg_loss = (avg_loss * (period - 1) + self.losses[idx]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    # =========================================================================
    # 3. INTERACTION GATE FILTERS (The IPO Model Logic - Page 12)
    # =========================================================================

    def check_gate_a(self, current_price: float) -> bool:
        """Gate A: Is price at a Support or Resistance structural boundary?"""
        at_support = (
            abs(current_price - self.support_level)
            <= self.support_level * self.tolerance_pct
        )
        at_resistance = (
            abs(current_price - self.resistance_level)
            <= self.resistance_level * self.tolerance_pct
        )
        return at_support or at_resistance

    def check_gate_b(self) -> bool:
        """Gate B: Is the 50/200 EMA structural regime trend direction aligned?"""
        if self.ema_50 is None or self.ema_200 is None:
            return False
        # Structural alignment validation: Golden Cross environment
        return self.ema_50 > self.ema_200

    def check_gate_c(self) -> bool:
        """Gate C: Is RSI confirming speed and magnitude momentum > 50?"""
        rsi_val = self.get_rsi()
        if rsi_val is None:
            return False
        return rsi_val > 50.0

    # =========================================================================
    # 4. RISK MANAGEMENT CIRCUIT BREAKERS (System Defense - Page 15)
    # =========================================================================

    def verify_circuit_breakers(self, current_time: datetime) -> bool:
        """Runs automated mechanical defense filters overriding manual human execution bias.

        Returns True if processing can continue, False if a hard execution block is active.
        """
        # Protocol C: Pre-Set Session End Trigger (Hard platform lock if target drawdown breached before 1:00 PM)
        if (
            current_time.time() < time(13, 0)
            and self.current_daily_drawdown >= 0.70 * self.daily_loss_limit
        ):
            self.system_status = "HARD_LOCK"
            return False

        # Protocol A: 15-Minute Hard Stop Trigger (Drawdown reaches 50% of the maximum daily limit)
        if self.current_daily_drawdown >= 0.50 * self.daily_loss_limit:
            self.system_status = "IDLE"
            return False

        return True

    def calculate_execution_position_size(self, base_size: float) -> float:
        """Protocol B: Half-Size Rule adjustment calculation.

        Reduces volume exposure footprint if tracking consecutive strategy losses.
        """
        if self.consecutive_losses >= 2:
            return base_size * 0.5
        return base_size

    # =========================================================================
    # 5. EXECUTION ROUTING ORCHESTRATION PIPELINE
    # =========================================================================

    def execute_pipeline(
        self,
        ohlcv: Dict[str, float],
        current_time: datetime,
        base_position_size: float,
    ) -> Dict[str, Union[str, float]]:
        """Processes incoming candles into exact trading decisions based on operational boundaries."""
        # 1. Update Core Data Matrices
        self.update_indicators(ohlcv["close"])

        # 2. Verify Risk Matrix Boundaries first
        if not self.verify_circuit_breakers(current_time):
            return {
                "decision": "IDLE",
                "reason": f"Risk Circuit Active. System Status: {self.system_status}",
                "allocated_size": 0.0,
            }

        # 3. Process structural filters (Gate Architecture)
        gate_a = self.check_gate_a(ohlcv["close"])
        gate_b = self.check_gate_b()
        gate_c = self.check_gate_c()

        rwb_ratio = self.calculate_wick_to_body_ratio(
            ohlcv["open"], ohlcv["high"], ohlcv["low"], ohlcv["close"]
        )

        # All Gates perfect path match verification
        if gate_a and gate_b and gate_c:
            self.system_status = "EXECUTE"
            size = self.calculate_execution_position_size(base_position_size)
            return {
                "decision": "EXECUTE",
                "reason": f"All Engine Gates Cleared. Wick-to-Body Matrix: {rwb_ratio:.2f}",
                "allocated_size": size,
            }

        # Faulty route exit structure path mapping
        self.system_status = "IDLE"
        failed_gates = []
        if not gate_a:
            failed_gates.append("Gate A (S/R Zone Match)")
        if not gate_b:
            failed_gates.append("Gate B (EMA Structure Alignment)")
        if not gate_c:
            failed_gates.append("Gate C (RSI Momentum > 50)")

        return {
            "decision": "IDLE",
            "reason": f"Gate failure rejection: {', '.join(failed_gates)}",
            "allocated_size": 0.0,
        }

    def register_trade_outcome(self, is_profit: bool, loss_amount: float = 0.0):
        """Updates internal risk variables dynamically to avoid cognitive narrowing metrics."""
        if is_profit:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.current_daily_drawdown += loss_amount


# =========================================================================
# RUNTIME SIMULATION WORKFLOW TESTBED
# =========================================================================
if __name__ == "__main__":
    print("Initializing DecodeLabs Systematic Trading Framework Test Run...")

    # Instantiating the asset class pipeline configurations
    engine = IPODecisionEngine(
        daily_loss_limit=1000.0,
        support_level=100.0,
        resistance_level=120.0,
        tolerance_pct=0.01,
    )

    # Simulate a sequence of candles to warm up indicators
    sample_ohlcvs = [
        {"open": 101.0, "high": 102.5, "low": 100.5, "close": 102.0},
        {"open": 102.0, "high": 103.0, "low": 101.5, "close": 102.8},
        {"open": 102.8, "high": 104.0, "low": 102.5, "close": 103.5},
    ]

    now = datetime.now()
    for candle in sample_ohlcvs:
        result = engine.execute_pipeline(candle, now, base_position_size=10.0)
        print(f"Candle close={candle['close']}: Decision -> {result}")

    # Example of registering a losing trade
    engine.register_trade_outcome(is_profit=False, loss_amount=200.0)
    print("After a loss, consecutive_losses=", engine.consecutive_losses)

    # Another candle to show half-size rule kicking in when consecutive losses >= 2
    engine.register_trade_outcome(is_profit=False, loss_amount=100.0)
    print("After second loss, consecutive_losses=", engine.consecutive_losses)

    candle = {"open": 103.5, "high": 104.5, "low": 103.0, "close": 104.0}
    result = engine.execute_pipeline(candle, now, base_position_size=10.0)
    print(f"Candle close={candle['close']}: Decision -> {result}")
