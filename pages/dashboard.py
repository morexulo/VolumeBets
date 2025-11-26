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
# Settings
# --------------------------------------------------------------------
MIN_BETS = 30  # minimum number of bets required to consider a group


# --------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------
def normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure 'date' column is a clean, Arrow-compatible datetime64[ns].
    """
    df = df.copy()

    if "date" not in df.columns:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()]
    df["date"] = df["date"].dt.normalize()
    df["date"] = df["date"].astype("datetime64[ns]")

    return df


def prepare_base_df(df: pd.DataFrame) -> pd.DataFrame:
    """Base cleaning for all analyses (in REAL DOLLARS)."""
    df = df.copy()
    df = normalize_date_column(df)

    # Ensure numeric columns are numeric
    for col in ["odds", "stake", "winnings", "profit", "roi_pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize text columns
    for col in ["bet_type", "sport", "win_loss", "result"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Keep only rows with valid stake for ROI
    if "stake" in df.columns:
        df = df[df["stake"].notna() & (df["stake"] > 0)]

    return df


def compute_roi_by_bet_type(df: pd.DataFrame) -> pd.DataFrame:
    """ROI, win-rate and totals grouped by bet_type (all in dollars)."""
    df = prepare_base_df(df)

    if "bet_type" not in df.columns:
        return pd.DataFrame()

    is_win = df["win_loss"].str.lower().eq("win") if "win_loss" in df.columns else None
    is_loss = df["win_loss"].str.lower().eq("loss") if "win_loss" in df.columns else None

    agg = {
        "bet": "count",
        "stake": "sum",
        "profit": "sum",
    }
    if is_win is not None:
        df["__is_win"] = is_win
        agg["__is_win"] = "sum"
    if is_loss is not None:
        df["__is_loss"] = is_loss
        agg["__is_loss"] = "sum"

    grouped = (
        df.groupby("bet_type")
        .agg(agg)
        .rename(
            columns={
                "bet": "bets",
                "stake": "stake_total",
                "profit": "profit_total",
            }
        )
    )

    # Minimum bets filter
    grouped = grouped[grouped["bets"] >= MIN_BETS]
    if grouped.empty:
        return pd.DataFrame()

    # Win-rate
    if "__is_win" in grouped.columns and "__is_loss" in grouped.columns:
        wins = grouped["__is_win"]
        losses = grouped["__is_loss"]
        grouped["win_rate_pct"] = (wins / (wins + losses)) * 100
        grouped = grouped.drop(columns=["__is_win", "__is_loss"], errors="ignore")

    # ROI in %
    grouped["roi_pct"] = (grouped["profit_total"] / grouped["stake_total"]) * 100

    # Ordenar de mayor a menor ROI
    grouped = grouped.sort_values("roi_pct", ascending=False).reset_index()

    return grouped


def build_equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    """
    Equity curve in REAL DOLLARS over time.

    Además:
    - Recorta la serie al ÚLTIMO día en el que cambia la equity
      (última apuesta con profit != 0), para que no haya una
      línea plana “futura” sin datos nuevos.
    """
    df = df.copy()
    df = normalize_date_column(df)

    if "date" not in df.columns or "profit" not in df.columns:
        return pd.DataFrame()

    df = df.sort_values("date")
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0.0)

    # Equity y drawdown
    df["equity"] = df["profit"].cumsum()
    df["running_max"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] - df["running_max"]

    # Recortar a la última apuesta que cambió equity (profit != 0)
    if (df["profit"] != 0).any():
        last_change_idx = df.index[df["profit"] != 0].max()
        df = df.loc[:last_change_idx]

    return df[["date", "equity", "running_max", "drawdown"]]


def compute_sport_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Win-rate, ROI and totals by sport (dollars, min bets filter)."""
    df = prepare_base_df(df)

    if "sport" not in df.columns:
        return pd.DataFrame()

    is_win = df["win_loss"].str.lower().eq("win") if "win_loss" in df.columns else None
    is_loss = df["win_loss"].str.lower().eq("loss") if "win_loss" in df.columns else None

    agg = {
        "bet": "count",
        "stake": "sum",
        "profit": "sum",
    }
    if is_win is not None:
        df["__is_win"] = is_win
        agg["__is_win"] = "sum"
    if is_loss is not None:
        df["__is_loss"] = is_loss
        agg["__is_loss"] = "sum"

    grouped = (
        df.groupby("sport")
        .agg(agg)
        .rename(
            columns={
                "bet": "bets",
                "stake": "stake_total",
                "profit": "profit_total",
            }
        )
    )

    # Minimum bets filter
    grouped = grouped[grouped["bets"] >= MIN_BETS]
    if grouped.empty:
        return pd.DataFrame()

    # Win-rate
    if "__is_win" in grouped.columns and "__is_loss" in grouped.columns:
        wins = grouped["__is_win"]
        losses = grouped["__is_loss"]
        grouped["win_rate_pct"] = (wins / (wins + losses)) * 100
        grouped = grouped.drop(columns=["__is_win", "__is_loss"], errors="ignore")

    # ROI %
    grouped["roi_pct"] = (grouped["profit_total"] / grouped["stake_total"]) * 100

    # Ordenar de mayor a menor ROI
    grouped = grouped.sort_values("roi_pct", ascending=False).reset_index()

    return grouped


