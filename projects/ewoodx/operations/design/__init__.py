"""
eWoodX Design-to-Projection Middleware.

Sits between eWoodX sensing measurement JSON (input) and eWoodX calibrated
projection (output), providing:
- 1:1 locked-scale CAD DXF import
- User-scaled PDF (vector + raster) and image import
- Interactive 2D placement and board-locking
- Poster-style mosaic/tiling with shared registration fiducials
- Built-in test scenarios and live eWoodX Stream Host integration
"""

from projects.ewoodx.operations.design.design_parsers import (
    ParsedDesign,
    parse_design_file,
    vectorize_raster_contours,
)
from projects.ewoodx.operations.design.mosaic_engine import (
    DesignTransform,
    MosaicConfig,
    MosaicEngine,
)

__all__ = [
    "ParsedDesign",
    "parse_design_file",
    "vectorize_raster_contours",
    "DesignTransform",
    "MosaicConfig",
    "MosaicEngine",
]
