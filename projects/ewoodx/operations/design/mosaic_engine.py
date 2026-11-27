"""
2D Placement, Board-Lock, Progressive Reclaimed-Timber Nesting, and Mosaic Engine.

Supports TWO complementary projection workflows:
1. Progressive Reclaimed-Timber Nesting (default for heterogeneous boards):
   - Each scanned board on the table can have a DIFFERENT size, shape, and angle.
   - Clips the design strictly to the exact scanned board polygon (even rotated
     or irregular contours).
   - Tracks previously projected board footprints ("CompletedRegion") in
     design-local mm so completed pieces are visually crossed off / hatched on
     the master drawing.
   - Automatically suggests the best remaining uncovered area for the next
     scanned board of ANY size using an O(1) integral-image search.
   - Places edge fiducial crosses on uncovered board edges and automatically
     re-projects matching fiducials from prior boards wherever a new board
     overlaps them — guaranteeing 0.00 mm alignment without knowing future
     board dimensions in advance.
2. Uniform Mosaic / Tiling & Single Placement:
   - Preserves classic poster-style uniform grid tiling and single placement
     for uniform stock sheets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from projects.ewoodx.operations.design.design_parsers import (
    ParsedDesign,
)


MAX_GRID_DIM = 12


@dataclass
class DesignTransform:
    """2D placement of a design in workspace millimeters."""

    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    rotation_deg: float = 0.0
    scale: float = 1.0
    flip_x: bool = False
    flip_y: bool = False
    locked_to_board: bool = False
    board_rel_x_mm: float = 0.0
    board_rel_y_mm: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "offset_x_mm": round(float(self.offset_x_mm), 3),
            "offset_y_mm": round(float(self.offset_y_mm), 3),
            "rotation_deg": round(float(self.rotation_deg), 3),
            "scale": round(float(self.scale), 6),
            "flip_x": bool(self.flip_x),
            "flip_y": bool(self.flip_y),
            "locked_to_board": bool(self.locked_to_board),
            "board_rel_x_mm": round(float(self.board_rel_x_mm), 3),
            "board_rel_y_mm": round(float(self.board_rel_y_mm), 3),
        }


@dataclass
class CompletedRegion:
    """One board footprint already projected/eliminated from the master drawing."""

    index: int
    board_id: str
    board_length_mm: float
    board_width_mm: float
    # Exact board contour stored in normalized design-local scaled mm
    polygon_design_mm: list[list[float]]
    # Fiducial alignment marks stamped along uncovered edges of this board
    fiducials_design_mm: list[dict[str, Any]] = field(default_factory=list)
    transform_snapshot: dict[str, Any] = field(default_factory=dict)
    measurement_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "board_id": self.board_id,
            "board_length_mm": round(self.board_length_mm, 1),
            "board_width_mm": round(self.board_width_mm, 1),
            "polygon_design_mm": self.polygon_design_mm,
            "fiducials_design_mm": self.fiducials_design_mm,
        }


@dataclass
class MosaicConfig:
    """Configuration for single, uniform mosaic, or progressive board-by-board nesting."""

    mode: str = "progressive"  # "progressive" | "single" | "mosaic"
    tile_source: str = "board"  # "board" | "table" | "custom"
    custom_tile_w_mm: float = 1200.0
    custom_tile_h_mm: float = 800.0
    overlap_mm: float = 0.0
    margin_mm: float = 0.0
    active_tile_index: int = 0
    show_registration_marks: bool = True
    show_tile_border: bool = True
    clip_to_board_in_single: bool = False
    skip_empty_tiles: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "tile_source": self.tile_source,
            "custom_tile_w_mm": round(float(self.custom_tile_w_mm), 2),
            "custom_tile_h_mm": round(float(self.custom_tile_h_mm), 2),
            "overlap_mm": round(float(self.overlap_mm), 2),
            "margin_mm": round(float(self.margin_mm), 2),
            "active_tile_index": int(self.active_tile_index),
            "show_registration_marks": bool(self.show_registration_marks),
            "show_tile_border": bool(self.show_tile_border),
            "clip_to_board_in_single": bool(self.clip_to_board_in_single),
            "skip_empty_tiles": bool(self.skip_empty_tiles),
        }


def effective_scale(design: ParsedDesign, transform: DesignTransform) -> float:
    """Return effective scale factor, strictly locked to 1.0 for DXF designs."""
    if design.scale_locked:
        return 1.0
    val = float(transform.scale)
    if not math.isfinite(val) or val <= 0.0:
        return 1.0
    return max(0.005, min(val, 500.0))


def transform_point(
    x: float,
    y: float,
    base_w: float,
    base_h: float,
    scale: float,
    transform: DesignTransform,
) -> list[float]:
    """Map one design-local point (base mm) into workspace coordinates (mm)."""
    w = base_w * scale
    h = base_h * scale
    px = x * scale
    py = y * scale

    if transform.flip_x:
        px = w - px
    if transform.flip_y:
        py = h - py

    cx = w * 0.5
    cy = h * 0.5
    dx = px - cx
    dy = py - cy

    rad = math.radians(transform.rotation_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    rx = dx * cos_r - dy * sin_r + cx
    ry = dx * sin_r + dy * cos_r + cy

    return [
        round(rx + transform.offset_x_mm, 3),
        round(ry + transform.offset_y_mm, 3),
    ]


def scaled_design_to_workspace(
    sx: float,
    sy: float,
    scaled_w: float,
    scaled_h: float,
    transform: DesignTransform,
) -> list[float]:
    """Map a scaled design-space point [0..scaled_w, 0..scaled_h] to workspace mm."""
    px = (scaled_w - sx) if transform.flip_x else sx
    py = (scaled_h - sy) if transform.flip_y else sy
    cx = scaled_w * 0.5
    cy = scaled_h * 0.5
    dx = px - cx
    dy = py - cy
    rad = math.radians(transform.rotation_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    rx = dx * cos_r - dy * sin_r + cx
    ry = dx * sin_r + dy * cos_r + cy
    return [
        round(rx + transform.offset_x_mm, 3),
        round(ry + transform.offset_y_mm, 3),
    ]


def workspace_to_scaled_design(
    wx: float,
    wy: float,
    scaled_w: float,
    scaled_h: float,
    transform: DesignTransform,
) -> list[float]:
    """Exact inverse of scaled_design_to_workspace: workspace mm -> scaled design mm."""
    cx = scaled_w * 0.5
    cy = scaled_h * 0.5
    rx = wx - transform.offset_x_mm - cx
    ry = wy - transform.offset_y_mm - cy

    rad = math.radians(-transform.rotation_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    px = rx * cos_r - ry * sin_r + cx
    py = rx * sin_r + ry * cos_r + cy

    sx = (scaled_w - px) if transform.flip_x else px
    sy = (scaled_h - py) if transform.flip_y else py
    return [round(sx, 3), round(sy, 3)]


def transformed_design_corners(
    design: ParsedDesign,
    transform: DesignTransform,
) -> list[list[float]]:
    """Return the 4 corners of the design bounding rectangle in workspace mm."""
    s = effective_scale(design, transform)
    bw, bh = design.base_width_mm, design.base_height_mm
    local_corners = [[0.0, 0.0], [bw, 0.0], [bw, bh], [0.0, bh]]
    return [
        transform_point(pt[0], pt[1], bw, bh, s, transform)
        for pt in local_corners
    ]


# ---------------------------------------------------------------------
# Geometric Clipping (Axis-Aligned Rect + General Rotated/Irregular Polygon)
# ---------------------------------------------------------------------

def clip_segment_liang_barsky(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    rx0: float,
    ry0: float,
    rx1: float,
    ry1: float,
) -> tuple[list[float], list[float]] | None:
    """Clip a 2D line segment to an axis-aligned rectangle via Liang-Barsky."""
    dx = x1 - x0
    dy = y1 - y0
    t0 = 0.0
    t1 = 1.0

    checks = (
        (-dx, x0 - rx0),
        (dx, rx1 - x0),
        (-dy, y0 - ry0),
        (dy, ry1 - y0),
    )

    for p, q in checks:
        if abs(p) < 1e-12:
            if q < 0.0:
                return None
        else:
            r = q / p
            if p < 0.0:
                if r > t1:
                    return None
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return None
                if r < t1:
                    t1 = r

    if t0 > t1:
        return None

    return (
        [x0 + t0 * dx, y0 + t0 * dy],
        [x0 + t1 * dx, y0 + t1 * dy],
    )


def clip_polyline_to_rect(
    points: list[list[float]],
    rx0: float,
    ry0: float,
    rx1: float,
    ry1: float,
) -> list[list[list[float]]]:
    """Clip a polyline against [rx0, ry0, rx1, ry1]."""
    if len(points) < 2:
        return []

    result: list[list[list[float]]] = []
    current: list[list[float]] = []

    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        clipped = clip_segment_liang_barsky(
            p0[0], p0[1], p1[0], p1[1], rx0, ry0, rx1, ry1
        )
        if clipped is None:
            if len(current) >= 2:
                result.append(current)
            current = []
            continue

        c0, c1 = clipped
        if not current:
            current = [c0, c1]
        else:
            last = current[-1]
            if math.hypot(last[0] - c0[0], last[1] - c0[1]) <= 0.05:
                current.append(c1)
            else:
                if len(current) >= 2:
                    result.append(current)
                current = [c0, c1]

    if len(current) >= 2:
        result.append(current)

    return result


def point_in_rect(
    x: float,
    y: float,
    rx0: float,
    ry0: float,
    rx1: float,
    ry1: float,
    eps: float = 1e-3,
) -> bool:
    return (rx0 - eps) <= x <= (rx1 + eps) and (ry0 - eps) <= y <= (ry1 + eps)


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test (works for convex, concave, rotated polygons)."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _segment_intersection_t(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> float | None:
    """Return parameter t in [0, 1] along segment A->B where it intersects segment C->D."""
    rx = bx - ax
    ry = by - ay
    sx = dx - cx
    sy = dy - cy
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-10:
        return None
    qpx = cx - ax
    qpy = cy - ay
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    if -1e-7 <= t <= 1.0 + 1e-7 and -1e-7 <= u <= 1.0 + 1e-7:
        return max(0.0, min(1.0, t))
    return None


def clip_polyline_to_polygons(
    points: list[list[float]],
    polygons: list[list[list[float]]],
) -> list[list[list[float]]]:
    """
    Clip a polyline against the union of one or more arbitrary 2D polygons
    (rotated boards, irregular timber slabs, or multi-timber captures).
    """
    if len(points) < 2 or not polygons:
        return []

    valid_polys = [p for p in polygons if len(p) >= 3]
    if not valid_polys:
        return []

    # Precompute AABB per polygon for fast rejection
    bboxes = [
        (
            min(pt[0] for pt in poly),
            min(pt[1] for pt in poly),
            max(pt[0] for pt in poly),
            max(pt[1] for pt in poly),
        )
        for poly in valid_polys
    ]

    result: list[list[list[float]]] = []
    current: list[list[float]] = []

    for i in range(len(points) - 1):
        ax, ay = points[i][0], points[i][1]
        bx, by = points[i + 1][0], points[i + 1][1]
        s_min_x, s_max_x = (ax, bx) if ax <= bx else (bx, ax)
        s_min_y, s_max_y = (ay, by) if ay <= by else (by, ay)

        ts = [0.0, 1.0]
        candidate_polys = []
        for poly, (px0, py0, px1, py1) in zip(valid_polys, bboxes):
            if s_max_x < px0 - 0.1 or s_min_x > px1 + 0.1 or s_max_y < py0 - 0.1 or s_min_y > py1 + 0.1:
                continue
            candidate_polys.append(poly)
            n = len(poly)
            for e in range(n):
                p0 = poly[e]
                p1 = poly[(e + 1) % n]
                t_hit = _segment_intersection_t(ax, ay, bx, by, p0[0], p0[1], p1[0], p1[1])
                if t_hit is not None:
                    ts.append(t_hit)

        if not candidate_polys:
            if len(current) >= 2:
                result.append(current)
            current = []
            continue

        ts.sort()
        # Deduplicate near-identical parameters
        uniq_ts = [ts[0]]
        for t in ts[1:]:
            if t - uniq_ts[-1] > 1e-5:
                uniq_ts.append(t)

        for k in range(len(uniq_ts) - 1):
            t0 = uniq_ts[k]
            t1 = uniq_ts[k + 1]
            tm = 0.5 * (t0 + t1)
            mx = ax + tm * (bx - ax)
            my = ay + tm * (by - ay)
            inside = any(point_in_polygon(mx, my, poly) for poly in candidate_polys)
            if inside:
                c0 = [ax + t0 * (bx - ax), ay + t0 * (by - ay)]
                c1 = [ax + t1 * (bx - ax), ay + t1 * (by - ay)]
                if not current:
                    current = [c0, c1]
                else:
                    last = current[-1]
                    if math.hypot(last[0] - c0[0], last[1] - c0[1]) <= 0.1:
                        current.append(c1)
                    else:
                        if len(current) >= 2:
                            result.append(current)
                        current = [c0, c1]
            else:
                if len(current) >= 2:
                    result.append(current)
                current = []

    if len(current) >= 2:
        result.append(current)

    return result


def clip_polyline_in_minus_out(
    points: list[list[float]],
    include_polys: list[list[list[float]]],
    exclude_polys: list[list[list[float]]],
) -> list[list[list[float]]]:
    """
    Clip a polyline to (Union of include_polys) MINUS (Union of exclude_polys).
    Used in progressive nesting so the active board projects ONLY the net new
    unprojected portion of the drawing and trims cleanly at the overlap cut line.
    """
    if not exclude_polys:
        return clip_polyline_to_polygons(points, include_polys)
    if len(points) < 2 or not include_polys:
        return []

    inc_valid = [p for p in include_polys if len(p) >= 3]
    exc_valid = [p for p in exclude_polys if len(p) >= 3]
    if not inc_valid:
        return []
    if not exc_valid:
        return clip_polyline_to_polygons(points, inc_valid)

    inc_bboxes = [
        (min(pt[0] for pt in p), min(pt[1] for pt in p), max(pt[0] for pt in p), max(pt[1] for pt in p))
        for p in inc_valid
    ]
    exc_bboxes = [
        (min(pt[0] for pt in p), min(pt[1] for pt in p), max(pt[0] for pt in p), max(pt[1] for pt in p))
        for p in exc_valid
    ]

    result: list[list[list[float]]] = []
    current: list[list[float]] = []

    for i in range(len(points) - 1):
        ax, ay = points[i][0], points[i][1]
        bx, by = points[i + 1][0], points[i + 1][1]
        s_min_x, s_max_x = (ax, bx) if ax <= bx else (bx, ax)
        s_min_y, s_max_y = (ay, by) if ay <= by else (by, ay)

        ts = [0.0, 1.0]
        cand_inc = []
        for poly, (px0, py0, px1, py1) in zip(inc_valid, inc_bboxes):
            if s_max_x < px0 - 0.1 or s_min_x > px1 + 0.1 or s_max_y < py0 - 0.1 or s_min_y > py1 + 0.1:
                continue
            cand_inc.append(poly)
            n = len(poly)
            for e in range(n):
                p0, p1 = poly[e], poly[(e + 1) % n]
                t_hit = _segment_intersection_t(ax, ay, bx, by, p0[0], p0[1], p1[0], p1[1])
                if t_hit is not None:
                    ts.append(t_hit)

        if not cand_inc:
            if len(current) >= 2:
                result.append(current)
            current = []
            continue

        cand_exc = []
        for poly, (px0, py0, px1, py1) in zip(exc_valid, exc_bboxes):
            if s_max_x < px0 - 0.1 or s_min_x > px1 + 0.1 or s_max_y < py0 - 0.1 or s_min_y > py1 + 0.1:
                continue
            cand_exc.append(poly)
            n = len(poly)
            for e in range(n):
                p0, p1 = poly[e], poly[(e + 1) % n]
                t_hit = _segment_intersection_t(ax, ay, bx, by, p0[0], p0[1], p1[0], p1[1])
                if t_hit is not None:
                    ts.append(t_hit)

        ts.sort()
        uniq_ts = [ts[0]]
        for t_val in ts[1:]:
            if t_val - uniq_ts[-1] > 1e-5:
                uniq_ts.append(t_val)

        for k in range(len(uniq_ts) - 1):
            t0 = uniq_ts[k]
            t1 = uniq_ts[k + 1]
            tm = 0.5 * (t0 + t1)
            mx = ax + tm * (bx - ax)
            my = ay + tm * (by - ay)
            in_board = any(point_in_polygon(mx, my, poly) for poly in cand_inc)
            in_prior = any(point_in_polygon(mx, my, poly) for poly in cand_exc)
            if in_board and not in_prior:
                c0 = [ax + t0 * (bx - ax), ay + t0 * (by - ay)]
                c1 = [ax + t1 * (bx - ax), ay + t1 * (by - ay)]
                if not current:
                    current = [c0, c1]
                else:
                    last = current[-1]
                    if math.hypot(last[0] - c0[0], last[1] - c0[1]) <= 0.1:
                        current.append(c1)
                    else:
                        if len(current) >= 2:
                            result.append(current)
                        current = [c0, c1]
            else:
                if len(current) >= 2:
                    result.append(current)
                current = []

    if len(current) >= 2:
        result.append(current)

    return result


def polygon_area_mm2(poly: list[list[float]]) -> float:
    """Compute unsigned area of a 2D polygon in mm² via shoelace formula."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
    return abs(area) * 0.5


