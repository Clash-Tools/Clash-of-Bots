"""Synthetic frames for engine tests; real LDPlayer frames live in tests/fixtures/frames."""

import cv2
import numpy as np
import pytest

W, H = 1600, 900


def make_patch(seed: int, w: int = 60, h: int = 40) -> np.ndarray:
    # Blocky random texture: distinctive for matching, unlike smooth noise.
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 256, (h // 4, w // 4, 3), dtype=np.uint8)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def blank_frame(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Low-contrast background so pasted patches dominate correlation.
    return rng.integers(90, 110, (H, W, 3), dtype=np.uint8)


def paste(frame: np.ndarray, patch: np.ndarray, x: int, y: int) -> np.ndarray:
    frame[y : y + patch.shape[0], x : x + patch.shape[1]] = patch
    return frame


@pytest.fixture
def tpl_dir(tmp_path):
    """Template folder with three anchors: a, b, c (seeds 1, 2, 3)."""
    for name, seed in (("a", 1), ("b", 2), ("c", 3)):
        cv2.imwrite(str(tmp_path / f"{name}.png"), make_patch(seed))
    (tmp_path / "templates.toml").write_text(
        '[defaults]\nthreshold = 0.9\n\n[templates.b]\nregion = [1000, 0, 600, 300]\n', "utf-8"
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _isolated_user_data(tmp_path, monkeypatch):
    """Snapshots, logs and farm.json go to a temp folder, never the real user data dir."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))


@pytest.fixture(autouse=True)
def _fresh_feature_flags(monkeypatch):
    """Each test starts from the flag defaults (D-038); a test turns flags on with COB_FLAGS."""
    from cob.core import flags

    monkeypatch.delenv("COB_FLAGS", raising=False)
    flags.reset()
    yield
    flags.reset()
