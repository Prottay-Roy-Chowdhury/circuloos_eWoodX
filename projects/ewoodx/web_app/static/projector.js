(() => {
  "use strict";

  const I18N = {
    en: {
      back: "Back",
      next: "Next",
      fs: "Fullscreen (F)",
      hud_keys: "F Fullscreen · ←/→ Step · B Blackout · H HUD",
      cut_word: "CUT",
      trim_word: "TRIM",
    },
    es: {
      back: "Atrás",
      next: "Siguiente",
      fs: "Pantalla completa (F)",
      hud_keys: "F Pantalla · ←/→ Paso · B Negro · H HUD",
      cut_word: "CORTE",
      trim_word: "SOBRANTE",
    },
    nl: {
      back: "Vorige",
      next: "Volgende",
      fs: "Volledig scherm (F)",
      hud_keys: "F Scherm · ←/→ Stap · B Zwart · H HUD",
      cut_word: "SNEDE",
      trim_word: "REST",
    },
  };

  const params = new URLSearchParams(location.search);
  let lang = params.get("lang") || localStorage.getItem("ewoodx_lang") || "es";
  if (!I18N[lang]) lang = "es";

  const canvas = document.getElementById("projectorCanvas");
  const ctx = canvas.getContext("2d");
  const tileLabel = document.getElementById("projTileLabel");
  const btnPrev = document.getElementById("btnProjPrev");
  const btnNext = document.getElementById("btnProjNext");
  const btnFs = document.getElementById("btnProjFullscreen");

  function syncLabels() {
    btnPrev.textContent = `← ${I18N[lang].back}`;
    btnNext.textContent = `${I18N[lang].next} →`;
    btnFs.textContent = I18N[lang].fs;
  }
  syncLabels();

  window.addEventListener("storage", (ev) => {
    if (ev.key === "ewoodx_lang" && I18N[ev.newValue]) {
      lang = ev.newValue;
      syncLabels();
      render();
    }
  });

  let state = null;
  let ws = null;
  const rasterCache = { key: null, img: null, loaded: false };

  function ensureRaster() {
    if (!state || !state.design || !state.design.has_raster) {
      rasterCache.key = null;
      rasterCache.img = null;
      rasterCache.loaded = false;
      return;
    }
    const mode = state.projector_display.raster_mode || "invert_high_contrast";
    const key = `${state.design.design_id}_${mode}`;
    if (rasterCache.key === key) return;
    rasterCache.key = key;
    rasterCache.loaded = false;
    const img = new Image();
    img.onload = () => {
      if (rasterCache.key === key) {
        rasterCache.img = img;
        rasterCache.loaded = true;
        render();
      }
    };
    img.src = `/api/design/raster?mode=${encodeURIComponent(mode)}&id=${encodeURIComponent(state.design.design_id)}`;
  }

  function applyState(s) {
    state = s;
    ensureRaster();
    const mode = state.mosaic_config.mode;
    if (mode === "progressive" && state.mosaic.progressive) {
      const prog = state.mosaic.progressive;
      const pct = Math.round(prog.coverage_pct || 0);
      tileLabel.textContent = `#${prog.active_board_number} · ${pct}%`;
      btnPrev.disabled = prog.completed_count === 0 || prog.reviewing_index === 1;
      btnNext.disabled = !state.design;
    } else if (mode === "mosaic" && state.mosaic.active_tile) {
      const at = state.mosaic.active_tile;
      tileLabel.textContent = `${at.number} / ${at.total} · ${at.code}`;
      btnPrev.disabled = false;
      btnNext.disabled = false;
    } else {
      tileLabel.textContent = "1:1";
      btnPrev.disabled = true;
      btnNext.disabled = true;
    }
    render();
  }

  function clipToPolygons(context, polygons) {
    if (!polygons || !polygons.length) return false;
    context.beginPath();
    let hasAny = false;
    polygons.forEach((poly) => {
      if (!poly || poly.length < 3) return;
      context.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) {
        context.lineTo(poly[i][0], poly[i][1]);
      }
      context.closePath();
      hasAny = true;
    });
    if (hasAny) context.clip();
    return hasAny;
  }

  function render() {
    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#0A0A0A";
    ctx.fillRect(0, 0, w, h);

    if (!state || state.projector_display.blanked) {
      ctx.restore();
      return;
    }

    const tw = state.workspace.table_width_mm;
    const th = state.workspace.table_height_mm;
    const scale = Math.min(w / tw, h / th);
    const ox = (w - tw * scale) * 0.5;
    const oy = (h - th * scale) * 0.5;

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);

    if (state.projector_display.mirror_x || state.projector_display.mirror_y) {
      ctx.translate(tw * 0.5, th * 0.5);
      ctx.scale(
        state.projector_display.mirror_x ? -1 : 1,
        state.projector_display.mirror_y ? -1 : 1
      );
      ctx.translate(-tw * 0.5, -th * 0.5);
    }

    ctx.translate(
      state.projector_display.fine_offset_x_mm || 0,
      state.projector_display.fine_offset_y_mm || 0
    );

    if (state.projector_display.show_board_contour) {
      state.board.contours_mm.forEach((contour) => {
        if (contour.length < 3) return;
        ctx.beginPath();
        ctx.moveTo(contour[0][0], contour[0][1]);
        for (let i = 1; i < contour.length; i++) ctx.lineTo(contour[i][0], contour[i][1]);
        ctx.closePath();
        ctx.strokeStyle = "#F5F1E8";
        ctx.lineWidth = 2 / scale;
        ctx.stroke();
      });

      (state.board.holes_mm || []).forEach((hole) => {
        if (hole.length < 3) return;
        ctx.beginPath();
        ctx.moveTo(hole[0][0], hole[0][1]);
        for (let i = 1; i < hole.length; i++) ctx.lineTo(hole[i][0], hole[i][1]);
        ctx.closePath();
        ctx.strokeStyle = "#F5F1E8";
        ctx.lineWidth = 1.6 / scale;
        ctx.stroke();
      });
    }

    const pg = state.mosaic.projection_geometry;

    if (
      state.design &&
      state.design.has_raster &&
      pg.raster_transform &&
      rasterCache.loaded &&
      rasterCache.img
    ) {
      const rt = pg.raster_transform;
      ctx.save();
      if (rt.clip_polygons_mm && rt.clip_polygons_mm.length) {
        clipToPolygons(ctx, rt.clip_polygons_mm);
      } else if (rt.clip_window) {
        ctx.beginPath();
        ctx.rect(
          rt.clip_window.x0,
          rt.clip_window.y0,
          rt.clip_window.width_mm,
          rt.clip_window.height_mm
        );
        ctx.clip();
      }
      ctx.globalAlpha = state.projector_display.raster_opacity ?? 0.9;
      ctx.translate(rt.center_x_mm, rt.center_y_mm);
      ctx.rotate((rt.rotation_deg * Math.PI) / 180);
      ctx.scale(rt.flip_x ? -1 : 1, rt.flip_y ? -1 : 1);
      ctx.drawImage(
        rasterCache.img,
        -rt.width_mm * 0.5,
        -rt.height_mm * 0.5,
        rt.width_mm,
        rt.height_mm
      );
      ctx.restore();
    }

    // Overlap trim waste shading (masks raster PDF/Image cleanly + marks offcut side)
    (pg.overlap_trim_polygons || []).forEach((tp) => {
      const poly = tp.polygon_mm;
      if (!poly || poly.length < 3) return;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.closePath();
      ctx.fillStyle = "rgba(10, 10, 10, 0.94)";
      ctx.fill();
      ctx.strokeStyle = "rgba(232, 176, 36, 0.35)";
      ctx.lineWidth = 1.2 / scale;
      ctx.stroke();
      if (tp.area_mm2 > 22000) {
        let tcx = 0;
        let tcy = 0;
        poly.forEach((p) => {
          tcx += p[0];
          tcy += p[1];
        });
        ctx.fillStyle = "rgba(232, 176, 36, 0.7)";
        ctx.font = `600 ${12 / scale}px "JetBrains Mono", monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(I18N[lang].trim_word, tcx / poly.length, tcy / poly.length);
      }
      ctx.restore();
    });

    (pg.tile_border || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.save();
      ctx.setLineDash([10 / scale, 7 / scale]);
      ctx.strokeStyle = "rgba(179, 139, 109, 0.85)";
      ctx.lineWidth = 1.6 / scale;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.stroke();
      ctx.restore();
    });

    if (state.mosaic_config.mode !== "progressive") {
      (pg.seam_lines || []).forEach((line) => {
        if (line.length < 2) return;
        ctx.save();
        ctx.setLineDash([7 / scale, 6 / scale]);
        ctx.strokeStyle = "rgba(96, 184, 134, 0.72)";
        ctx.lineWidth = 1.6 / scale;
        ctx.beginPath();
        ctx.moveTo(line[0][0], line[0][1]);
        ctx.lineTo(line[1][0], line[1][1]);
        ctx.stroke();
        ctx.restore();
      });
    }

    const lw = (state.projector_display.line_width_px || 2.4) / scale;
    ctx.strokeStyle = "#62B3D1";
    ctx.lineWidth = lw * 0.9;
    (pg.mill_geo || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.stroke();
    });

    ctx.strokeStyle = "#E05A4F";
    ctx.lineWidth = lw * 1.1;
    (pg.cut_geo || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.stroke();
    });

    // Vivid Amber JOINT CUT LINES projected onto the physical board
    (pg.joint_cut_lines || []).forEach((jc) => {
      const p0 = jc.points[0];
      const p1 = jc.points[1];
      const dx = p1[0] - p0[0];
      const dy = p1[1] - p0[1];
      const len = Math.max(1, Math.hypot(dx, dy));
      const nx = -dy / len;
      const ny = dx / len;
      const tick = 12 / scale;

      ctx.save();
      ctx.strokeStyle = "#E8B024";
      ctx.lineWidth = 3.5 / scale;
      ctx.setLineDash([14 / scale, 6 / scale]);
      ctx.beginPath();
      ctx.moveTo(p0[0], p0[1]);
      ctx.lineTo(p1[0], p1[1]);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.lineWidth = 2.6 / scale;
      ctx.beginPath();
      ctx.moveTo(p0[0] - nx * tick, p0[1] - ny * tick);
      ctx.lineTo(p0[0] + nx * tick, p0[1] + ny * tick);
      ctx.moveTo(p1[0] - nx * tick, p1[1] - ny * tick);
      ctx.lineTo(p1[0] + nx * tick, p1[1] + ny * tick);
      ctx.stroke();

      const btag = (jc.from_boards || [jc.from_board]).map((n) => `#${n}`).join("/");
      const lbl = `${I18N[lang].cut_word} ${btag} · ${Math.round(jc.length_mm)}mm`;
      const mx = 0.5 * (p0[0] + p1[0]) + (jc.kept_normal ? jc.kept_normal[0] : 0) * (24 / scale);
      const my = 0.5 * (p0[1] + p1[1]) + (jc.kept_normal ? jc.kept_normal[1] : 0) * (24 / scale);
      ctx.font = `700 ${13 / scale}px "JetBrains Mono", monospace`;
      const twLbl = ctx.measureText(lbl).width + 14 / scale;
      const thLbl = 22 / scale;
      ctx.fillStyle = "#E8B024";
      ctx.fillRect(mx - twLbl * 0.5, my - thLbl * 0.5, twLbl, thLbl);
      ctx.fillStyle = "#111111";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(lbl, mx, my);
      ctx.restore();
    });

    const r = 9 / scale;
    ctx.strokeStyle = "#60B886";
    ctx.lineWidth = 2 / scale;
    (pg.points_geo || []).forEach((pt) => {
      ctx.beginPath();
      ctx.arc(pt[0], pt[1], r, 0, Math.PI * 2);
      ctx.moveTo(pt[0] - r * 1.7, pt[1]);
      ctx.lineTo(pt[0] + r * 1.7, pt[1]);
      ctx.moveTo(pt[0], pt[1] - r * 1.7);
      ctx.lineTo(pt[0], pt[1] + r * 1.7);
      ctx.stroke();
    });

    ctx.fillStyle = "#E8DFC8";
    ctx.font = `500 ${14 / scale}px "JetBrains Mono", monospace`;
    (pg.labels || []).forEach((lb) => {
      if (lb.text && lb.text.startsWith("CUT #")) return;
      ctx.fillText(lb.text, lb.pos[0], lb.pos[1]);
    });

    ctx.restore();

    if (state.projector_display.show_hud) {
      const hudH = 32;
      ctx.fillStyle = "rgba(18, 18, 18, 0.9)";
      ctx.fillRect(0, h - hudH, w, hudH);
      ctx.strokeStyle = "#2E2E2E";
      ctx.beginPath();
      ctx.moveTo(0, h - hudH);
      ctx.lineTo(w, h - hudH);
      ctx.stroke();

      ctx.fillStyle = "#F5F1E8";
      ctx.font = '500 12px "JetBrains Mono", monospace';
      let modeStr = "1:1";
      if (state.mosaic_config.mode === "progressive" && state.mosaic.progressive) {
        const p = state.mosaic.progressive;
        modeStr = `#${p.active_board_number} · ${Math.round(p.coverage_pct || 0)}%`;
      } else if (state.mosaic_config.mode === "mosaic" && state.mosaic.active_tile) {
        const at = state.mosaic.active_tile;
        modeStr = `${at.number}/${at.total} [${at.code}]`;
      }
      ctx.fillText(
        `eWoodX · ${modeStr} · ${Math.round(state.board.length_mm)}×${Math.round(state.board.width_mm)} mm`,
        16,
        h - 11
      );

      ctx.fillStyle = "#808080";
      ctx.textAlign = "right";
      ctx.fillText(I18N[lang].hud_keys, w - 16, h - 11);
    }

    ctx.restore();
  }

  async function postJson(url, body = {}) {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {});
    else document.exitFullscreen().catch(() => {});
  }

  btnFs.addEventListener("click", toggleFullscreen);
  btnPrev.addEventListener("click", () => postJson("/api/step/back"));
  btnNext.addEventListener("click", () => postJson("/api/step/next"));

  window.addEventListener("keydown", (ev) => {
    if (!state) return;
    if (ev.key.toLowerCase() === "f") toggleFullscreen();
    else if (ev.key === "ArrowRight" || ev.key === " " || ev.key === "PageDown") {
      ev.preventDefault();
      if (state.mosaic_config.mode === "progressive" || state.mosaic_config.mode === "mosaic") {
        postJson("/api/step/next");
      }
    } else if (ev.key === "ArrowLeft" || ev.key === "PageUp") {
      ev.preventDefault();
      if (state.mosaic_config.mode === "progressive" || state.mosaic_config.mode === "mosaic") {
        postJson("/api/step/back");
      }
    } else if (ev.key.toLowerCase() === "b") {
      postJson("/api/projector/display", { blanked: !state.projector_display.blanked });
    } else if (ev.key.toLowerCase() === "h") {
      postJson("/api/projector/display", { show_hud: !state.projector_display.show_hud });
    }
  });

  window.addEventListener("resize", render);

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "state" && msg.data) applyState(msg.data);
      } catch (e) {
        console.error(e);
      }
    };
    ws.onclose = () => setTimeout(connectWS, 1500);
  }

  fetch("/api/state")
    .then((r) => r.json())
    .then((s) => applyState(s))
    .catch(() => {});
  connectWS();
})();
