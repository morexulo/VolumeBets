import os
import pandas as pd
from utils.data_loader import load_bets_csv


DATA_PATH = os.path.join("data", "allsportsbets(2025).csv")


def main():
    print("=== Tipster CSV Audit Tool ===")
    print(f"Loading CSV: {DATA_PATH}")

    if not os.path.exists(DATA_PATH):
        print("ERROR: CSV not found.")
        return

    df = load_bets_csv(DATA_PATH)

    print("\n--- HEAD (first 20 rows) ---")
    print(df.head(20))

    print("\n--- Column types ---")
    print(df.dtypes)

    print("\n--- Unique bet types ---")
    if "bet_type" in df.columns:
        print(df["bet_type"].unique())

    print("\n--- Unique sports ---")
    if "sport" in df.columns:
        print(df["sport"].unique())

    print("\n--- Statistics summary (numerical columns) ---")
    print(df.describe(include="number"))

    # ======================================================
    # VALIDATION CHECKS
    # ======================================================

    issues = {}

    # 1) Wins with negative profit
    if "win_loss" in df.columns and "profit" in df.columns:
        mask = (df["win_loss"].str.lower() == "win") & (df["profit"] < 0)
        issues["wins_negative_profit"] = df[mask]

    # 2) Loss with positive profit
        mask2 = (df["win_loss"].str.lower() == "loss") & (df["profit"] > 0)
        issues["loss_positive_profit"] = df[mask2]

    # 3) Zero or negative stake
    if "stake" in df.columns:
        mask3 = df["stake"] <= 0
        issues["invalid_stake"] = df[mask3]

    # 4) Winnings lower than 0 on Win
    if "winnings" in df.columns:
        mask4 = (df["win_loss"].str.lower() == "win") & (df["winnings"] <= 0)
        issues["win_with_zero_winnings"] = df[mask4]

    # 5) ROI absurd (>300% or < -200%)
    if "roi_pct" in df.columns:
        mask5 = (df["roi_pct"] > 300) | (df["roi_pct"] < -200)
        issues["absurd_roi"] = df[mask5]

    # ======================================================
    # REPORT
    # ======================================================

    print("\n=== VALIDATION REPORT ===")

    for issue_name, issue_df in issues.items():
        count = len(issue_df)
        if count > 0:
            print(f"\n⚠ {issue_name} → {count} problematic rows")
            print(issue_df.head(10))
        else:
            print(f"\n✓ {issue_name} → OK (0 issues)")

    print("\n=== AUDIT COMPLETE ===")


if __name__ == "__main__":
    main()
