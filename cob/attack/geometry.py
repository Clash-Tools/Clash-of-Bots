"""Deploy geometry from the red no-deploy border: works at any zoom, no camera normalisation needed.

The border pixels are projected on the two isometric axes u = y + kx and v = y - kx; robust
percentiles of u and v give the four edges of the base diamond. Deploy points sit just outside one
edge, skipping UI boxes.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cob.vision.frame import Region

log = logging.getLogger(__name__)

Point = tuple[int, int]


@dataclass(frozen=True)
class BorderConfig:
    hsv_lo: tuple[int, int, int]
    hsv_hi: tuple[int, int, int]
    min_r_minus_g: int
    min_r_minus_b: int
    iso_slope: float
    percentile: float
    min_pixels: int
    ui: tuple[Region, ...]
    max_width: float = 1500.0  # fitted diamond larger than this = scenery mixed in, not trusted
    max_height: float = 1150.0
    # #164: a clean red line (little thick red around) may outline a base that fills the map
    big_width: float = 1720.0
    big_height: float = 1260.0
    max_thick_share: float = 0.3  # more of the mask in thick blobs than this = red scenery about


@dataclass(frozen=True)
class DeployConfig:
    edge: str
    margin: float
    t_from: float
    t_to: float
    points: int
    min_y: int


@dataclass(frozen=True)
class Diamond:
    """Base outline as u/v bounds (u = y + kx, v = y - kx)."""

    u_min: float
    u_max: float
    v_min: float
    v_max: float
    k: float
    line_only: bool = False  # fitted on line_mask (scenery around): check points against that mask too

    def _pt(self, u: float, v: float) -> tuple[float, float]:
        return (u - v) / (2 * self.k), (u + v) / 2

    @property
    def corners(self) -> dict[str, tuple[float, float]]:
        return {"top": self._pt(self.u_min, self.v_min), "right": self._pt(self.u_max, self.v_min),
                "bottom": self._pt(self.u_max, self.v_max), "left": self._pt(self.u_min, self.v_max)}


EDGES = {  # edge name -> (from corner, to corner, outward normal sign on u, on v)
    "top_left": ("left", "top", -1, 0),
    "top_right": ("top", "right", 0, -1),
    "bottom_right": ("right", "bottom", 1, 0),
    "bottom_left": ("bottom", "left", 0, 1),
}


def load_attack_config(root: Path) -> tuple[BorderConfig, DeployConfig, dict, dict]:
    """(border, deploy, troop bar, damage number) settings from attack.toml."""
    data = tomllib.loads((Path(root) / "attack.toml").read_text("utf-8"))
    b = data["border"]
    border = BorderConfig(tuple(b["hsv_lo"]), tuple(b["hsv_hi"]), b["min_r_minus_g"], b["min_r_minus_b"],
                          float(b["iso_slope"]), float(b["percentile"]), int(b["min_pixels"]),
                          tuple(tuple(r) for r in b["ui"]), float(b.get("max_width", 1500)),
                          float(b.get("max_height", 1150)))
    d = data["deploy"]
    if d["edge"] not in EDGES and d["edge"] != "auto":
        raise ValueError(f"attack.toml deploy.edge must be 'auto' or one of {sorted(EDGES)}")
    deploy = DeployConfig(d["edge"], float(d["margin"]), float(d["t_from"]), float(d["t_to"]),
                          int(d["points"]), int(d["min_y"]))
    return border, deploy, data["bar"], data["damage"]


def border_mask(bgr: np.ndarray, cfg: BorderConfig) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    b, g, r = (c.astype(np.int16) for c in cv2.split(bgr))
    mask = (cv2.inRange(hsv, cfg.hsv_lo, cfg.hsv_hi) > 0) & (r - g > cfg.min_r_minus_g) \
        & (r - b > cfg.min_r_minus_b)
    for x, y, w, h in cfg.ui:
        mask[y:y + h, x:x + w] = False
    return mask


def thin_lines(mask: np.ndarray, blob: int = 5, grow: int = 9) -> np.ndarray:
    """`mask` without its thick parts: the red no-deploy line is 1-2 px wide, while red buildings,
    painted ground, tents and UI that pass the colour filter are solid blobs (#164)."""
    m8 = mask.astype(np.uint8)
    thick = cv2.morphologyEx(m8, cv2.MORPH_OPEN, np.ones((blob, blob), np.uint8))
    thick = cv2.dilate(thick, np.ones((grow, grow), np.uint8))
    return (m8 > 0) & (thick == 0)


def _shifted(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """a moved by (dx, dy); uncovered pixels get a very low value (never brighter than a ridge)."""
    out = np.full_like(a, -1e4)
    h, w = a.shape
    out[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)] = \
        a[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)]
    return out


