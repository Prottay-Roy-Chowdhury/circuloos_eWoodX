"""
Built-in test scenarios and sample CAD/PDF generators for offline evaluation.

Allows testing the full eWoodX Design-to-Projection workflow (JSON board input,
1:1 DXF placement, PDF scaling, and multi-tile poster mosaic) without needing
the physical camera, stream host, or ceiling projector connected.
"""

from __future__ import annotations

import io
import math
from typing import Any

import ezdxf
import fitz
from PIL import Image, ImageDraw

from projects.ewoodx.config.sensing import (
    TABLE_HEIGHT_MM,
    TABLE_WIDTH_MM,
)


def _rect_corners(
    center_x: float,
    center_y: float,
    length_mm: float,
    width_mm: float,
    angle_deg: float = 0.0,
) -> list[list[float]]:
    hx = length_mm * 0.5
    hy = width_mm * 0.5
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    local = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    corners = []
    for lx, ly in local:
        wx = center_x + lx * cos_a - ly * sin_a
        wy = center_y + lx * sin_a + ly * cos_a
        corners.append([round(wx, 2), round(wy, 2)])
    return corners


def make_custom_board_measurement(
    length_mm: float = 1200.0,
    width_mm: float = 800.0,
    thickness_mm: float = 22.0,
    angle_deg: float = 0.0,
    center_x_mm: float | None = None,
    center_y_mm: float | None = None,
    timber_id: str = "T-TEST-0001",
    defects: list[dict[str, Any]] | None = None,
    holes_mm: list[list[list[float]]] | None = None,
) -> dict[str, Any]:
    """Generate a valid eWoodX timber measurement JSON dictionary."""
    length_mm = max(100.0, float(length_mm))
    width_mm = max(100.0, float(width_mm))
    thickness_mm = max(0.0, float(thickness_mm))

    cx = TABLE_WIDTH_MM * 0.5 if center_x_mm is None else float(center_x_mm)
    cy = TABLE_HEIGHT_MM * 0.5 if center_y_mm is None else float(center_y_mm)

    corners = _rect_corners(cx, cy, length_mm, width_mm, angle_deg)
    gross_area = round(length_mm * width_mm, 2)

    return {
        "timber_id": timber_id,
        "source_image": "simulated_test_scenario.jpg",
        "reference_frame": {
            "origin_marker_id": 1,
            "origin_mm": [0.0, 0.0, 0.0],
            "x_axis": [1.0, 0.0, 0.0],
            "y_axis": [0.0, 1.0, 0.0],
            "z_axis": [0.0, 0.0, 1.0],
            "description": "Origin at Marker 1 outer corner; +X towards Marker 0; +Y towards Marker 2.",
        },
        "length_mm": round(max(length_mm, width_mm), 2),
        "width_mm": round(min(length_mm, width_mm), 2),
        "gross_surface_area_mm2": gross_area,
        "total_hole_area_mm2": 0.0,
        "surface_area_mm2": gross_area,
        "surface_area_cm2": round(gross_area / 100.0, 2),
        "side_lengths_mm": [
            round(length_mm, 2),
            round(width_mm, 2),
            round(length_mm, 2),
            round(width_mm, 2),
        ],
        "corners_mm": corners,
        "contour_mm": corners,
        "holes_mm": holes_mm or [],
        "inner_contours_mm": holes_mm or [],
        "hole_count": len(holes_mm or []),
        "timber_thickness_mm": round(thickness_mm, 1),
        "thickness_mm": round(thickness_mm, 1),
        "thickness_source": "test_scenario",
        "color_rgb": [194, 154, 108],
        "color_hex": "#C29A6C",
        "defects": defects if defects is not None else [],
        "hand_drawn_shapes": [],
        "hand_drawn_shape_count": 0,
    }


