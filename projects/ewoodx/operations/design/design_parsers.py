"""
Design file parsers for eWoodX Design Projection middleware.

Supported formats:
- DXF: Exact CAD vector geometry with LOCKED 1:1 physical scale (only unit
  declaration mm/cm/m/in when unspecified in header; no arbitrary rescaling).
- PDF: Vector paths + high-resolution raster via PyMuPDF (fitz), with
  user-adjustable physical scale.
- Raster images (PNG, JPG, BMP, WEBP, TIF): User-adjustable physical scale,
  plus optional OpenCV contour vectorization for eWoodX projector streaming.
"""

from __future__ import annotations

import io
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import ezdxf
from ezdxf import path as ezdxf_path
import fitz
import numpy as np
from PIL import Image


# DXF $INSUNITS mapping -> (unit_name, factor_to_mm)
DXF_INSUNITS_MAP: dict[int, tuple[str, float]] = {
    0: ("mm", 1.0),       # Unitless -> default to eWoodX standard mm
    1: ("in", 25.4),
    2: ("ft", 304.8),
    4: ("mm", 1.0),
    5: ("cm", 10.0),
    6: ("m", 1000.0),
}

UNIT_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}

PT_TO_MM = 25.4 / 72.0

# AutoCAD ACI color index palette (most common colors)
ACI_PALETTE: dict[int, str] = {
    1: "#FF3B30",  # Red
    2: "#FFD60A",  # Yellow
    3: "#30D158",  # Green
    4: "#00DCFF",  # Cyan
    5: "#0A84FF",  # Blue
    6: "#FF2D92",  # Magenta
    7: "#FFFFFF",  # White
    8: "#9E9E9E",  # Dark gray
    9: "#C7C7CC",  # Light gray
    30: "#FF9F0A", # Orange
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


@dataclass
class ParsedDesign:
    """Normalized 2D design representation in millimeter base coordinates."""

    design_id: str
    filename: str
    file_format: str  # "dxf", "pdf", "image"
    scale_locked: bool
    needs_scale_prompt: bool
    source_units: str
    unit_to_mm: float
    base_width_mm: float
    base_height_mm: float
    layers: list[dict[str, Any]] = field(default_factory=list)
    polylines: list[dict[str, Any]] = field(default_factory=list)
    points: list[dict[str, Any]] = field(default_factory=list)
    labels: list[dict[str, Any]] = field(default_factory=list)
    has_raster: bool = False
    raster_width_px: int = 0
    raster_height_px: int = 0
    raster_png_bytes: bytes | None = None
    raw_bytes: bytes | None = None
    pdf_page_count: int = 0
    pdf_page_index: int = 0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary_dict(self) -> dict[str, Any]:
        """Lightweight metadata + layers summary without full polyline dump."""
        return {
            "design_id": self.design_id,
            "filename": self.filename,
            "file_format": self.file_format,
            "scale_locked": self.scale_locked,
            "needs_scale_prompt": self.needs_scale_prompt,
            "source_units": self.source_units,
            "unit_to_mm": self.unit_to_mm,
            "base_width_mm": round(self.base_width_mm, 3),
            "base_height_mm": round(self.base_height_mm, 3),
            "layers": self.layers,
            "polyline_count": len(self.polylines),
            "point_count": len(self.points),
            "label_count": len(self.labels),
            "has_raster": self.has_raster,
            "raster_width_px": self.raster_width_px,
            "raster_height_px": self.raster_height_px,
            "pdf_page_count": self.pdf_page_count,
            "pdf_page_index": self.pdf_page_index,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

    def to_full_dict(self) -> dict[str, Any]:
        """Full JSON-serializable geometry representation (excludes raw bytes)."""
        data = self.to_summary_dict()
        data["polylines"] = self.polylines
        data["points"] = self.points
        data["labels"] = self.labels
        return data


def _classify_layer_role(layer_name: str) -> tuple[str, str]:
    """Infer default eWoodX geometry role and color from layer name."""
    lower = layer_name.lower()
    if any(k in lower for k in ("mill", "pocket", "engrave", "fres", "grab", "rabbet", "dado")):
        return "mill", "#00DCFF"
    if any(k in lower for k in ("drill", "point", "hole", "taladr", "pin", "dowel")):
        return "points", "#30D158"
    if any(k in lower for k in ("ref", "guide", "grid", "dim", "cota", "aux", "text")):
        return "reference", "#FFD60A"
    return "cut", "#FF453A"


def _aci_to_hex(aci: int | None, fallback: str) -> str:
    if aci is None or aci in (0, 256):
        return fallback
    if aci in ACI_PALETTE:
        return ACI_PALETTE[aci]
    try:
        r, g, b = ezdxf.colors.aci2rgb(aci)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return fallback


def _extract_dxf_entity(
    entity: Any,
    doc: Any,
    unit_scale: float,
    out_polylines: list[dict[str, Any]],
    out_points: list[dict[str, Any]],
    out_labels: list[dict[str, Any]],
    depth: int = 0,
) -> None:
    """Recursively extract 2D polylines, points, and labels from a DXF entity."""
    if depth > 6:
        return

    dxftype = entity.dxftype()
    layer_name = str(getattr(entity.dxf, "layer", "0") or "0")
    role, default_color = _classify_layer_role(layer_name)

    # Resolve color from entity or layer
    color = default_color
    try:
        aci = int(getattr(entity.dxf, "color", 256))
        if aci == 256 and doc.layers.has_entry(layer_name):
            aci = int(doc.layers.get(layer_name).dxf.color)
        color = _aci_to_hex(aci, default_color)
    except Exception:
        pass

    if dxftype == "INSERT":
        try:
            for virtual in entity.virtual_entities():
                _extract_dxf_entity(
                    virtual,
                    doc,
                    unit_scale,
                    out_polylines,
                    out_points,
                    out_labels,
                    depth=depth + 1,
                )
        except Exception:
            pass
        return

    if dxftype == "POINT":
        loc = entity.dxf.location
        out_points.append({
            "pos": [float(loc.x) * unit_scale, float(loc.y) * unit_scale],
            "layer": layer_name,
            "color": color,
        })
        return

    if dxftype in ("TEXT", "MTEXT"):
        try:
            text = (
                entity.plain_text()
                if dxftype == "MTEXT"
                else str(getattr(entity.dxf, "text", ""))
            ).strip()
            insert = entity.dxf.insert
            if text:
                out_labels.append({
                    "text": text[:80],
                    "pos": [float(insert.x) * unit_scale, float(insert.y) * unit_scale],
                    "layer": layer_name,
                    "color": color,
                })
        except Exception:
            pass
        return

    if dxftype == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        pts = [
            [float(start.x) * unit_scale, float(start.y) * unit_scale],
            [float(end.x) * unit_scale, float(end.y) * unit_scale],
        ]
        out_polylines.append({
            "points": pts,
            "closed": False,
            "layer": layer_name,
            "role": role,
            "color": color,
        })
        return

    if dxftype in ("LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"):
        try:
            # Chord tolerance in source drawing units (~0.5 mm)
            chord_tol = max(0.05, 0.5 / max(unit_scale, 1e-6))
            p = ezdxf_path.make_path(entity)
            vertices = list(p.flattening(distance=chord_tol))
            if len(vertices) >= 2:
                pts = [
                    [float(v.x) * unit_scale, float(v.y) * unit_scale]
                    for v in vertices
                ]
                is_closed = bool(
                    dxftype == "CIRCLE"
                    or getattr(entity, "closed", False)
                    or getattr(entity, "is_closed", False)
                )
                if is_closed and len(pts) >= 3:
                    dx = pts[0][0] - pts[-1][0]
                    dy = pts[0][1] - pts[-1][1]
                    if math.hypot(dx, dy) > 1e-3:
                        pts.append(pts[0][:])
                out_polylines.append({
                    "points": pts,
                    "closed": is_closed,
                    "layer": layer_name,
                    "role": role,
                    "color": color,
                })
        except Exception:
            # Fallback for simple CIRCLE if path conversion fails
            if dxftype == "CIRCLE":
                cx = float(entity.dxf.center.x) * unit_scale
                cy = float(entity.dxf.center.y) * unit_scale
                r = float(entity.dxf.radius) * unit_scale
                if r > 0:
                    steps = 64
                    pts = [
                        [
                            cx + r * math.cos(2.0 * math.pi * i / steps),
                            cy + r * math.sin(2.0 * math.pi * i / steps),
                        ]
                        for i in range(steps + 1)
                    ]
                    out_polylines.append({
                        "points": pts,
                        "closed": True,
                        "layer": layer_name,
                        "role": role,
                        "color": color,
                    })


def parse_dxf_bytes(
    raw_bytes: bytes,
    filename: str,
    unit_override: str | None = None,
) -> ParsedDesign:
    """
    Parse a DXF file at exact 1:1 physical scale.

    DXF files ALWAYS have scale_locked=True. Only the source drawing unit
    (mm, cm, m, in, ft) can be declared if the CAD file was exported unitless.
    """
    warnings: list[str] = []

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1", errors="replace")

    doc = ezdxf.read(io.StringIO(text))
    insunits = int(doc.header.get("$INSUNITS", 0))
    detected_unit, detected_factor = DXF_INSUNITS_MAP.get(insunits, ("mm", 1.0))

    if unit_override and unit_override in UNIT_TO_MM:
        source_unit = unit_override
        unit_scale = UNIT_TO_MM[unit_override]
    else:
        source_unit = detected_unit
        unit_scale = detected_factor
        if insunits == 0:
            warnings.append(
                "El DXF no declara unidades ($INSUNITS=0). Se asumen milímetros (mm); "
                "puedes cambiar la unidad de origen si el CAD estaba en cm o m."
            )

    msp = doc.modelspace()
    raw_polylines: list[dict[str, Any]] = []
    raw_points: list[dict[str, Any]] = []
    raw_labels: list[dict[str, Any]] = []

    for entity in msp:
        _extract_dxf_entity(
            entity,
            doc,
            unit_scale,
            raw_polylines,
            raw_points,
            raw_labels,
        )

    # Compute bounding box in CAD coordinates (Y-up)
    all_x: list[float] = []
    all_y: list[float] = []
    for pl in raw_polylines:
        for pt in pl["points"]:
            all_x.append(pt[0])
            all_y.append(pt[1])
    for pt in raw_points:
        all_x.append(pt["pos"][0])
        all_y.append(pt["pos"][1])
    for lb in raw_labels:
        all_x.append(lb["pos"][0])
        all_y.append(lb["pos"][1])

    if not all_x:
        raise ValueError("El archivo DXF no contiene geometría 2D reconocible.")

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    width_mm = max(1.0, max_x - min_x)
    height_mm = max(1.0, max_y - min_y)

    # Normalize to top-left (0, 0) with +Y downward (eWoodX workspace convention)
    # CAD +Y is upward, so y_workspace = max_y - y_cad keeps drawing right-side up.
    polylines: list[dict[str, Any]] = []
    layer_counts: dict[str, dict[str, Any]] = {}

    for pl in raw_polylines:
        norm_pts = [
            [round(pt[0] - min_x, 3), round(max_y - pt[1], 3)]
            for pt in pl["points"]
        ]
        polylines.append({
            "points": norm_pts,
            "closed": pl["closed"],
            "layer": pl["layer"],
            "role": pl["role"],
            "color": pl["color"],
        })
        entry = layer_counts.setdefault(
            pl["layer"],
            {
                "name": pl["layer"],
                "role": pl["role"],
                "color": pl["color"],
                "visible": True,
                "entity_count": 0,
            },
        )
        entry["entity_count"] += 1

    points: list[dict[str, Any]] = []
    for pt in raw_points:
        points.append({
            "pos": [round(pt["pos"][0] - min_x, 3), round(max_y - pt["pos"][1], 3)],
            "layer": pt["layer"],
            "color": pt["color"],
        })
        entry = layer_counts.setdefault(
            pt["layer"],
            {
                "name": pt["layer"],
                "role": "points",
                "color": pt["color"],
                "visible": True,
                "entity_count": 0,
            },
        )
        entry["entity_count"] += 1

    labels: list[dict[str, Any]] = []
    for lb in raw_labels:
        labels.append({
            "text": lb["text"],
            "pos": [round(lb["pos"][0] - min_x, 3), round(max_y - lb["pos"][1], 3)],
            "layer": lb["layer"],
            "color": lb["color"],
        })
        entry = layer_counts.setdefault(
            lb["layer"],
            {
                "name": lb["layer"],
                "role": "reference",
                "color": lb["color"],
                "visible": True,
                "entity_count": 0,
            },
        )
        entry["entity_count"] += 1

    return ParsedDesign(
        design_id=str(uuid.uuid4())[:8],
        filename=filename,
        file_format="dxf",
        scale_locked=True,
        needs_scale_prompt=False,
        source_units=source_unit,
        unit_to_mm=unit_scale,
        base_width_mm=width_mm,
        base_height_mm=height_mm,
        layers=list(layer_counts.values()),
        polylines=polylines,
        points=points,
        labels=labels,
        has_raster=False,
        raw_bytes=raw_bytes,
        warnings=warnings,
        metadata={
            "dxf_version": doc.dxfversion,
            "insunits": insunits,
            "cad_bbox_mm": [round(min_x, 2), round(min_y, 2), round(max_x, 2), round(max_y, 2)],
        },
    )


def _sample_cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 16,
) -> list[list[float]]:
    pts: list[list[float]] = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = (
            mt ** 3 * p0[0]
            + 3 * mt ** 2 * t * p1[0]
            + 3 * mt * t ** 2 * p2[0]
            + t ** 3 * p3[0]
        )
        y = (
            mt ** 3 * p0[1]
            + 3 * mt ** 2 * t * p1[1]
            + 3 * mt * t ** 2 * p2[1]
            + t ** 3 * p3[1]
        )
        pts.append([round(x, 3), round(y, 3)])
    return pts


def parse_pdf_bytes(
    raw_bytes: bytes,
    filename: str,
    page_index: int = 0,
) -> ParsedDesign:
    """
    Parse a PDF page into both vector paths (when present) and raster PNG.

    PDF designs allow user-defined scaling (scale_locked=False) and trigger
    the scale prompt on import.
    """
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    try:
        page_count = len(doc)
        if page_count == 0:
            raise ValueError("El PDF no contiene páginas.")

        idx = max(0, min(int(page_index), page_count - 1))
        page = doc[idx]
        rect = page.rect
        base_width_mm = max(1.0, float(rect.width) * PT_TO_MM)
        base_height_mm = max(1.0, float(rect.height) * PT_TO_MM)

        # Extract vector drawings
        polylines: list[dict[str, Any]] = []
        drawings = page.get_drawings()
        for d in drawings:
            stroke = d.get("color")
            if stroke and len(stroke) >= 3:
                r, g, b = [int(max(0, min(255, round(c * 255)))) for c in stroke[:3]]
                # If stroke is nearly black (typical print PDF), show bright white/red for projection
                color = "#FF453A" if (r < 40 and g < 40 and b < 40) else f"#{r:02X}{g:02X}{b:02X}"
            else:
                color = "#FF453A"

            current_pts: list[list[float]] = []

            def flush_current(closed: bool = False) -> None:
                nonlocal current_pts
                if len(current_pts) >= 2:
                    polylines.append({
                        "points": current_pts,
                        "closed": closed,
                        "layer": "PDF_Vectors",
                        "role": "cut",
                        "color": color,
                    })
                current_pts = []

            for item in d.get("items", []):
                kind = item[0]
                if kind == "l":
                    p1 = [round(item[1].x * PT_TO_MM, 3), round(item[1].y * PT_TO_MM, 3)]
                    p2 = [round(item[2].x * PT_TO_MM, 3), round(item[2].y * PT_TO_MM, 3)]
                    if current_pts and math.hypot(current_pts[-1][0] - p1[0], current_pts[-1][1] - p1[1]) < 0.2:
                        current_pts.append(p2)
                    else:
                        flush_current(False)
                        current_pts = [p1, p2]
                elif kind == "c":
                    pts = _sample_cubic_bezier(
                        (item[1].x * PT_TO_MM, item[1].y * PT_TO_MM),
                        (item[2].x * PT_TO_MM, item[2].y * PT_TO_MM),
                        (item[3].x * PT_TO_MM, item[3].y * PT_TO_MM),
                        (item[4].x * PT_TO_MM, item[4].y * PT_TO_MM),
                    )
                    if current_pts and math.hypot(current_pts[-1][0] - pts[0][0], current_pts[-1][1] - pts[0][1]) < 0.2:
                        current_pts.extend(pts[1:])
                    else:
                        flush_current(False)
                        current_pts = pts
                elif kind == "re":
                    flush_current(False)
                    r_box = item[1]
                    x0, y0 = round(r_box.x0 * PT_TO_MM, 3), round(r_box.y0 * PT_TO_MM, 3)
                    x1, y1 = round(r_box.x1 * PT_TO_MM, 3), round(r_box.y1 * PT_TO_MM, 3)
                    # Skip full-page background white fill rectangle
                    if abs((x1 - x0) - base_width_mm) < 1.0 and abs((y1 - y0) - base_height_mm) < 1.0 and not stroke:
                        continue
                    polylines.append({
                        "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]],
                        "closed": True,
                        "layer": "PDF_Vectors",
                        "role": "cut",
                        "color": color,
                    })
                elif kind == "qu":
                    flush_current(False)
                    q = item[1]
                    qpts = [
                        [round(q.ul.x * PT_TO_MM, 3), round(q.ul.y * PT_TO_MM, 3)],
                        [round(q.ur.x * PT_TO_MM, 3), round(q.ur.y * PT_TO_MM, 3)],
                        [round(q.lr.x * PT_TO_MM, 3), round(q.lr.y * PT_TO_MM, 3)],
                        [round(q.ll.x * PT_TO_MM, 3), round(q.ll.y * PT_TO_MM, 3)],
                    ]
                    qpts.append(qpts[0][:])
                    polylines.append({
                        "points": qpts,
                        "closed": True,
                        "layer": "PDF_Vectors",
                        "role": "cut",
                        "color": color,
                    })
            flush_current(bool(d.get("closePath", False)))

        # Render raster PNG capped at 2600px on longest side for fast responsiveness
        max_dim_pt = max(float(rect.width), float(rect.height), 1.0)
        zoom = min(200.0 / 72.0, 2600.0 / max_dim_pt)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        raster_png = pix.tobytes("png")

        layers = []
        if polylines:
            layers.append({
                "name": "PDF_Vectors",
                "role": "cut",
                "color": "#FF453A",
                "visible": True,
                "entity_count": len(polylines),
            })

        warnings: list[str] = []
        if not polylines:
            warnings.append(
                "El PDF no contiene trazados vectoriales (parece escaneado/imagen). "
                "Se proyectará como imagen y puedes vectorizar contornos si usas eWoodX Stream."
            )

        return ParsedDesign(
            design_id=str(uuid.uuid4())[:8],
            filename=filename,
            file_format="pdf",
            scale_locked=False,
            needs_scale_prompt=True,
            source_units="mm",
            unit_to_mm=1.0,
            base_width_mm=base_width_mm,
            base_height_mm=base_height_mm,
            layers=layers,
            polylines=polylines,
            has_raster=True,
            raster_width_px=pix.width,
            raster_height_px=pix.height,
            raster_png_bytes=raster_png,
            raw_bytes=raw_bytes,
            pdf_page_count=page_count,
            pdf_page_index=idx,
            warnings=warnings,
            metadata={
                "page_size_mm": [round(base_width_mm, 2), round(base_height_mm, 2)],
                "has_vectors": len(polylines) > 0,
            },
        )
    finally:
        doc.close()


def parse_image_bytes(
    raw_bytes: bytes,
    filename: str,
) -> ParsedDesign:
    """
    Parse a raster image (PNG, JPG, BMP, WEBP, TIF).

    Images allow user-defined physical scaling (scale_locked=False) and prompt
    for exact target dimensions/scale immediately on import.
    """
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img = img.convert("RGBA")
        w_px, h_px = img.size
        if w_px <= 0 or h_px <= 0:
            raise ValueError("La imagen no tiene dimensiones válidas.")

        # Try embedded DPI, fallback to 96 DPI
        dpi_info = img.info.get("dpi")
        dpi = 96.0
        if isinstance(dpi_info, (tuple, list)) and len(dpi_info) >= 1:
            try:
                candidate = float(dpi_info[0])
                if 20.0 <= candidate <= 2400.0:
                    dpi = candidate
            except (TypeError, ValueError):
                pass

        base_width_mm = (w_px / dpi) * 25.4
        base_height_mm = (h_px / dpi) * 25.4

        # Cap stored PNG at max 2600px on longest side for snappy projection
        max_side = max(w_px, h_px)
        if max_side > 2600:
            ratio = 2600.0 / max_side
            img = img.resize((int(w_px * ratio), int(h_px * ratio)), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

    return ParsedDesign(
        design_id=str(uuid.uuid4())[:8],
        filename=filename,
        file_format="image",
        scale_locked=False,
        needs_scale_prompt=True,
        source_units="px",
        unit_to_mm=25.4 / dpi,
        base_width_mm=base_width_mm,
        base_height_mm=base_height_mm,
        layers=[],
        polylines=[],
        has_raster=True,
        raster_width_px=w_px,
        raster_height_px=h_px,
        raster_png_bytes=png_bytes,
        raw_bytes=raw_bytes,
        warnings=[
            "Imagen cargada. Define el ancho o alto físico real (en mm) para proyectar a escala exacta."
        ],
        metadata={
            "original_size_px": [w_px, h_px],
            "detected_dpi": round(dpi, 1),
        },
    )


def vectorize_raster_contours(
    png_bytes: bytes,
    base_width_mm: float,
    base_height_mm: float,
    threshold: int = 160,
    invert: bool = True,
    simplify_mm: float = 1.2,
    min_contour_points: int = 4,
) -> list[dict[str, Any]]:
    """
    Extract vector polylines from a raster PNG using OpenCV contour tracing.

    Useful when projecting a raster image or scanned PDF through the
    vector-based eWoodXProjectorComposer stream.
    """
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen para vectorizar.")

    h_px, w_px = img.shape[:2]
    thresh_mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(img, int(threshold), 255, thresh_mode)

    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    scale_x = base_width_mm / max(float(w_px), 1.0)
    scale_y = base_height_mm / max(float(h_px), 1.0)
    epsilon_px = max(1.0, float(simplify_mm) / max(min(scale_x, scale_y), 1e-6))

    polylines: list[dict[str, Any]] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 25.0:
            continue
        approx = cv2.approxPolyDP(cnt, epsilon_px, closed=True)
        if len(approx) < min_contour_points:
            continue
        pts = [
            [round(float(p[0][0]) * scale_x, 2), round(float(p[0][1]) * scale_y, 2)]
            for p in approx
        ]
        # Ignore outer border frame artifact
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs)) > base_width_mm * 0.98 and (max(ys) - min(ys)) > base_height_mm * 0.98:
            continue
        pts.append(pts[0][:])
        polylines.append({
            "points": pts,
            "closed": True,
            "layer": "Vectorized_Contours",
            "role": "cut",
            "color": "#00DCFF",
        })

    # Sort largest contours first and cap to keep streaming crisp
    polylines.sort(key=lambda pl: len(pl["points"]), reverse=True)
    return polylines[:600]


def parse_design_file(
    raw_bytes: bytes,
    filename: str,
    unit_override: str | None = None,
    pdf_page_index: int = 0,
) -> ParsedDesign:
    """Dispatch design parsing based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".dxf":
        return parse_dxf_bytes(raw_bytes, filename, unit_override=unit_override)
    if ext == ".pdf":
        return parse_pdf_bytes(raw_bytes, filename, page_index=pdf_page_index)
    if ext in IMAGE_EXTENSIONS:
        return parse_image_bytes(raw_bytes, filename)
    raise ValueError(
        f"Formato no soportado: '{ext}'. Usa DXF (escala 1:1 fija), PDF o imagen (PNG, JPG, BMP, WEBP)."
    )
