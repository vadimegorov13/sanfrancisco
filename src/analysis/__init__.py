"""
Analysis package.

Modules:
  pipeline  — analysis pipeline orchestrator (run_pipeline)
  plotter   — figure generation from merged table
  scorer    — composite issue-pressure score
  clusterer — hierarchical clustering
  anomaly   — anomaly detection
"""

from .pipeline import run_pipeline

__all__ = ["run_pipeline"]
