"""Heuristic analysis of trading patterns."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class PoliticianMetrics:
    """Trading metrics for a single politician."""

    politician_id: str
    politician_name: str
    total_trades: int
    purchase_count: int
    sale_count: int
    unique_assets: int
    total_volume_min: float
    total_volume_max: float
    sector_concentration: dict[str, int]
    recent_activity_score: float  # Trades in last 30 days weighted higher


@dataclass
class AssetMetrics:
    """Trading metrics for a single asset."""

    asset_id: str
    asset_name: str
    ticker: str | None
    sector: str | None
    total_trades: int
    politician_count: int
    purchase_count: int
    sale_count: int
    net_flow: float  # Positive = more buying, negative = more selling


@dataclass
class SectorMetrics:
    """Trading metrics by sector."""

    sector: str
    total_trades: int
    politician_count: int
    purchase_count: int
    sale_count: int
    net_flow: float
    top_assets: list[dict[str, Any]]


@dataclass
class CommitteeCorrelation:
    """Correlation between committee membership and trading activity."""

    committee: str
    sector: str
    correlation_score: float  # 0-1, higher = stronger correlation
    trade_count: int
    politician_count: int


class HeuristicAnalyzer:
    """Analyzes trading patterns and calculates heuristics."""

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self.logger = structlog.get_logger()

    def analyze_politicians(
        self, trades: list[dict[str, Any]], politicians: list[dict[str, Any]]
    ) -> list[PoliticianMetrics]:
        """Calculate metrics for each politician.

        Args:
            trades: List of trade records from API
            politicians: List of politician records from API

        Returns:
            List of politician metrics sorted by activity
        """
        # Group trades by politician
        trades_by_politician: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            pid = trade.get("politician_id") or trade.get("report", {}).get("politician_id")
            if pid:
                trades_by_politician[pid].append(trade)

        # Build politician lookup
        politician_map = {p["id"]: p for p in politicians}

        metrics: list[PoliticianMetrics] = []
        cutoff_date = date.today() - timedelta(days=30)

        for pid, ptrades in trades_by_politician.items():
            pol = politician_map.get(pid, {})
            name = f"{pol.get('first_name', '')} {pol.get('last_name', '')}".strip() or "Unknown"

            purchases = [t for t in ptrades if t.get("transaction_type") == "purchase"]
            sales = [t for t in ptrades if t.get("transaction_type") in ("sale", "sale_full")]

            # Calculate volume
            volume_min = sum(
                t.get("amount_min", 0) or 0 for t in ptrades if t.get("amount_min")
            )
            volume_max = sum(
                t.get("amount_max", 0) or 0 for t in ptrades if t.get("amount_max")
            )

            # Sector concentration
            sectors: dict[str, int] = defaultdict(int)
            unique_assets = set()
            recent_trades = 0

            for t in ptrades:
                asset = t.get("asset", {})
                sector = asset.get("sector", "Unknown")
                sectors[sector] += 1
                unique_assets.add(asset.get("id", t.get("asset_id")))

                # Recent activity score
                tdate = t.get("transaction_date")
                if tdate:
                    try:
                        if isinstance(tdate, str):
                            tdate = date.fromisoformat(tdate)
                        if isinstance(tdate, date) and tdate >= cutoff_date:
                            recent_trades += 1
                    except (ValueError, TypeError):
                        pass

            # Weight recent trades more heavily
            recent_score = recent_trades * 2 + (len(ptrades) - recent_trades) * 0.5

            metrics.append(
                PoliticianMetrics(
                    politician_id=pid,
                    politician_name=name,
                    total_trades=len(ptrades),
                    purchase_count=len(purchases),
                    sale_count=len(sales),
                    unique_assets=len(unique_assets),
                    total_volume_min=volume_min,
                    total_volume_max=volume_max,
                    sector_concentration=dict(sectors),
                    recent_activity_score=recent_score,
                )
            )

        # Sort by recent activity score
        return sorted(metrics, key=lambda x: x.recent_activity_score, reverse=True)

    def analyze_assets(self, trades: list[dict[str, Any]]) -> list[AssetMetrics]:
        """Calculate metrics for each asset.

        Args:
            trades: List of trade records from API

        Returns:
            List of asset metrics sorted by activity
        """
        # Group trades by asset
        trades_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            asset_id = trade.get("asset_id") or trade.get("asset", {}).get("id")
            if asset_id:
                trades_by_asset[asset_id].append(trade)

        metrics: list[AssetMetrics] = []

        for asset_id, atrades in trades_by_asset.items():
            # Get asset info from first trade
            first_trade = atrades[0]
            asset = first_trade.get("asset", {})
            name = asset.get("name", "Unknown")
            ticker = asset.get("ticker")
            sector = asset.get("sector")

            purchases = [t for t in atrades if t.get("transaction_type") == "purchase"]
            sales = [t for t in atrades if t.get("transaction_type") in ("sale", "sale_full")]

            # Calculate net flow (simplified: count-based)
            net_flow = len(purchases) - len(sales)

            # Count unique politicians
            politicians = set()
            for t in atrades:
                pid = t.get("politician_id") or t.get("report", {}).get("politician_id")
                if pid:
                    politicians.add(pid)

            metrics.append(
                AssetMetrics(
                    asset_id=asset_id,
                    asset_name=name,
                    ticker=ticker,
                    sector=sector,
                    total_trades=len(atrades),
                    politician_count=len(politicians),
                    purchase_count=len(purchases),
                    sale_count=len(sales),
                    net_flow=net_flow,
                )
            )

        # Sort by total trades
        return sorted(metrics, key=lambda x: x.total_trades, reverse=True)

    def analyze_sectors(self, trades: list[dict[str, Any]]) -> list[SectorMetrics]:
        """Calculate metrics by sector.

        Args:
            trades: List of trade records from API

        Returns:
            List of sector metrics sorted by activity
        """
        # Group trades by sector
        trades_by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            asset = trade.get("asset", {})
            sector = asset.get("sector", "Unknown")
            trades_by_sector[sector].append(trade)

        metrics: list[SectorMetrics] = []

        for sector, strades in trades_by_sector.items():
            purchases = [t for t in strades if t.get("transaction_type") == "purchase"]
            sales = [t for t in strades if t.get("transaction_type") in ("sale", "sale_full")]

            # Calculate net flow
            net_flow = len(purchases) - len(sales)

            # Count unique politicians
            politicians = set()
            for t in strades:
                pid = t.get("politician_id") or t.get("report", {}).get("politician_id")
                if pid:
                    politicians.add(pid)

            # Top assets in this sector
            asset_counts: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "ticker": None})
            for t in strades:
                asset = t.get("asset", {})
                aid = asset.get("id", "unknown")
                asset_counts[aid]["count"] += 1
                asset_counts[aid]["name"] = asset.get("name", "Unknown")
                asset_counts[aid]["ticker"] = asset.get("ticker")

            top_assets = sorted(
                [{"id": k, **v} for k, v in asset_counts.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:5]

            metrics.append(
                SectorMetrics(
                    sector=sector,
                    total_trades=len(strades),
                    politician_count=len(politicians),
                    purchase_count=len(purchases),
                    sale_count=len(sales),
                    net_flow=net_flow,
                    top_assets=top_assets,
                )
            )

        # Sort by total trades
        return sorted(metrics, key=lambda x: x.total_trades, reverse=True)

    def detect_unusual_patterns(
        self, trades: list[dict[str, Any]], politicians: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect unusual trading patterns.

        Args:
            trades: List of trade records from API
            politicians: List of politician records from API

        Returns:
            List of detected patterns/alerts
        """
        alerts: list[dict[str, Any]] = []

        # Build politician lookup
        politician_map = {p["id"]: p for p in politicians}

        # 1. Detect concentrated buying in a single asset
        asset_politicians: dict[str, set[str]] = defaultdict(set)
        for trade in trades:
            asset_id = trade.get("asset_id") or trade.get("asset", {}).get("id")
            pid = trade.get("politician_id") or trade.get("report", {}).get("politician_id")
            if asset_id and pid:
                asset_politicians[asset_id].add(pid)

        for asset_id, pols in asset_politicians.items():
            if len(pols) >= 3:  # 3+ politicians trading same asset
                # Get asset info
                for trade in trades:
                    if (trade.get("asset_id") == asset_id or
                        trade.get("asset", {}).get("id") == asset_id):
                        asset = trade.get("asset", {})
                        alerts.append({
                            "type": "concentrated_activity",
                            "severity": "medium",
                            "message": f"{len(pols)} politicians trading {asset.get('name', asset_id)}",
                            "asset_id": asset_id,
                            "asset_name": asset.get("name"),
                            "ticker": asset.get("ticker"),
                            "politician_count": len(pols),
                        })
                        break

        # 2. Detect large transactions
        for trade in trades:
            amount_min = trade.get("amount_min")
            if amount_min and amount_min >= 100000:  # $100k+
                pid = trade.get("politician_id") or trade.get("report", {}).get("politician_id")
                pol = politician_map.get(pid, {})
                asset = trade.get("asset", {})

                alerts.append({
                    "type": "large_transaction",
                    "severity": "low",
                    "message": (
                        f"Large transaction: {pol.get('last_name', 'Unknown')} "
                        f"{trade.get('transaction_type', 'traded')} "
                        f"{asset.get('name', 'unknown asset')}"
                    ),
                    "politician_id": pid,
                    "politician_name": f"{pol.get('first_name', '')} {pol.get('last_name', '')}".strip(),
                    "asset_name": asset.get("name"),
                    "amount_min": amount_min,
                    "transaction_type": trade.get("transaction_type"),
                })

        # 3. Detect rapid trading (multiple trades in short period)
        trades_by_politician: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            pid = trade.get("politician_id") or trade.get("report", {}).get("politician_id")
            if pid:
                trades_by_politician[pid].append(trade)

        for pid, ptrades in trades_by_politician.items():
            if len(ptrades) >= 5:  # 5+ trades in period
                pol = politician_map.get(pid, {})
                alerts.append({
                    "type": "high_activity",
                    "severity": "low",
                    "message": f"{pol.get('last_name', 'Unknown')} made {len(ptrades)} trades",
                    "politician_id": pid,
                    "politician_name": f"{pol.get('first_name', '')} {pol.get('last_name', '')}".strip(),
                    "trade_count": len(ptrades),
                })

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return alerts
