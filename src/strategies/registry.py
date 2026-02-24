"""Strategy Registry — hybrid SQLite metadata + disk artifacts.

Stores strategy lifecycle information in SQLite for queryability and saves
PyTorch .pt model files to disk with SHA256 integrity verification.

Lifecycle statuses:
  experimental      → approved_for_paper → approved_for_live

Promotion Framework:
  Promotion decisions must comply with the institutional-grade framework
  documented in docs/PROMOTION_FRAMEWORK.md. All Gate B (paper → live)
  promotions must be recorded as a decision rubric JSON conforming to
  reports/promotions/decision_rubric.json and stored in reports/promotions/.
  Weekly reviews should use docs/WEEKLY_REVIEW_TEMPLATE.md.

Design (Q3 research answer):
  - SQLite table for: ID, name, version, type, parameters, artifact path,
    SHA256 hash, status, created timestamp.
  - Disk folder: strategies/<name>/<version>/model.pt
  - SHA256 verified on every load() to detect tampering or file corruption.
  - Rule-based strategies (type='rule') can be saved with no artifact file.
  - Neural net strategies (type='nn') must supply weights bytes.

Usage:
    from src.strategies.registry import StrategyRegistry

    reg = StrategyRegistry(db_path="trading.db", artifacts_dir="strategies")
    reg.save("bollinger_bands", "1.0.0", "rule", {"period": 20, "std": 2.0})
    meta = reg.load("bollinger_bands", "1.0.0")
    reg.promote("bollinger_bands", "1.0.0", "approved_for_paper")
    rows = reg.list_strategies(status="approved_for_paper")
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_VALID_STATUSES = ("experimental", "approved_for_paper", "approved_for_live")
_VALID_TYPES = ("rule", "nn")
_DEFAULT_PAPER_READINESS_THRESHOLDS = {
    "min_closed_trade_count": 20,
    "min_win_rate": 0.50,
    "min_profit_factor": 1.10,
    "min_realized_pnl": 0.0,
    "min_fill_rate": 0.90,
    "max_avg_slippage_pct": 0.0025,
}


def paper_readiness_failures(
    paper_summary: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None,
) -> List[str]:
    """Return a list of failed paper-readiness checks (empty means ready)."""
    cfg = dict(_DEFAULT_PAPER_READINESS_THRESHOLDS)
    if thresholds:
        cfg.update(thresholds)

    closed_trade_count = int(paper_summary.get("closed_trade_count", 0) or 0)
    win_rate = float(paper_summary.get("win_rate", 0.0) or 0.0)
    profit_factor_raw = paper_summary.get("profit_factor", 0.0)
    if isinstance(profit_factor_raw, str) and profit_factor_raw.lower() == "inf":
        profit_factor = float("inf")
    else:
        profit_factor = float(profit_factor_raw or 0.0)
    realized_pnl = float(paper_summary.get("realized_pnl", 0.0) or 0.0)
    fill_rate = float(paper_summary.get("fill_rate", 0.0) or 0.0)
    avg_slippage_pct = float(paper_summary.get("avg_slippage_pct", 0.0) or 0.0)

    failures: List[str] = []
    if closed_trade_count < int(cfg["min_closed_trade_count"]):
        failures.append(
            f"closed_trade_count={closed_trade_count} < min_closed_trade_count={int(cfg['min_closed_trade_count'])}"
        )
    if win_rate < float(cfg["min_win_rate"]):
        failures.append(f"win_rate={win_rate:.6f} < min_win_rate={float(cfg['min_win_rate']):.6f}")
    if profit_factor < float(cfg["min_profit_factor"]):
        failures.append(
            f"profit_factor={profit_factor:.6f} < min_profit_factor={float(cfg['min_profit_factor']):.6f}"
        )
    if realized_pnl < float(cfg["min_realized_pnl"]):
        failures.append(
            f"realized_pnl={realized_pnl:.6f} < min_realized_pnl={float(cfg['min_realized_pnl']):.6f}"
        )
    if fill_rate < float(cfg["min_fill_rate"]):
        failures.append(
            f"fill_rate={fill_rate:.6f} < min_fill_rate={float(cfg['min_fill_rate']):.6f}"
        )
    if avg_slippage_pct > float(cfg["max_avg_slippage_pct"]):
        failures.append(
            f"avg_slippage_pct={avg_slippage_pct:.6f} > max_avg_slippage_pct={float(cfg['max_avg_slippage_pct']):.6f}"
        )

    return failures


class StrategyRegistry:
    """
    Hybrid strategy registry: SQLite metadata + disk artifacts.

    Rule-based strategies store only parameters in SQLite (no artifact file).
    Neural network strategies store parameters + a .pt file with hash verification.
    """

    def __init__(
        self,
        db_path: str = "trading.db",
        artifacts_dir: str = "strategies",
    ):
        self._db_path = db_path
        self._artifacts_dir = Path(artifacts_dir)
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    strategy_id     TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    version         TEXT NOT NULL,
                    type            TEXT CHECK(type IN ('rule', 'nn')),
                    parameters      TEXT,
                    artifact_path   TEXT,
                    artifact_sha256 TEXT,
                    status          TEXT CHECK(status IN (
                        'experimental',
                        'approved_for_paper',
                        'approved_for_live'
                    )),
                    created_at      TEXT NOT NULL
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        name: str,
        version: str,
        strategy_type: str,
        parameters: Dict[str, Any],
        status: str = "experimental",
        weights: Optional[bytes] = None,
    ) -> str:
        """
        Register a strategy (or update an existing entry via upsert).

        Args:
            name:          Strategy name (e.g., "bollinger_bands").
            version:       Semantic version string (e.g., "1.0.0").
            strategy_type: "rule" for rule-based, "nn" for neural network.
            parameters:    Configuration dict (serialised as JSON).
            status:        Initial lifecycle status (default "experimental").
            weights:       Raw bytes for .pt artifact. Required for type="nn";
                           omit for type="rule".

        Returns:
            strategy_id string (name:version).

        Raises:
            ValueError: Invalid type, status, or missing weights for nn strategy.
        """
        if strategy_type not in _VALID_TYPES:
            raise ValueError(
                f"Invalid strategy_type {strategy_type!r}. " f"Must be one of: {_VALID_TYPES}"
            )
        if status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status {status!r}. Must be one of: {_VALID_STATUSES}")
        if strategy_type == "nn" and weights is None:
            raise ValueError("weights are required for strategy_type='nn'")

        strategy_id = f"{name}:{version}"
        artifact_path_str: Optional[str] = None
        sha256: Optional[str] = None

        if weights is not None:
            folder = self._artifacts_dir / name / version
            folder.mkdir(parents=True, exist_ok=True)
            artifact_file = folder / "model.pt"
            artifact_file.write_bytes(weights)
            artifact_path_str = str(artifact_file)
            sha256 = hashlib.sha256(weights).hexdigest()
            logger.info(f"Artifact saved: {artifact_file}  sha256={sha256[:12]}…")

        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO strategies
                   (strategy_id, name, version, type, parameters,
                    artifact_path, artifact_sha256, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    strategy_id,
                    name,
                    version,
                    strategy_type,
                    json.dumps(parameters),
                    artifact_path_str,
                    sha256,
                    status,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

        logger.info(f"Strategy registered: {strategy_id}  [{status}]")
        return strategy_id

    def load(self, name: str, version: str) -> Dict[str, Any]:
        """
        Load strategy metadata and, if present, verify and return the artifact.

        Returns:
            {
              "metadata": { all SQLite columns, parameters decoded from JSON },
              "weights":  bytes or None
            }

        Raises:
            ValueError: Strategy not found, artifact file missing, or hash mismatch.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM strategies WHERE name=? AND version=?",
                (name, version),
            ).fetchone()

        if row is None:
            raise ValueError(f"Strategy not found: {name}:{version}")

        metadata = dict(row)
        metadata["parameters"] = json.loads(metadata.get("parameters") or "{}")

        weights: Optional[bytes] = None
        if metadata.get("artifact_path"):
            artifact_file = Path(metadata["artifact_path"])
            if not artifact_file.exists():
                raise ValueError(f"Artifact file missing for {name}:{version}: {artifact_file}")
            weights = artifact_file.read_bytes()
            actual_sha256 = hashlib.sha256(weights).hexdigest()
            if actual_sha256 != metadata["artifact_sha256"]:
                raise ValueError(
                    f"SHA256 mismatch for {name}:{version}. "
                    f"Expected {metadata['artifact_sha256']}, "
                    f"got {actual_sha256}. Artifact may be corrupted."
                )

        return {"metadata": metadata, "weights": weights}

    def list_strategies(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all registered strategies.

        Args:
            status: Optional filter (e.g., "approved_for_paper").

        Returns:
            List of dicts with parameters decoded from JSON, sorted newest first.
        """
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM strategies WHERE status=? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM strategies ORDER BY created_at DESC").fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["parameters"] = json.loads(d.get("parameters") or "{}")
            result.append(d)
        return result

    def promote(
        self,
        name: str,
        version: str,
        new_status: str,
        *,
        paper_summary: Optional[Dict[str, Any]] = None,
        readiness_thresholds: Optional[Dict[str, float]] = None,
        checklist_path: Optional[str] = None,
    ) -> None:
        """
        Advance a strategy's lifecycle status.

        Valid flow:  experimental → approved_for_paper → approved_for_live

        Promotion to approved_for_live is guarded by paper-readiness metrics.
        Caller must provide paper_summary from paper-session reporting.

        Raises:
            ValueError: Unknown status or strategy not found.
        """
        if new_status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status {new_status!r}. Must be one of: {_VALID_STATUSES}")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM strategies WHERE name=? AND version=?",
                (name, version),
            ).fetchone()
            if row is None:
                raise ValueError(f"Strategy not found: {name}:{version}")

            current_status = str(row["status"])
            if new_status == "approved_for_live":
                from src.promotions.checklist import (
                    load_promotion_checklist,
                    validate_promotion_checklist,
                )

                if checklist_path is None:
                    raise ValueError("Promotion checklist is required for approved_for_live")
                checklist = load_promotion_checklist(checklist_path)
                checklist_errors = validate_promotion_checklist(checklist, name)
                if checklist_errors:
                    raise ValueError("Promotion checklist invalid: " + "; ".join(checklist_errors))
                if current_status != "approved_for_paper":
                    raise ValueError(
                        "Promotion to approved_for_live requires current status approved_for_paper"
                    )
                if paper_summary is None:
                    raise ValueError("paper_summary is required for promotion to approved_for_live")
                failures = paper_readiness_failures(
                    paper_summary,
                    readiness_thresholds,
                )
                if failures:
                    raise ValueError("Paper readiness gate failed: " + "; ".join(failures))

            affected = conn.execute(
                "UPDATE strategies SET status=? WHERE name=? AND version=?",
                (new_status, name, version),
            ).rowcount
            conn.commit()

        if affected == 0:
            raise ValueError(f"Strategy not found: {name}:{version}")
        logger.info(f"Strategy {name}:{version} promoted → [{new_status}]")
