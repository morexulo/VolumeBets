import pandas as pd
from typing import Union, IO, Any


def _to_float(value: Any):
    """
    Convierte strings tipo '0,25', '1.35$', '93%' en float.
    No asume si es dinero o unidades: solo limpia formato.
    """
    if pd.isna(value):
        return pd.NA

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if s == "":
        return pd.NA

    # Quitar símbolos y espacios típicos
    s = s.replace("$", "")
    s = s.replace("%", "")
    s = s.replace(" ", "")

    # Convertir coma decimal europea a punto
    s = s.replace(",", ".")

    try:
        return float(s)
    except Exception:
        return pd.NA


def load_bets_csv(path: Union[str, IO]) -> pd.DataFrame:
    """
    Carga el CSV de apuestas 'All Spots Bets 2025' con formato:

    Cabecera:
        All Spots Bets 2025;;2.00$ Unit;;;
        01/01/2025;Starts at $274.88;Bets;Wins;...
        ... (resumen)
        Date;Bet;Odds;Result;Win/Loss;Stake;Winnings;Unit Stake;Unit Winnings;ROI %;Bet Type;Sport;...

    Reglas importantes:
    - 'Stake' y 'Winnings' están en DÓLARES.
      * Stake = cantidad arriesgada en $
      * Winnings = BENEFICIO NETO en $ (no el payout total)
        - En un win con ROI 93%: stake 0.30$, winnings 0.28$ (profit=0.28)
        - En un loss: stake X, winnings 0$ (profit=0)
    - 'Unit Stake' y 'Unit Winnings' son unidades internas (no las usamos).
    - 'ROI %' original está calculado con unidades (y 0% en muchas pérdidas) → NO lo usamos.

    Devolvemos:
    - date: datetime normalizado (día)
    - stake: float ($ arriesgado)
    - winnings: float ($ beneficio neto)
    - profit: float ($ beneficio neto, igual a winnings)
    - roi_pct: float (% ROI real por apuesta = profit / stake * 100)
    - bet, result, win_loss, bet_type, sport: texto limpio
    """

    # 1) Leer el CSV con el separador correcto y saltando las 3 primeras líneas de metadatos
    df = pd.read_csv(
        path,
        sep=";",
        skiprows=3,  # saltamos título y resumen
        engine="python",
    )

    # 2) Eliminar columnas vacías tipo 'Unnamed: 12'
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    # 3) Normalizar nombres de columnas
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("%", "_pct")
        .str.replace("/", "_")
        .str.replace("__", "_")
    )

    # 4) Renombrados específicos si hace falta
    rename_map = {
        "roi__pct": "roi_pct",  # por si se genera doble underscore
        "win_loss_": "win_loss",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 5) Convertir fecha y normalizarla (dd/mm/yyyy en origen)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df = df[df["date"].notna()]
        df["date"] = df["date"].dt.normalize()
        df["date"] = df["date"].astype("datetime64[ns]")

    # 6) Limpiar columnas de texto clave
    for col in ["bet", "result", "win_loss", "bet_type", "sport"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 7) Convertir a float las columnas numéricas relevantes en $
    #    Stake = dinero arriesgado; Winnings = beneficio neto en $
    money_cols = ["odds", "stake", "winnings"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(_to_float)

    # 8) Profit en dólares: ES IGUAL a 'winnings' (beneficio neto)
    #    NO restamos stake, porque el CSV ya guarda el neto en 'Winnings'.
    if "winnings" in df.columns:
        df["profit"] = df["winnings"]
    else:
        df["profit"] = pd.NA

    # 9) Eliminar ROI % original y unidades internas: NO son fiables para dinero real
    for col in ["roi_pct", "unit_stake", "unit_winnings"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    # 10) Recalcular ROI % REAL por apuesta (en dinero)
    #     roi_pct = profit / stake * 100
    df["roi_pct"] = pd.NA
    if "stake" in df.columns and "profit" in df.columns:
        mask = df["stake"].notna() & (df["stake"] != 0)
        df.loc[mask, "roi_pct"] = (df.loc[mask, "profit"] / df.loc[mask, "stake"]) * 100

    # 11) Filtrar filas claramente inválidas (sin fecha o sin apuesta)
    if "date" in df.columns and "bet" in df.columns:
        df = df[df["date"].notna() & df["bet"].notna()]

    df.reset_index(drop=True, inplace=True)
    return df