def get_builtin_board_scenarios() -> dict[str, dict[str, Any]]:
    """Return dictionary of ready-to-use eWoodX test board scenarios."""
    b1 = make_custom_board_measurement(
        length_mm=1200.0,
        width_mm=800.0,
        thickness_mm=22.0,
        angle_deg=0.0,
        timber_id="T-TEST-1200x800",
        defects=[{"x_mm": 640.0, "y_mm": 410.0, "label": "Nudo"}],
    )

    # 1100 x 800 slightly angled with a knot hole
    hole_cx, hole_cy = 1040.0, 560.0
    hole_poly = [
        [round(hole_cx + 35.0 * math.cos(2 * math.pi * i / 16), 2),
         round(hole_cy + 25.0 * math.sin(2 * math.pi * i / 16), 2)]
        for i in range(16)
    ]
    b2 = make_custom_board_measurement(
        length_mm=1100.0,
        width_mm=800.0,
        thickness_mm=28.0,
        angle_deg=5.5,
        timber_id="T-TEST-1100x800",
        defects=[
            {"x_mm": 720.0, "y_mm": 430.0, "label": "Nudo 1"},
            {"x_mm": 1180.0, "y_mm": 660.0, "label": "Grieta"},
        ],
        holes_mm=[hole_poly],
    )

    b3 = make_custom_board_measurement(
        length_mm=1600.0,
        width_mm=560.0,
        thickness_mm=35.0,
        angle_deg=0.0,
        timber_id="T-TEST-PLANK-1600",
        defects=[{"x_mm": 1350.0, "y_mm": 520.0, "label": "Defecto"}],
    )

    b4_scrap = make_custom_board_measurement(
        length_mm=920.0,
        width_mm=660.0,
        thickness_mm=24.0,
        angle_deg=-3.5,
        timber_id="T-TEST-920x660",
        defects=[{"x_mm": 980.0, "y_mm": 470.0, "label": "Nudo"}],
    )

    # Multi-timber eWoodX capture format
    t_left = make_custom_board_measurement(
        length_mm=720.0,
        width_mm=780.0,
        thickness_mm=20.0,
        angle_deg=0.0,
        center_x_mm=490.0,
        center_y_mm=520.0,
        timber_id="T-MULTI-01",
    )
    t_right = make_custom_board_measurement(
        length_mm=720.0,
        width_mm=780.0,
        thickness_mm=20.0,
        angle_deg=-2.0,
        center_x_mm=1290.0,
        center_y_mm=520.0,
        timber_id="T-MULTI-02",
    )
    b4_multi = {
        "source": "simulated_multi_timber.json",
        "timber_id": "MULTI-CAPTURE-01",
        "timber_thickness_mm": 20.0,
        "thickness_mm": 20.0,
        "timbers": [t_left, t_right],
    }

    return {
        "board_1200x800": {
            "id": "board_1200x800",
            "name": "Tabla estándar 1,20 × 0,80 m (22 mm)",
            "description": "Tablero rectangular centrado en mesa eWoodX (1780×1040 mm) con 1 defecto.",
            "measurement": b1,
        },
        "board_1100x800_angled": {
            "id": "board_1100x800_angled",
            "name": "Tabla 1,10 × 0,80 m inclinada 5.5° (28 mm)",
            "description": "Tabla con ligera rotación, un agujero interno y dos nudos.",
            "measurement": b2,
        },
        "board_1600x560_plank": {
            "id": "board_1600x560_plank",
            "name": "Tablón largo 1,60 × 0,56 m (35 mm)",
            "description": "Tablón recuperado largo para probar encajes longitudinales.",
            "measurement": b3,
        },
        "board_920x660_scrap": {
            "id": "board_920x660_scrap",
            "name": "Tabla corta 0,92 × 0,66 m (-3.5°)",
            "description": "Tabla recuperada de formato menor para probar nesting progresivo heterogéneo.",
            "measurement": b4_scrap,
        },
        "multi_timber_pair": {
            "id": "multi_timber_pair",
            "name": "Doble tabla (formato multi-timber eWoodX)",
            "description": "Dos tablas detectadas simultáneamente en formato timbers[].",
            "measurement": b4_multi,
        },
    }


