"""Tiny per-user MLP autoencoder over 7-day derived-metric z windows.

torch is imported lazily inside functions so the app runs without the wheel
when ENABLE_AUTOENCODER is off.
"""
import numpy as np

WINDOW, FEATURES = 7, 4        # 7 days × [resting_hr, hrv_night, skin_temp_night, motion_total] z's
INPUT = WINDOW * FEATURES      # 28


def _torch():
    import torch
    import torch.nn as nn
    return torch, nn


def build_model():
    torch, nn = _torch()

    class DailyWindowAE(nn.Module):
        """Trained on the user's own recent history, so high reconstruction
        error = 'this week doesn't look like you'."""
        def __init__(self):
            super().__init__()
            self.enc = nn.Sequential(nn.Linear(INPUT, 16), nn.ReLU(), nn.Linear(16, 8))
            self.dec = nn.Sequential(nn.Linear(8, 16), nn.ReLU(), nn.Linear(16, INPUT))

        def forward(self, x):
            return self.dec(self.enc(x))

    return DailyWindowAE()


def make_windows(z: np.ndarray) -> np.ndarray:
    """z: (days, 4), complete rows only -> flattened overlapping 7-day windows."""
    return np.stack([z[i:i + WINDOW].ravel()
                     for i in range(len(z) - WINDOW + 1)]).astype("float32")


def train(z: np.ndarray, epochs: int = 200, seed: int = 0):
    torch, nn = _torch()
    torch.manual_seed(seed)  # reproducible thresholds; e2e expectations depend on it
    x = torch.from_numpy(make_windows(z))
    model = build_model()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(x), x)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        errs = ((model(x) - x) ** 2).mean(dim=1).numpy()
    threshold = float(errs.mean() + 3 * errs.std())   # 3σ over the user's own history
    return model, threshold, {"train_mse": float(errs.mean()), "threshold": threshold,
                              "n_windows": int(len(x))}


def score_latest(model, z: np.ndarray) -> float:
    torch, _ = _torch()
    x = torch.from_numpy(z[-WINDOW:].ravel().astype("float32")).unsqueeze(0)
    with torch.no_grad():
        return float(((model(x) - x) ** 2).mean())


def load_checkpoint(path: str):
    torch, _ = _torch()
    model = build_model()
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    return model


def save_checkpoint(model, path: str) -> None:
    torch, _ = _torch()
    torch.save(model.state_dict(), path)
