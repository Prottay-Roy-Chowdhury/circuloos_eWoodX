"""Automated tests for eWoodX Design-to-Projection & Mosaic Middleware."""

from __future__ import annotations

import io
import json
import unittest

import numpy as np
from PIL import Image, ImageDraw

from projects.ewoodx.operations.design.design_parsers import (
    parse_design_file,
    vectorize_raster_contours,
)
from projects.ewoodx.operations.design.ewoodx_bridge import (
    build_ewoodx_projector_payload,
    extract_board_summary,
    normalize_input_board_json,
)
from projects.ewoodx.operations.design.mosaic_engine import (
    DesignTransform,
    MosaicConfig,
    MosaicEngine,
    clip_polyline_to_polygons,
    clip_polyline_to_rect,
    effective_scale,
    point_in_polygon,
    workspace_to_scaled_design,
)
from projects.ewoodx.operations.design.sample_scenarios import (
    generate_sample_blueprint_pdf,
    generate_sample_fitting_dxf,
    generate_sample_mosaic_dxf,
    generate_sample_sketch_png,
    get_builtin_board_scenarios,
)
from projects.ewoodx.operations.design_composer import (
    EWoodXDesignComposer as DesignProjectorSession,
    MosaicUpdateRequest,
    PartToggleRequest,
    RescanBoardRequest,
    TransformUpdateRequest,
)
from projects.ewoodx.operations.projection.projector_geometry import (
    ProjectorGeometry,
)
from projects.ewoodx.operations.projection.projector_renderer import (
    ProjectorRenderer,
)