def generate_sample_fitting_dxf() -> bytes:
    """
    Generate a 960 x 620 mm woodworking panel DXF (1:1 mm) that fits inside
    a 1200 x 800 mm board for testing 2D pan and Lock-to-Board.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # Millimeters

    doc.layers.add("CUT", color=1)
    doc.layers.add("MILL_POCKETS", color=4)
    doc.layers.add("DRILL_HOLES", color=3)
    doc.layers.add("LABELS", color=2)

    msp = doc.modelspace()

    # Outer panel profile with chamfered corners (960 x 620 mm)
    c = 45.0
    w, h = 960.0, 620.0
    outer = [
        (c, 0), (w - c, 0), (w, c), (w, h - c),
        (w - c, h), (c, h), (0, h - c), (0, c), (c, 0),
    ]
    msp.add_lwpolyline(outer, close=True, dxfattribs={"layer": "CUT"})

    # Central decorative arch cutout
    msp.add_lwpolyline(
        [(280, 160), (680, 160), (680, 420), (280, 420)],
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    msp.add_circle((480, 290), radius=95.0, dxfattribs={"layer": "CUT"})

    # Milling mortise pockets
    for px in (90.0, 810.0):
        for py in (95.0, 465.0):
            msp.add_lwpolyline(
                [(px, py), (px + 60, py), (px + 60, py + 60), (px, py + 60)],
                close=True,
                dxfattribs={"layer": "MILL_POCKETS"},
            )
    # Center slot pocket
    msp.add_lwpolyline(
        [(180, 515), (780, 515), (780, 545), (180, 545)],
        close=True,
        dxfattribs={"layer": "MILL_POCKETS"},
    )

    # Dowel drill centers
    for dx in (60.0, 480.0, 900.0):
        for dy in (60.0, 560.0):
            msp.add_point((dx, dy), dxfattribs={"layer": "DRILL_HOLES"})
            msp.add_circle((dx, dy), radius=10.0, dxfattribs={"layer": "DRILL_HOLES"})

    msp.add_text("PANEL A-01 (960x620mm)", dxfattribs={"layer": "LABELS", "height": 22}).set_placement((300, 65))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def generate_sample_mosaic_dxf() -> bytes:
    """
    Generate an oversized 2200 x 1300 mm curved furniture template DXF (1:1 mm)
    designed specifically to demonstrate 2x2 poster-style mosaic projection on
    a 1200 x 800 mm board with shared registration marks.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # Millimeters

    doc.layers.add("CUT_OUTLINE", color=1)
    doc.layers.add("MILL_JOINERY", color=4)
    doc.layers.add("DRILL_PINS", color=3)
    doc.layers.add("LABELS", color=2)

    msp = doc.modelspace()

    # Smooth organic tabletop/bench silhouette (2200 x 1300 mm)
    w, h = 2200.0, 1300.0
    outline_pts = []
    steps = 96
    for i in range(steps + 1):
        theta = 2.0 * math.pi * i / steps
        # Superellipse-like rounded table with gentle organic waist
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        rx = 1100.0 * (abs(cos_t) ** 0.72) * (1.0 if cos_t >= 0 else -1.0)
        ry = 650.0 * (abs(sin_t) ** 0.78) * (1.0 if sin_t >= 0 else -1.0)
        waist = 1.0 - 0.08 * math.exp(-((rx / 420.0) ** 2))
        outline_pts.append((1100.0 + rx, 650.0 + ry * waist))
    msp.add_lwpolyline(outline_pts, close=True, dxfattribs={"layer": "CUT_OUTLINE"})

    # Internal structural ribs & decorative circles spanning across all 4 tiles
    for cx, cy, rad in (
        (450, 360, 150),
        (1750, 360, 150),
        (450, 940, 150),
        (1750, 940, 150),
        (1100, 650, 210),
    ):
        msp.add_circle((cx, cy), radius=rad, dxfattribs={"layer": "CUT_OUTLINE"})

    # Longitudinal structural spline crossing vertical seam
    msp.add_spline(
        [
            (220, 650),
            (620, 510),
            (1100, 650),
            (1580, 790),
            (1980, 650),
        ],
        dxfattribs={"layer": "MILL_JOINERY"},
    )
    msp.add_spline(
        [
            (220, 650),
            (620, 790),
            (1100, 650),
            (1580, 510),
            (1980, 650),
        ],
        dxfattribs={"layer": "MILL_JOINERY"},
    )

    # Transverse joinery mortise channels crossing horizontal seam
    for x_mid in (650.0, 1100.0, 1550.0):
        msp.add_lwpolyline(
            [
                (x_mid - 35, 190),
                (x_mid + 35, 190),
                (x_mid + 35, 1110),
                (x_mid - 35, 1110),
            ],
            close=True,
            dxfattribs={"layer": "MILL_JOINERY"},
        )

    # Alignment/dowel drill points distributed across all quadrants
    for px in (260, 820, 1380, 1940):
        for py in (220, 650, 1080):
            msp.add_point((px, py), dxfattribs={"layer": "DRILL_PINS"})
            msp.add_circle((px, py), radius=12.0, dxfattribs={"layer": "DRILL_PINS"})

    # Quadrant labels
    msp.add_text("ZONA INF-IZQ", dxfattribs={"layer": "LABELS", "height": 26}).set_placement((280, 260))
    msp.add_text("ZONA INF-DER", dxfattribs={"layer": "LABELS", "height": 26}).set_placement((1560, 260))
    msp.add_text("ZONA SUP-IZQ", dxfattribs={"layer": "LABELS", "height": 26}).set_placement((280, 1020))
    msp.add_text("ZONA SUP-DER", dxfattribs={"layer": "LABELS", "height": 26}).set_placement((1560, 1020))
    msp.add_text("MESA ORGANICA 2200x1300mm", dxfattribs={"layer": "LABELS", "height": 30}).set_placement((760, 650))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def generate_sample_blueprint_pdf() -> bytes:
    """
    Generate a clean A4 landscape vector PDF (297 x 210 mm, drawn at 1:5 scale)
    for evaluating PDF import + interactive scale selection.
    """
    doc = fitz.open()
    # A4 landscape in points (1 mm = 72 / 25.4 pt)
    mm_to_pt = 72.0 / 25.4
    page = doc.new_page(width=297.0 * mm_to_pt, height=210.0 * mm_to_pt)

    shape = page.new_shape()
    # Outer cut outline (representing 1:5 scale of a ~1350 x 900 mm workpiece)
    shape.draw_rect(fitz.Rect(15 * mm_to_pt, 15 * mm_to_pt, 282 * mm_to_pt, 195 * mm_to_pt))
    shape.draw_circle(fitz.Point(85 * mm_to_pt, 105 * mm_to_pt), 38 * mm_to_pt)
    shape.draw_circle(fitz.Point(212 * mm_to_pt, 105 * mm_to_pt), 38 * mm_to_pt)
    shape.draw_line(
        fitz.Point(85 * mm_to_pt, 67 * mm_to_pt),
        fitz.Point(212 * mm_to_pt, 67 * mm_to_pt),
    )
    shape.draw_line(
        fitz.Point(85 * mm_to_pt, 143 * mm_to_pt),
        fitz.Point(212 * mm_to_pt, 143 * mm_to_pt),
    )
    shape.finish(color=(0.85, 0.1, 0.1), width=1.6)
    shape.commit()

    page.insert_text(
        fitz.Point(25 * mm_to_pt, 30 * mm_to_pt),
        "PLANO PDF DE PRUEBA (ESCALA 1:5 -> APLICAR x5 = 1485x1050 mm)",
        fontsize=11,
        color=(0.1, 0.1, 0.1),
    )
    data = doc.tobytes()
    doc.close()
    return data


