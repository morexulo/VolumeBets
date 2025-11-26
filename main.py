import os
import sys
from typing import Optional

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------
# Add project root to PYTHONPATH so we can import from utils/*
# --------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from utils.data_loader import load_bets_csv  # noqa: E402


# --------------------------------------------------------------------
# Page configuration
# --------------------------------------------------------------------
st.set_page_config(
    page_title="VolumeBets – Data Explorer",
    page_icon="📈",
    layout="wide",
)

st.title("VolumeBets – Data Explorer")
st.write(
    "Upload your betting CSV, check that the data looks correct, "
    "and then use the Dashboard page for full performance analytics."
)


# --------------------------------------------------------------------
# Sidebar – data loading
# --------------------------------------------------------------------
st.header("1. Load data")

# Cargar SIEMPRE el CSV desde la carpeta data/
DATA_PATH = "data/allsportsbets(2025).csv"

try:
    df = load_bets_csv(DATA_PATH)
    st.success(f"Loaded fixed dataset from: {DATA_PATH}")
except Exception as e:
    st.error(f"Failed to load dataset: {e}")
    st.stop()

# Mostrar preview
st.dataframe(df.head(), use_container_width=True)



# --------------------------------------------------------------------
# Data exploration (simple and Arrow-safe)
# --------------------------------------------------------------------
if df is not None and not df.empty:
    st.subheader("Data preview")
    st.dataframe(df.head(20), use_container_width=True)

    # Quick summary metrics
    st.subheader("Quick summary")
    col1, col2, col3, col4 = st.columns(4)

    num_bets = len(df)
    num_sports = df["sport"].nunique() if "sport" in df.columns else 0
    num_bet_types = df["bet_type"].nunique() if "bet_type" in df.columns else 0

    if "date" in df.columns and df["date"].notna().any():
        # date already normalized in loader
        min_date = df["date"].min()
        max_date = df["date"].max()
        date_range_str = f"{min_date.date()} → {max_date.date()}"
    else:
        date_range_str = "N/A"

    col1.metric("Number of bets", num_bets)
    col2.metric("Different sports", num_sports)
    col3.metric("Different bet types", num_bet_types)
    col4.metric("Date range", date_range_str)

    # Column list
    st.subheader("Available columns")
    st.write(list(df.columns))

    st.info(
        "If the preview and summary look correct, open the **Dashboard** page "
        "from the left sidebar to see ROI, equity curve and sport-level performance."
    )
else:
    st.stop()
