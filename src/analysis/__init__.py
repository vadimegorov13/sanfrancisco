"""
Analysis package 

Modules:
  pipeline  — end-to-end v1 orchestrator (run_v1_pipeline)
  plotter   — figure generation from merged table
  scorer    — composite issue-pressure score
  clusterer — hierarchical clustering
  anomaly   — anomaly detection
"""

from .pipeline import run_v1_pipeline

__all__ = ["run_v1_pipeline"]