def generate_sample_sketch_png() -> bytes:
    """
    Generate a clean high-contrast woodworking stencil PNG (no embedded real scale)
    for testing Image import + user-defined physical scaling + optional vectorization.
    """
    w, h = 1000, 620
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Outer chair/arch silhouette
    draw.rounded_rectangle([60, 50, w - 60, h - 50], radius=55, outline=(18, 18, 18), width=10)
    # Two symmetrical arch cutouts
    draw.rounded_rectangle([140, 130, 440, 490], radius=120, outline=(18, 18, 18), width=8)
    draw.rounded_rectangle([560, 130, 860, 490], radius=120, outline=(18, 18, 18), width=8)
    # Center joinery holes
    for cy in (190, 310, 430):
        draw.ellipse([482, cy - 18, 518, cy + 18], outline=(18, 18, 18), width=7)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_sample_assembly_dxf() -> bytes:
    """
    Generate a 1:1 woodworking timber-frame assembly DXF (1600 x 900 mm)
    consisting of closed polylines for horizontal rails, vertical stiles,
    inner cross-members, and two angled diagonal braces (+/- 32 deg) so the
    Parts / Assembly Material List tab can display exact squared OBB & AABB
    cut dimensions for both square and diagonal members.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # Millimeters
    doc.layers.add("ASSEMBLY_FRAME", color=1)  # Red -> cut/frame
    doc.layers.add("ASSEMBLY_BRACES", color=4)  # Cyan -> diagonals/braces

    msp = doc.modelspace()

    def add_bar(cx: float, cy: float, length: float, width: float, angle_deg: float, layer: str) -> None:
        pts = _rect_corners(cx, cy, length, width, angle_deg)
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})

    # 2 Horizontal top & bottom rails (1600 x 90 mm, 0 deg)
    add_bar(800.0, 45.0, 1600.0, 90.0, 0.0, "ASSEMBLY_FRAME")
    add_bar(800.0, 855.0, 1600.0, 90.0, 0.0, "ASSEMBLY_FRAME")

    # 4 Vertical stiles (720 x 80 mm, 90 deg)
    for sx in (40.0, 560.0, 1040.0, 1560.0):
        add_bar(sx, 450.0, 720.0, 80.0, 90.0, "ASSEMBLY_FRAME")

    # 2 Center horizontal cross-rails (400 x 70 mm, 0 deg)
    add_bar(800.0, 290.0, 400.0, 70.0, 0.0, "ASSEMBLY_FRAME")
    add_bar(800.0, 610.0, 400.0, 70.0, 0.0, "ASSEMBLY_FRAME")

    # 2 Angled diagonal timber braces fitted inside the left & right bays (620 x 65 mm, +38 deg and -38 deg)
    add_bar(300.0, 450.0, 620.0, 65.0, 38.0, "ASSEMBLY_BRACES")
    add_bar(1300.0, 450.0, 620.0, 65.0, -38.0, "ASSEMBLY_BRACES")

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