# --------------------------------------------------------------------
# Page configuration
# --------------------------------------------------------------------
st.set_page_config(
    page_title="Tipster Analytics – Dashboard",
    page_icon="💵",
    layout="wide",
)

st.title("Tipster Analytics – Real Money Performance Dashboard")
st.write(
    f"All metrics here are calculated in **real dollars** based on Stake and Winnings. "
    f"Only bet types and sports with at least **{MIN_BETS} bets** are included "
    f"for ROI and win-rate to avoid misleading stats on tiny samples."
)


# --------------------------------------------------------------------
# Sidebar – data loading
# --------------------------------------------------------------------
st.sidebar.header("1. Load data")

uploaded_file = st.sidebar.file_uploader(
    "Upload betting CSV file",
    type=["csv"],
    help="File like 'All Spots Bets 2025', separated by ';'.",
)

example_path = os.path.join(ROOT_DIR, "data", "allsportsbets(2025).csv")
use_example = False
if os.path.exists(example_path):
    use_example = st.sidebar.checkbox(
        "Use example CSV from data/ folder",
        value=uploaded_file is None,
        help="Use the local file if you don't want to upload it manually.",
    )

df: Optional[pd.DataFrame] = None

if uploaded_file is not None:
    st.success("CSV uploaded successfully.")
    df = load_bets_csv(uploaded_file)
elif use_example and os.path.exists(example_path):
    st.info("Using example CSV from data/ folder.")
    df = load_bets_csv(example_path)
else:
    st.warning("Upload a CSV or enable the example file option to continue.")
    st.stop()

if df is None or df.empty:
    st.error("The loaded DataFrame is empty. Please check the CSV.")
    st.stop()

df = normalize_date_column(df)


# --------------------------------------------------------------------
# 1) ROI by Bet Type (dollars)
# --------------------------------------------------------------------
st.header("1. ROI by Bet Type (min. 30 bets, real $)")

roi_bt = compute_roi_by_bet_type(df)

if roi_bt.empty:
    st.warning(
        f"Could not compute ROI by bet type with the minimum of {MIN_BETS} bets. "
        f"Increase the sample size or lower the threshold in the code if needed."
    )
else:
    # Ordenar explícitamente por ROI % descendente
    roi_bt = roi_bt.sort_values("roi_pct", ascending=False)

    col_table, col_chart = st.columns([2, 3])

    with col_table:
        st.markdown("**Detailed table (in dollars)**")
        display_cols = [
            "bet_type",
            "bets",
            "stake_total",
            "profit_total",
            "win_rate_pct",
            "roi_pct",
        ]
        display_cols = [c for c in display_cols if c in roi_bt.columns]
        st.dataframe(roi_bt[display_cols].round(2), use_container_width=True)

    with col_chart:
        st.markdown("**ROI % by Bet Type (ordered)**")

        import plotly.express as px

        fig = px.bar(
            roi_bt,
            x="bet_type",
            y="roi_pct",
            text=roi_bt["roi_pct"].round(2).astype(str) + "%",
            title="ROI % by Bet Type (sorted high → low)",
        )

        fig.update_traces(
            textposition="outside",
            marker_color="#74b9ff"
        )
        fig.update_layout(
            xaxis_title="Bet Type",
            yaxis_title="ROI %",
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"ROI is calculated as total profit / total stake for each bet type, in real dollars. "
        f"Only bet types with at least {MIN_BETS} bets are included. "
        f"Bars are sorted from highest to lowest ROI%."
    )


# --------------------------------------------------------------------
# 2) Equity Curve (real dollars)
# --------------------------------------------------------------------
st.header("2. Equity Curve (Real Dollars over Time)")

equity_df = build_equity_curve(df)

if equity_df.empty:
    st.warning("Could not build equity curve (missing date or profit).")
else:
    # Elimina cualquier fila que tenga equity = 0 al principio (antes de la primera apuesta)
    first_real = equity_df[equity_df["equity"] != 0].index
    if len(first_real) > 0:
        equity_df = equity_df.loc[first_real[0]:]

    final_equity = equity_df["equity"].iloc[-1]
    max_drawdown = equity_df["drawdown"].min()
    peak_equity = equity_df["running_max"].max()

    c1, c2, c3 = st.columns(3)
    c1.metric("Final equity ($)", f"{final_equity:.2f}")
    c2.metric("Max drawdown ($)", f"{max_drawdown:.2f}")
    c3.metric("Peak equity ($)", f"{peak_equity:.2f}")

    # Gráfico limpiado: solo desde el primer cambio real
    st.line_chart(
        equity_df.set_index("date")[["equity", "running_max"]],
        use_container_width=True
    )

    st.caption(
        "Equity is the cumulative sum of profit in real dollars. "
        "The curve begins only at the first real bankroll change, "
        "hiding months with no activity."
    )