def _line_kernel(length: int, slope: float) -> np.ndarray:
    k = np.zeros((length, length), np.uint8)
    c = length // 2
    cv2.line(k, (0, c - round(c * slope)), (length - 1, c + round(c * slope)), 1, 1)
    return k


LINE_MIN_PIXELS = 2000  # fewer line pixels: too little of the line survived (JPEG, odd zoom) to trust
LINE_RIDGE = 8.0  # how much redder than both sides a line pixel is
LINE_RUN = 15  # px: shortest straight run along an isometric direction


def line_mask(bgr: np.ndarray, cfg: BorderConfig) -> np.ndarray:
    """Only the red no-deploy line itself (#178): pixels that pass the colour filter, are redder than
    both neighbours across an isometric direction (a 1-2 px ridge, not the edge of a red area) and lie
    on a straight run along that direction. Red scenery (striped tents, party colours, an orange carpet
    under the line) passes border_mask but not this. Needs a lossless frame: JPEG blurs the ridge away."""
    b, g, r = cv2.split(bgr.astype(np.float32))
    red = r - (g + b) / 2
    colour = cv2.dilate(border_mask(bgr, cfg).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    out = np.zeros(red.shape, bool)
    d = 2
    # u = const lines run along (1, -k), their normal is about (1, 1); v = const lines: (1, k) and (-1, 1)
    for nx, ny, slope in ((d, d, -cfg.iso_slope), (-d, d, cfg.iso_slope)):
        ridge = ((red - _shifted(red, nx, ny) > LINE_RIDGE) & (red - _shifted(red, -nx, -ny) > LINE_RIDGE)
                 & colour)
        grown = cv2.dilate(ridge.astype(np.uint8), np.ones((2, 2), np.uint8))
        out |= (cv2.morphologyEx(grown, cv2.MORPH_OPEN, _line_kernel(LINE_RUN, slope)) > 0) & ridge
    for x, y, w, h in cfg.ui:
        out[y:y + h, x:x + w] = False
    return out


def _fit_line(bgr: np.ndarray, cfg: BorderConfig, margin: float = 80.0) -> Diamond | None:
    """Diamond around line_mask, with stray bits far outside the bulk of the line dropped first."""
    ys, xs = np.nonzero(line_mask(bgr, cfg))
    if len(xs) < LINE_MIN_PIXELS:
        return None
    k = cfg.iso_slope
    u, v = ys + k * xs, ys - k * xs
    lo_u, hi_u, lo_v, hi_v = (np.percentile(u, 5), np.percentile(u, 95), np.percentile(v, 5),
                              np.percentile(v, 95))
    keep = (u > lo_u - margin) & (u < hi_u + margin) & (v > lo_v - margin) & (v < hi_v + margin)
    u, v, p = u[keep], v[keep], cfg.percentile
    d = Diamond(float(np.percentile(u, p)), float(np.percentile(u, 100 - p)), float(np.percentile(v, p)),
                float(np.percentile(v, 100 - p)), k, line_only=True)
    c = d.corners
    if c["right"][0] - c["left"][0] > cfg.big_width or c["bottom"][1] - c["top"][1] > cfg.big_height:
        return None
    return d


def red_mask(bgr: np.ndarray, cfg: BorderConfig, base: Diamond) -> np.ndarray:
    """What deploy points must stay clear of: the colour mask, or for a base found through the line
    alone (red scenery about) the line itself, a little widened, so scenery does not push them away."""
    if base.line_only:
        return cv2.dilate(line_mask(bgr, cfg).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    return border_mask(bgr, cfg)


def find_base(bgr: np.ndarray, cfg: BorderConfig) -> Diamond | None:
    base = _find_base(bgr, cfg)
    if base is None:
        # #178: red scenery mixed into the colour mask (live: a party scenery with pink stripes, an
        # orange carpet under the line). Fit on the line alone before giving the base up.
        base = _fit_line(bgr, cfg)
        if base is not None:
            c = base.corners
            log.info("base outline from the red line alone (red scenery about): %.0f x %.0f px",
                     c["right"][0] - c["left"][0], c["bottom"][1] - c["top"][1])
    return base


def _find_base(bgr: np.ndarray, cfg: BorderConfig) -> Diamond | None:
    mask = border_mask(bgr, cfg)
    raw = int(np.count_nonzero(mask))
    if raw < cfg.min_pixels:
        return None
    line = thin_lines(mask)
    ys, xs = np.nonzero(line)
    if len(xs) < cfg.min_pixels:
        return None
    # #164: bases that fill the map have a red line near the map edge, larger than the usual limit. Allow
    # that only when the mask is clean (mostly thin line); with much thick red about, keep the old limit.
    clean = 1 - len(xs) / raw <= cfg.max_thick_share
    max_w, max_h = (cfg.big_width, cfg.big_height) if clean else (cfg.max_width, cfg.max_height)
    k = cfg.iso_slope
    u = ys + k * xs
    v = ys - k * xs
    p = cfg.percentile
    d = Diamond(float(np.percentile(u, p)), float(np.percentile(u, 100 - p)),
                float(np.percentile(v, p)), float(np.percentile(v, 100 - p)), k)
    c = d.corners
    width, height = c["right"][0] - c["left"][0], c["bottom"][1] - c["top"][1]
    if width > max_w or height > max_h:
        # Red/orange scenery (e.g. painted ground) passed the colour filter: deploying on this
        # outline could put troops anywhere, so report no base and let the caller skip it.
        log.info("base outline implausible (%.0f x %.0f px); not trusted", width, height)
        return None
    return d


def _in_ui(pt: Point, ui: tuple[Region, ...]) -> bool:
    x, y = pt
    return any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in ui)


def deploy_points(base: Diamond, cfg: DeployConfig, ui: tuple[Region, ...],
                  size: tuple[int, int] = (1600, 900),
                  red: np.ndarray | None = None) -> tuple[str, list[Point]]:
    """(edge, points): points along one edge, `margin` px outside it, on screen and off the UI.

    edge "auto" picks the edge with the most usable points (the camera position varies per battle).
    `red` (border_mask of the same frame): every point is checked against the real red line and
    pushed outward until it is clear of it (see clear_of_red).
    """
    if cfg.edge != "auto":
        return cfg.edge, _edge_points(base, cfg, cfg.edge, ui, size, red)
    best = max(EDGES, key=lambda e: len(_edge_points(base, cfg, e, ui, size, red)))
    return best, _edge_points(base, cfg, best, ui, size, red)


def deploy_sides(base: Diamond, cfg: DeployConfig, ui: tuple[Region, ...], sides: int = 1,
                 size: tuple[int, int] = (1600, 900),
                 red: np.ndarray | None = None) -> tuple[str, list[Point]]:
    """#44: points along `sides` edges (1 or 2). Two sides are the best edge (as deploy_points picks
    it) plus its neighbour with more usable points, joined at their shared corner into one path, so
    troops tapped along it in turn spread around that corner instead of bunching on one face."""
    edge, points = deploy_points(base, cfg, ui, size, red)
    if sides < 2:
        return edge, points
    a, b = EDGES[edge][:2]
    others = {e: _edge_points(base, cfg, e, ui, size, red) for e, v in EDGES.items()
              if e != edge and (a in v[:2] or b in v[:2])}
    if not others:
        return edge, points
    second = max(others, key=lambda e: len(others[e]))
    shared = ({a, b} & set(EDGES[second][:2])).pop()
    first_pts = points if b == shared else points[::-1]  # ends at the shared corner
    second_pts = others[second] if EDGES[second][0] == shared else others[second][::-1]  # starts there
    return f"{edge}+{second}", first_pts + second_pts


def spell_points(base: Diamond, points: list[Point], ui: tuple[Region, ...], depth: float = 0.3,
                 size: tuple[int, int] = (1600, 900), max_y: int = 725) -> list[Point]:
    """Spell targets: each deploy point moved `depth` of the way towards the base centre, so spells land
    on the buildings the troops from that edge reach first. Off-screen / UI / troop-bar spots dropped."""
    c = base.corners
    cx = sum(p[0] for p in c.values()) / 4
    cy = sum(p[1] for p in c.values()) / 4
    out = []
    for x, y in points:
        pt = (int(round(x + (cx - x) * depth)), int(round(y + (cy - y) * depth)))
        if 0 <= pt[0] < size[0] and 0 <= pt[1] < min(size[1], max_y) and not _in_ui(pt, ui):
            out.append(pt)
    return out


RED_CLEARANCE = 18  # px: no red-line pixel this close to a deploy point
RED_STEP, RED_MAX_STEPS = 10, 8


def outward(edge: str, k: float) -> tuple[float, float]:
    """Unit screen vector pointing away from the base across `edge` (grad u = (k, 1), grad v = (-k, 1))."""
    _, _, su, sv = EDGES[edge]
    gx, gy = (su * k, su * 1.0) if su else (-sv * k, sv * 1.0)
    n = float(np.hypot(gx, gy))
    return gx / n, gy / n


def clear_of_red(pt: Point, direction: tuple[float, float], red: np.ndarray,
                 clearance: int = RED_CLEARANCE) -> Point | None:
    """`pt`, or the first point outward from it with no red-line pixel within `clearance` px.
    The fitted outline is a diamond with the outermost 1 % of red pixels trimmed, while the real red
    line follows the buildings, so a point `margin` px outside the diamond can still sit on or inside
    the line: the game then refuses the tap and that troop is never deployed (live, both villages).
    None when no clear spot is found within RED_MAX_STEPS steps or the point leaves the frame."""
    h, w = red.shape[:2]
    x, y = float(pt[0]), float(pt[1])
    for _ in range(RED_MAX_STEPS + 1):
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < w and 0 <= yi < h):
            return None
        window = red[max(0, yi - clearance):yi + clearance + 1, max(0, xi - clearance):xi + clearance + 1]
        if not window.any():
            return xi, yi
        x, y = x + direction[0] * RED_STEP, y + direction[1] * RED_STEP
    return None


