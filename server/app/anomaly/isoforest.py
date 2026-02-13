import pandas as pd
from sklearn.ensemble import IsolationForest

from app.constants import ISOFOREST_MIN_DAYS


def isoforest_flags(feature_df: pd.DataFrame) -> list[dict]:
    """Multivariate outlier days over the four derived-metric z's.

    feature_df: indexed by day, one column per derived metric (z values).
    Rows with any NaN are dropped, never imputed. Returns flagged rows as
    {day, score, top_feature} — top_feature gives the user a "why".
    """
    df = feature_df.dropna()
    if len(df) < ISOFOREST_MIN_DAYS:
        return []
    model = IsolationForest(n_estimators=200, contamination=0.03, random_state=0)
    model.fit(df.values)
    scores = model.decision_function(df.values)
    preds = model.predict(df.values)
    flags = []
    for i, (day, row) in enumerate(df.iterrows()):
        if preds[i] == -1:
            flags.append({"day": day, "score": float(scores[i]),
                          "top_feature": row.abs().idxmax()})
    return flags