# --------------------------------------------------------------------
# 3) Win-Rate and ROI by Sport (dollars)
# --------------------------------------------------------------------
st.header("3. Win-rate and ROI by Sport (min. 30 bets, real $)")

sport_stats = compute_sport_stats(df)

if sport_stats.empty:
    st.warning(
        f"Could not compute sport-level stats with the minimum of {MIN_BETS} bets "
        f"per sport. Increase the sample size or adjust the threshold."
    )
else:

    st.markdown("### Ordering options")

    order_option = st.radio(
        "Sort chart by:",
        ["ROI % (highest first)", "Number of bets (highest first)"],
        index=0,
        horizontal=True
    )

    # Ordenar según la opción seleccionada
    if order_option == "ROI % (highest first)":
        ordered = sport_stats.sort_values("roi_pct", ascending=False)
    else:
        ordered = sport_stats.sort_values("bets", ascending=False)

    # -------------------------------
    # Tabla de performance
    # -------------------------------
    st.markdown("**Sport performance table (sorted)**")

    display_cols = [
        "sport",
        "bets",
        "stake_total",
        "profit_total",
        "win_rate_pct",
        "roi_pct",
    ]
    display_cols = [c for c in display_cols if c in ordered.columns]

    st.dataframe(ordered[display_cols].round(2), use_container_width=True)

    # -------------------------------
    # Gráfico con etiquetas
    # -------------------------------
    st.markdown("**ROI % by Sport (ordered)**")

    import altair as alt

    chart_data = ordered[["sport", "roi_pct", "bets"]].copy()
    chart_data["bets_label"] = (
        "NUMBER OF BETS = " + chart_data["bets"].astype(int).astype(str)
    )

    bars = (
        alt.Chart(chart_data)
        .mark_bar(color="#8ec7ff")
        .encode(
            x=alt.X("sport:N", sort=list(chart_data["sport"]), title="Sport"),
            y=alt.Y("roi_pct:Q", title="ROI %"),
            tooltip=["sport", "roi_pct", "bets"],
        )
    )

    # Etiqueta ROI %
    labels_roi = (
        alt.Chart(chart_data)
        .mark_text(
            align="center",
            baseline="bottom",
            dy=-3,
            color="white",
            fontSize=12,
            fontWeight="bold",
        )
        .encode(
            x=alt.X("sport:N", sort=list(chart_data["sport"])),
            y="roi_pct:Q",
            text=alt.Text("roi_pct:Q", format=".2f"),
        )
    )

    # Etiqueta NUMBER OF BETS dentro de la barra
    labels_bets = (
        alt.Chart(chart_data)
        .mark_text(
            align="center",
            baseline="top",
            dy=14,
            color="#000000",
            fontSize=11,
        )
        .encode(
            x=alt.X("sport:N", sort=list(chart_data["sport"])),
            y="roi_pct:Q",
            text="bets_label:N",
        )
    )

    final_chart = bars + labels_roi + labels_bets

    st.altair_chart(final_chart, use_container_width=True)

    st.caption(
        "Bars are sorted according to the selected method. "
        "Each bar shows the ROI% on top and the number of bets inside."
    )


# --------------------------------------------------------------------
# 4) Best and Worst Markets (Bet Types, dollars)
# --------------------------------------------------------------------
st.header("4. Best and Worst Markets (Bet Types, real $)")

if roi_bt.empty:
    st.warning(
        "Market ranking uses ROI by bet type, but there are no bet types "
        f"with at least {MIN_BETS} bets."
    )
else:
    top_n = 3

    sorted_bt = roi_bt.sort_values("roi_pct", ascending=False)

    top_markets = sorted_bt.head(top_n)

    worst_markets = sorted_bt.tail(top_n)

    # Ensure they don't overlap
    worst_markets = worst_markets[~worst_markets["bet_type"].isin(top_markets["bet_type"])]

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Top profitable markets")
        st.dataframe(
            top_markets[["bet_type", "bets", "roi_pct", "profit_total"]].round(2),
            use_container_width=True,
        )

    with col_right:
        st.subheader("Worst markets")
        st.dataframe(
            worst_markets[["bet_type", "bets", "roi_pct", "profit_total"]].round(2),
            use_container_width=True,
        )

    st.caption(
        f"These rankings only consider bet types with at least {MIN_BETS} bets, "
        "and are ordered from best to worst by ROI in dollars."
    )