class TestDesignProjectionMiddleware(unittest.TestCase):

    def test_dxf_import_1to1_and_scale_lock(self) -> None:
        raw = generate_sample_fitting_dxf()
        design = parse_design_file(raw, "panel_960x620.dxf")

        self.assertEqual(design.file_format, "dxf")
        self.assertTrue(design.scale_locked)
        self.assertFalse(design.needs_scale_prompt)
        self.assertAlmostEqual(design.base_width_mm, 960.0, delta=1.0)
        self.assertAlmostEqual(design.base_height_mm, 620.0, delta=1.0)
        self.assertGreater(len(design.polylines), 5)
        self.assertGreater(len(design.points), 0)

        # Verify scale cannot be altered in session for DXF
        session = DesignProjectorSession()
        session.load_design_bytes(raw, "panel_960x620.dxf")
        snap = session.update_transform(TransformUpdateRequest(scale=3.5))
        self.assertAlmostEqual(snap["mosaic"]["effective_scale"], 1.0, places=5)
        self.assertAlmostEqual(snap["mosaic"]["scaled_width_mm"], 960.0, delta=1.0)

    def test_pdf_import_vectors_and_user_scaling(self) -> None:
        raw = generate_sample_blueprint_pdf()
        design = parse_design_file(raw, "plano_1a5.pdf")

        self.assertEqual(design.file_format, "pdf")
        self.assertFalse(design.scale_locked)
        self.assertTrue(design.needs_scale_prompt)
        self.assertTrue(design.has_raster)
        self.assertAlmostEqual(design.base_width_mm, 297.0, delta=1.0)
        self.assertAlmostEqual(design.base_height_mm, 210.0, delta=1.0)
        self.assertGreater(len(design.polylines), 0)

        session = DesignProjectorSession()
        session.load_design_bytes(raw, "plano_1a5.pdf")
        snap = session.update_transform(TransformUpdateRequest(scale=5.0, confirm_scale=True))
        self.assertAlmostEqual(snap["mosaic"]["effective_scale"], 5.0, places=3)
        self.assertAlmostEqual(snap["mosaic"]["scaled_width_mm"], 297.0 * 5.0, delta=3.0)
        self.assertFalse(snap["design"]["needs_scale_prompt"])

    def test_image_import_scaling_and_vectorization(self) -> None:
        img = Image.new("RGB", (400, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 30, 360, 170], outline=(0, 0, 0), width=6)
        draw.ellipse([150, 50, 250, 150], outline=(0, 0, 0), width=6)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        design = parse_design_file(raw, "sketch.png")
        self.assertEqual(design.file_format, "image")
        self.assertFalse(design.scale_locked)
        self.assertTrue(design.needs_scale_prompt)
        self.assertTrue(design.has_raster)

        polys = vectorize_raster_contours(
            design.raster_png_bytes,
            design.base_width_mm,
            design.base_height_mm,
        )
        self.assertGreater(len(polys), 0)

        session = DesignProjectorSession()
        session.load_design_bytes(raw, "sketch.png")
        snap = session.update_transform(TransformUpdateRequest(target_width_mm=1000.0))
        self.assertAlmostEqual(snap["mosaic"]["scaled_width_mm"], 1000.0, delta=1.0)
        self.assertAlmostEqual(snap["mosaic"]["scaled_height_mm"], 500.0, delta=1.0)

    def test_board_json_formats(self) -> None:
        # Simplified meters JSON
        simple = normalize_input_board_json({"width_m": 1.10, "height_m": 0.80, "thickness_mm": 25.0})
        summary = extract_board_summary(simple)
        self.assertAlmostEqual(summary["length_mm"], 1100.0, delta=0.5)
        self.assertAlmostEqual(summary["width_mm"], 800.0, delta=0.5)
        self.assertAlmostEqual(summary["thickness_mm"], 25.0, delta=0.1)

        # Native multi-timber JSON
        scenarios = get_builtin_board_scenarios()
        multi = normalize_input_board_json(scenarios["multi_timber_pair"]["measurement"])
        multi_sum = extract_board_summary(multi)
        self.assertEqual(len(multi_sum["contours_mm"]), 2)

    def test_lock_to_board_prevents_drag_and_follows_board(self) -> None:
        session = DesignProjectorSession(start_with_test_scenario="fit_dxf")
        s1 = session.update_transform(TransformUpdateRequest(offset_x_mm=350.0, offset_y_mm=180.0))
        self.assertAlmostEqual(s1["transform"]["offset_x_mm"], 350.0, delta=0.1)

        # Lock to board
        s2 = session.update_transform(TransformUpdateRequest(locked_to_board=True))
        self.assertTrue(s2["transform"]["locked_to_board"])

        # Attempt to drag -> must stay locked
        s3 = session.update_transform(TransformUpdateRequest(offset_x_mm=700.0, offset_y_mm=500.0))
        self.assertAlmostEqual(s3["transform"]["offset_x_mm"], 350.0, delta=0.1)
        self.assertAlmostEqual(s3["transform"]["offset_y_mm"], 180.0, delta=0.1)

    def test_liang_barsky_clipping(self) -> None:
        poly = [[-50.0, 50.0], [150.0, 50.0]]
        clipped = clip_polyline_to_rect(poly, 0.0, 0.0, 100.0, 100.0)
        self.assertEqual(len(clipped), 1)
        self.assertAlmostEqual(clipped[0][0][0], 0.0, places=3)
        self.assertAlmostEqual(clipped[0][1][0], 100.0, places=3)

    def test_mosaic_2x2_tiling_and_shared_seam_fiducials(self) -> None:
        session = DesignProjectorSession(start_with_test_scenario="mosaic_2x2")
        s_tile0 = session.get_state_snapshot()
        self.assertEqual(s_tile0["mosaic_config"]["mode"], "mosaic")
        tiles = s_tile0["mosaic"]["tiles"]
        self.assertEqual(len(tiles), 4)  # 2x2 grid for 2200x1300 on 1200x800 with 50mm overlap

        # Check all projected cut coordinates lie cleanly within the projection window
        pw = s_tile0["mosaic"]["projection_window"]
        for poly in s_tile0["mosaic"]["projection_geometry"]["cut_geo"]:
            for pt in poly:
                self.assertGreaterEqual(pt[0], pw["x0"] - 0.1)
                self.assertLessEqual(pt[0], pw["x1"] + 0.1)
                self.assertGreaterEqual(pt[1], pw["y0"] - 0.1)
                self.assertLessEqual(pt[1], pw["y1"] + 0.1)

        # Verify Tile 0 (F1C1) right seam and Tile 1 (F1C2) left seam share IDENTICAL world coordinates & labels!
        labels_t0 = {lb["text"] for lb in s_tile0["mosaic"]["projection_geometry"]["labels"]}
        self.assertIn("V1-F1A", labels_t0)
        self.assertIn("V1-F1B", labels_t0)

        shift0_x = s_tile0["mosaic"]["projection_geometry"]["shift_x_mm"]
        shift0_y = s_tile0["mosaic"]["projection_geometry"]["shift_y_mm"]
        seam0 = s_tile0["mosaic"]["projection_geometry"]["seam_lines"][0]
        world_seam0_x = seam0[0][0] - shift0_x

        s_tile1 = session.update_mosaic(MosaicUpdateRequest(active_tile_index=1))
        labels_t1 = {lb["text"] for lb in s_tile1["mosaic"]["projection_geometry"]["labels"]}
        self.assertIn("V1-F1A", labels_t1)
        self.assertIn("V1-F1B", labels_t1)

        shift1_x = s_tile1["mosaic"]["projection_geometry"]["shift_x_mm"]
        seam1 = s_tile1["mosaic"]["projection_geometry"]["seam_lines"][0]
        world_seam1_x = seam1[0][0] - shift1_x
        self.assertAlmostEqual(world_seam0_x, world_seam1_x, delta=0.05)

    def test_compatibility_with_native_ewoodx_projector_renderer(self) -> None:
        session = DesignProjectorSession(start_with_test_scenario="mosaic_2x2")
        payload = session.get_ewoodx_payload()

        # Render with Prottay's actual ProjectorRenderer using identity-like scale homography
        H = np.array([
            [0.65, 0.0, 40.0],
            [0.0, 0.65, 40.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float32)
        geom = ProjectorGeometry(
            homography=H,
            projector_height_mm=2300.0,
            projector_pos_x_mm=920.0,
            projector_pos_y_mm=50.0,
        )
        renderer = ProjectorRenderer(geometry=geom)
        frame = renderer.render(
            data=payload,
            is_connected=True,
            packet_count=1,
            thickness_mm=payload["thickness_mm"],
        )
        self.assertEqual(frame.ndim, 3)
        self.assertEqual(frame.shape[2], 3)
        self.assertGreater(int(np.count_nonzero(frame)), 5000)

    def test_polygon_clipping_rotated_board(self) -> None:
        scenarios = get_builtin_board_scenarios()
        angled = scenarios["board_1100x800_angled"]["measurement"]
        poly = angled["contour_mm"]
        # Long horizontal line cutting across the entire table through the rotated board
        line = [[0.0, 520.0], [1780.0, 520.0]]
        clipped = clip_polyline_to_polygons(line, [poly])
        self.assertEqual(len(clipped), 1)
        # Endpoints must lie on/inside the rotated polygon (strictly narrower than full 1780mm table)
        seg = clipped[0]
        self.assertGreater(seg[0][0], 200.0)
        self.assertLess(seg[-1][0], 1580.0)
        mid_x = 0.5 * (seg[0][0] + seg[-1][0])
        mid_y = 0.5 * (seg[0][1] + seg[-1][1])
        self.assertTrue(point_in_polygon(mid_x, mid_y, poly))

    def test_progressive_heterogeneous_nesting_flow(self) -> None:
        # Starts with Board #1 (1200x800) stamped DONE + Board #2 (1100x800 5.5 deg) auto-nested!
        session = DesignProjectorSession(start_with_test_scenario="progressive_demo")
        s1 = session.get_state_snapshot()
        self.assertEqual(s1["mosaic_config"]["mode"], "progressive")
        prog1 = s1["mosaic"]["progressive"]
        self.assertEqual(prog1["completed_count"], 1)
        self.assertEqual(prog1["active_board_number"], 2)
        cov1 = prog1["coverage_pct"]
        self.assertGreater(cov1, 25.0)
        self.assertEqual(len(prog1["completed_regions_world"]), 1)
        # Active board #2 (1100x800 rotated 5.5 deg) must auto-square to 5.5 deg
        self.assertAlmostEqual(s1["transform"]["rotation_deg"], 5.5, delta=0.5)
        # Must emit exact straight overlap joint cut line against Board #1 AND trim polygon!
        jcuts2 = prog1["joint_cut_lines"]
        self.assertEqual(len(jcuts2), 1)
        self.assertAlmostEqual(jcuts2[0]["length_mm"], 800.0, delta=5.0)
        self.assertEqual(len(prog1["overlap_trim_polygons"]), 1)
        self.assertGreater(prog1["material_stats"]["utilization_pct"], 85.0)
        # Native eWoodX projector payload must also carry the joint cut line!
        payload2 = session.get_ewoodx_payload()
        self.assertEqual(len(payload2["joint_cut_geo"]), 1)
        # Projected geometry must include polygon clip boundaries
        self.assertIsNotNone(s1["mosaic"]["projection_geometry"]["clip_polygons_mm"])

        # Commit Board #2 (1100x800 rotated 5.5 deg) -> coverage jumps cleanly
        s2 = session.step_next()
        prog2 = s2["mosaic"]["progressive"]
        self.assertEqual(prog2["completed_count"], 2)
        self.assertGreater(prog2["coverage_pct"], cov1 + 20.0)

        # Scan Board #3 of a COMPLETELY DIFFERENT shape (1600x560 long plank) -> auto-nests squarely!
        s3 = session.load_board_scenario("board_1600x560_plank")
        self.assertAlmostEqual(s3["board"]["length_mm"], 1600.0, delta=2.0)
        self.assertAlmostEqual(s3["board"]["width_mm"], 560.0, delta=2.0)
        # Board #3 must merge collinear horizontal saw cut across #1 and #2 into ONE 1600mm cut!
        jcuts3 = s3["mosaic"]["progressive"]["joint_cut_lines"]
        self.assertEqual(len(jcuts3), 1)
        self.assertAlmostEqual(jcuts3[0]["length_mm"], 1600.0, delta=5.0)
        s3_done = session.step_next()
        prog3 = s3_done["mosaic"]["progressive"]
        self.assertEqual(prog3["completed_count"], 3)
        self.assertGreater(prog3["coverage_pct"], prog2["coverage_pct"] + 15.0)

        # Scan Board #4 (920x660 -3.5 deg) -> auto-squares to -3.5 deg, produces 2 orthogonal L-cuts -> 100%!
        s4 = session.load_board_scenario("board_920x660_scrap")
        jcuts4 = s4["mosaic"]["progressive"]["joint_cut_lines"]
        self.assertEqual(len(jcuts4), 2)
        s4_done = session.step_next()
        self.assertGreaterEqual(s4_done["mosaic"]["progressive"]["coverage_pct"], 99.0)

        # Back reviews completed Board #4 then Board #3; Next steps forward cleanly
        s_rev4 = session.step_back()
        self.assertEqual(s_rev4["mosaic"]["progressive"]["reviewing_index"], 4)
        s_rev3 = session.step_back()
        self.assertEqual(s_rev3["mosaic"]["progressive"]["reviewing_index"], 3)
        s_fwd4 = session.step_next()
        self.assertEqual(s_fwd4["mosaic"]["progressive"]["reviewing_index"], 4)
        s_live = session.step_next()
        self.assertIsNone(s_live["mosaic"]["progressive"]["reviewing_index"])

        # Undo drops the last stamped region cleanly
        s_undo = session.undo_last_region()
        self.assertEqual(s_undo["mosaic"]["progressive"]["completed_count"], 3)

    def test_sample_sketch_png_and_pdf_1to1_option(self) -> None:
        raw_png = generate_sample_sketch_png()
        session = DesignProjectorSession()
        s_img = session.load_design_bytes(raw_png, "ejemplo_plantilla_imagen.png")
        self.assertEqual(s_img["design"]["file_format"], "image")
        self.assertFalse(s_img["design"]["scale_locked"])
        self.assertTrue(s_img["design"]["needs_scale_prompt"])
        # User scales image by specifying real physical height in mm
        s_img_scaled = session.update_transform(TransformUpdateRequest(target_height_mm=650.0))
        self.assertAlmostEqual(s_img_scaled["mosaic"]["scaled_height_mm"], 650.0, delta=1.5)
        self.assertFalse(s_img_scaled["design"]["needs_scale_prompt"])

        # PDF can be kept at 1:1 real scale OR scaled freely
        raw_pdf = generate_sample_blueprint_pdf()
        s_pdf = session.load_design_bytes(raw_pdf, "plano.pdf")
        self.assertEqual(s_pdf["design"]["file_format"], "pdf")
        s_pdf_1to1 = session.update_transform(TransformUpdateRequest(scale=1.0, confirm_scale=True))
        self.assertAlmostEqual(s_pdf_1to1["mosaic"]["effective_scale"], 1.0, places=4)
        self.assertFalse(s_pdf_1to1["design"]["needs_scale_prompt"])

    def test_assembly_parts_bounding_box_list_and_csv(self) -> None:
        session = DesignProjectorSession()
        snap = session.load_sample_design("assembly_frame_dxf")
        parts = snap["mosaic"]["parts"]

        # Assembly DXF has 10 polylines: 2x 1600x90, 2x 760x65 (+/-38 deg), 4x 720x80, 2x 400x70
        self.assertEqual(parts["total_count"], 10)
        self.assertEqual(parts["group_count"], 4)
        self.assertAlmostEqual(parts["master_bbox"]["width_mm"], 1600.0, delta=1.5)
        self.assertAlmostEqual(parts["master_bbox"]["height_mm"], 900.0, delta=1.5)

        # Verify diagonal braces (+/-38 deg) get EXACT squared OBB (620 x 65 mm) despite tilted AABB!
        tilted = [it for it in parts["items"] if not it["is_orthogonal"]]
        self.assertEqual(len(tilted), 2)
        for br in tilted:
            self.assertAlmostEqual(br["length_mm"], 620.0, delta=1.5)
            self.assertAlmostEqual(br["width_mm"], 65.0, delta=1.5)
            self.assertAlmostEqual(abs(br["angle_deg"]), 38.0, delta=1.0)
            # Axis-aligned AABB must be significantly larger than OBB width because it's rotated!
            self.assertGreater(br["aabb_h_mm"], 400.0)

        # Toggle prepared checklist & verify CSV export
        s_chk = session.toggle_part_prepared(PartToggleRequest(part_id="P01", prepared=True))
        self.assertEqual(s_chk["mosaic"]["parts"]["prepared_count"], 1)
        csv_text = session.build_parts_csv().decode("utf-8-sig")
        self.assertIn("Largo_OBB_mm", csv_text)
        self.assertIn("P01,", csv_text)
        self.assertIn(",SI", csv_text)

    def test_rescan_accidentally_moved_board_preserves_exact_local_coords(self) -> None:
        session = DesignProjectorSession(start_with_test_scenario="progressive_demo")
        before = session.get_state_snapshot()
        s = effective_scale(session.design, session.transform)
        sw = session.design.base_width_mm * s
        sh = session.design.base_height_mm * s

        # Record design-local coordinates of ALL 4 physical corners of Board #2 BEFORE bump
        corners_before = before["board"]["contours_mm"][0]
        design_corners_before = [
            workspace_to_scaled_design(pt[0], pt[1], sw, sh, session.transform)
            for pt in corners_before
        ]
        jcut_len_before = before["mosaic"]["progressive"]["joint_cut_lines"][0]["length_mm"]
        util_before = before["mosaic"]["progressive"]["material_stats"]["utilization_pct"]

        # Accidentally bump AND rotate the board on the workbench!
        res = session.rescan_moved_board(
            RescanBoardRequest(dx_mm=95.0, dy_mm=-45.0, d_angle_deg=6.5, auto_project=True)
        )
        after = res["state"]
        self.assertTrue(res["rescanned"])
        self.assertTrue(res["rescan"]["size_match"])
        self.assertAlmostEqual(res["rescan"]["dx_mm"], 95.0, delta=0.5)
        self.assertAlmostEqual(res["rescan"]["dy_mm"], -45.0, delta=0.5)
        self.assertAlmostEqual(res["rescan"]["d_angle_deg"], 6.5, delta=0.2)
        self.assertFalse(after["projector_display"]["blanked"])

        # Every single physical board corner must map back to the EXACT same design mm (< 0.25 mm error!)
        corners_after = after["board"]["contours_mm"][0]
        design_corners_after = [
            workspace_to_scaled_design(pt[0], pt[1], sw, sh, session.transform)
            for pt in corners_after
        ]
        for p_before, p_after in zip(design_corners_before, design_corners_after):
            err = float(np.hypot(p_after[0] - p_before[0], p_after[1] - p_before[1]))
            self.assertLess(err, 0.25)

        # Joint cut line length and material utilization must remain identical after bump recovery!
        jcut_len_after = after["mosaic"]["progressive"]["joint_cut_lines"][0]["length_mm"]
        util_after = after["mosaic"]["progressive"]["material_stats"]["utilization_pct"]
        self.assertAlmostEqual(jcut_len_after, jcut_len_before, delta=1.0)
        self.assertAlmostEqual(util_after, util_before, delta=0.5)


if __name__ == "__main__":
    unittest.main()
