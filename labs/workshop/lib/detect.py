"""Per-port normal model and the detector zoo Lab 08 compares.

Lab 03 fits one Phase I model to one series. Lab 04 fits one geometry to one reference table.
Lab 08 has five ports whose roles differ by more than any shared model could absorb, so every
port gets its own seasonal profile, its own scale, and its own fitted detectors. That choice is
what makes the peer comparison in the RCA section mean anything: if all five shared a model,
"the other ports moved too" would already be baked into every score.

Nothing here is a new algorithm. Max |z| is Lab 04's marginal baseline, Mahalanobis and the two
PCA statistics are Lab 04 §4 and §6, LOF is Lab 02 §7 and Lab 04 §5, and IsolationForest is
Lab 02 §7. They are gathered here so the capstone can call them rather than paste them.

The one addition is MinCovDet, the robust covariance Lab 04's conclusion named as unfinished
business. It answers a question the other two cannot: an empirical covariance estimated on a
reference period that still contains a few contaminated rows is dragged toward those rows, and
the detector then treats the contamination as normal.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf, MinCovDet
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

from .features import FEATURES, time_of_week

MAD_TO_SIGMA = 1.4826
SEED = 0

# Every entry maps a name to a score where larger means more anomalous, which is the only
# property the calibration and scoring code relies on. A detector belongs in this dict when it
# scores one row at a time from a model fitted on normal-only reference rows; a change-point
# statistic that needs a run of samples does not, which is why CUSUM and EWMA stay in Lab 03.
DETECTORS = ("Max |z|", "Mahalanobis", "Robust Mahalanobis", "PCA T2", "PCA SPE",
             "LOF", "IsolationForest")


class PortModel:
    """Seasonal profile, robust scale and fitted detectors for one port.

    Fit on reference rows only. `fit_mask` is expected to have the labelled incident windows
    already removed, which is Phase I practice: known assignable causes come out of the
    reference before the limits are estimated. That step needs the incident log, and depending
    on the log is a real assumption rather than a free one, so the notebook states it where the
    split is made instead of hiding it here.
    """

    def __init__(self, features=FEATURES, n_components_variance=0.95, seed=SEED):
        self.features = list(features)
        self.n_components_variance = n_components_variance
        self.seed = seed

    def fit(self, frame, fit_mask):
        values = frame[self.features].to_numpy(float)
        bucket = time_of_week(frame["timestamp"])
        fit_mask = np.asarray(fit_mask, bool)
        if fit_mask.sum() < 2 * len(self.features):
            raise ValueError(f"reference has {fit_mask.sum()} rows, too few to fit "
                             f"{len(self.features)} features")

        # Median per hour-of-week, taken over reference rows. Median rather than mean because a
        # bucket holds only a handful of samples per week and one survivor of the event purge
        # would move a mean.
        self.profile_ = np.zeros((168, len(self.features)))
        overall = np.median(values[fit_mask], axis=0)
        for b in range(168):
            rows = fit_mask & (bucket == b)
            self.profile_[b] = np.median(values[rows], axis=0) if rows.any() else overall

        residual = values - self.profile_[bucket]
        ref = residual[fit_mask]

        # MAD first, standard deviation only where MAD is exactly zero. On this fleet that
        # fallback fires on error_rate, discard_rate and unknown_proto_pps, whose reference
        # values are zero more than half the time. Those are the signature features of four of
        # the ten incident types, so silently dropping them would make those incidents
        # unattributable; the notebook prints the fallback list rather than letting it pass.
        mad = np.median(np.abs(ref - np.median(ref, axis=0)), axis=0) * MAD_TO_SIGMA
        std = ref.std(axis=0)
        self.scale_ = np.where(mad > 0, mad, std)
        self.mad_fallback_ = [f for f, m in zip(self.features, mad) if m == 0]
        dead = [f for f, s in zip(self.features, self.scale_) if s <= 0]
        if dead:
            raise ValueError(f"features with no spread at all in the reference: {dead}. "
                             "A constant column cannot be standardised; drop it upstream.")

        z_ref = ref / self.scale_
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.lw_ = LedoitWolf().fit(z_ref)
            self.mcd_ = MinCovDet(random_state=self.seed, support_fraction=0.9).fit(z_ref)
            self.pca_ = PCA(random_state=self.seed).fit(z_ref)
            cumulative = np.cumsum(self.pca_.explained_variance_ratio_)
            self.k_ = int(np.searchsorted(cumulative, self.n_components_variance) + 1)
            self.lof_ = LocalOutlierFactor(n_neighbors=20, novelty=True).fit(z_ref)
            self.iforest_ = IsolationForest(n_estimators=300,
                                            random_state=self.seed).fit(z_ref)
        self.condition_number_ = float(np.linalg.cond(self.lw_.covariance_))
        return self

    def standardize(self, frame):
        """Deviation of each sample from its own hour-of-week, in robust units."""
        values = frame[self.features].to_numpy(float)
        bucket = time_of_week(frame["timestamp"])
        return (values - self.profile_[bucket]) / self.scale_

    def _pca_parts(self, z):
        centred = z - self.pca_.mean_
        loadings = self.pca_.components_[:self.k_]
        projected = centred @ loadings.T
        reconstruction = projected @ loadings
        eigenvalues = self.pca_.explained_variance_[:self.k_]
        return projected, reconstruction, centred, eigenvalues

    def score(self, frame):
        """Every detector's score for every row, as a dict of arrays. Higher is more anomalous."""
        z = self.standardize(frame)
        projected, reconstruction, centred, eigenvalues = self._pca_parts(z)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return {
                "Max |z|": np.abs(z).max(axis=1),
                "Mahalanobis": np.sqrt(np.clip(self.lw_.mahalanobis(z), 0, None)),
                "Robust Mahalanobis": np.sqrt(np.clip(self.mcd_.mahalanobis(z), 0, None)),
                "PCA T2": (projected ** 2 / eigenvalues).sum(axis=1),
                "PCA SPE": ((centred - reconstruction) ** 2).sum(axis=1),
                "LOF": -self.lof_.score_samples(z),
                "IsolationForest": -self.iforest_.score_samples(z),
            }

    def per_feature_spe(self, frame):
        """PCA SPE broken down by feature. An additive score attributes itself for free."""
        z = self.standardize(frame)
        _, reconstruction, centred, _ = self._pca_parts(z)
        return (centred - reconstruction) ** 2


