"""Deprecated import shim for the Kubernetes dashboard service."""

from app.dashboards.kubernetes.service import get_dashboard_overview

__all__ = ['get_dashboard_overview']