def intersect_polygons_mm(
    poly_a: list[list[float]],
    poly_b: list[list[float]],
) -> tuple[float, list[list[float]]]:
    """
    Compute exact intersection polygon of two 2D polygons in mm.
    Uses cv2.intersectConvexConvex for convex boards (fast & exact float mm),
    falling back to OpenCV mask intersection for non-convex slabs.
    """
    if len(poly_a) < 3 or len(poly_b) < 3:
        return 0.0, []

    arr_a = np.array(poly_a, dtype=np.float32).reshape((-1, 1, 2))
    arr_b = np.array(poly_b, dtype=np.float32).reshape((-1, 1, 2))

    if cv2.isContourConvex(arr_a) and cv2.isContourConvex(arr_b):
        area, inter = cv2.intersectConvexConvex(arr_a, arr_b)
        if area > 20.0 and inter is not None and len(inter) >= 3:
            pts = [[round(float(pt[0][0]), 2), round(float(pt[0][1]), 2)] for pt in inter]
            return float(area), pts
        return 0.0, []

    # General non-convex fallback via local high-res mask
    all_pts = poly_a + poly_b
    min_x = min(p[0] for p in all_pts) - 2.0
    min_y = min(p[1] for p in all_pts) - 2.0
    max_x = max(p[0] for p in all_pts) + 2.0
    max_y = max(p[1] for p in all_pts) + 2.0
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    scale = min(400.0 / span_x, 400.0 / span_y, 2.0)
    gw = max(8, int(math.ceil(span_x * scale)) + 2)
    gh = max(8, int(math.ceil(span_y * scale)) + 2)

    ma = np.zeros((gh, gw), dtype=np.uint8)
    mb = np.zeros((gh, gw), dtype=np.uint8)
    pa = np.array([[(p[0] - min_x) * scale, (p[1] - min_y) * scale] for p in poly_a], dtype=np.int32)
    pb = np.array([[(p[0] - min_x) * scale, (p[1] - min_y) * scale] for p in poly_b], dtype=np.int32)
    cv2.fillPoly(ma, [pa], 255)
    cv2.fillPoly(mb, [pb], 255)
    inter_mask = cv2.bitwise_and(ma, mb)
    cnts, _ = cv2.findContours(inter_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0.0, []
    biggest = max(cnts, key=cv2.contourArea)
    pts = [
        [round(float(pt[0][0]) / scale + min_x, 2), round(float(pt[0][1]) / scale + min_y, 2)]
        for pt in biggest
    ]
    area = polygon_area_mm2(pts)
    return (area, pts) if area > 20.0 else (0.0, [])


def compute_overlap_joint_cut_lines(
    board_contours_mm: list[list[list[float]]],
    prior_regions_world: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Compute exact straight JOINT / TRIM CUT LINES where previously stamped boards
    overlap the newly scanned active board, PLUS exact overlap trim polygons so
    the operator immediately sees:
      - WHERE to saw the newly placed board (joint_cut_lines)
      - WHICH side of the saw line is overlap trim waste (overlap_trim_polygons)
    """
    if not board_contours_mm or not prior_regions_world:
        return [], []

    board_np = [np.array(poly, dtype=np.float32).reshape((-1, 1, 2)) for poly in board_contours_mm if len(poly) >= 3]
    prior_np_list = [
        (reg["index"], reg["polygon_mm"], np.array(reg["polygon_mm"], dtype=np.float32).reshape((-1, 1, 2)))
        for reg in prior_regions_world
        if len(reg.get("polygon_mm") or []) >= 3
    ]
    if not board_np or not prior_np_list:
        return [], []

    # 1. Exact overlap trim polygons (Active Board ∩ Prior Board #k)
    overlap_trim_polygons: list[dict[str, Any]] = []
    for b_poly in board_contours_mm:
        for reg_idx, p_poly, _ in prior_np_list:
            area, inter_pts = intersect_polygons_mm(b_poly, p_poly)
            if area > 40.0 and len(inter_pts) >= 3:
                overlap_trim_polygons.append({
                    "from_board": reg_idx,
                    "polygon_mm": inter_pts,
                    "area_mm2": round(area, 1),
                })

    # 2. Exact straight joint cut segments along outer frontier of Union(Prior Boards) strictly inside Active Board
    joint_cut_lines: list[dict[str, Any]] = []
    for reg_idx, p_poly, _ in prior_np_list:
        other_prior = [(oidx, opoly, onp) for (oidx, opoly, onp) in prior_np_list if oidx != reg_idx]
        n = len(p_poly)
        for i in range(n):
            a = p_poly[i]
            b = p_poly[(i + 1) % n]
            ax, ay = a[0], a[1]
            bx, by = b[0], b[1]
            if math.hypot(bx - ax, by - ay) < 10.0:
                continue

            ts = [0.0, 1.0]
            # Collect intersections with active board borders
            for b_poly in board_contours_mm:
                bn = len(b_poly)
                for e in range(bn):
                    t_hit = _segment_intersection_t(ax, ay, bx, by, b_poly[e][0], b_poly[e][1], b_poly[(e + 1) % bn][0], b_poly[(e + 1) % bn][1])
                    if t_hit is not None:
                        ts.append(t_hit)
            # Collect intersections with other prior completed boards
            for _, opoly, _ in other_prior:
                on = len(opoly)
                for e in range(on):
                    t_hit = _segment_intersection_t(ax, ay, bx, by, opoly[e][0], opoly[e][1], opoly[(e + 1) % on][0], opoly[(e + 1) % on][1])
                    if t_hit is not None:
                        ts.append(t_hit)

            ts.sort()
            uniq_ts = [ts[0]]
            for t_val in ts[1:]:
                if t_val - uniq_ts[-1] > 1e-4:
                    uniq_ts.append(t_val)

            for k in range(len(uniq_ts) - 1):
                t0 = uniq_ts[k]
                t1 = uniq_ts[k + 1]
                p0 = [ax + t0 * (bx - ax), ay + t0 * (by - ay)]
                p1 = [ax + t1 * (bx - ax), ay + t1 * (by - ay)]
                seg_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                if seg_len < 18.0:
                    continue

                mx = 0.5 * (p0[0] + p1[0])
                my = 0.5 * (p0[1] + p1[1])

                # Must lie STRICTLY inside active board (>2.5 mm from outer edge -> actual saw cut through timber!)
                in_active_strict = any(cv2.pointPolygonTest(bnp, (mx, my), True) > 2.5 for bnp in board_np)
                if not in_active_strict:
                    continue

                # Must NOT lie strictly inside another already-completed board,
                # nor duplicate a collinear boundary already owned by an earlier board!
                buried_in_other = any(
                    cv2.pointPolygonTest(onp, (mx, my), True) > (2.5 if oidx > reg_idx else -2.0)
                    for oidx, _, onp in other_prior
                )
                if buried_in_other:
                    continue

                # Compute unit normal pointing toward the KEPT side (outside this prior board)
                dx = (p1[0] - p0[0]) / seg_len
                dy = (p1[1] - p0[1]) / seg_len
                nx, ny = -dy, dx
                if point_in_polygon(mx + nx * 6.0, my + ny * 6.0, p_poly):
                    nx, ny = -nx, -ny

                joint_cut_lines.append({
                    "points": [[round(p0[0], 2), round(p0[1], 2)], [round(p1[0], 2), round(p1[1], 2)]],
                    "from_board": reg_idx,
                    "from_boards": [reg_idx],
                    "length_mm": round(seg_len, 1),
                    "label": f"CUT #{reg_idx} · {int(round(seg_len))}mm",
                    "label_pos": [round(mx + nx * 16.0, 2), round(my + ny * 16.0, 2)],
                    "kept_normal": [round(nx, 4), round(ny, 4)],
                })

    # 3. Merge collinear touching saw segments (e.g. Board #1 + #2 bottom edge -> one straight saw cut!)
    merged: list[dict[str, Any]] = []
    for seg in joint_cut_lines:
        p0, p1 = seg["points"][0], seg["points"][1]
        v = [p1[0] - p0[0], p1[1] - p0[1]]
        lv = max(1e-6, math.hypot(v[0], v[1]))
        uv = [v[0] / lv, v[1] / lv]
        did_merge = False
        for m in merged:
            mp0, mp1 = m["points"][0], m["points"][1]
            mv = [mp1[0] - mp0[0], mp1[1] - mp0[1]]
            lmv = max(1e-6, math.hypot(mv[0], mv[1]))
            umv = [mv[0] / lmv, mv[1] / lmv]
            # Parallel check (|dot| > 0.999) and same kept normal direction
            if abs(uv[0] * umv[0] + uv[1] * umv[1]) < 0.999:
                continue
            kn_dot = seg["kept_normal"][0] * m["kept_normal"][0] + seg["kept_normal"][1] * m["kept_normal"][1]
            if kn_dot < 0.9:
                continue
            # Endpoint touch check (within 4 mm)
            d_pairs = [
                (math.hypot(mp1[0] - p0[0], mp1[1] - p0[1]), mp0, p1),
                (math.hypot(mp1[0] - p1[0], mp1[1] - p1[1]), mp0, p0),
                (math.hypot(mp0[0] - p0[0], mp0[1] - p0[1]), mp1, p1),
                (math.hypot(mp0[0] - p1[0], mp0[1] - p1[1]), mp1, p0),
            ]
            best_d, na, nb = min(d_pairs, key=lambda item: item[0])
            if best_d <= 4.0:
                m["points"] = [[round(na[0], 2), round(na[1], 2)], [round(nb[0], 2), round(nb[1], 2)]]
                new_len = math.hypot(nb[0] - na[0], nb[1] - na[1])
                m["length_mm"] = round(new_len, 1)
                boards = sorted(set(m["from_boards"] + seg["from_boards"]))
                m["from_boards"] = boards
                m["from_board"] = boards[0]
                btag = "/".join(f"#{b}" for b in boards)
                m["label"] = f"CUT {btag} · {int(round(new_len))}mm"
                mmx = 0.5 * (na[0] + nb[0])
                mmy = 0.5 * (na[1] + nb[1])
                m["label_pos"] = [
                    round(mmx + m["kept_normal"][0] * 16.0, 2),
                    round(mmy + m["kept_normal"][1] * 16.0, 2),
                ]
                did_merge = True
                break
        if not did_merge:
            merged.append(seg)

    return merged, overlap_trim_polygons


def extract_board_oriented_box(
    board_contours_mm: list[list[list[float]]] | None,
    board_bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float, float]:
    """
    Return (center_x, center_y, long_len_mm, short_wid_mm, angle_deg) of the
    scanned board's minimum-area oriented rectangle in workspace mm.
    angle_deg is in (-90, 90] along the long_len_mm axis.
    """
    if board_contours_mm and len(board_contours_mm[0]) >= 3:
        pts_arr = np.array(board_contours_mm[0], dtype=np.float32)
        (bcx, bcy), (rw, rh), ang = cv2.minAreaRect(pts_arr)
        if rw >= rh:
            board_len, board_wid, board_ang = float(rw), float(rh), float(ang)
        else:
            board_len, board_wid, board_ang = float(rh), float(rw), float(ang + 90.0)
        while board_ang > 90.0:
            board_ang -= 180.0
        while board_ang <= -90.0:
            board_ang += 180.0
        if board_len >= 40.0 and board_wid >= 40.0:
            return float(bcx), float(bcy), board_len, board_wid, board_ang

    bx0, by0, bx1, by1 = board_bounds
    bw = max(50.0, bx1 - bx0)
    bh = max(50.0, by1 - by0)
    bcx = 0.5 * (bx0 + bx1)
    bcy = 0.5 * (by0 + by1)
    if bw >= bh:
        return bcx, bcy, bw, bh, 0.0
    return bcx, bcy, bh, bw, 90.0


def reanchor_transform_to_moved_board(
    design: ParsedDesign,
    transform: DesignTransform,
    old_contours_mm: list[list[list[float]]] | None,
    old_bounds: tuple[float, float, float, float],
    new_contours_mm: list[list[list[float]]] | None,
    new_bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Exact 2D SE(2) rigid-body re-anchoring when a physical board on the table is
    accidentally bumped (translated AND/OR rotated) and re-scanned.

    Preserves the EXACT relative millimeter position & orientation between the
    digital drawing (plus any completed regions / joint cut lines) and the
    physical wooden piece:
      - Computes old & new oriented board boxes (center, length, width, angle).
      - Uses shortest signed angular delta mod 180 deg to avoid +/-90 wrap flips.
      - Maps the exact design-space point that sat at the old board center directly
        onto the new board center under (old_rotation + d_theta).

    Returns (new_offset_x_mm, new_offset_y_mm, new_rotation_deg, delta_info).
    """
    old_cx, old_cy, old_len, old_wid, old_ang = extract_board_oriented_box(old_contours_mm, old_bounds)
    new_cx, new_cy, new_len, new_wid, new_ang = extract_board_oriented_box(new_contours_mm, new_bounds)

    # Shortest signed rotation delta in (-90, +90] to safely handle 88 deg -> -88 deg wraps
    d_theta = ((new_ang - old_ang + 90.0) % 180.0) - 90.0
    dx = new_cx - old_cx
    dy = new_cy - old_cy

    s = effective_scale(design, transform)
    scaled_w = max(1.0, design.base_width_mm * s)
    scaled_h = max(1.0, design.base_height_mm * s)

    # Exact design-local point glued to the physical board center BEFORE the bump
    anchor_design = workspace_to_scaled_design(old_cx, old_cy, scaled_w, scaled_h, transform)

    new_rot = (transform.rotation_deg + d_theta) % 360.0
    tmp_t = DesignTransform(
        offset_x_mm=0.0,
        offset_y_mm=0.0,
        rotation_deg=new_rot,
        scale=transform.scale,
        flip_x=transform.flip_x,
        flip_y=transform.flip_y,
    )
    mapped_anchor = scaled_design_to_workspace(anchor_design[0], anchor_design[1], scaled_w, scaled_h, tmp_t)
    new_off_x = round(new_cx - mapped_anchor[0], 3)
    new_off_y = round(new_cy - mapped_anchor[1], 3)

    size_diff = max(abs(new_len - old_len), abs(new_wid - old_wid))
    delta_info = {
        "dx_mm": round(dx, 1),
        "dy_mm": round(dy, 1),
        "d_angle_deg": round(d_theta, 2),
        "prev_center_mm": [round(old_cx, 2), round(old_cy, 2)],
        "new_center_mm": [round(new_cx, 2), round(new_cy, 2)],
        "size_diff_mm": round(size_diff, 1),
        "size_match": size_diff <= 45.0,
    }
    return new_off_x, new_off_y, round(new_rot, 3), delta_info


def extract_polyline_parts(
    design: ParsedDesign,
    transform: DesignTransform,
    prepared_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    Extract every visible polyline as an Assembly / Cut-List part with its exact
    squared Minimum Bounding Box (OBB via cv2.minAreaRect), Axis-Aligned Bounding
    Box (AABB), orientation angle, perimeter, and grouped material stock summary.
    Works accurately for both orthogonal (0°/90°) and angled/diagonal polylines.
    """
    prepared_ids = prepared_ids or set()
    s = effective_scale(design, transform)
    scaled_w = round(design.base_width_mm * s, 2)
    scaled_h = round(design.base_height_mm * s, 2)
    layer_map = {layer["name"]: layer for layer in design.layers}

    raw_items: list[dict[str, Any]] = []
    all_pts_design: list[list[float]] = []

    for pl_idx, pl in enumerate(design.polylines):
        layer_info = layer_map.get(pl["layer"])
        if layer_info is not None and not layer_info.get("visible", True):
            continue
        pts_base = pl.get("points") or []
        if len(pts_base) < 2:
            continue

        pts_s = [
            [
                round((scaled_w - p[0] * s) if transform.flip_x else (p[0] * s), 2),
                round((scaled_h - p[1] * s) if transform.flip_y else (p[1] * s), 2),
            ]
            for p in pts_base
        ]

        # Compute polyline perimeter / length
        perim = 0.0
        for i in range(len(pts_s) - 1):
            perim += math.hypot(pts_s[i + 1][0] - pts_s[i][0], pts_s[i + 1][1] - pts_s[i][1])
        if perim < 5.0:
            continue

        all_pts_design.extend(pts_s)

        min_x = min(p[0] for p in pts_s)
        max_x = max(p[0] for p in pts_s)
        min_y = min(p[1] for p in pts_s)
        max_y = max(p[1] for p in pts_s)
        aabb_w = max(0.0, max_x - min_x)
        aabb_h = max(0.0, max_y - min_y)
        aabb_corners = [
            [round(min_x, 2), round(min_y, 2)],
            [round(max_x, 2), round(min_y, 2)],
            [round(max_x, 2), round(max_y, 2)],
            [round(min_x, 2), round(max_y, 2)],
        ]

        if len(pts_s) == 2:
            dx = pts_s[1][0] - pts_s[0][0]
            dy = pts_s[1][1] - pts_s[0][1]
            obb_len = math.hypot(dx, dy)
            obb_wid = 0.0
            ang = math.degrees(math.atan2(dy, dx))
            while ang > 90.0:
                ang -= 180.0
            while ang <= -90.0:
                ang += 180.0
            cx = 0.5 * (pts_s[0][0] + pts_s[1][0])
            cy = 0.5 * (pts_s[0][1] + pts_s[1][1])
            obb_corners = [pts_s[0], pts_s[1], pts_s[1], pts_s[0]]
        else:
            arr = np.array(pts_s, dtype=np.float32)
            rect = cv2.minAreaRect(arr)
            (cx, cy), (rw, rh), ang = rect
            if rw >= rh:
                obb_len, obb_wid, obb_ang = float(rw), float(rh), float(ang)
            else:
                obb_len, obb_wid, obb_ang = float(rh), float(rw), float(ang + 90.0)
            while obb_ang > 90.0:
                obb_ang -= 180.0
            while obb_ang <= -90.0:
                obb_ang += 180.0
            ang = obb_ang
            box_pts = cv2.boxPoints(rect)
            obb_corners = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in box_pts]

        # Snap tiny angle jitter OR rotationally-symmetric shapes (e.g. discretized circles)
        # where OBB saves < 1.5% over clean axis-aligned AABB to exact orthogonal 0° / 90°!
        aabb_long = max(aabb_w, aabb_h)
        aabb_short = min(aabb_w, aabb_h)
        obb_matches_aabb = (
            abs(obb_len - aabb_long) <= max(2.0, 0.015 * aabb_long)
            and abs(obb_wid - aabb_short) <= max(2.0, 0.015 * max(aabb_short, 1.0))
        )
        is_ortho = abs(ang) <= 0.6 or abs(abs(ang) - 90.0) <= 0.6 or obb_matches_aabb
        if is_ortho:
            if abs(aabb_w - aabb_h) <= max(2.0, 0.02 * aabb_long):
                ang = 0.0
            else:
                ang = 90.0 if aabb_h > aabb_w else 0.0
            obb_len = aabb_long
            obb_wid = aabb_short
            obb_corners = aabb_corners

        role = layer_info.get("role", pl["role"]) if layer_info else pl["role"]
        group_len = int(round(obb_len))
        group_wid = int(round(obb_wid))
        group_key = f"{group_len} × {group_wid} mm" if group_wid > 0 else f"{group_len} mm"

        raw_items.append({
            "source_index": pl_idx,
            "layer": pl["layer"],
            "role": role,
            "closed": bool(pl.get("closed", False)),
            "vertex_count": len(pts_s),
            "length_mm": round(obb_len, 1),
            "width_mm": round(obb_wid, 1),
            "angle_deg": round(ang, 1),
            "is_orthogonal": is_ortho,
            "aabb_w_mm": round(aabb_w, 1),
            "aabb_h_mm": round(aabb_h, 1),
            "area_mm2": round(obb_len * obb_wid, 1),
            "perimeter_mm": round(perim, 1),
            "center_design_mm": [round(float(cx), 2), round(float(cy), 2)],
            "obb_corners_design_mm": obb_corners,
            "aabb_corners_design_mm": aabb_corners,
            "points_design_mm": pts_s,
            "group_key": group_key,
        })

    # Sort cleanly: longest / largest stock pieces first (standard carpentry cut-list order)
    raw_items.sort(key=lambda it: (-it["length_mm"], -it["width_mm"], it["center_design_mm"][1], it["center_design_mm"][0]))

    items: list[dict[str, Any]] = []
    groups_map: dict[str, dict[str, Any]] = {}
    prepared_count = 0

    for i, item in enumerate(raw_items):
        pid = f"P{i + 1:02d}"
        is_prep = pid in prepared_ids
        if is_prep:
            prepared_count += 1
        item["id"] = pid
        item["index"] = i
        item["prepared"] = is_prep
        items.append(item)

        gk = item["group_key"]
        if gk not in groups_map:
            groups_map[gk] = {
                "key": gk,
                "length_mm": item["length_mm"],
                "width_mm": item["width_mm"],
                "count": 0,
                "prepared_count": 0,
                "part_ids": [],
            }
        groups_map[gk]["count"] += 1
        if is_prep:
            groups_map[gk]["prepared_count"] += 1
        groups_map[gk]["part_ids"].append(pid)

    groups = sorted(
        groups_map.values(),
        key=lambda g: (-g["count"], -g["length_mm"], -g["width_mm"]),
    )

    # Master bounding box of all visible polylines
    if all_pts_design:
        m_min_x = min(p[0] for p in all_pts_design)
        m_max_x = max(p[0] for p in all_pts_design)
        m_min_y = min(p[1] for p in all_pts_design)
        m_max_y = max(p[1] for p in all_pts_design)
        m_arr = np.array(all_pts_design, dtype=np.float32)
        (_, _), (mrw, mrh), mang = cv2.minAreaRect(m_arr)
        m_obb_len = max(float(mrw), float(mrh))
        m_obb_wid = min(float(mrw), float(mrh))
    else:
        m_min_x, m_min_y, m_max_x, m_max_y = 0.0, 0.0, scaled_w, scaled_h
        m_obb_len, m_obb_wid = max(scaled_w, scaled_h), min(scaled_w, scaled_h)

    return {
        "total_count": len(items),
        "group_count": len(groups),
        "prepared_count": prepared_count,
        "master_bbox": {
            "min_x": round(m_min_x, 1),
            "min_y": round(m_min_y, 1),
            "max_x": round(m_max_x, 1),
            "max_y": round(m_max_y, 1),
            "width_mm": round(max(0.0, m_max_x - m_min_x), 1),
            "height_mm": round(max(0.0, m_max_y - m_min_y), 1),
            "obb_length_mm": round(m_obb_len, 1),
            "obb_width_mm": round(m_obb_wid, 1),
        },
        "groups": groups,
        "items": items,
    }


# ---------------------------------------------------------------------
# Progressive Reclaimed-Timber Coverage, Fiducials & Auto-Nesting
# ---------------------------------------------------------------------

def _build_coverage_mask(
    scaled_w: float,
    scaled_h: float,
    completed_regions: list[CompletedRegion],
    grid_res: int = 200,
) -> tuple[np.ndarray, float, float]:
    """Rasterize union of completed regions onto a fast binary mask in design space."""
    aspect = scaled_w / max(scaled_h, 1.0)
    if aspect >= 1.0:
        gw = grid_res
        gh = max(24, int(round(grid_res / aspect)))
    else:
        gh = grid_res
        gw = max(24, int(round(grid_res * aspect)))

    mask = np.zeros((gh, gw), dtype=np.uint8)
    sx = gw / max(scaled_w, 1.0)
    sy = gh / max(scaled_h, 1.0)

    for reg in completed_regions:
        if len(reg.polygon_design_mm) < 3:
            continue
        pts = np.array(
            [[int(round(p[0] * sx)), int(round(p[1] * sy))] for p in reg.polygon_design_mm],
            dtype=np.int32,
        ).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], 1)

    return mask, sx, sy


def compute_coverage_percent(
    scaled_w: float,
    scaled_h: float,
    completed_regions: list[CompletedRegion],
) -> float:
    """Return exact percentage [0..100] of the drawing covered by completed boards."""
    if not completed_regions or scaled_w <= 0 or scaled_h <= 0:
        return 0.0
    mask, _, _ = _build_coverage_mask(scaled_w, scaled_h, completed_regions)
    return round(100.0 * float(np.count_nonzero(mask)) / float(mask.size), 1)


def compute_board_edge_fiducials(
    board_poly_design_mm: list[list[float]],
    scaled_w: float,
    scaled_h: float,
    completed_regions: list[CompletedRegion],
    board_number: int,
    inset_mm: float = 20.0,
) -> list[dict[str, Any]]:
    """
    Place alignment crosshairs inset from each edge of the current board that
    still borders UNCOVERED areas of the drawing, so future boards of ANY size
    overlapping this edge automatically inherit these exact physical marks.
    """
    if len(board_poly_design_mm) < 3:
        return []

    cx = sum(p[0] for p in board_poly_design_mm) / len(board_poly_design_mm)
    cy = sum(p[1] for p in board_poly_design_mm) / len(board_poly_design_mm)
    mask, sx, sy = _build_coverage_mask(scaled_w, scaled_h, completed_regions)
    gh, gw = mask.shape

    def is_uncovered_in_design(px: float, py: float) -> bool:
        if px < 5.0 or py < 5.0 or px > scaled_w - 5.0 or py > scaled_h - 5.0:
            return False
        gx = max(0, min(gw - 1, int(round(px * sx))))
        gy = max(0, min(gh - 1, int(round(py * sy))))
        return mask[gy, gx] == 0

    fiducials: list[dict[str, Any]] = []
    letter_idx = 0
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    n = len(board_poly_design_mm)

    for i in range(n):
        p0 = board_poly_design_mm[i]
        p1 = board_poly_design_mm[(i + 1) % n]
        ex = p1[0] - p0[0]
        ey = p1[1] - p0[1]
        edge_len = math.hypot(ex, ey)
        if edge_len < 120.0:
            continue

        # Unit inward normal pointing towards board centroid
        nx, ny = -ey / edge_len, ex / edge_len
        mid_x, mid_y = 0.5 * (p0[0] + p1[0]), 0.5 * (p0[1] + p1[1])
        if (cx - mid_x) * nx + (cy - mid_y) * ny < 0:
            nx, ny = -nx, -ny

        # Probe just OUTSIDE this edge to see if uncovered drawing lies beyond it
        probe_x = mid_x - nx * 35.0
        probe_y = mid_y - ny * 35.0
        probe_q1_x = p0[0] + ex * 0.25 - nx * 35.0
        probe_q1_y = p0[1] + ey * 0.25 - ny * 35.0
        probe_q3_x = p0[0] + ex * 0.75 - nx * 35.0
        probe_q3_y = p0[1] + ey * 0.75 - ny * 35.0

        if not (
            is_uncovered_in_design(probe_x, probe_y)
            or is_uncovered_in_design(probe_q1_x, probe_q1_y)
            or is_uncovered_in_design(probe_q3_x, probe_q3_y)
        ):
            continue

        for frac in (0.25, 0.75):
            fx = p0[0] + ex * frac + nx * inset_mm
            fy = p0[1] + ey * frac + ny * inset_mm
            if 0.0 <= fx <= scaled_w and 0.0 <= fy <= scaled_h:
                code = f"M{board_number}-{letters[letter_idx % len(letters)]}"
                letter_idx += 1
                fiducials.append({
                    "code": code,
                    "pos_design_mm": [round(fx, 2), round(fy, 2)],
                    "origin_board": board_number,
                })

    return fiducials


def suggest_next_board_placement(
    design: ParsedDesign,
    transform: DesignTransform,
    board_bounds: tuple[float, float, float, float],
    completed_regions: list[CompletedRegion],
    board_contours_mm: list[list[list[float]]] | None = None,
    overlap_mm: float = 0.0,
) -> tuple[float, float, float]:
    """
    Square, minimum-waste orthogonal (guillotine) nesting for reclaimed timber boards.

    Automatically aligns the drawing squarely with the scanned board's principal
    axis (testing BOTH 0° and 90° orthogonal orientations relative to the board),
    maximizing newly covered design area while minimizing material waste, keeping
    offcuts consolidated into one clean straight saw cut, and avoiding thin slivers.

    Returns (offset_x_mm, offset_y_mm, rotation_deg).
    """
    bcx, bcy, board_len, board_wid, board_ang = extract_board_oriented_box(
        board_contours_mm=board_contours_mm,
        board_bounds=board_bounds,
    )
    s = effective_scale(design, transform)
    scaled_w = max(1.0, design.base_width_mm * s)
    scaled_h = max(1.0, design.base_height_mm * s)

    def _map_rect_to_transform(rx0: float, ry0: float, rw: float, rh: float, rot_deg: float) -> tuple[float, float, float]:
        target_cx = rx0 + 0.5 * rw
        target_cy = ry0 + 0.5 * rh
        tmp_t = DesignTransform(
            offset_x_mm=0.0,
            offset_y_mm=0.0,
            rotation_deg=rot_deg,
            scale=transform.scale,
            flip_x=transform.flip_x,
            flip_y=transform.flip_y,
        )
        mapped = scaled_design_to_workspace(target_cx, target_cy, scaled_w, scaled_h, tmp_t)
        return round(bcx - mapped[0], 2), round(bcy - mapped[1], 2), round(rot_deg % 360.0, 2)

    # First board: align squarely with the board's straight edges (center if design fits, top-left if nesting)
    if not completed_regions:
        rot0 = board_ang % 360.0
        rot90 = (board_ang + 90.0) % 360.0
        fits0 = (scaled_w <= board_len + 1.0) and (scaled_h <= board_wid + 1.0)
        fits90 = (scaled_w <= board_wid + 1.0) and (scaled_h <= board_len + 1.0)
        if fits0:
            return _map_rect_to_transform(0.5 * (scaled_w - board_len), 0.5 * (scaled_h - board_wid), board_len, board_wid, rot0)
        if fits90:
            return _map_rect_to_transform(0.5 * (scaled_w - board_wid), 0.5 * (scaled_h - board_len), board_wid, board_len, rot90)
        # Oversized drawing: square top-left anchor, picking orientation with less sliver waste
        best_init = None
        for rot_deg, eff_w, eff_h, tie_bonus in (
            (rot0, board_len, board_wid, 0.01),
            (rot90, board_wid, board_len, 0.0),
        ):
            cov_w = min(scaled_w, eff_w)
            cov_h = min(scaled_h, eff_h)
            useful = cov_w * cov_h
            rem_x = max(0.0, scaled_w - eff_w)
            rem_y = max(0.0, scaled_h - eff_h)
            sliver_pen = 0.0
            if 10.0 < rem_x < 220.0:
                sliver_pen += 0.14 * eff_w * eff_h
            if 10.0 < rem_y < 220.0:
                sliver_pen += 0.14 * eff_w * eff_h
            sc = useful - sliver_pen + tie_bonus * eff_w * eff_h
            if best_init is None or sc > best_init[0]:
                best_init = (sc, 0.0, 0.0, eff_w, eff_h, rot_deg)
        _, rx0, ry0, rw, rh, rot_deg = best_init
        return _map_rect_to_transform(rx0, ry0, rw, rh, rot_deg)

    # Subsequent heterogeneous boards: orthogonal minimum-waste guillotine search
    mask, sx, sy = _build_coverage_mask(scaled_w, scaled_h, completed_regions, grid_res=200)
    gh, gw = mask.shape
    uncovered = (1 - mask).astype(np.uint8)
    integral_unc = cv2.integral(uncovered)
    integral_cov = cv2.integral(mask.astype(np.uint8))
    cell_area_mm2 = (1.0 / sx) * (1.0 / sy)

    # Precompute existing completed region bounding edges in design mm for exact flush snapping
    reg_boxes: list[tuple[float, float, float, float]] = []
    for reg in completed_regions:
        if not reg.polygon_design_mm:
            continue
        reg_boxes.append((
            min(p[0] for p in reg.polygon_design_mm),
            min(p[1] for p in reg.polygon_design_mm),
            max(p[0] for p in reg.polygon_design_mm),
            max(p[1] for p in reg.polygon_design_mm),
        ))

    ov = max(0.0, min(float(overlap_mm), min(board_len, board_wid) * 0.3))
    sliver_min = 240.0

    best_score = -1e30
    best_choice: tuple[float, float, float, float, float] | None = None

    orientations = [
        (board_ang % 360.0, board_len, board_wid, True),
        ((board_ang + 90.0) % 360.0, board_wid, board_len, False),
    ]

    for rot_deg, eff_w, eff_h, is_primary_grain in orientations:
        board_area = eff_w * eff_h

        # Build rich candidate anchors: flush design walls + flush prior board edges + coarse grid
        x_cands_raw: list[float] = [0.0, scaled_w - eff_w]
        y_cands_raw: list[float] = [0.0, scaled_h - eff_h]
        if eff_w > scaled_w:
            x_cands_raw.append(0.5 * (scaled_w - eff_w))
        if eff_h > scaled_h:
            y_cands_raw.append(0.5 * (scaled_h - eff_h))

        for rx0, ry0, rx1, ry1 in reg_boxes:
            x_cands_raw.extend([rx1, rx1 - ov, rx0, rx0 - eff_w, rx0 - eff_w + ov, rx1 - eff_w])
            y_cands_raw.extend([ry1, ry1 - ov, ry0, ry0 - eff_h, ry0 - eff_h + ov, ry1 - eff_h])

        # Add coarse fallback grid spanning design
        max_x = max(0.0, scaled_w - eff_w)
        max_y = max(0.0, scaled_h - eff_h)
        step_x = max(60.0, eff_w / 10.0)
        step_y = max(60.0, eff_h / 10.0)
        gx = 0.0
        while gx <= max_x + 1.0:
            x_cands_raw.append(gx)
            gx += step_x
        gy = 0.0
        while gy <= max_y + 1.0:
            y_cands_raw.append(gy)
            gy += step_y

        # Deduplicate close candidates (within 3mm) & clamp sensible range
        def _clean_cands(vals: list[float], limit_min: float, limit_max: float) -> list[float]:
            clamped = sorted(max(limit_min, min(limit_max, v)) for v in vals)
            out: list[float] = []
            for v in clamped:
                if not out or abs(v - out[-1]) > 3.0:
                    out.append(v)
            return out

        xs = _clean_cands(x_cands_raw, min(0.0, scaled_w - eff_w) - eff_w * 0.15, max(0.0, scaled_w - eff_w) + eff_w * 0.15)
        ys = _clean_cands(y_cands_raw, min(0.0, scaled_h - eff_h) - eff_h * 0.15, max(0.0, scaled_h - eff_h) + eff_h * 0.15)

        for y0 in ys:
            y1 = y0 + eff_h
            iy0 = max(0.0, min(scaled_h, y0))
            iy1 = max(0.0, min(scaled_h, y1))
            if iy1 <= iy0 + 1.0:
                continue
            cy0 = max(0, min(gh, int(round(iy0 * sy))))
            cy1 = max(cy0, min(gh, int(round(iy1 * sy))))

            # Pre-check flush Y conditions
            flush_top = abs(y0) <= 6.0
            flush_bot = abs(y1 - scaled_h) <= 6.0
            shares_y_band = any((abs(y0 - ry0) <= 12.0 and abs(y1 - ry1) <= 12.0) for _, ry0, _, ry1 in reg_boxes)
            touches_y_reg = any((abs(y0 - ry1) <= ov + 12.0 or abs(y1 - ry0) <= ov + 12.0 or abs(y0 - ry0) <= 12.0) for _, ry0, _, ry1 in reg_boxes)

            for x0 in xs:
                x1 = x0 + eff_w
                ix0 = max(0.0, min(scaled_w, x0))
                ix1 = max(0.0, min(scaled_w, x1))
                if ix1 <= ix0 + 1.0:
                    continue
                cx0 = max(0, min(gw, int(round(ix0 * sx))))
                cx1 = max(cx0, min(gw, int(round(ix1 * sx))))

                unc_cells = float(
                    integral_unc[cy1, cx1]
                    - integral_unc[cy0, cx1]
                    - integral_unc[cy1, cx0]
                    + integral_unc[cy0, cx0]
                )
                if unc_cells <= 0.5:
                    continue
                cov_cells = float(
                    integral_cov[cy1, cx1]
                    - integral_cov[cy0, cx1]
                    - integral_cov[cy1, cx0]
                    + integral_cov[cy0, cx0]
                )

                a_new = unc_cells * cell_area_mm2
                a_overlap = cov_cells * cell_area_mm2
                a_in = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
                a_out = max(0.0, board_area - a_in)

                # Core minimum-waste objective:
                # 1. Maximize newly covered drawing area (fewest total boards!)
                # 2. Penalize overhang outside drawing slightly more than overlap inside drawing
                #    so scrap consolidates on ONE clean straight saw cut instead of two thin edges.
                score = a_new - 0.26 * a_out - 0.14 * a_overlap

                # 3. Guillotine / square shelf-completion bonus (avoids fragmented L-shaped leftovers!)
                flush_left = abs(x0) <= 6.0
                flush_right = abs(x1 - scaled_w) <= 6.0
                shares_x_band = any((abs(x0 - rx0) <= 12.0 and abs(x1 - rx1) <= 12.0) for rx0, _, rx1, _ in reg_boxes)
                touches_x_reg = any((abs(x0 - rx1) <= ov + 12.0 or abs(x1 - rx0) <= ov + 12.0 or abs(x0 - rx0) <= 12.0) for rx0, _, rx1, _ in reg_boxes)

                if shares_y_band and (flush_right or flush_left):
                    score += 0.16 * board_area  # Completes a full clean horizontal shelf!
                if shares_x_band and (flush_bot or flush_top):
                    score += 0.16 * board_area  # Completes a full clean vertical column!
                if (flush_left or flush_right) and (flush_top or flush_bot):
                    score += 0.05 * board_area  # Clean corner anchor!
                elif (flush_left or flush_right or touches_x_reg) and (flush_top or flush_bot or touches_y_reg):
                    score += 0.03 * board_area

                # 4. Penalize creating narrow unusable slivers along outer edges
                rem_left = ix0
                rem_right = scaled_w - ix1
                rem_top = iy0
                rem_bot = scaled_h - iy1
                if 15.0 < rem_right < sliver_min:
                    score -= 0.12 * board_area
                if 15.0 < rem_bot < sliver_min:
                    score -= 0.12 * board_area
                if 15.0 < rem_left < sliver_min and not any(rx1 >= ix0 - 8.0 for _, _, rx1, _ in reg_boxes):
                    score -= 0.10 * board_area
                if 15.0 < rem_top < sliver_min and not any(ry1 >= iy0 - 8.0 for _, _, _, ry1 in reg_boxes):
                    score -= 0.10 * board_area

                # 5. Subtle reading-order & natural grain tie-breakers
                score -= 0.015 * (iy0 / scaled_h) * board_area + 0.008 * (ix0 / scaled_w) * board_area
                if is_primary_grain:
                    score += 0.004 * board_area

                if score > best_score:
                    best_score = score
                    best_choice = (x0, y0, eff_w, eff_h, rot_deg)

    if best_choice is None:
        return _map_rect_to_transform(0.5 * (scaled_w - board_len), 0.5 * (scaled_h - board_wid), board_len, board_wid, board_ang % 360.0)

    bx, by, bw_sel, bh_sel, rot_sel = best_choice
    return _map_rect_to_transform(bx, by, bw_sel, bh_sel, rot_sel)


def suggest_next_board_offset(
    design: ParsedDesign,
    transform: DesignTransform,
    board_bounds: tuple[float, float, float, float],
    completed_regions: list[CompletedRegion],
    overlap_mm: float = 0.0,
    board_contours_mm: list[list[list[float]]] | None = None,
) -> tuple[float, float]:
    """Backwards-compatible wrapper returning (offset_x_mm, offset_y_mm)."""
    ox, oy, _ = suggest_next_board_placement(
        design=design,
        transform=transform,
        board_bounds=board_bounds,
        completed_regions=completed_regions,
        board_contours_mm=board_contours_mm,
        overlap_mm=overlap_mm,
    )
    return ox, oy


# ---------------------------------------------------------------------
# Main Mosaic & Progressive Nesting Engine
# ---------------------------------------------------------------------

class MosaicEngine:
    """Computes transformed workspace geometry, progressive nesting, mosaic grid, and active projection."""

    @staticmethod
    def resolve_projection_window(
        board_bounds: tuple[float, float, float, float],
        table_size_mm: tuple[float, float],
        cfg: MosaicConfig,
    ) -> dict[str, float]:
        """Resolve the physical target projection window [x0, y0, x1, y1] on the table."""
        bx0, by0, bx1, by1 = board_bounds
        table_w, table_h = table_size_mm
        margin = max(0.0, float(cfg.margin_mm))

        if cfg.tile_source == "table":
            w = max(50.0, table_w - 2.0 * margin)
            h = max(50.0, table_h - 2.0 * margin)
            x0 = margin
            y0 = margin
        elif cfg.tile_source == "custom":
            w = max(50.0, float(cfg.custom_tile_w_mm) - 2.0 * margin)
            h = max(50.0, float(cfg.custom_tile_h_mm) - 2.0 * margin)
            bcx = 0.5 * (bx0 + bx1)
            bcy = 0.5 * (by0 + by1)
            x0 = bcx - 0.5 * w
            y0 = bcy - 0.5 * h
        else:
            bw = max(50.0, bx1 - bx0)
            bh = max(50.0, by1 - by0)
            safe_margin = min(margin, min(bw, bh) * 0.4)
            w = max(50.0, bw - 2.0 * safe_margin)
            h = max(50.0, bh - 2.0 * safe_margin)
            x0 = bx0 + safe_margin
            y0 = by0 + safe_margin

        return {
            "x0": round(x0, 3),
            "y0": round(y0, 3),
            "x1": round(x0 + w, 3),
            "y1": round(y0 + h, 3),
            "width_mm": round(w, 3),
            "height_mm": round(h, 3),
        }

    @classmethod
    def compute(
        cls,
        design: ParsedDesign | None,
        transform: DesignTransform,
        board_bounds: tuple[float, float, float, float],
        table_size_mm: tuple[float, float],
        mosaic_cfg: MosaicConfig,
        board_contours_mm: list[list[list[float]]] | None = None,
        completed_regions: list[CompletedRegion] | None = None,
        reviewing_region_index: int | None = None,
        prepared_part_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Compute complete overview state, progressive nesting state, and active projection geometry."""
        completed_regions = completed_regions or []
        proj_win = cls.resolve_projection_window(
            board_bounds=board_bounds,
            table_size_mm=table_size_mm,
            cfg=mosaic_cfg,
        )

        # Fallback contour if caller didn't pass explicit polygons
        if not board_contours_mm:
            bx0, by0, bx1, by1 = board_bounds
            board_contours_mm = [[[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]]]

        if design is None:
            return {
                "projection_window": proj_win,
                "design_bounds": None,
                "design_corners": [],
                "effective_scale": 1.0,
                "scaled_width_mm": 0.0,
                "scaled_height_mm": 0.0,
                "exceeds_window": False,
                "suggested_grid": {"rows": 1, "cols": 1, "total": 1},
                "world_design": {"polylines": [], "points": [], "labels": []},
                "tiles": [],
                "active_tile": None,
                "parts": {
                    "total_count": 0,
                    "group_count": 0,
                    "prepared_count": 0,
                    "master_bbox": {
                        "min_x": 0.0,
                        "min_y": 0.0,
                        "max_x": 0.0,
                        "max_y": 0.0,
                        "width_mm": 0.0,
                        "height_mm": 0.0,
                        "obb_length_mm": 0.0,
                        "obb_width_mm": 0.0,
                    },
                    "groups": [],
                    "items": [],
                },
                "progressive": {
                    "completed_count": 0,
                    "active_board_number": 1,
                    "coverage_pct": 0.0,
                    "reviewing_index": None,
                    "completed_regions_world": [],
                    "inherited_fiducials": [],
                    "new_fiducials": [],
                    "joint_cut_lines": [],
                    "overlap_trim_polygons": [],
                    "material_stats": {
                        "board_area_mm2": 0.0,
                        "useful_area_mm2": 0.0,
                        "overlap_trim_mm2": 0.0,
                        "utilization_pct": 0.0,
                    },
                },
                "projection_geometry": {
                    "cut_geo": [],
                    "mill_geo": [],
                    "points_geo": [],
                    "labels": [],
                    "tile_border": [],
                    "seam_lines": [],
                    "joint_cut_lines": [],
                    "overlap_trim_polygons": [],
                    "raster_transform": None,
                    "clip_polygons_mm": board_contours_mm,
                    "shift_x_mm": 0.0,
                    "shift_y_mm": 0.0,
                },
            }

        s = effective_scale(design, transform)
        scaled_w = design.base_width_mm * s
        scaled_h = design.base_height_mm * s
        corners = transformed_design_corners(design, transform)
        d_min_x = min(c[0] for c in corners)
        d_max_x = max(c[0] for c in corners)
        d_min_y = min(c[1] for c in corners)
        d_max_y = max(c[1] for c in corners)
        design_w_bbox = d_max_x - d_min_x
        design_h_bbox = d_max_y - d_min_y

        layer_map = {layer["name"]: layer for layer in design.layers}

        world_polylines: list[dict[str, Any]] = []
        for pl in design.polylines:
            layer_info = layer_map.get(pl["layer"])
            if layer_info is not None and not layer_info.get("visible", True):
                continue
            role = layer_info.get("role", pl["role"]) if layer_info else pl["role"]
            color = layer_info.get("color", pl["color"]) if layer_info else pl["color"]
            pts = [
                transform_point(p[0], p[1], design.base_width_mm, design.base_height_mm, s, transform)
                for p in pl["points"]
            ]
            world_polylines.append({
                "points": pts,
                "closed": pl["closed"],
                "layer": pl["layer"],
                "role": role,
                "color": color,
            })

        world_points: list[dict[str, Any]] = []
        for pt in design.points:
            layer_info = layer_map.get(pt["layer"])
            if layer_info is not None and not layer_info.get("visible", True):
                continue
            world_points.append({
                "pos": transform_point(
                    pt["pos"][0], pt["pos"][1], design.base_width_mm, design.base_height_mm, s, transform
                ),
                "layer": pt["layer"],
                "color": layer_info.get("color", pt["color"]) if layer_info else pt["color"],
            })

        world_labels: list[dict[str, Any]] = []
        for lb in design.labels:
            layer_info = layer_map.get(lb["layer"])
            if layer_info is not None and not layer_info.get("visible", True):
                continue
            world_labels.append({
                "text": lb["text"],
                "pos": transform_point(
                    lb["pos"][0], lb["pos"][1], design.base_width_mm, design.base_height_mm, s, transform
                ),
                "layer": lb["layer"],
                "color": layer_info.get("color", lb["color"]) if layer_info else lb["color"],
            })

        # Map completed regions into current workspace mm so canvas hatches them over the drawing!
        completed_regions_world: list[dict[str, Any]] = []
        for reg in completed_regions:
            poly_world = [
                scaled_design_to_workspace(p[0], p[1], scaled_w, scaled_h, transform)
                for p in reg.polygon_design_mm
            ]
            fids_world = [
                {
                    "code": f["code"],
                    "pos_mm": scaled_design_to_workspace(
                        f["pos_design_mm"][0], f["pos_design_mm"][1], scaled_w, scaled_h, transform
                    ),
                    "origin_board": f["origin_board"],
                }
                for f in reg.fiducials_design_mm
            ]
            completed_regions_world.append({
                "index": reg.index,
                "board_id": reg.board_id,
                "board_length_mm": reg.board_length_mm,
                "board_width_mm": reg.board_width_mm,
                "polygon_mm": poly_world,
                "fiducials_world": fids_world,
            })

        coverage_pct = compute_coverage_percent(scaled_w, scaled_h, completed_regions)

        tile_w = proj_win["width_mm"]
        tile_h = proj_win["height_mm"]
        ov = max(0.0, min(float(mosaic_cfg.overlap_mm), min(tile_w, tile_h) * 0.45))
        step_x = max(10.0, tile_w - ov)
        step_y = max(10.0, tile_h - ov)

        exceeds_window = (design_w_bbox > tile_w + 1.0) or (design_h_bbox > tile_h + 1.0)
        sugg_cols = max(1, math.ceil(max(0.0, design_w_bbox - ov) / step_x))
        sugg_rows = max(1, math.ceil(max(0.0, design_h_bbox - ov) / step_y))

        # Uniform grid (computed for "mosaic" mode and backwards compatibility)
        c_min = math.floor((d_min_x - proj_win["x0"] + 1e-4) / step_x)
        c_max = max(c_min, math.ceil((d_max_x - proj_win["x0"] - tile_w - 1e-4) / step_x))
        r_min = math.floor((d_min_y - proj_win["y0"] + 1e-4) / step_y)
        r_max = max(r_min, math.ceil((d_max_y - proj_win["y0"] - tile_h - 1e-4) / step_y))
        if (c_max - c_min + 1) > MAX_GRID_DIM:
            c_max = c_min + MAX_GRID_DIM - 1
        if (r_max - r_min + 1) > MAX_GRID_DIM:
            r_max = r_min + MAX_GRID_DIM - 1

        raw_tiles: list[dict[str, Any]] = []
        grid_rows = r_max - r_min + 1
        grid_cols = c_max - c_min + 1
        for r_idx, r in enumerate(range(r_min, r_max + 1)):
            for c_idx, c in enumerate(range(c_min, c_max + 1)):
                tx0 = proj_win["x0"] + c * step_x
                ty0 = proj_win["y0"] + r * step_y
                tx1 = tx0 + tile_w
                ty1 = ty0 + tile_h
                has_content = False
                if design.has_raster:
                    if not (tx1 < d_min_x or tx0 > d_max_x or ty1 < d_min_y or ty0 > d_max_y):
                        has_content = True
                if not has_content:
                    for pl in world_polylines:
                        if clip_polyline_to_rect(pl["points"], tx0, ty0, tx1, ty1):
                            has_content = True
                            break
                if not has_content:
                    for pt in world_points:
                        if point_in_rect(pt["pos"][0], pt["pos"][1], tx0, ty0, tx1, ty1):
                            has_content = True
                            break
                raw_tiles.append({
                    "grid_r": r,
                    "grid_c": c,
                    "row": r_idx + 1,
                    "col": c_idx + 1,
                    "rows": grid_rows,
                    "cols": grid_cols,
                    "code": f"F{r_idx + 1}C{c_idx + 1}",
                    "x0": round(tx0, 3),
                    "y0": round(ty0, 3),
                    "x1": round(tx1, 3),
                    "y1": round(ty1, 3),
                    "width_mm": round(tile_w, 3),
                    "height_mm": round(tile_h, 3),
                    "has_content": has_content,
                    "has_left": c > c_min,
                    "has_right": c < c_max,
                    "has_top": r > r_min,
                    "has_bottom": r < r_max,
                })

        if mosaic_cfg.skip_empty_tiles:
            tiles = [t for t in raw_tiles if t["has_content"]] or raw_tiles[:1]
        else:
            tiles = raw_tiles
        for idx, tile in enumerate(tiles):
            tile["index"] = idx
            tile["number"] = idx + 1
            tile["total"] = len(tiles)

        # Build active projection geometry
        cut_geo: list[list[list[float]]] = []
        mill_geo: list[list[list[float]]] = []
        points_geo: list[list[float]] = []
        labels_out: list[dict[str, Any]] = []
        tile_border: list[list[list[float]]] = []
        seam_lines: list[list[list[float]]] = []
        active_tile: dict[str, Any] | None = None
        shift_x = 0.0
        shift_y = 0.0
        clip_polygons_mm: list[list[list[float]]] | None = None
        inherited_fiducials: list[dict[str, Any]] = []
        new_fiducials: list[dict[str, Any]] = []
        joint_cut_lines: list[dict[str, Any]] = []
        overlap_trim_polygons: list[dict[str, Any]] = []
        prior_polys_world: list[list[list[float]]] = []
        material_stats: dict[str, float] = {
            "board_area_mm2": 0.0,
            "useful_area_mm2": 0.0,
            "overlap_trim_mm2": 0.0,
            "utilization_pct": 0.0,
        }
        active_board_num = len(completed_regions) + 1

        if mosaic_cfg.mode == "progressive":
            # Clip strictly to the EXACT scanned board polygon(s) (handles rotated / irregular boards!)
            clip_polygons_mm = board_contours_mm

            # Determine prior completed boards strictly before the active (or reviewed) board
            prior_regions_world = [
                reg_w
                for reg_w in completed_regions_world
                if (reviewing_region_index is None or reg_w["index"] < reviewing_region_index)
            ]
            prior_polys_world = [reg_w["polygon_mm"] for reg_w in prior_regions_world if len(reg_w["polygon_mm"]) >= 3]

            # 1. Exact overlap JOINT CUT LINES & trim waste polygons (Active Board ∩ Prior Boards)
            joint_cut_lines, overlap_trim_polygons = compute_overlap_joint_cut_lines(
                board_contours_mm=board_contours_mm,
                prior_regions_world=prior_regions_world,
            )

            # 2. Clip drawing geometry to (Active Board MINUS Prior Completed Boards) so operator
            #    only cuts the net new piece and sees a razor-sharp trim boundary at the joint cut line!
            for pl in world_polylines:
                clipped_list = clip_polyline_in_minus_out(pl["points"], board_contours_mm, prior_polys_world)
                for seg in clipped_list:
                    rounded = [[round(p[0], 2), round(p[1], 2)] for p in seg]
                    if pl["role"] == "mill":
                        mill_geo.append(rounded)
                    else:
                        cut_geo.append(rounded)

            for pt in world_points:
                in_b = any(point_in_polygon(pt["pos"][0], pt["pos"][1], poly) for poly in board_contours_mm)
                in_p = any(point_in_polygon(pt["pos"][0], pt["pos"][1], poly) for poly in prior_polys_world)
                if in_b and not in_p:
                    points_geo.append([round(pt["pos"][0], 2), round(pt["pos"][1], 2)])

            for lb in world_labels:
                in_b = any(point_in_polygon(lb["pos"][0], lb["pos"][1], poly) for poly in board_contours_mm)
                in_p = any(point_in_polygon(lb["pos"][0], lb["pos"][1], poly) for poly in prior_polys_world)
                if in_b and not in_p:
                    labels_out.append({
                        "text": lb["text"],
                        "pos": [round(lb["pos"][0], 2), round(lb["pos"][1], 2)],
                    })

            # Expose joint cut lines also in seam_lines & labels for projector / OpenCV compatibility
            for jc in joint_cut_lines:
                seam_lines.append(jc["points"])
                labels_out.append({
                    "text": jc["label"],
                    "pos": jc["label_pos"],
                })

            # Compute material utilization stats for the active board
            board_area = sum(polygon_area_mm2(p) for p in board_contours_mm)
            overlap_trim_area = sum(float(tp["area_mm2"]) for tp in overlap_trim_polygons)
            if board_area > 1.0:
                # Net area of active board that falls inside design bounds AND outside prior boards
                design_poly_world = corners if len(corners) == 4 else []
                in_design_area = 0.0
                if design_poly_world:
                    for b_poly in board_contours_mm:
                        a_in, _ = intersect_polygons_mm(b_poly, design_poly_world)
                        in_design_area += a_in
                overlap_in_design = 0.0
                if design_poly_world:
                    for tp in overlap_trim_polygons:
                        a_ov, _ = intersect_polygons_mm(tp["polygon_mm"], design_poly_world)
                        overlap_in_design += a_ov
                useful_area = max(0.0, in_design_area - overlap_in_design)
                material_stats = {
                    "board_area_mm2": round(board_area, 1),
                    "useful_area_mm2": round(useful_area, 1),
                    "overlap_trim_mm2": round(overlap_trim_area, 1),
                    "utilization_pct": round(min(100.0, 100.0 * useful_area / board_area), 1),
                }

            if mosaic_cfg.show_registration_marks and board_contours_mm:
                # 1. Re-project ANY fiducial marks from previously stamped boards that fall inside THIS board!
                seen_codes: set[str] = set()
                for reg_w in prior_regions_world:
                    for fid in reg_w["fiducials_world"]:
                        fx, fy = fid["pos_mm"]
                        if any(point_in_polygon(fx, fy, poly) for poly in board_contours_mm):
                            if fid["code"] not in seen_codes:
                                seen_codes.add(fid["code"])
                                inherited_fiducials.append(fid)
                                points_geo.append([round(fx, 2), round(fy, 2)])
                                labels_out.append({
                                    "text": fid["code"],
                                    "pos": [round(fx + 10.0, 2), round(fy - 8.0, 2)],
                                })

                # 2. Place alignment ticks directly along each JOINT CUT LINE (so cut edges match nose-to-nose!)
                for idx_jc, jc in enumerate(joint_cut_lines):
                    p0, p1 = jc["points"][0], jc["points"][1]
                    if jc["length_mm"] >= 140.0:
                        fracs = (0.25, 0.75)
                    else:
                        fracs = (0.5,)
                    for fi, frac in enumerate(fracs):
                        jx = round(p0[0] + (p1[0] - p0[0]) * frac, 2)
                        jy = round(p0[1] + (p1[1] - p0[1]) * frac, 2)
                        points_geo.append([jx, jy])

                # 3. Generate new edge fiducials on uncovered edges of THIS board (kept side only!)
                primary_board_design = [
                    workspace_to_scaled_design(p[0], p[1], scaled_w, scaled_h, transform)
                    for p in board_contours_mm[0]
                ]
                prior_completed_objs = [
                    r for r in completed_regions
                    if (reviewing_region_index is None or r.index < reviewing_region_index)
                ]
                new_fids_design = compute_board_edge_fiducials(
                    board_poly_design_mm=primary_board_design,
                    scaled_w=scaled_w,
                    scaled_h=scaled_h,
                    completed_regions=prior_completed_objs,
                    board_number=reviewing_region_index if reviewing_region_index is not None else active_board_num,
                    inset_mm=max(14.0, min(28.0, ov * 0.5)),
                )
                for nf in new_fids_design:
                    wpos = scaled_design_to_workspace(
                        nf["pos_design_mm"][0], nf["pos_design_mm"][1], scaled_w, scaled_h, transform
                    )
                    if any(point_in_polygon(wpos[0], wpos[1], poly) for poly in prior_polys_world):
                        continue
                    new_fiducials.append({**nf, "pos_mm": wpos})
                    points_geo.append([round(wpos[0], 2), round(wpos[1], 2)])
                    labels_out.append({
                        "text": nf["code"],
                        "pos": [round(wpos[0] + 10.0, 2), round(wpos[1] - 8.0, 2)],
                    })

                # Clean board badge inside top-left of board
                badge_num = reviewing_region_index if reviewing_region_index is not None else active_board_num
                labels_out.append({
                    "text": f"#{badge_num}",
                    "pos": [round(board_bounds[0] + 18.0, 2), round(board_bounds[1] + 28.0, 2)],
                })

        elif mosaic_cfg.mode == "mosaic" and tiles:
            active_idx = max(0, min(int(mosaic_cfg.active_tile_index), len(tiles) - 1))
            active_tile = tiles[active_idx]
            tx0, ty0, tx1, ty1 = active_tile["x0"], active_tile["y0"], active_tile["x1"], active_tile["y1"]
            shift_x = proj_win["x0"] - tx0
            shift_y = proj_win["y0"] - ty0

            def map_pt(pt: list[float]) -> list[float]:
                return [round(pt[0] + shift_x, 2), round(pt[1] + shift_y, 2)]

            for pl in world_polylines:
                for seg in clip_polyline_to_rect(pl["points"], tx0, ty0, tx1, ty1):
                    mapped = [map_pt(p) for p in seg]
                    if pl["role"] == "mill":
                        mill_geo.append(mapped)
                    else:
                        cut_geo.append(mapped)

            for pt in world_points:
                if point_in_rect(pt["pos"][0], pt["pos"][1], tx0, ty0, tx1, ty1):
                    points_geo.append(map_pt(pt["pos"]))

            for lb in world_labels:
                if point_in_rect(lb["pos"][0], lb["pos"][1], tx0, ty0, tx1, ty1):
                    labels_out.append({"text": lb["text"], "pos": map_pt(lb["pos"])})

            px0, py0, px1, py1 = proj_win["x0"], proj_win["y0"], proj_win["x1"], proj_win["y1"]
            if mosaic_cfg.show_tile_border:
                tile_border.append([[round(px0, 2), round(py0, 2)], [round(px1, 2), round(py0, 2)], [round(px1, 2), round(py1, 2)], [round(px0, 2), round(py1, 2)], [round(px0, 2), round(py0, 2)]])

            if mosaic_cfg.show_registration_marks:
                half_ov = ov * 0.5
                r_num, c_num = active_tile["row"], active_tile["col"]
                if active_tile["has_right"]:
                    seam_wx = tx1 - half_ov
                    seam_lines.append([map_pt([seam_wx, ty0]), map_pt([seam_wx, ty1])])
                    for suffix, wy in (("A", ty0 + tile_h * 0.25), ("B", ty0 + tile_h * 0.75)):
                        pm = map_pt([seam_wx, wy])
                        points_geo.append(pm)
                        labels_out.append({"text": f"V{c_num}-F{r_num}{suffix}", "pos": [round(pm[0] + 10.0, 2), round(pm[1] - 8.0, 2)]})
                if active_tile["has_left"]:
                    seam_wx = tx0 + half_ov
                    seam_lines.append([map_pt([seam_wx, ty0]), map_pt([seam_wx, ty1])])
                    for suffix, wy in (("A", ty0 + tile_h * 0.25), ("B", ty0 + tile_h * 0.75)):
                        pm = map_pt([seam_wx, wy])
                        points_geo.append(pm)
                        labels_out.append({"text": f"V{c_num - 1}-F{r_num}{suffix}", "pos": [round(pm[0] + 10.0, 2), round(pm[1] - 8.0, 2)]})
                if active_tile["has_bottom"]:
                    seam_wy = ty1 - half_ov
                    seam_lines.append([map_pt([tx0, seam_wy]), map_pt([tx1, seam_wy])])
                    for suffix, wx in (("A", tx0 + tile_w * 0.25), ("B", tx0 + tile_w * 0.75)):
                        pm = map_pt([wx, seam_wy])
                        points_geo.append(pm)
                        labels_out.append({"text": f"H{r_num}-C{c_num}{suffix}", "pos": [round(pm[0] + 10.0, 2), round(pm[1] - 8.0, 2)]})
                if active_tile["has_top"]:
                    seam_wy = ty0 + half_ov
                    seam_lines.append([map_pt([tx0, seam_wy]), map_pt([tx1, seam_wy])])
                    for suffix, wx in (("A", tx0 + tile_w * 0.25), ("B", tx0 + tile_w * 0.75)):
                        pm = map_pt([wx, seam_wy])
                        points_geo.append(pm)
                        labels_out.append({"text": f"H{r_num - 1}-C{c_num}{suffix}", "pos": [round(pm[0] + 10.0, 2), round(pm[1] - 8.0, 2)]})
                labels_out.append({
                    "text": f"MOSAICO {active_tile['number']}/{active_tile['total']} [{active_tile['code']}]",
                    "pos": [round(px0 + 18.0, 2), round(py0 + 26.0, 2)],
                })
        else:
            clip_rect = (
                (proj_win["x0"], proj_win["y0"], proj_win["x1"], proj_win["y1"])
                if mosaic_cfg.clip_to_board_in_single
                else None
            )
            for pl in world_polylines:
                segs = clip_polyline_to_rect(pl["points"], *clip_rect) if clip_rect is not None else [pl["points"]]
                for seg in segs:
                    rounded = [[round(p[0], 2), round(p[1], 2)] for p in seg]
                    if pl["role"] == "mill":
                        mill_geo.append(rounded)
                    else:
                        cut_geo.append(rounded)
            for pt in world_points:
                if clip_rect is None or point_in_rect(pt["pos"][0], pt["pos"][1], *clip_rect):
                    points_geo.append([round(pt["pos"][0], 2), round(pt["pos"][1], 2)])
            for lb in world_labels:
                if clip_rect is None or point_in_rect(lb["pos"][0], lb["pos"][1], *clip_rect):
                    labels_out.append({"text": lb["text"], "pos": [round(lb["pos"][0], 2), round(lb["pos"][1], 2)]})

        raster_transform = None
        if design.has_raster:
            raster_transform = {
                "center_x_mm": round(transform.offset_x_mm + scaled_w * 0.5 + shift_x, 3),
                "center_y_mm": round(transform.offset_y_mm + scaled_h * 0.5 + shift_y, 3),
                "width_mm": round(scaled_w, 3),
                "height_mm": round(scaled_h, 3),
                "rotation_deg": round(transform.rotation_deg, 3),
                "flip_x": bool(transform.flip_x),
                "flip_y": bool(transform.flip_y),
                "clip_window": (
                    proj_win
                    if (mosaic_cfg.mode == "mosaic" or mosaic_cfg.clip_to_board_in_single)
                    else None
                ),
                "clip_polygons_mm": clip_polygons_mm if mosaic_cfg.mode == "progressive" else None,
                "exclude_polygons_mm": prior_polys_world if mosaic_cfg.mode == "progressive" else None,
            }

        parts_summary = extract_polyline_parts(
            design=design,
            transform=transform,
            prepared_ids=prepared_part_ids,
        )

        return {
            "projection_window": proj_win,
            "design_bounds": {
                "min_x": round(d_min_x, 2),
                "min_y": round(d_min_y, 2),
                "max_x": round(d_max_x, 2),
                "max_y": round(d_max_y, 2),
                "width_mm": round(design_w_bbox, 2),
                "height_mm": round(design_h_bbox, 2),
            },
            "design_corners": corners,
            "effective_scale": round(s, 6),
            "scaled_width_mm": round(scaled_w, 2),
            "scaled_height_mm": round(scaled_h, 2),
            "exceeds_window": exceeds_window,
            "suggested_grid": {"rows": sugg_rows, "cols": sugg_cols, "total": sugg_rows * sugg_cols},
            "world_design": {
                "polylines": world_polylines,
                "points": world_points,
                "labels": world_labels,
            },
            "tiles": tiles,
            "active_tile": active_tile,
            "parts": parts_summary,
            "progressive": {
                "completed_count": len(completed_regions),
                "active_board_number": reviewing_region_index if reviewing_region_index is not None else active_board_num,
                "coverage_pct": coverage_pct,
                "reviewing_index": reviewing_region_index,
                "completed_regions_world": completed_regions_world,
                "inherited_fiducials": inherited_fiducials,
                "new_fiducials": new_fiducials,
                "joint_cut_lines": joint_cut_lines,
                "overlap_trim_polygons": overlap_trim_polygons,
                "material_stats": material_stats,
            },
            "projection_geometry": {
                "cut_geo": cut_geo,
                "mill_geo": mill_geo,
                "points_geo": points_geo,
                "labels": labels_out,
                "tile_border": tile_border,
                "seam_lines": seam_lines,
                "joint_cut_lines": joint_cut_lines,
                "overlap_trim_polygons": overlap_trim_polygons,
                "raster_transform": raster_transform,
                "clip_polygons_mm": clip_polygons_mm,
                "shift_x_mm": round(shift_x, 3),
                "shift_y_mm": round(shift_y, 3),
            },
        }
