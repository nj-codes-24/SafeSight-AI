"""Cached resources shared by the pages."""
from pathlib import Path

import streamlit as st

from database.database import IncidentDB

WEIGHTS = Path(__file__).resolve().parents[2] / "models" / "best.pt"


@st.cache_resource(show_spinner="Loading detection model")
def get_detector():
    from inference.detector import Detector  # torch is slow to import; only Live monitoring needs it

    return Detector()


@st.cache_resource
def get_db():
    return IncidentDB()


def model_ready() -> bool:
    return WEIGHTS.exists()