def _edge_points(base: Diamond, cfg: DeployConfig, edge: str, ui: tuple[Region, ...],
                 size: tuple[int, int], red: np.ndarray | None = None) -> list[Point]:
    a_name, b_name, su, sv = EDGES[edge]
    # Shift the edge outward in u/v space; |grad u| = |grad v| = sqrt(1 + k^2) px per unit.
    shift = cfg.margin * np.hypot(1, base.k)
    moved = Diamond(base.u_min + min(su, 0) * shift, base.u_max + max(su, 0) * shift,
                    base.v_min + min(sv, 0) * shift, base.v_max + max(sv, 0) * shift, base.k)
    (ax, ay), (bx, by) = moved.corners[a_name], moved.corners[b_name]
    out: list[Point] = []
    away = outward(edge, base.k)
    for t in np.linspace(cfg.t_from, cfg.t_to, cfg.points):
        pt: Point | None = (int(round(ax + (bx - ax) * t)), int(round(ay + (by - ay) * t)))
        if red is not None:
            pt = clear_of_red(pt, away, red)
        if pt is not None and 0 <= pt[0] < size[0] and cfg.min_y <= pt[1] < size[1] and not _in_ui(pt, ui):
            out.append(pt)
    return out


def draw_base(bgr: np.ndarray, border: BorderConfig, deploy: DeployConfig,
              chosen: list[Point] | None = None) -> np.ndarray:
    """The frame as the attack saw it, for failure reports (#170): red-line mask in magenta, the fitted
    outline in cyan (none drawn when no base was found), deploy points of every edge in yellow and the
    points actually used in green. UI boxes the fit ignores are outlined in grey."""
    out = bgr.copy()
    mask = border_mask(bgr, border)
    out[mask] = (255, 0, 255)
    for x, y, w, h in border.ui:
        cv2.rectangle(out, (x, y), (x + w - 1, y + h - 1), (128, 128, 128), 1)
    base = find_base(bgr, border)
    note = "no base outline"
    if base is not None:
        if base.line_only:
            mask = red_mask(bgr, border, base)
            out[mask] = (255, 255, 255)  # the line the fit used
        c = base.corners
        poly = np.array([c["top"], c["right"], c["bottom"], c["left"]], np.int32)
        cv2.polylines(out, [poly], True, (255, 255, 0), 2)
        counts = []
        for edge in EDGES:
            pts = _edge_points(base, deploy, edge, border.ui, (bgr.shape[1], bgr.shape[0]), mask)
            counts.append(f"{edge} {len(pts)}")
            for p in pts:
                cv2.circle(out, p, 7, (0, 255, 255), 2)
        note = f"outline {c['right'][0] - c['left'][0]:.0f} x {c['bottom'][1] - c['top'][1]:.0f} px; " \
               + ", ".join(counts)
    for p in chosen or []:
        cv2.circle(out, tuple(int(v) for v in p), 9, (0, 255, 0), 3)
    cv2.putText(out, note, (340, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(out, note, (340, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    return out