def fit_fleet(frame, fit_mask, features=FEATURES, seed=SEED):
    """One PortModel per port. Returns {port_id: PortModel}."""
    fit_mask = np.asarray(fit_mask, bool)
    models = {}
    for port, group in frame.groupby("port_id", sort=True):
        idx = group.index.to_numpy()
        models[port] = PortModel(features=features, seed=seed).fit(
            group.reset_index(drop=True), fit_mask[idx])
    return models


def score_fleet(frame, models):
    """Every detector's score for every row of `frame`, as a DataFrame aligned to its index."""
    out = pd.DataFrame(index=frame.index, columns=list(DETECTORS), dtype=float)
    for port, group in frame.groupby("port_id", sort=True):
        scores = models[port].score(group.reset_index(drop=True))
        for name, values in scores.items():
            out.loc[group.index, name] = values
    if out.isna().any().any():
        missing = out.columns[out.isna().any()].tolist()
        raise ValueError(f"scoring left gaps in {missing}; a port had no fitted model")
    return out


def standardize_fleet(frame, models):
    """The robust z matrix for every row, as a DataFrame with one column per feature."""
    features = next(iter(models.values())).features
    out = pd.DataFrame(index=frame.index, columns=features, dtype=float)
    for port, group in frame.groupby("port_id", sort=True):
        out.loc[group.index, :] = models[port].standardize(group.reset_index(drop=True))
    return out
