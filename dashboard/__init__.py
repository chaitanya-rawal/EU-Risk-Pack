"""Self-contained HTML dashboard builder."""

from euro_risk_pack.dashboard.builder import (
    build_dashboard,
    format_metric_cards,
    prepare_chart_data,
)
from euro_risk_pack.dashboard.template import DASHBOARD_TEMPLATE

__all__ = [
    "DASHBOARD_TEMPLATE",
    "build_dashboard",
    "format_metric_cards",
    "prepare_chart_data",
]
