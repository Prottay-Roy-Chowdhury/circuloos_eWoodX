(() => {
  "use strict";

  // -------------------------------------------------------------------
  // Trilingual Dictionary (EN / ES / NL) — Icon-First, Short 1-2 Words
  // -------------------------------------------------------------------
  const I18N = {
    en: {
      scan: "Scan",
      upload: "Upload",
      send: "Send",
      sent: "Sent",
      back: "Back",
      next: "Next",
      view_split: "Split",
      view_table: "Table",
      view_projector: "Projector",
      hint: "Drag drawing · Next stamps board as done · Scan next board of any size",
      hint_mosaic: "Drag drawing · Click tile to project",
      drop_here: "Drop DXF · PDF · Image · JSON",
      settings: "Settings",
      close: "Close",
      sec_mode: "Projection Mode",
      mode_progressive: "Progressive nesting (variable boards)",
      mode_mosaic: "Uniform mosaic (fixed grid)",
      mode_single: "Single fit (no split)",
      overlap: "Overlap (mm)",
      margin: "Margin (mm)",
      reg_marks: "Registration marks",
      reset_progress: "Reset progress",
      center: "Center",
      sec_board: "Board (JSON)",
      sec_drawing: "Drawing",
      sec_projector: "Projector & eWoodX Stream",
      length_mm: "Length (mm)",
      width_mm: "Width (mm)",
      thickness_mm: "Thickness (mm)",
      angle_deg: "Angle (°)",
      apply: "Apply",
      cancel: "Cancel",
      clear: "Clear",
      align_board: "Align board",
      cad_unit: "DXF source unit (1:1 locked)",
      vectorize: "Vectorize contours",
      open_projector: "Open Projector Window",
      show_board: "Board contour",
      connect: "Connect",
      disconnect: "Disconnect",
      export_json: "Download eWoodX JSON",
      scale_title: "Drawing Scale",
      scale_title_pdf: "PDF Scale (1:1 or Scaled)",
      scale_title_img: "Image Real Dimensions",
      scale_desc: "PDFs can be 1:1 or scaled; images require real dimensions in mm.",
      scale_desc_pdf: "Choose 1:1 if the PDF is already full scale, or set a ratio / real width in mm.",
      scale_desc_img: "Images have no CAD scale. Enter the real physical width or height in mm.",
      scale_factor: "Scale factor",
      target_width: "Real width (mm)",
      target_height: "Real height (mm)",
      base_size: "Base:",
      final_size: "Final:",
      cap_table: "TABLE",
      cap_projector: "PROJECTOR",
      cap_blanked: "PROJECTOR OFF",
      done_boards: "done",
      review_tag: "REVIEW",
      empty_drop: "Drop DXF · PDF · Image",
      toast_scanned: "Board scanned",
      toast_sent: "Sent to projector",
      toast_locked: "Locked to board",
      toast_unlocked: "Unlocked",
      toast_loaded: "Loaded",
      toast_stamped: "Board marked done",
      toast_undone: "Last board undone",
      toast_nested: "Auto-nested on remaining area",
      toast_reset: "Progress reset",
      scale_click_hint: "Click to adjust scale",
      dxf_locked_hint: "DXF 1:1 locked",
      cut_word: "CUT",
      trim_word: "TRIM",
      use_word: "fit",
      view_parts: "Parts",
      parts_total_bbox: "Envelope",
      parts_count: "Parts",
      parts_ready: "Ready",
      parts_all: "All",
      col_bbox: "Squared BBox (mm)",
      col_angle: "Angle / AABB",
      col_layer: "Layer",
      parts_empty: "Upload a DXF or vector drawing to list each polyline bounding box.",
      cap_parts: "ASSEMBLY · BBOX",
      hint_parts: "Click a size group or piece to inspect its squared bounding box · Tick when prepared",
      rescan_tip: "Re-scan moved board & keep lines locked (R)",
      rescan_json: "Re-scan JSON",
      rescan_tag: "RE-SYNC",
      toast_rescanned: "Board re-anchored & re-projected",
      toast_rescan_warn: "Re-anchored (size changed)",
    },
    es: {
      scan: "Escanear",
      upload: "Subir",
      send: "Enviar",
      sent: "Enviado",
      back: "Atrás",
      next: "Siguiente",
      view_split: "Dividida",
      view_table: "Mesa",
      view_projector: "Proyector",
      hint: "Arrastra el dibujo · Siguiente marca la tabla como hecha · Escanea cualquier tamaño",
      hint_mosaic: "Arrastra el dibujo · Clic en baldosa para proyectar",
      drop_here: "Suelta DXF · PDF · Imagen · JSON",
      settings: "Ajustes",
      close: "Cerrar",
      sec_mode: "Modo de proyección",
      mode_progressive: "Nesting progresivo (tablas distintas)",
      mode_mosaic: "Mosaico uniforme (cuadrícula fija)",
      mode_single: "Encaje único (sin recorte)",
      overlap: "Solape (mm)",
      margin: "Margen (mm)",
      reg_marks: "Marcas de registro",
      reset_progress: "Reiniciar progreso",
      center: "Centrar",
      sec_board: "Tabla (JSON)",
      sec_drawing: "Dibujo",
      sec_projector: "Proyector y eWoodX Stream",
      length_mm: "Largo (mm)",
      width_mm: "Ancho (mm)",
      thickness_mm: "Grosor (mm)",
      angle_deg: "Ángulo (°)",
      apply: "Aplicar",
      cancel: "Cancelar",
      clear: "Quitar",
      align_board: "Alinear tabla",
      cad_unit: "Unidad origen DXF (1:1 fija)",
      vectorize: "Vectorizar contornos",
      open_projector: "Abrir ventana proyector",
      show_board: "Contorno de tabla",
      connect: "Conectar",
      disconnect: "Desconectar",
      export_json: "Descargar JSON eWoodX",
      scale_title: "Escala del dibujo",
      scale_title_pdf: "Escala del PDF (1:1 o escalado)",
      scale_title_img: "Tamaño real de la imagen",
      scale_desc: "Los PDF pueden venir a 1:1 o reducidos; las imágenes necesitan tamaño real en mm.",
      scale_desc_pdf: "Pulsa 1:1 si el PDF ya está a escala real, o elige un factor / ancho en mm.",
      scale_desc_img: "Las imágenes no traen escala. Indica el ancho o alto real en milímetros.",
      scale_factor: "Factor de escala",
      target_width: "Ancho real (mm)",
      target_height: "Alto real (mm)",
      base_size: "Base:",
      final_size: "Final:",
      cap_table: "MESA",
      cap_projector: "PROYECTOR",
      cap_blanked: "PROYECTOR APAGADO",
      done_boards: "hechas",
      review_tag: "REVISIÓN",
      empty_drop: "Suelta DXF · PDF · Imagen",
      toast_scanned: "Tabla escaneada",
      toast_sent: "Enviado al proyector",
      toast_locked: "Fijado a tabla",
      toast_unlocked: "Desbloqueado",
      toast_loaded: "Cargado",
      toast_stamped: "Tabla marcada como hecha",
      toast_undone: "Última tabla deshecha",
      toast_nested: "Auto-anidado en zona libre",
      toast_reset: "Progreso reiniciado",
      scale_click_hint: "Clic para cambiar escala",
      dxf_locked_hint: "DXF 1:1 bloqueado",
      cut_word: "CORTE",
      trim_word: "SOBRANTE",
      use_word: "uso",
      view_parts: "Piezas",
      parts_total_bbox: "Envolvente",
      parts_count: "Piezas",
      parts_ready: "Listas",
      parts_all: "Todas",
      col_bbox: "Caja cuadrada (mm)",
      col_angle: "Ángulo / AABB",
      col_layer: "Capa",
      parts_empty: "Sube un DXF o dibujo vectorial para listar el bounding box de cada polilínea.",
      cap_parts: "ENSAMBLAJE · BBOX",
      hint_parts: "Clic en una medida o pieza para resaltar su caja cuadrada · Marca al prepararla",
      rescan_tip: "Re-escanear pieza movida manteniendo líneas y proyectar (R)",
      rescan_json: "Re-escanear JSON",
      rescan_tag: "RE-UBICADA",
      toast_rescanned: "Pieza re-ubicada y re-proyectada",
      toast_rescan_warn: "Re-ubicada (tamaño distinto)",
    },
    nl: {
      scan: "Scannen",
      upload: "Uploaden",
      send: "Zenden",
      sent: "Verzonden",
      back: "Vorige",
      next: "Volgende",
      view_split: "Gesplitst",
      view_table: "Tafel",
      view_projector: "Projector",
      hint: "Sleep tekening · Volgende markeert plank als klaar · Scan elk formaat",
      hint_mosaic: "Sleep tekening · Klik op tegel om te projecteren",
      drop_here: "Sleep DXF · PDF · Afbeelding · JSON",
      settings: "Instellingen",
      close: "Sluiten",
      sec_mode: "Projectiemodus",
      mode_progressive: "Progressief nesten (wisselende planken)",
      mode_mosaic: "Uniform mozaïek (vast raster)",
      mode_single: "Enkele pasvorm",
      overlap: "Overlap (mm)",
      margin: "Marge (mm)",
      reg_marks: "Registratiemerken",
      reset_progress: "Voortgang resetten",
      center: "Centreren",
      sec_board: "Plank (JSON)",
      sec_drawing: "Tekening",
      sec_projector: "Projector & eWoodX Stream",
      length_mm: "Lengte (mm)",
      width_mm: "Breedte (mm)",
      thickness_mm: "Dikte (mm)",
      angle_deg: "Hoek (°)",
      apply: "Toepassen",
      cancel: "Annuleren",
      clear: "Wissen",
      align_board: "Uitlijnen",
      cad_unit: "DXF-eenheid (1:1 vast)",
      vectorize: "Contouren vectoriseren",
      open_projector: "Projectorvenster openen",
      show_board: "Plankcontour",
      connect: "Verbinden",
      disconnect: "Loskoppelen",
      export_json: "eWoodX JSON downloaden",
      scale_title: "Tekening schaal",
      scale_title_pdf: "PDF-schaal (1:1 of geschaald)",
      scale_title_img: "Werkelijke afmeting afbeelding",
      scale_desc: "PDF kan 1:1 of geschaald zijn; afbeeldingen vragen maten in mm.",
      scale_desc_pdf: "Kies 1:1 als de PDF op ware grootte is, of stel een schaal / breedte in mm in.",
      scale_desc_img: "Afbeeldingen hebben geen schaal. Vul de werkelijke breedte of hoogte in mm in.",
      scale_factor: "Schaalfactor",
      target_width: "Echte breedte (mm)",
      target_height: "Echte hoogte (mm)",
      base_size: "Basis:",
      final_size: "Eindmaat:",
      cap_table: "TAFEL",
      cap_projector: "PROJECTOR",
      cap_blanked: "PROJECTOR UIT",
      done_boards: "klaar",
      review_tag: "BEKIJKEN",
      empty_drop: "Sleep DXF · PDF · Afbeelding",
      toast_scanned: "Plank gescand",
      toast_sent: "Verzonden naar projector",
      toast_locked: "Vastgezet op plank",
      toast_unlocked: "Ontgrendeld",
      toast_loaded: "Geladen",
      toast_stamped: "Plank gemarkeerd als klaar",
      toast_undone: "Laatste plank ongedaan gemaakt",
      toast_nested: "Automatisch op vrije zone geplaatst",
      toast_reset: "Voortgang gereset",
      scale_click_hint: "Klik om schaal aan te passen",
      dxf_locked_hint: "DXF 1:1 vergrendeld",
      cut_word: "SNEDE",
      trim_word: "REST",
      use_word: "benut",
      view_parts: "Onderdelen",
      parts_total_bbox: "Omhulling",
      parts_count: "Stuks",
      parts_ready: "Klaar",
      parts_all: "Alle",
      col_bbox: "Vierkant vak (mm)",
      col_angle: "Hoek / AABB",
      col_layer: "Laag",
      parts_empty: "Upload een DXF of vectortekening om de bounding box van elke polylijn te tonen.",
      cap_parts: "MONTAGE · BBOX",
      hint_parts: "Klik op een maatgroep of rij om het vak te bekijken · Vink af wanneer klaar",
      rescan_tip: "Verschoven plank herscannen & lijnen behouden (R)",
      rescan_json: "JSON herscannen",
      rescan_tag: "HER-UITGELIJND",
      toast_rescanned: "Plank opnieuw uitgelijnd & geprojecteerd",
      toast_rescan_warn: "Opnieuw uitgelijnd (andere maat)",
    },
  };

  const urlParams = new URLSearchParams(location.search);
  let lang = urlParams.get("lang") || localStorage.getItem("ewoodx_lang") || "es";
  if (!I18N[lang]) lang = "es";

  const t = (key) => (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;

  function applyLanguage(newLang) {
    if (!I18N[newLang]) return;
    lang = newLang;
    localStorage.setItem("ewoodx_lang", lang);
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.dataset.i18n;
      if (I18N[lang][k]) el.textContent = I18N[lang][k];
    });
    document.querySelectorAll("#langSwitch button").forEach((b) => {
      b.classList.toggle("active", b.dataset.lang === lang);
    });
    if (state) {
      updateUI();
      renderAll();
    }
  }

  // -------------------------------------------------------------------
  // State & Caches
  // -------------------------------------------------------------------
  let state = null;
  let ws = null;
  let currentView = urlParams.get("view") || "split";
  let projectorWin = null;
  let promptedDesignId = null;
  let opencvTimer = null;
  let lastOpencvRev = -1;
  let selectedPartId = null;
  let hoveredPartId = null;
  let selectedGroupKey = null;
  let partsBoxMode = "obb";

  const cam = { zoom: 1.0, panX: 0, panY: 0, initialized: false };
  const drag = { mode: null, startScreenX: 0, startScreenY: 0, startOffX: 0, startOffY: 0, moved: false };
  let liveOffX = null;
  let liveOffY = null;
  let dragTimer = null;

  const rasterCache = {
    overview: { key: null, img: null, loaded: false },
    preview: { key: null, img: null, loaded: false },
  };

  // Reusable seamless 45-degree Swiss architectural hatch pattern for eliminated/done boards
  const hatchCanvas = document.createElement("canvas");
  hatchCanvas.width = 12;
  hatchCanvas.height = 12;
  const hctx = hatchCanvas.getContext("2d");
  hctx.fillStyle = "rgba(179, 139, 109, 0.16)";
  hctx.fillRect(0, 0, 12, 12);
  hctx.strokeStyle = "rgba(140, 103, 75, 0.62)";
  hctx.lineWidth = 1.15;
  hctx.beginPath();
  hctx.moveTo(-6, 6);
  hctx.lineTo(6, -6);
  hctx.moveTo(-6, 18);
  hctx.lineTo(18, -6);
  hctx.moveTo(6, 18);
  hctx.lineTo(18, 6);
  hctx.stroke();

  // Reusable dark-surface amber offcut/trim hatch pattern for projector preview
  const trimHatchCanvas = document.createElement("canvas");
  trimHatchCanvas.width = 14;
  trimHatchCanvas.height = 14;
  const thctx = trimHatchCanvas.getContext("2d");
  thctx.fillStyle = "rgba(20, 20, 20, 0.92)";
  thctx.fillRect(0, 0, 14, 14);
  thctx.strokeStyle = "rgba(232, 176, 36, 0.28)";
  thctx.lineWidth = 1.1;
  thctx.beginPath();
  thctx.moveTo(-7, 7);
  thctx.lineTo(7, -7);
  thctx.moveTo(-7, 21);
  thctx.lineTo(21, -7);
  thctx.moveTo(7, 21);
  thctx.lineTo(21, 7);
  thctx.stroke();

  const $ = (id) => document.getElementById(id);
  const overviewCanvas = $("overviewCanvas");
  const overviewCtx = overviewCanvas.getContext("2d");
  const previewCanvas = $("previewCanvas");
  const previewCtx = previewCanvas.getContext("2d");
  const partsCanvas = $("partsCanvas");
  const partsCtx = partsCanvas.getContext("2d");

  let toastTimer = null;
  function showToast(msg) {
    const el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 2200);
  }

  async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        if (j.detail) detail = j.detail;
      } catch (_) {}
      showToast(detail);
      throw new Error(detail);
    }
    return res.json();
  }

  async function postJson(url, body = {}) {
    const data = await api(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (data && data.state) applyState(data.state);
    else if (data && data.revision !== undefined) applyState(data);
    return data;
  }

  // -------------------------------------------------------------------
  // Raster Loading
  // -------------------------------------------------------------------
  function ensureRaster(slot, mode) {
    const cache = rasterCache[slot];
    if (!state || !state.design || !state.design.has_raster) {
      cache.key = null;
      cache.img = null;
      cache.loaded = false;
      return;
    }
    const key = `${state.design.design_id}_${mode}`;
    if (cache.key === key) return;
    cache.key = key;
    cache.loaded = false;
    const img = new Image();
    img.onload = () => {
      if (cache.key === key) {
        cache.img = img;
        cache.loaded = true;
        renderAll();
      }
    };
    img.src = `/api/design/raster?mode=${encodeURIComponent(mode)}&id=${encodeURIComponent(state.design.design_id)}`;
  }

  // -------------------------------------------------------------------
  // State Application & UI Sync
  // -------------------------------------------------------------------
  function applyState(newState) {
    const prevDesignId = state && state.design ? state.design.design_id : null;
    state = newState;
    if (drag.mode !== "design") {
      liveOffX = null;
      liveOffY = null;
    }

    ensureRaster("overview", "original");
    ensureRaster("preview", state.projector_display.raster_mode || "invert_high_contrast");

    updateUI();

    const curDesignId = state.design ? state.design.design_id : null;
    if (!cam.initialized || curDesignId !== prevDesignId) {
      if (curDesignId !== prevDesignId) {
        selectedPartId = null;
        hoveredPartId = null;
        selectedGroupKey = null;
      }
      fitOverviewCamera();
      cam.initialized = true;
    }

    renderAll();

    if (
      state.design &&
      state.design.needs_scale_prompt &&
      !state.design.scale_locked &&
      promptedDesignId !== state.design.design_id
    ) {
      promptedDesignId = state.design.design_id;
      openScaleModal();
    }

    if (state.sandbox && state.sandbox.enabled && currentView === "opencv") {
      refreshOpencvFrame(true);
    }
  }

  function updateUI() {
    if (!state) return;
    const b = state.board;
    const d = state.design;
    const tr = state.transform;
    const mc = state.mosaic_config;
    const m = state.mosaic;
    const pd = state.projector_display;
    const st = state.stream;
    const sb = state.sandbox || { enabled: false };
    const prog = m.progressive || {
      completed_count: 0,
      active_board_number: 1,
      coverage_pct: 0,
      reviewing_index: null,
      inherited_fiducials: [],
      new_fiducials: [],
    };

    const dimsText = `${Math.round(b.length_mm)} × ${Math.round(b.width_mm)} mm`;
    $("topBoardDims").textContent = dimsText;
    $("boardDimsLabel").textContent = dimsText;
    $("boardAngleLabel").textContent = `${b.angle_deg.toFixed(1)}° · ${Math.round(b.thickness_mm)} mm`;
    if ($("btnRescan")) $("btnRescan").title = t("rescan_tip");

    const dot = $("streamDot");
    dot.classList.toggle("online", !!st.connected);
    dot.title = st.connected ? "eWoodX Stream Online" : "Local Mode";

    // Topbar coverage bar
    const pct = Math.min(100, Math.max(0, Math.round(prog.coverage_pct || 0)));
    $("progressPill").classList.toggle("hidden", !d || mc.mode !== "progressive");
    $("progressFill").style.width = `${pct}%`;
    $("progressPctLabel").textContent = `${pct}%`;

    // Stage captions & hints
    const isReviewing = mc.mode === "progressive" && prog.reviewing_index !== null;
    $("overviewCaption").textContent = `${t("cap_table")} · ${dimsText}${isReviewing ? ` · ${t("review_tag")} #${prog.reviewing_index}` : ""}`;

    if (pd.blanked) {
      $("previewCaption").textContent = t("cap_blanked");
    } else if (mc.mode === "progressive") {
      const util = prog.material_stats ? Math.round(prog.material_stats.utilization_pct || 0) : 0;
      const utilPart = d && util > 0 ? ` · ${util}% ${t("use_word")}` : "";
      $("previewCaption").textContent = `${t("cap_projector")} · #${prog.active_board_number}${utilPart}`;
    } else if (mc.mode === "mosaic" && m.active_tile) {
      $("previewCaption").textContent = `${t("cap_projector")} · ${m.active_tile.number}/${m.active_tile.total} [${m.active_tile.code}]`;
    } else {
      $("previewCaption").textContent = `${t("cap_projector")} · 1:1`;
    }

    $("stageHint").textContent =
      currentView === "parts"
        ? t("hint_parts")
        : mc.mode === "mosaic"
        ? t("hint_mosaic")
        : t("hint");

    // Drawing summary & scale badge (clickable for PDF & Image, locked for DXF)
    const scaleBadge = $("designScaleBadge");
    if (d) {
      $("designNameLabel").textContent = `${Math.round(m.scaled_width_mm)} × ${Math.round(m.scaled_height_mm)} mm`;
      $("designNameLabel").title = d.filename;
      if (d.scale_locked) {
        scaleBadge.textContent = "1:1";
        scaleBadge.className = "scale-badge locked";
        scaleBadge.title = t("dxf_locked_hint");
      } else {
        const sVal = m.effective_scale;
        scaleBadge.textContent = Math.abs(sVal - 1.0) < 0.005 ? "1:1" : `×${sVal.toFixed(2)}`;
        scaleBadge.className = "scale-badge clickable";
        scaleBadge.title = t("scale_click_hint");
      }
    } else {
      $("designNameLabel").textContent = "—";
      scaleBadge.textContent = "—";
      scaleBadge.className = "scale-badge";
      scaleBadge.title = "";
    }

    // Back / Progress / Next Stepper
    const stepCenter = $("stepperCenter");
    stepCenter.classList.toggle("reviewing", isReviewing);
    if (mc.mode === "progressive") {
      $("tileCounter").textContent = `#${prog.active_board_number}`;
      $("stepperPct").textContent = `${pct}%`;
      $("btnPrevTile").disabled = !d || prog.completed_count === 0 || prog.reviewing_index === 1;
      $("btnNextTile").disabled = !d;
      $("progressiveMetaLabel").textContent = isReviewing
        ? `${t("review_tag")} #${prog.reviewing_index}/${prog.completed_count}`
        : `${prog.completed_count} ${t("done_boards")}`;

      const jcuts = prog.joint_cut_lines || [];
      const inh = (prog.inherited_fiducials || []).map((f) => f.code);
      const nw = (prog.new_fiducials || []).map((f) => f.code);
      let metaRight = "—";
      if (jcuts.length) {
        const totalCutMm = Math.round(jcuts.reduce((acc, c) => acc + (c.length_mm || 0), 0));
        metaRight = `${t("cut_word")} ${jcuts.length}× · ${totalCutMm} mm`;
      } else if (inh.length) {
        metaRight = inh.slice(0, 3).join(" · ");
      } else if (nw.length) {
        metaRight = nw.slice(0, 3).join(" · ");
      }
      $("fiducialsMetaLabel").textContent = metaRight;
    } else if (mc.mode === "mosaic" && m.active_tile) {
      $("tileCounter").textContent = `${m.active_tile.number}/${m.active_tile.total}`;
      $("stepperPct").textContent = m.active_tile.code;
      $("btnPrevTile").disabled = m.tiles.length <= 1;
      $("btnNextTile").disabled = m.tiles.length <= 1;
      $("progressiveMetaLabel").textContent = `${m.tiles.length} tiles`;
      $("fiducialsMetaLabel").textContent = `${Math.round(mc.overlap_mm)} mm`;
    } else {
      $("tileCounter").textContent = "1:1";
      $("stepperPct").textContent = "100%";
      $("btnPrevTile").disabled = true;
      $("btnNextTile").disabled = true;
      $("progressiveMetaLabel").textContent = "1:1";
      $("fiducialsMetaLabel").textContent = "—";
    }

    // Canvas icon toolbar
    const locked = !!tr.locked_to_board;
    $("btnToggleLock").classList.toggle("is-locked", locked);
    $("btnToggleLock").disabled = !d;
    $("lockIconUnlocked").classList.toggle("hidden", locked);
    $("lockIconLocked").classList.toggle("hidden", !locked);
    $("btnAutoNest").disabled = !d || locked;
    $("btnRotPlus90").disabled = !d || locked;
    $("btnUndoRegion").disabled = !d || prog.completed_count === 0;

    // Blackout button
    $("btnBlankProjector").classList.toggle("is-active", !!pd.blanked);

    // OpenCV Sandbox tab visibility
    $("tabOpencvView").classList.toggle("hidden", !sb.enabled);
    $("btnSbNudgeRight").classList.toggle("hidden", !sb.enabled);
    $("btnSbAutoFeed").classList.toggle("hidden", !sb.enabled);
    if (sb.enabled) {
      $("btnSbAutoFeed").classList.toggle("is-active", !!sb.auto_feed_enabled);
      if (sb.current_scenario_id && $("boardScenarioSelect").value !== sb.current_scenario_id) {
        $("boardScenarioSelect").value = sb.current_scenario_id;
      }
    }

    // Drawer inputs sync
    syncInput("modeSelect", mc.mode);
    syncInput("overlapInput", Math.round(mc.overlap_mm));
    syncInput("marginInput", Math.round(mc.margin_mm));
    $("chkRegMarks").checked = !!mc.show_registration_marks;
    $("chkShowBoard").checked = !!pd.show_board_contour;
    $("btnProjMirrorX").classList.toggle("is-active", !!pd.mirror_x);
    $("btnProjMirrorY").classList.toggle("is-active", !!pd.mirror_y);
    syncInput("fineOffX", pd.fine_offset_x_mm);
    syncInput("fineOffY", pd.fine_offset_y_mm);
    syncInput("rasterModeSelect", pd.raster_mode || "invert_high_contrast");
    $("btnConnectStream").disabled = !!st.connected;
    $("btnDisconnectStream").disabled = !st.connected;
    $("btnResetRegions").disabled = prog.completed_count === 0;

    // DXF units / PDF page / Raster / Layers inside drawer
    if (d && d.file_format === "dxf") {
      $("dxfUnitBox").classList.remove("hidden");
      syncInput("dxfUnitSelect", d.source_units || "mm");
    } else {
      $("dxfUnitBox").classList.add("hidden");
    }

    if (d && d.file_format === "pdf" && d.pdf_page_count > 1) {
      $("pdfPageRow").classList.remove("hidden");
      const sel = $("pdfPageSelect");
      if (sel.options.length !== d.pdf_page_count) {
        sel.innerHTML = "";
        for (let i = 0; i < d.pdf_page_count; i++) {
          const opt = document.createElement("option");
          opt.value = String(i);
          opt.textContent = `${i + 1} / ${d.pdf_page_count}`;
          sel.appendChild(opt);
        }
      }
      sel.value = String(d.pdf_page_index || 0);
    } else {
      $("pdfPageRow").classList.add("hidden");
    }

    $("rasterDisplayControls").classList.toggle("hidden", !(d && d.has_raster));
    renderLayerList(d);
    updatePartsPanel();
  }

  // -------------------------------------------------------------------
  // Assembly / Material Cut List Panel (Polyline Squared Bounding Boxes)
  // -------------------------------------------------------------------
  function updatePartsPanel() {
    if (!state) return;
    const parts = (state.mosaic && state.mosaic.parts) || {
      total_count: 0,
      group_count: 0,
      prepared_count: 0,
      master_bbox: { width_mm: 0, height_mm: 0 },
      groups: [],
      items: [],
    };
    const items = parts.items || [];
    const groups = parts.groups || [];
    const mb = parts.master_bbox || { width_mm: 0, height_mm: 0 };

    $("partsTabCount").textContent = String(parts.total_count || 0);
    $("partsTotalCount").textContent = String(parts.total_count || 0);
    $("partsReadyCount").textContent = `${parts.prepared_count || 0} / ${parts.total_count || 0}`;
    $("partsMasterBbox").textContent =
      parts.total_count > 0 ? `${Math.round(mb.width_mm)} × ${Math.round(mb.height_mm)} mm` : "—";
    $("partsMapCaption").textContent = `${t("cap_parts")} (${partsBoxMode.toUpperCase()}) · ${
      parts.total_count > 0 ? `${Math.round(mb.width_mm)} × ${Math.round(mb.height_mm)} mm` : "—"
    }`;

    $("btnExportPartsCsv").disabled = parts.total_count === 0;
    $("btnResetParts").disabled = (parts.prepared_count || 0) === 0;

    // Validate selectedGroupKey still exists
    if (selectedGroupKey && !groups.some((g) => g.key === selectedGroupKey)) {
      selectedGroupKey = null;
    }

    // Render grouped stock summary chips
    const chipsEl = $("partsGroupChips");
    chipsEl.innerHTML = "";
    if (groups.length > 0) {
      const allBtn = document.createElement("button");
      allBtn.className = `group-chip${selectedGroupKey === null ? " active" : ""}`;
      allBtn.innerHTML = `<span>${t("parts_all")}</span><span class="g-qty">${parts.total_count}</span>`;
      allBtn.addEventListener("click", () => {
        selectedGroupKey = null;
        selectedPartId = null;
        updatePartsPanel();
        renderPartsCanvas();
      });
      chipsEl.appendChild(allBtn);

      groups.forEach((g) => {
        const btn = document.createElement("button");
        btn.className = `group-chip${selectedGroupKey === g.key ? " active" : ""}`;
        btn.innerHTML = `<span class="g-qty">${g.count}×</span><span>${g.key}</span>`;
        btn.addEventListener("click", () => {
          selectedGroupKey = selectedGroupKey === g.key ? null : g.key;
          selectedPartId = null;
          updatePartsPanel();
          renderPartsCanvas();
        });
        chipsEl.appendChild(btn);
      });
    }

    // Render interactive polyline bounding box table
    const tbody = $("partsTableBody");
    tbody.innerHTML = "";
    const filtered = selectedGroupKey ? items.filter((it) => it.group_key === selectedGroupKey) : items;
    $("partsEmptyState").classList.toggle("hidden", filtered.length > 0);

    filtered.forEach((it) => {
      const tr = document.createElement("tr");
      if (it.id === selectedPartId) tr.classList.add("is-selected");
      if (it.prepared) tr.classList.add("is-prepared");

      const dimsStr =
        it.width_mm > 0.5
          ? `${it.length_mm.toFixed(0)} × ${it.width_mm.toFixed(0)} mm`
          : `${it.length_mm.toFixed(0)} mm`;

      const angleHtml = it.is_orthogonal
        ? `<span>${it.angle_deg.toFixed(0)}°</span>`
        : `<span class="angle-tilted">${it.angle_deg.toFixed(1)}°</span><span class="aabb-sub">AABB ${Math.round(it.aabb_w_mm)}×${Math.round(it.aabb_h_mm)}</span>`;

      tr.innerHTML = `
        <td class="col-chk"><input type="checkbox" ${it.prepared ? "checked" : ""} /></td>
        <td class="col-id">${it.id}</td>
        <td class="cell-dims">${dimsStr}</td>
        <td class="cell-angle">${angleHtml}</td>
        <td class="cell-layer">${it.layer}</td>
      `;

      const chk = tr.querySelector("input");
      chk.addEventListener("click", (ev) => ev.stopPropagation());
      chk.addEventListener("change", (ev) => {
        postJson("/api/parts/toggle", { part_id: it.id, prepared: ev.target.checked });
      });

      tr.addEventListener("mouseenter", () => {
        hoveredPartId = it.id;
        renderPartsCanvas();
      });
      tr.addEventListener("mouseleave", () => {
        if (hoveredPartId === it.id) {
          hoveredPartId = null;
          renderPartsCanvas();
        }
      });
      tr.addEventListener("click", () => {
        selectedPartId = selectedPartId === it.id ? null : it.id;
        updatePartsPanel();
        renderPartsCanvas();
      });

      tbody.appendChild(tr);
    });
  }

  function renderPartsCanvas() {
    if (!state || $("partsPane").classList.contains("hidden")) return;
    const { w, h, dpr } = resizeCanvas(partsCanvas);
    if (!w || !h) return;

    const ctx = partsCtx;
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, w, h);

    const parts = (state.mosaic && state.mosaic.parts) || { items: [], master_bbox: null };
    const items = parts.items || [];
    const mb = parts.master_bbox;

    if (!items.length || !mb || (mb.width_mm <= 0 && mb.height_mm <= 0)) {
      ctx.fillStyle = "rgba(17, 17, 17, 0.5)";
      ctx.font = '600 13px "Helvetica Neue", Arial, sans-serif';
      ctx.textAlign = "center";
      ctx.fillText(t("parts_empty"), w * 0.5, h * 0.5);
      ctx.restore();
      return;
    }

    const pad = 58;
    const spanX = Math.max(50, mb.width_mm);
    const spanY = Math.max(50, mb.height_mm);
    const scale = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);
    const ox = (w - spanX * scale) * 0.5 - mb.min_x * scale;
    const oy = (h - spanY * scale) * 0.5 - mb.min_y * scale;

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);

    // Subtle Swiss architectural grid
    const gridStep = spanX > 1500 ? 200 : 100;
    ctx.strokeStyle = "#F3EFE7";
    ctx.lineWidth = 1 / scale;
    ctx.beginPath();
    for (let x = Math.floor(mb.min_x / gridStep) * gridStep; x <= mb.max_x + gridStep; x += gridStep) {
      ctx.moveTo(x, mb.min_y - gridStep);
      ctx.lineTo(x, mb.max_y + gridStep);
    }
    for (let y = Math.floor(mb.min_y / gridStep) * gridStep; y <= mb.max_y + gridStep; y += gridStep) {
      ctx.moveTo(mb.min_x - gridStep, y);
      ctx.lineTo(mb.max_x + gridStep, y);
    }
    ctx.stroke();

    // Master Overall Bounding Box + Swiss Drafting Dimension Lines
    ctx.save();
    ctx.strokeStyle = "#CFC7B8";
    ctx.lineWidth = 1.1 / scale;
    ctx.setLineDash([6 / scale, 4 / scale]);
    ctx.strokeRect(mb.min_x, mb.min_y, mb.width_mm, mb.height_mm);
    ctx.setLineDash([]);

    // Top width dimension bar
    const dimOff = 18 / scale;
    const tick = 5 / scale;
    ctx.strokeStyle = "#808080";
    ctx.lineWidth = 1 / scale;
    ctx.beginPath();
    ctx.moveTo(mb.min_x, mb.min_y - dimOff);
    ctx.lineTo(mb.max_x, mb.min_y - dimOff);
    ctx.moveTo(mb.min_x, mb.min_y - dimOff - tick);
    ctx.lineTo(mb.min_x, mb.min_y - dimOff + tick);
    ctx.moveTo(mb.max_x, mb.min_y - dimOff - tick);
    ctx.lineTo(mb.max_x, mb.min_y - dimOff + tick);
    // Left height dimension bar
    ctx.moveTo(mb.min_x - dimOff, mb.min_y);
    ctx.lineTo(mb.min_x - dimOff, mb.max_y);
    ctx.moveTo(mb.min_x - dimOff - tick, mb.min_y);
    ctx.lineTo(mb.min_x - dimOff + tick, mb.min_y);
    ctx.moveTo(mb.min_x - dimOff - tick, mb.max_y);
    ctx.lineTo(mb.min_x - dimOff + tick, mb.max_y);
    ctx.stroke();

    ctx.fillStyle = "#111111";
    ctx.font = `600 ${11 / scale}px "JetBrains Mono", monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${Math.round(mb.width_mm)} mm`, mb.min_x + mb.width_mm * 0.5, mb.min_y - dimOff - 4 / scale);

    ctx.save();
    ctx.translate(mb.min_x - dimOff - 6 / scale, mb.min_y + mb.height_mm * 0.5);
    ctx.rotate(-Math.PI * 0.5);
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${Math.round(mb.height_mm)} mm`, 0, 0);
    ctx.restore();
    ctx.restore();

    const activeFocusId = hoveredPartId || selectedPartId;

    // Pass 1: Non-highlighted pieces + their squared bounding boxes
    const drawPiece = (it, isHighlighted) => {
      const box = partsBoxMode === "aabb" ? it.aabb_corners_design_mm : it.obb_corners_design_mm;
      const pts = it.points_design_mm || [];
      const isDimmed =
        !isHighlighted &&
        ((selectedGroupKey && it.group_key !== selectedGroupKey) ||
          (activeFocusId && activeFocusId !== it.id));

      // Draw Squared Bounding Box (OBB or AABB)
      if (box && box.length === 4) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(box[0][0], box[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(box[i][0], box[i][1]);
        ctx.closePath();

        if (isHighlighted) {
          ctx.fillStyle = "rgba(232, 176, 36, 0.22)";
          ctx.fill();
          ctx.strokeStyle = "#C78200";
          ctx.lineWidth = 2.6 / scale;
          ctx.stroke();
        } else if (it.prepared) {
          ctx.fillStyle = isDimmed ? "rgba(38, 107, 71, 0.05)" : "rgba(38, 107, 71, 0.13)";
          ctx.fill();
          ctx.strokeStyle = isDimmed ? "rgba(38, 107, 71, 0.25)" : "rgba(38, 107, 71, 0.7)";
          ctx.lineWidth = 1.2 / scale;
          ctx.setLineDash([5 / scale, 4 / scale]);
          ctx.stroke();
        } else {
          ctx.fillStyle = isDimmed ? "rgba(179, 139, 109, 0.03)" : "rgba(179, 139, 109, 0.08)";
          ctx.fill();
          ctx.strokeStyle = isDimmed ? "rgba(140, 103, 75, 0.2)" : "rgba(140, 103, 75, 0.65)";
          ctx.lineWidth = 1.1 / scale;
          ctx.setLineDash([5 / scale, 4 / scale]);
          ctx.stroke();
        }
        ctx.restore();
      }

      // Draw actual polyline geometry
      if (pts.length >= 2) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
        if (it.closed) ctx.closePath();
        ctx.strokeStyle = isHighlighted
          ? "#111111"
          : isDimmed
          ? "rgba(17, 17, 17, 0.18)"
          : it.role === "mill"
          ? "#2C6782"
          : "#B83A2E";
        ctx.lineWidth = (isHighlighted ? 2.4 : 1.5) / scale;
        ctx.stroke();
        ctx.restore();
      }

      // Piece ID pill at center
      const [cx, cy] = it.center_design_mm;
      ctx.save();
      const lbl = isHighlighted
        ? `${it.id} · ${Math.round(it.length_mm)}×${Math.round(it.width_mm)}`
        : it.id;
      ctx.font = `700 ${(isHighlighted ? 11 : 9.5) / scale}px "JetBrains Mono", monospace`;
      const twLbl = ctx.measureText(lbl).width + 10 / scale;
      const thLbl = (isHighlighted ? 19 : 15) / scale;
      ctx.fillStyle = isHighlighted
        ? "#111111"
        : it.prepared
        ? "#266B47"
        : isDimmed
        ? "rgba(255, 255, 255, 0.65)"
        : "rgba(255, 255, 255, 0.94)";
      ctx.fillRect(cx - twLbl * 0.5, cy - thLbl * 0.5, twLbl, thLbl);
      ctx.strokeStyle = isHighlighted ? "#C78200" : it.prepared ? "#266B47" : "#CFC7B8";
      ctx.lineWidth = (isHighlighted ? 1.5 : 1.0) / scale;
      ctx.strokeRect(cx - twLbl * 0.5, cy - thLbl * 0.5, twLbl, thLbl);
      ctx.fillStyle = isHighlighted || it.prepared ? "#FFFFFF" : isDimmed ? "#999999" : "#111111";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(lbl, cx, cy);
      ctx.restore();
    };

    const highlightedList = [];
    items.forEach((it) => {
      const hi =
        (activeFocusId && it.id === activeFocusId) ||
        (!activeFocusId && selectedGroupKey && it.group_key === selectedGroupKey);
      if (hi) highlightedList.push(it);
      else drawPiece(it, false);
    });
    highlightedList.forEach((it) => drawPiece(it, true));

    ctx.restore();
    ctx.restore();
  }

  function syncInput(id, val) {
    const el = $(id);
    if (!el || document.activeElement === el) return;
    el.value = String(val);
  }

  function renderLayerList(design) {
    const sec = $("layersSection");
    const list = $("layerList");
    if (!design || !design.layers || !design.layers.length) {
      sec.classList.add("hidden");
      return;
    }
    sec.classList.remove("hidden");
    list.innerHTML = "";
    design.layers.forEach((ly) => {
      const row = document.createElement("div");
      row.className = "layer-row";
      row.innerHTML = `
        <div class="layer-left">
          <input type="checkbox" ${ly.visible ? "checked" : ""} />
          <span class="layer-dot" style="background:${ly.color || "#B83A2E"}"></span>
          <span class="layer-name" title="${ly.name}">${ly.name} (${ly.entity_count})</span>
        </div>
        <select class="layer-role">
          <option value="cut" ${ly.role === "cut" ? "selected" : ""}>Cut</option>
          <option value="mill" ${ly.role === "mill" ? "selected" : ""}>Mill</option>
          <option value="points" ${ly.role === "points" ? "selected" : ""}>Points</option>
        </select>
      `;
      row.querySelector("input").addEventListener("change", (ev) => {
        postJson("/api/design/layer", { name: ly.name, visible: ev.target.checked });
      });
      row.querySelector("select").addEventListener("change", (ev) => {
        postJson("/api/design/layer", { name: ly.name, role: ev.target.value });
      });
      list.appendChild(row);
    });
  }

  // -------------------------------------------------------------------
  // Overview Camera & Coordinate Helpers
  // -------------------------------------------------------------------
  function resizeCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return { w: 0, h: 0, dpr: 1 };
    const dpr = window.devicePixelRatio || 1;
    const tw = Math.round(rect.width * dpr);
    const th = Math.round(rect.height * dpr);
    if (canvas.width !== tw || canvas.height !== th) {
      canvas.width = tw;
      canvas.height = th;
    }
    return { w: rect.width, h: rect.height, dpr };
  }

  function fitOverviewCamera() {
    if (!state) return;
    const rect = overviewCanvas.getBoundingClientRect();
    const w = Math.max(rect.width, 320);
    const h = Math.max(rect.height, 260);
    let minX = 0;
    let minY = 0;
    let maxX = state.workspace.table_width_mm;
    let maxY = state.workspace.table_height_mm;

    if (state.mosaic.design_bounds) {
      const db = state.mosaic.design_bounds;
      minX = Math.min(minX, db.min_x);
      minY = Math.min(minY, db.min_y);
      maxX = Math.max(maxX, db.max_x);
      maxY = Math.max(maxY, db.max_y);
    }
    const pad = 110;
    const spanX = Math.max(200, maxX - minX + pad * 2);
    const spanY = Math.max(200, maxY - minY + pad * 2);
    cam.zoom = Math.min(w / spanX, h / spanY);
    cam.panX = (w - (maxX - minX) * cam.zoom) * 0.5 - minX * cam.zoom;
    cam.panY = (h - (maxY - minY) * cam.zoom) * 0.5 - minY * cam.zoom;
  }

  const worldToScreen = (wx, wy) => [wx * cam.zoom + cam.panX, wy * cam.zoom + cam.panY];
  const screenToWorld = (sx, sy) => [(sx - cam.panX) / cam.zoom, (sy - cam.panY) / cam.zoom];

  function clipToPolygons(context, polygons) {
    if (!polygons || !polygons.length) return false;
    context.beginPath();
    let hasAny = false;
    polygons.forEach((poly) => {
      if (!poly || poly.length < 3) return;
      context.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) context.lineTo(poly[i][0], poly[i][1]);
      context.closePath();
      hasAny = true;
    });
    if (hasAny) context.clip();
    return hasAny;
  }

  function polyCentroid(pts) {
    if (!pts || !pts.length) return [0, 0];
    let sx = 0;
    let sy = 0;
    pts.forEach((p) => {
      sx += p[0];
      sy += p[1];
    });
    return [sx / pts.length, sy / pts.length];
  }

  // -------------------------------------------------------------------
  // Render Left Pane: Swiss Drafting Table + Master Drawing + Hatched Eliminated Boards + Active Board
  // -------------------------------------------------------------------
  function renderOverview() {
    if (!state || $("overviewPane").classList.contains("hidden")) return;
    const { w, h, dpr } = resizeCanvas(overviewCanvas);
    if (!w || !h) return;

    const ctx = overviewCtx;
    ctx.save();
    ctx.scale(dpr, dpr);

    // Pure white architectural drafting surface
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, w, h);

    // Subtle 200mm Swiss drafting grid
    ctx.save();
    ctx.translate(cam.panX, cam.panY);
    ctx.scale(cam.zoom, cam.zoom);

    const gridStep = 200;
    const [vx0, vy0] = screenToWorld(0, 0);
    const [vx1, vy1] = screenToWorld(w, h);
    ctx.strokeStyle = "#F0ECE4";
    ctx.lineWidth = 1 / cam.zoom;
    ctx.beginPath();
    for (let x = Math.floor(vx0 / gridStep) * gridStep; x <= vx1; x += gridStep) {
      ctx.moveTo(x, vy0);
      ctx.lineTo(x, vy1);
    }
    for (let y = Math.floor(vy0 / gridStep) * gridStep; y <= vy1; y += gridStep) {
      ctx.moveTo(vx0, y);
      ctx.lineTo(vx1, y);
    }
    ctx.stroke();

    // eWoodX calibrated work table surface
    const tw = state.workspace.table_width_mm;
    const th = state.workspace.table_height_mm;
    ctx.fillStyle = "#FAF7F1";
    ctx.fillRect(0, 0, tw, th);
    ctx.strokeStyle = "#CFC7B8";
    ctx.lineWidth = 1.2 / cam.zoom;
    ctx.strokeRect(0, 0, tw, th);

    // ---------------------------------------------------------------
    // 1. Master Drawing (full scale in workspace coordinates)
    // ---------------------------------------------------------------
    const d = state.design;
    const m = state.mosaic;
    const tr = state.transform;
    const dragDx = liveOffX !== null ? liveOffX - tr.offset_x_mm : 0;
    const dragDy = liveOffY !== null ? liveOffY - tr.offset_y_mm : 0;

    if (d) {
      ctx.save();
      ctx.translate(dragDx, dragDy);

      // Master drawing bounding paper backdrop
      if (m.design_corners && m.design_corners.length === 4) {
        ctx.beginPath();
        ctx.moveTo(m.design_corners[0][0], m.design_corners[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(m.design_corners[i][0], m.design_corners[i][1]);
        ctx.closePath();
        ctx.fillStyle = "rgba(255, 255, 255, 0.72)";
        ctx.fill();
        ctx.strokeStyle = "#C7BFB0";
        ctx.lineWidth = 1 / cam.zoom;
        ctx.stroke();
      }

      // Raster PDF/Image in overview
      if (d.has_raster && rasterCache.overview.loaded && rasterCache.overview.img) {
        const sw = m.scaled_width_mm;
        const sh = m.scaled_height_mm;
        const cx = tr.offset_x_mm + sw * 0.5;
        const cy = tr.offset_y_mm + sh * 0.5;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate((tr.rotation_deg * Math.PI) / 180);
        ctx.scale(tr.flip_x ? -1 : 1, tr.flip_y ? -1 : 1);
        ctx.globalAlpha = 0.85;
        ctx.drawImage(rasterCache.overview.img, -sw * 0.5, -sh * 0.5, sw, sh);
        ctx.restore();
      }

      // Vector polylines
      (m.world_design.polylines || []).forEach((pl) => {
        if (pl.points.length < 2) return;
        ctx.beginPath();
        ctx.moveTo(pl.points[0][0], pl.points[0][1]);
        for (let i = 1; i < pl.points.length; i++) ctx.lineTo(pl.points[i][0], pl.points[i][1]);
        ctx.strokeStyle = pl.role === "mill" ? "#2C6782" : "#B83A2E";
        ctx.lineWidth = (pl.role === "mill" ? 1.5 : 1.9) / cam.zoom;
        ctx.stroke();
      });

      // Vector points
      const pr = 4.5 / cam.zoom;
      ctx.strokeStyle = "#266B47";
      ctx.lineWidth = 1.4 / cam.zoom;
      (m.world_design.points || []).forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt.pos[0], pt.pos[1], pr, 0, Math.PI * 2);
        ctx.stroke();
      });

      // -------------------------------------------------------------
      // 2. Progressive Mode: Hatched Eliminated / Completed Boards!
      //    Moves WITH the drawing so operator sees what is already done!
      // -------------------------------------------------------------
      const prog = m.progressive;
      if (state.mosaic_config.mode === "progressive" && prog && prog.completed_regions_world) {
        const pattern = ctx.createPattern(hatchCanvas, "repeat");
        prog.completed_regions_world.forEach((reg) => {
          const poly = reg.polygon_mm;
          if (!poly || poly.length < 3) return;
          const isBeingReviewed = prog.reviewing_index === reg.index;

          ctx.save();
          ctx.beginPath();
          ctx.moveTo(poly[0][0], poly[0][1]);
          for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
          ctx.closePath();

          if (pattern) {
            ctx.save();
            ctx.clip();
            ctx.scale(1 / cam.zoom, 1 / cam.zoom);
            ctx.fillStyle = pattern;
            ctx.fillRect(-10000, -10000, 20000, 20000);
            ctx.restore();
          } else {
            ctx.fillStyle = "rgba(179, 139, 109, 0.25)";
            ctx.fill();
          }

          ctx.strokeStyle = isBeingReviewed ? "#111111" : "#8C674B";
          ctx.lineWidth = (isBeingReviewed ? 2.2 : 1.4) / cam.zoom;
          if (!isBeingReviewed) ctx.setLineDash([7 / cam.zoom, 4 / cam.zoom]);
          ctx.stroke();
          ctx.restore();

          // Stamp Swiss Badge (#1 · 1200×800 + crisp vector check) at region centroid
          const [cx, cy] = polyCentroid(poly);
          const badgeW = 86 / cam.zoom;
          const badgeH = 34 / cam.zoom;
          ctx.save();
          ctx.fillStyle = isBeingReviewed ? "#111111" : "rgba(255, 255, 255, 0.95)";
          ctx.strokeStyle = isBeingReviewed ? "#111111" : "#8C674B";
          ctx.lineWidth = 1.2 / cam.zoom;
          ctx.fillRect(cx - badgeW * 0.5, cy - badgeH * 0.5, badgeW, badgeH);
          ctx.strokeRect(cx - badgeW * 0.5, cy - badgeH * 0.5, badgeW, badgeH);

          // Crisp geometric checkmark (no emoji)
          const chkX = cx - 22 / cam.zoom;
          const chkY = cy - 4 / cam.zoom;
          ctx.beginPath();
          ctx.moveTo(chkX, chkY);
          ctx.lineTo(chkX + 4 / cam.zoom, chkY + 4 / cam.zoom);
          ctx.lineTo(chkX + 11 / cam.zoom, chkY - 5 / cam.zoom);
          ctx.strokeStyle = isBeingReviewed ? "#F5F1E8" : "#266B47";
          ctx.lineWidth = 1.8 / cam.zoom;
          ctx.stroke();

          ctx.fillStyle = isBeingReviewed ? "#FFFFFF" : "#111111";
          ctx.font = `700 ${12 / cam.zoom}px "JetBrains Mono", monospace`;
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.fillText(`#${reg.index}`, cx - 4 / cam.zoom, cy - 5 / cam.zoom);

          ctx.fillStyle = isBeingReviewed ? "#D4CCC0" : "#6B6B6B";
          ctx.font = `500 ${9.5 / cam.zoom}px "JetBrains Mono", monospace`;
          ctx.textAlign = "center";
          ctx.fillText(
            `${Math.round(reg.board_length_mm)}×${Math.round(reg.board_width_mm)}`,
            cx,
            cy + 9 / cam.zoom
          );
          ctx.restore();
        });
      }

      ctx.restore(); // end drag translation
    }

    // ---------------------------------------------------------------
    // 3. Uniform Mosaic Grid (only when in "mosaic" mode)
    // ---------------------------------------------------------------
    if (state.mosaic_config.mode === "mosaic" && m.tiles && m.tiles.length) {
      const activeIdx = m.active_tile ? m.active_tile.index : 0;
      m.tiles.forEach((tile) => {
        const isActive = tile.index === activeIdx;
        ctx.save();
        ctx.fillStyle = isActive ? "rgba(179, 139, 109, 0.14)" : "rgba(255, 255, 255, 0.04)";
        ctx.fillRect(tile.x0, tile.y0, tile.width_mm, tile.height_mm);
        ctx.strokeStyle = isActive ? "#111111" : "#9E9689";
        ctx.lineWidth = (isActive ? 2.2 : 1.1) / cam.zoom;
        if (!isActive) ctx.setLineDash([6 / cam.zoom, 5 / cam.zoom]);
        ctx.strokeRect(tile.x0, tile.y0, tile.width_mm, tile.height_mm);

        const tagW = 48 / cam.zoom;
        const tagH = 20 / cam.zoom;
        ctx.setLineDash([]);
        ctx.fillStyle = isActive ? "#111111" : "#FFFFFF";
        ctx.fillRect(tile.x0 + 6 / cam.zoom, tile.y0 + 6 / cam.zoom, tagW, tagH);
        ctx.strokeStyle = "#111111";
        ctx.lineWidth = 1 / cam.zoom;
        ctx.strokeRect(tile.x0 + 6 / cam.zoom, tile.y0 + 6 / cam.zoom, tagW, tagH);

        ctx.fillStyle = isActive ? "#FFFFFF" : "#111111";
        ctx.font = `600 ${11 / cam.zoom}px "JetBrains Mono", monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(
          `${tile.number}/${tile.total}`,
          tile.x0 + 6 / cam.zoom + tagW * 0.5,
          tile.y0 + 6 / cam.zoom + tagH * 0.5
        );
        ctx.restore();
      });
    }

    // Ghost previous board silhouette & displacement vector when recently re-scanned!
    const rs = state.rescan;
    if (rs && rs.prev_contours_mm && rs.prev_contours_mm.length) {
      rs.prev_contours_mm.forEach((contour) => {
        if (contour.length < 3) return;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(contour[0][0], contour[0][1]);
        for (let i = 1; i < contour.length; i++) ctx.lineTo(contour[i][0], contour[i][1]);
        ctx.closePath();
        ctx.strokeStyle = "rgba(38, 107, 71, 0.55)";
        ctx.lineWidth = 1.6 / cam.zoom;
        ctx.setLineDash([6 / cam.zoom, 5 / cam.zoom]);
        ctx.stroke();
        ctx.restore();
      });

      if (rs.prev_center_mm && rs.new_center_mm) {
        const [x0, y0] = rs.prev_center_mm;
        const [x1, y1] = rs.new_center_mm;
        const dist = Math.hypot(x1 - x0, y1 - y0);
        if (dist > 4) {
          const ang = Math.atan2(y1 - y0, x1 - x0);
          const head = 10 / cam.zoom;
          ctx.save();
          ctx.strokeStyle = "#266B47";
          ctx.fillStyle = "#266B47";
          ctx.lineWidth = 2.2 / cam.zoom;
          ctx.beginPath();
          ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x1 - head * Math.cos(ang - 0.45), y1 - head * Math.sin(ang - 0.45));
          ctx.lineTo(x1 - head * Math.cos(ang + 0.45), y1 - head * Math.sin(ang + 0.45));
          ctx.closePath();
          ctx.fill();

          const dxStr = `${rs.dx_mm >= 0 ? "+" : ""}${Math.round(rs.dx_mm)}`;
          const dyStr = `${rs.dy_mm >= 0 ? "+" : ""}${Math.round(rs.dy_mm)}`;
          const daStr = `${rs.d_angle_deg >= 0 ? "+" : ""}${rs.d_angle_deg.toFixed(1)}°`;
          const lbl = `${t("rescan_tag")} · ${dxStr}, ${dyStr} mm · ${daStr}`;
          const mx = x1 + 48 / cam.zoom;
          const my = Math.max(y0, y1) + 24 / cam.zoom;
          ctx.font = `700 ${10 / cam.zoom}px "JetBrains Mono", monospace`;
          const twLbl = ctx.measureText(lbl).width + 12 / cam.zoom;
          const thLbl = 18 / cam.zoom;
          ctx.fillStyle = "#266B47";
          ctx.fillRect(mx - twLbl * 0.5, my - thLbl * 0.5, twLbl, thLbl);
          ctx.fillStyle = "#FFFFFF";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(lbl, mx, my);
          ctx.restore();
        }
      }
    }

    // ---------------------------------------------------------------
    // 4. Active Scanned Timber Board Contour (Exact Reclaimed Polygon!)
    // ---------------------------------------------------------------
    const isReviewing =
      state.mosaic_config.mode === "progressive" &&
      m.progressive &&
      m.progressive.reviewing_index !== null;

    state.board.contours_mm.forEach((contour) => {
      if (contour.length < 3) return;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(contour[0][0], contour[0][1]);
      for (let i = 1; i < contour.length; i++) ctx.lineTo(contour[i][0], contour[i][1]);
      ctx.closePath();
      ctx.fillStyle = "rgba(179, 139, 109, 0.13)";
      ctx.fill();
      ctx.strokeStyle = isReviewing ? "#8C674B" : "#111111";
      ctx.lineWidth = 2.5 / cam.zoom;
      if (isReviewing) ctx.setLineDash([8 / cam.zoom, 5 / cam.zoom]);
      ctx.stroke();
      ctx.restore();
    });

    // Timber holes & defects
    (state.board.holes_mm || []).forEach((hole) => {
      if (hole.length < 3) return;
      ctx.beginPath();
      ctx.moveTo(hole[0][0], hole[0][1]);
      for (let i = 1; i < hole.length; i++) ctx.lineTo(hole[i][0], hole[i][1]);
      ctx.closePath();
      ctx.fillStyle = "rgba(184, 58, 46, 0.12)";
      ctx.fill();
      ctx.strokeStyle = "#B83A2E";
      ctx.lineWidth = 1.4 / cam.zoom;
      ctx.stroke();
    });

    (state.board.defects || []).forEach((def) => {
      if (def.x_mm === undefined || def.y_mm === undefined) return;
      const r = Math.max(8, (def.diameter_mm || 20) * 0.5);
      ctx.beginPath();
      ctx.arc(def.x_mm, def.y_mm, r, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(184, 58, 46, 0.7)";
      ctx.lineWidth = 1.3 / cam.zoom;
      ctx.stroke();
    });

    // Active board overlap JOINT CUT LINES (where to saw newly placed board!)
    if (
      state.mosaic_config.mode === "progressive" &&
      m.progressive &&
      m.progressive.joint_cut_lines &&
      m.progressive.joint_cut_lines.length
    ) {
      m.progressive.joint_cut_lines.forEach((jc) => {
        const p0 = jc.points[0];
        const p1 = jc.points[1];
        const dx = p1[0] - p0[0];
        const dy = p1[1] - p0[1];
        const len = Math.max(1, Math.hypot(dx, dy));
        const nx = -dy / len;
        const ny = dx / len;
        const tick = 9 / cam.zoom;

        ctx.save();
        // Crisp white halo under amber saw line so it stands out cleanly on the drafting table
        ctx.strokeStyle = "rgba(255, 255, 255, 0.92)";
        ctx.lineWidth = 6.0 / cam.zoom;
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.stroke();

        // Deep Swiss Amber saw-cut line with clean architectural end ticks
        ctx.strokeStyle = "#C78200";
        ctx.lineWidth = 3.0 / cam.zoom;
        ctx.setLineDash([12 / cam.zoom, 5 / cam.zoom]);
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.stroke();

        ctx.setLineDash([]);
        ctx.lineWidth = 2.4 / cam.zoom;
        ctx.beginPath();
        ctx.moveTo(p0[0] - nx * tick, p0[1] - ny * tick);
        ctx.lineTo(p0[0] + nx * tick, p0[1] + ny * tick);
        ctx.moveTo(p1[0] - nx * tick, p1[1] - ny * tick);
        ctx.lineTo(p1[0] + nx * tick, p1[1] + ny * tick);
        ctx.stroke();

        // Sharp localized pill badge: CORTE #1 · 800mm
        const btag = (jc.from_boards || [jc.from_board]).map((n) => `#${n}`).join("/");
        const lbl = `${t("cut_word")} ${btag} · ${Math.round(jc.length_mm)}mm`;
        const mx = 0.5 * (p0[0] + p1[0]) + (jc.kept_normal ? jc.kept_normal[0] : 0) * (18 / cam.zoom);
        const my = 0.5 * (p0[1] + p1[1]) + (jc.kept_normal ? jc.kept_normal[1] : 0) * (18 / cam.zoom);
        ctx.font = `700 ${10.5 / cam.zoom}px "JetBrains Mono", monospace`;
        const twLbl = ctx.measureText(lbl).width + 12 / cam.zoom;
        const thLbl = 18 / cam.zoom;
        ctx.fillStyle = "#C78200";
        ctx.fillRect(mx - twLbl * 0.5, my - thLbl * 0.5, twLbl, thLbl);
        ctx.fillStyle = "#FFFFFF";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(lbl, mx, my);
        ctx.restore();
      });
    }

    // Active board registration fiducials (inherited + new) in progressive mode
    if (
      state.mosaic_config.mode === "progressive" &&
      state.mosaic_config.show_registration_marks &&
      m.progressive
    ) {
      const drawFid = (fid, inherited) => {
        const [fx, fy] = fid.pos_mm;
        const r = (inherited ? 8.5 : 6.5) / cam.zoom;
        ctx.save();
        ctx.strokeStyle = "#266B47";
        ctx.lineWidth = (inherited ? 2.2 : 1.5) / cam.zoom;
        ctx.beginPath();
        ctx.arc(fx, fy, r, 0, Math.PI * 2);
        if (inherited) {
          ctx.moveTo(fx + r * 1.55, fy);
          ctx.arc(fx, fy, r * 1.55, 0, Math.PI * 2);
        }
        ctx.moveTo(fx - r * 2.0, fy);
        ctx.lineTo(fx + r * 2.0, fy);
        ctx.moveTo(fx, fy - r * 2.0);
        ctx.lineTo(fx, fy + r * 2.0);
        ctx.stroke();

        // Crisp label pill
        const lbl = fid.code;
        ctx.font = `700 ${10 / cam.zoom}px "JetBrains Mono", monospace`;
        const twLbl = ctx.measureText(lbl).width + 8 / cam.zoom;
        const thLbl = 15 / cam.zoom;
        const lx = fx + 9 / cam.zoom;
        const ly = fy - 17 / cam.zoom;
        ctx.fillStyle = inherited ? "#266B47" : "#FFFFFF";
        ctx.fillRect(lx, ly, twLbl, thLbl);
        ctx.strokeStyle = "#266B47";
        ctx.lineWidth = 1 / cam.zoom;
        ctx.strokeRect(lx, ly, twLbl, thLbl);
        ctx.fillStyle = inherited ? "#FFFFFF" : "#266B47";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(lbl, lx + 4 / cam.zoom, ly + thLbl * 0.5);
        ctx.restore();
      };

      (m.progressive.new_fiducials || []).forEach((f) => drawFid(f, false));
      (m.progressive.inherited_fiducials || []).forEach((f) => drawFid(f, true));
    }

    // Active board index pill in top-left of scanned board
    if (d && state.mosaic_config.mode === "progressive" && m.progressive) {
      const bb = state.board.bounds;
      const numStr = `#${m.progressive.active_board_number}`;
      const pw = 36 / cam.zoom;
      const ph = 20 / cam.zoom;
      ctx.save();
      ctx.fillStyle = "#111111";
      ctx.fillRect(bb.min_x + 8 / cam.zoom, bb.min_y + 8 / cam.zoom, pw, ph);
      ctx.fillStyle = "#FFFFFF";
      ctx.font = `700 ${11 / cam.zoom}px "JetBrains Mono", monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(numStr, bb.min_x + 8 / cam.zoom + pw * 0.5, bb.min_y + 8 / cam.zoom + ph * 0.5);
      ctx.restore();
    }

    ctx.restore();

    // Empty-state prompt when no drawing loaded
    if (!d) {
      ctx.save();
      ctx.fillStyle = "rgba(17, 17, 17, 0.55)";
      ctx.font = '600 14px "Helvetica Neue", Arial, sans-serif';
      ctx.textAlign = "center";
      ctx.fillText(t("empty_drop"), w * 0.5, h * 0.5);
      ctx.restore();
    }

    ctx.restore();
  }

  // -------------------------------------------------------------------
  // Render Right Pane: Exact Active Board Projection Preview
  // -------------------------------------------------------------------
  function renderProjectorPreview() {
    if (!state || $("previewPane").classList.contains("hidden")) return;
    const { w, h, dpr } = resizeCanvas(previewCanvas);
    if (!w || !h) return;

    const ctx = previewCtx;
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#141414";
    ctx.fillRect(0, 0, w, h);

    if (state.projector_display.blanked) {
      ctx.fillStyle = "#6B6B6B";
      ctx.font = '600 13px "JetBrains Mono", monospace';
      ctx.textAlign = "center";
      ctx.fillText(t("cap_blanked"), w * 0.5, h * 0.5);
      ctx.restore();
      return;
    }

    const tw = state.workspace.table_width_mm;
    const th = state.workspace.table_height_mm;
    const pad = 26;
    const scale = Math.min((w - pad * 2) / tw, (h - pad * 2) / th);
    const ox = (w - tw * scale) * 0.5;
    const oy = (h - th * scale) * 0.5;

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);

    // Table outline
    ctx.strokeStyle = "#2A2A2A";
    ctx.lineWidth = 1.2 / scale;
    ctx.strokeRect(0, 0, tw, th);

    // Subtle ghost of previous board position on dark projector preview right after Re-Scan
    const rsPrev = state.rescan;
    if (rsPrev && rsPrev.prev_contours_mm && rsPrev.prev_contours_mm.length) {
      rsPrev.prev_contours_mm.forEach((contour) => {
        if (contour.length < 3) return;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(contour[0][0], contour[0][1]);
        for (let i = 1; i < contour.length; i++) ctx.lineTo(contour[i][0], contour[i][1]);
        ctx.closePath();
        ctx.strokeStyle = "rgba(96, 184, 134, 0.35)";
        ctx.lineWidth = 1.4 / scale;
        ctx.setLineDash([7 / scale, 6 / scale]);
        ctx.stroke();
        ctx.restore();
      });
    }

    // Board contour on dark surface
    if (state.projector_display.show_board_contour) {
      state.board.contours_mm.forEach((contour) => {
        if (contour.length < 3) return;
        ctx.beginPath();
        ctx.moveTo(contour[0][0], contour[0][1]);
        for (let i = 1; i < contour.length; i++) ctx.lineTo(contour[i][0], contour[i][1]);
        ctx.closePath();
        ctx.fillStyle = "rgba(245, 241, 232, 0.04)";
        ctx.fill();
        ctx.strokeStyle = "#F5F1E8";
        ctx.lineWidth = 1.8 / scale;
        ctx.stroke();
      });

      (state.board.holes_mm || []).forEach((hole) => {
        if (hole.length < 3) return;
        ctx.beginPath();
        ctx.moveTo(hole[0][0], hole[0][1]);
        for (let i = 1; i < hole.length; i++) ctx.lineTo(hole[i][0], hole[i][1]);
        ctx.closePath();
        ctx.strokeStyle = "#A09888";
        ctx.lineWidth = 1.4 / scale;
        ctx.stroke();
      });
    }

    const pg = state.mosaic.projection_geometry;

    // Clipped Raster PDF / Image (supports exact rotated polygon clipping!)
    if (
      state.design &&
      state.design.has_raster &&
      pg.raster_transform &&
      rasterCache.preview.loaded &&
      rasterCache.preview.img
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
        rasterCache.preview.img,
        -rt.width_mm * 0.5,
        -rt.height_mm * 0.5,
        rt.width_mm,
        rt.height_mm
      );
      ctx.restore();
    }

    // Overlap Trim Waste Polygons (masks out already-projected overlap side + amber offcut hatch!)
    const trimPolys = pg.overlap_trim_polygons || [];
    if (trimPolys.length) {
      const trimPat = ctx.createPattern(trimHatchCanvas, "repeat");
      trimPolys.forEach((tp) => {
        const poly = tp.polygon_mm;
        if (!poly || poly.length < 3) return;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(poly[0][0], poly[0][1]);
        for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
        ctx.closePath();
        if (trimPat) {
          ctx.save();
          ctx.clip();
          ctx.scale(1 / scale, 1 / scale);
          ctx.fillStyle = trimPat;
          ctx.fillRect(-10000, -10000, 20000, 20000);
          ctx.restore();
        } else {
          ctx.fillStyle = "rgba(20, 20, 20, 0.92)";
          ctx.fill();
        }

        // Subtle TRIM/SOBRANTE tag centered inside large enough offcut strips
        if (tp.area_mm2 > 22000) {
          const [tcx, tcy] = polyCentroid(poly);
          ctx.fillStyle = "rgba(232, 176, 36, 0.65)";
          ctx.font = `600 ${9.5 / scale}px "JetBrains Mono", monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(t("trim_word"), tcx, tcy);
        }
        ctx.restore();
      });
    }

    // Tile border / seam lines (mosaic mode only — progressive uses dedicated joint_cut_lines)
    (pg.tile_border || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.save();
      ctx.setLineDash([8 / scale, 6 / scale]);
      ctx.strokeStyle = "rgba(179, 139, 109, 0.8)";
      ctx.lineWidth = 1.4 / scale;
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
        ctx.setLineDash([6 / scale, 5 / scale]);
        ctx.strokeStyle = "rgba(96, 184, 134, 0.72)";
        ctx.lineWidth = 1.4 / scale;
        ctx.beginPath();
        ctx.moveTo(line[0][0], line[0][1]);
        ctx.lineTo(line[1][0], line[1][1]);
        ctx.stroke();
        ctx.restore();
      });
    }

    // Mill paths (muted cyan)
    ctx.strokeStyle = "#62B3D1";
    ctx.lineWidth = 1.9 / scale;
    (pg.mill_geo || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.stroke();
    });

    // Cut paths (high-contrast terracotta red)
    ctx.strokeStyle = "#E05A4F";
    ctx.lineWidth = 2.3 / scale;
    (pg.cut_geo || []).forEach((poly) => {
      if (poly.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.stroke();
    });

    // Projected Overlap JOINT CUT LINES (vivid Swiss Gold/Amber saw line on dark projector!)
    (pg.joint_cut_lines || []).forEach((jc) => {
      const p0 = jc.points[0];
      const p1 = jc.points[1];
      const dx = p1[0] - p0[0];
      const dy = p1[1] - p0[1];
      const len = Math.max(1, Math.hypot(dx, dy));
      const nx = -dy / len;
      const ny = dx / len;
      const tick = 10 / scale;

      ctx.save();
      ctx.strokeStyle = "#E8B024";
      ctx.lineWidth = 3.2 / scale;
      ctx.setLineDash([12 / scale, 5 / scale]);
      ctx.beginPath();
      ctx.moveTo(p0[0], p0[1]);
      ctx.lineTo(p1[0], p1[1]);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.lineWidth = 2.4 / scale;
      ctx.beginPath();
      ctx.moveTo(p0[0] - nx * tick, p0[1] - ny * tick);
      ctx.lineTo(p0[0] + nx * tick, p0[1] + ny * tick);
      ctx.moveTo(p1[0] - nx * tick, p1[1] - ny * tick);
      ctx.lineTo(p1[0] + nx * tick, p1[1] + ny * tick);
      ctx.stroke();

      const btag = (jc.from_boards || [jc.from_board]).map((n) => `#${n}`).join("/");
      const lbl = `${t("cut_word")} ${btag} · ${Math.round(jc.length_mm)}mm`;
      const mx = 0.5 * (p0[0] + p1[0]) + (jc.kept_normal ? jc.kept_normal[0] : 0) * (20 / scale);
      const my = 0.5 * (p0[1] + p1[1]) + (jc.kept_normal ? jc.kept_normal[1] : 0) * (20 / scale);
      ctx.font = `700 ${11 / scale}px "JetBrains Mono", monospace`;
      const twLbl = ctx.measureText(lbl).width + 12 / scale;
      const thLbl = 18 / scale;
      ctx.fillStyle = "#E8B024";
      ctx.fillRect(mx - twLbl * 0.5, my - thLbl * 0.5, twLbl, thLbl);
      ctx.fillStyle = "#111111";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(lbl, mx, my);
      ctx.restore();
    });

    // Registration fiducials & drill points
    const r = 7 / scale;
    ctx.strokeStyle = "#60B886";
    ctx.lineWidth = 1.8 / scale;
    (pg.points_geo || []).forEach((pt) => {
      ctx.beginPath();
      ctx.arc(pt[0], pt[1], r, 0, Math.PI * 2);
      ctx.moveTo(pt[0] - r * 1.6, pt[1]);
      ctx.lineTo(pt[0] + r * 1.6, pt[1]);
      ctx.moveTo(pt[0], pt[1] - r * 1.6);
      ctx.lineTo(pt[0], pt[1] + r * 1.6);
      ctx.stroke();
    });

    // Labels (skip raw CUT #... labels already rendered as crisp localized pills above)
    ctx.fillStyle = "#E8DFC8";
    ctx.font = `500 ${11.5 / scale}px "JetBrains Mono", monospace`;
    (pg.labels || []).forEach((lb) => {
      if (lb.text && lb.text.startsWith("CUT #")) return;
      ctx.fillText(lb.text, lb.pos[0], lb.pos[1]);
    });

    ctx.restore();
    ctx.restore();
  }

  function renderAll() {
    renderOverview();
    renderProjectorPreview();
    renderPartsCanvas();
  }

  // -------------------------------------------------------------------
  // Canvas Pointer & Wheel Interaction
  // -------------------------------------------------------------------
  overviewCanvas.addEventListener("pointerdown", (ev) => {
    if (!state) return;
    const rect = overviewCanvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const [wx, wy] = screenToWorld(sx, sy);

    drag.startScreenX = sx;
    drag.startScreenY = sy;
    drag.moved = false;

    const isPanBtn = ev.button === 1 || ev.button === 2 || ev.shiftKey;
    if (isPanBtn || !state.design || state.transform.locked_to_board) {
      drag.mode = "pan";
      drag.startOffX = cam.panX;
      drag.startOffY = cam.panY;
    } else {
      drag.mode = "design";
      drag.startOffX = state.transform.offset_x_mm;
      drag.startOffY = state.transform.offset_y_mm;
      liveOffX = drag.startOffX;
      liveOffY = drag.startOffY;
    }
    overviewCanvas.setPointerCapture(ev.pointerId);
  });

  overviewCanvas.addEventListener("pointermove", (ev) => {
    if (!state) return;
    const rect = overviewCanvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const [wx, wy] = screenToWorld(sx, sy);
    $("cursorCoords").textContent = `X ${wx.toFixed(1)} · Y ${wy.toFixed(1)} mm`;

    if (!drag.mode) return;
    const dxPx = sx - drag.startScreenX;
    const dyPx = sy - drag.startScreenY;
    if (Math.hypot(dxPx, dyPx) > 3) drag.moved = true;

    if (drag.mode === "pan") {
      cam.panX = drag.startOffX + dxPx;
      cam.panY = drag.startOffY + dyPx;
      renderOverview();
    } else if (drag.mode === "design") {
      liveOffX = drag.startOffX + dxPx / cam.zoom;
      liveOffY = drag.startOffY + dyPx / cam.zoom;
      renderOverview();
      if (!dragTimer) {
        dragTimer = setTimeout(() => {
          dragTimer = null;
          if (liveOffX !== null && liveOffY !== null) {
            postJson("/api/transform", { offset_x_mm: liveOffX, offset_y_mm: liveOffY }).catch(() => {});
          }
        }, 70);
      }
    }
  });

  overviewCanvas.addEventListener("pointerup", (ev) => {
    if (!drag.mode) return;
    const mode = drag.mode;
    const moved = drag.moved;
    drag.mode = null;
    try {
      overviewCanvas.releasePointerCapture(ev.pointerId);
    } catch (_) {}

    if (mode === "design" && moved && liveOffX !== null && liveOffY !== null) {
      clearTimeout(dragTimer);
      dragTimer = null;
      const fx = liveOffX;
      const fy = liveOffY;
      liveOffX = null;
      liveOffY = null;
      postJson("/api/transform", { offset_x_mm: fx, offset_y_mm: fy });
      return;
    }

    liveOffX = null;
    liveOffY = null;

    // Click tile in uniform mosaic mode
    if (!moved && state && state.mosaic_config.mode === "mosaic" && state.mosaic.tiles.length) {
      const rect = overviewCanvas.getBoundingClientRect();
      const [wx, wy] = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      const hit = state.mosaic.tiles.find(
        (tile) => wx >= tile.x0 && wx <= tile.x1 && wy >= tile.y0 && wy <= tile.y1
      );
      if (hit) postJson("/api/mosaic", { active_tile_index: hit.index });
    }
  });

  overviewCanvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = overviewCanvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const [wx, wy] = screenToWorld(sx, sy);
    const factor = ev.deltaY < 0 ? 1.14 : 1 / 1.14;
    cam.zoom = Math.max(0.05, Math.min(6.0, cam.zoom * factor));
    cam.panX = sx - wx * cam.zoom;
    cam.panY = sy - wy * cam.zoom;
    renderOverview();
  });

  overviewCanvas.addEventListener("contextmenu", (ev) => ev.preventDefault());

  // -------------------------------------------------------------------
  // Scale Modal (PDF: 1:1 Real OR Scale Ratio · Image: Physical mm)
  // -------------------------------------------------------------------
  function openScaleModal() {
    if (!state || !state.design || state.design.scale_locked) return;
    const d = state.design;
    const isPdf = d.file_format === "pdf";
    const s = state.mosaic.effective_scale || 1.0;

    $("scaleModalTitle").textContent = isPdf ? t("scale_title_pdf") : t("scale_title_img");
    $("scaleModalDesc").textContent = isPdf ? t("scale_desc_pdf") : t("scale_desc_img");
    $("pdfScalePresetRow").classList.toggle("hidden", !isPdf);

    $("modalScaleFactor").value = Number(s.toFixed(3));
    $("modalTargetWidth").value = Math.round(d.base_width_mm * s);
    $("modalTargetHeight").value = Math.round(d.base_height_mm * s);
    $("modalBaseSize").textContent = `${Math.round(d.base_width_mm)} × ${Math.round(d.base_height_mm)} mm`;
    updateModalPreview();
    $("scaleModal").classList.remove("hidden");
  }

  function updateModalPreview() {
    if (!state || !state.design) return;
    const d = state.design;
    const s = Math.max(0.005, parseFloat($("modalScaleFactor").value) || 1.0);
    $("modalFinalSize").textContent = `${Math.round(d.base_width_mm * s)} × ${Math.round(d.base_height_mm * s)} mm`;
  }

  document.querySelectorAll(".scale-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!state || !state.design) return;
      const s = parseFloat(btn.dataset.scale) || 1.0;
      $("modalScaleFactor").value = s;
      $("modalTargetWidth").value = Math.round(state.design.base_width_mm * s);
      $("modalTargetHeight").value = Math.round(state.design.base_height_mm * s);
      updateModalPreview();
    });
  });

  $("modalScaleFactor").addEventListener("input", () => {
    if (!state || !state.design) return;
    const s = Math.max(0.005, parseFloat($("modalScaleFactor").value) || 1.0);
    $("modalTargetWidth").value = Math.round(state.design.base_width_mm * s);
    $("modalTargetHeight").value = Math.round(state.design.base_height_mm * s);
    updateModalPreview();
  });

  $("modalTargetWidth").addEventListener("input", () => {
    if (!state || !state.design) return;
    const tw = Math.max(10, parseFloat($("modalTargetWidth").value) || 100);
    const s = tw / Math.max(state.design.base_width_mm, 1e-6);
    $("modalScaleFactor").value = Number(s.toFixed(3));
    $("modalTargetHeight").value = Math.round(state.design.base_height_mm * s);
    updateModalPreview();
  });

  $("modalTargetHeight").addEventListener("input", () => {
    if (!state || !state.design) return;
    const th = Math.max(10, parseFloat($("modalTargetHeight").value) || 100);
    const s = th / Math.max(state.design.base_height_mm, 1e-6);
    $("modalScaleFactor").value = Number(s.toFixed(3));
    $("modalTargetWidth").value = Math.round(state.design.base_width_mm * s);
    updateModalPreview();
  });

  $("btnScaleModalCancel").addEventListener("click", () => {
    $("scaleModal").classList.add("hidden");
    postJson("/api/transform", { confirm_scale: true }).catch(() => {});
  });

  $("btnScaleModalConfirm").addEventListener("click", async () => {
    const s = Math.max(0.005, parseFloat($("modalScaleFactor").value) || 1.0);
    $("scaleModal").classList.add("hidden");
    await postJson("/api/transform", { scale: s, confirm_scale: true });
    fitOverviewCamera();
    renderOverview();
  });

  // -------------------------------------------------------------------
  // File Upload & Global Drag-and-Drop
  // -------------------------------------------------------------------
  async function handleFileUpload(file) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    const fd = new FormData();
    fd.append("file", file);

    if (lower.endsWith(".json")) {
      const data = await api("/api/board/upload", { method: "POST", body: fd });
      applyState(data);
      showToast(`${t("toast_scanned")}: ${file.name}`);
    } else {
      const data = await api("/api/design/upload", { method: "POST", body: fd });
      applyState(data);
      showToast(`${t("toast_loaded")}: ${file.name}`);
    }
  }

  let dragDepth = 0;
  window.addEventListener("dragenter", (ev) => {
    ev.preventDefault();
    dragDepth++;
    $("dropVeil").classList.remove("hidden");
  });
  window.addEventListener("dragleave", (ev) => {
    ev.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) $("dropVeil").classList.add("hidden");
  });
  window.addEventListener("dragover", (ev) => ev.preventDefault());
  window.addEventListener("drop", (ev) => {
    ev.preventDefault();
    dragDepth = 0;
    $("dropVeil").classList.add("hidden");
    const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });

  // -------------------------------------------------------------------
  // Views & OpenCV Live Sandbox Preview
  // -------------------------------------------------------------------
  function setView(view) {
    currentView = view;
    document.querySelectorAll(".nav-tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    const sv = $("stageViews");
    sv.classList.toggle("split", view === "split");
    $("overviewPane").classList.toggle("hidden", view === "projector" || view === "opencv" || view === "parts");
    $("previewPane").classList.toggle("hidden", view === "overview" || view === "opencv" || view === "parts");
    $("opencvPane").classList.toggle("hidden", view !== "opencv");
    $("partsPane").classList.toggle("hidden", view !== "parts");

    clearInterval(opencvTimer);
    if (view === "opencv") {
      refreshOpencvFrame(true);
      opencvTimer = setInterval(() => refreshOpencvFrame(false), 900);
    } else {
      if (state) updateUI();
      setTimeout(() => {
        fitOverviewCamera();
        renderAll();
      }, 30);
    }
  }

  function refreshOpencvFrame(force) {
    if (!state || !state.sandbox || !state.sandbox.enabled) return;
    if (!force && state.revision === lastOpencvRev) return;
    lastOpencvRev = state.revision;
    $("opencvFrameImg").src = `/api/sandbox/opencv-frame?t=${Date.now()}`;
  }

  function openProjectorWindow() {
    const url = `/projector?lang=${encodeURIComponent(lang)}`;
    if (!projectorWin || projectorWin.closed) {
      projectorWin = window.open(url, "eWoodXProjector", "width=1280,height=800");
    } else {
      projectorWin.focus();
    }
  }

  // -------------------------------------------------------------------
  // Button Wiring (Core 4 Kiosk Actions + Canvas Tools + Drawer)
  // -------------------------------------------------------------------
  document.querySelectorAll(".nav-tab").forEach((b) => {
    b.addEventListener("click", () => setView(b.dataset.view));
  });

  document.querySelectorAll("#langSwitch button").forEach((b) => {
    b.addEventListener("click", () => applyLanguage(b.dataset.lang));
  });

  // Drawer open/close
  $("btnOpenDrawer").addEventListener("click", () => $("settingsDrawer").classList.remove("hidden"));
  $("btnCloseDrawer").addEventListener("click", () => $("settingsDrawer").classList.add("hidden"));
  $("settingsDrawer").addEventListener("click", (ev) => {
    if (ev.target === $("settingsDrawer")) $("settingsDrawer").classList.add("hidden");
  });

  // 1. SCAN (Next board) + RE-SCAN (Same bumped/moved board -> rigid re-anchor & re-project)
  $("btnScan").addEventListener("click", async () => {
    await postJson("/api/scan");
    showToast(`${t("toast_scanned")} · ${Math.round(state.board.length_mm)}×${Math.round(state.board.width_mm)} mm`);
  });

  $("btnRescan").addEventListener("click", async () => {
    const data = await postJson("/api/rescan", { auto_project: true });
    const btn = $("btnRescan");
    btn.classList.add("rescan-flash");
    setTimeout(() => btn.classList.remove("rescan-flash"), 950);
    const rs = data && data.rescan;
    if (rs) {
      const dxStr = `${rs.dx_mm >= 0 ? "+" : ""}${Math.round(rs.dx_mm)}`;
      const dyStr = `${rs.dy_mm >= 0 ? "+" : ""}${Math.round(rs.dy_mm)}`;
      const daStr = `${rs.d_angle_deg >= 0 ? "+" : ""}${rs.d_angle_deg.toFixed(1)}°`;
      const prefix = rs.size_match ? t("toast_rescanned") : t("toast_rescan_warn");
      showToast(`${prefix} · ${dxStr}, ${dyStr} mm · ${daStr}`);
    } else {
      showToast(t("toast_rescanned"));
    }
  });

  $("btnRescanJsonUpload").addEventListener("click", () => $("rescanJsonInput").click());
  $("rescanJsonInput").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    ev.target.value = "";
    const fd = new FormData();
    fd.append("file", file);
    const data = await api("/api/rescan/upload", { method: "POST", body: fd });
    if (data && data.state) applyState(data.state);
    showToast(t("toast_rescanned"));
  });

  // 2. UPLOAD + Quick Demo Links + Clickable Scale Badge
  $("btnUploadDrawing").addEventListener("click", () => $("designFileInput").click());
  $("designFileInput").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (file) handleFileUpload(file);
    ev.target.value = "";
  });

  $("btnSampleDxf").addEventListener("click", async () => {
    await postJson("/api/design/sample/mosaic_large_dxf");
    showToast(`${t("toast_loaded")}: DXF 1:1`);
  });
  $("btnSampleAsm").addEventListener("click", async () => {
    await postJson("/api/design/sample/assembly_frame_dxf");
    showToast(`${t("toast_loaded")}: Assembly DXF 1:1`);
  });
  $("btnSamplePdf").addEventListener("click", async () => {
    promptedDesignId = null;
    await postJson("/api/design/sample/blueprint_pdf");
  });
  $("btnSampleImg").addEventListener("click", async () => {
    promptedDesignId = null;
    await postJson("/api/design/sample/sketch_png");
  });

  // Parts / Assembly tab controls
  document.querySelectorAll("#partsBoxSwitch button").forEach((btn) => {
    btn.addEventListener("click", () => {
      partsBoxMode = btn.dataset.box || "obb";
      document.querySelectorAll("#partsBoxSwitch button").forEach((b) => {
        b.classList.toggle("active", b.dataset.box === partsBoxMode);
      });
      updatePartsPanel();
      renderPartsCanvas();
    });
  });

  $("btnExportPartsCsv").addEventListener("click", () => {
    window.open("/api/export/parts-csv", "_blank");
  });

  $("btnResetParts").addEventListener("click", () => {
    postJson("/api/parts/toggle", { reset: true });
  });

  $("designScaleBadge").addEventListener("click", () => {
    if (state && state.design && !state.design.scale_locked) openScaleModal();
  });

  // 3. BACK / NEXT (Progressive Stamp & Auto-Nest OR Mosaic Tile Step)
  $("btnPrevTile").addEventListener("click", () => postJson("/api/step/back"));
  $("btnNextTile").addEventListener("click", async () => {
    const wasProg = state && state.mosaic_config.mode === "progressive";
    const wasReview = wasProg && state.mosaic.progressive && state.mosaic.progressive.reviewing_index !== null;
    await postJson("/api/step/next");
    if (wasProg && !wasReview) {
      showToast(`${t("toast_stamped")} (${Math.round(state.mosaic.progressive.coverage_pct)}%)`);
    }
  });

  // 4. SEND DRAWING + BLACKOUT
  $("btnSendDrawing").addEventListener("click", async () => {
    await postJson("/api/send");
    const btn = $("btnSendDrawing");
    btn.classList.add("sent-flash");
    const span = btn.querySelector("span");
    if (span) span.textContent = t("sent");
    showToast(t("toast_sent"));
    setTimeout(() => {
      btn.classList.remove("sent-flash");
      if (span) span.textContent = t("send");
    }, 1100);
  });

  $("btnBlankProjector").addEventListener("click", () => {
    if (!state) return;
    postJson("/api/projector/display", { blanked: !state.projector_display.blanked });
  });

  // Canvas 4 Universal Tools (Lock · Auto-Nest · Rotate 90° · Undo)
  $("btnToggleLock").addEventListener("click", async () => {
    if (!state || !state.design) return;
    const nextLock = !state.transform.locked_to_board;
    await postJson("/api/transform", { locked_to_board: nextLock });
    showToast(nextLock ? t("toast_locked") : t("toast_unlocked"));
  });

  $("btnAutoNest").addEventListener("click", async () => {
    if (!state || !state.design) return;
    if (state.mosaic_config.mode === "progressive") {
      await postJson("/api/progressive/auto-nest");
      showToast(t("toast_nested"));
    } else {
      await postJson("/api/transform", { action: "center_on_board" });
    }
  });

  $("btnRotPlus90").addEventListener("click", () => {
    if (!state || !state.design) return;
    postJson("/api/transform", { delta_rotation_deg: 90 });
  });

  $("btnUndoRegion").addEventListener("click", async () => {
    if (!state) return;
    await postJson("/api/progressive/undo");
    showToast(t("toast_undone"));
  });

  // Zoom controls
  $("btnZoomIn").addEventListener("click", () => {
    cam.zoom = Math.min(6.0, cam.zoom * 1.22);
    renderOverview();
  });
  $("btnZoomOut").addEventListener("click", () => {
    cam.zoom = Math.max(0.05, cam.zoom / 1.22);
    renderOverview();
  });
  $("btnZoomFit").addEventListener("click", () => {
    fitOverviewCamera();
    renderOverview();
  });

  // Drawer Controls
  $("modeSelect").addEventListener("change", (ev) => postJson("/api/mosaic", { mode: ev.target.value }));
  $("overlapInput").addEventListener("change", (ev) =>
    postJson("/api/mosaic", { overlap_mm: parseFloat(ev.target.value) || 0 })
  );
  $("marginInput").addEventListener("change", (ev) =>
    postJson("/api/mosaic", { margin_mm: parseFloat(ev.target.value) || 0 })
  );
  $("chkRegMarks").addEventListener("change", (ev) =>
    postJson("/api/mosaic", { show_registration_marks: ev.target.checked })
  );
  $("btnResetRegions").addEventListener("click", async () => {
    await postJson("/api/progressive/reset");
    showToast(t("toast_reset"));
  });
  $("btnCenterBoard").addEventListener("click", () =>
    postJson("/api/transform", { action: "center_on_board" })
  );

  $("boardScenarioSelect").addEventListener("change", async (ev) => {
    const sid = ev.target.value;
    if (state && state.sandbox && state.sandbox.enabled) {
      await postJson(`/api/sandbox/emit/${encodeURIComponent(sid)}`);
    } else {
      await postJson(`/api/board/scenario/${encodeURIComponent(sid)}`);
    }
    showToast(t("toast_scanned"));
  });

  $("btnUploadBoardJson").addEventListener("click", () => $("boardJsonInput").click());
  $("boardJsonInput").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (file) handleFileUpload(file);
    ev.target.value = "";
  });

  $("btnApplyCustomBoard").addEventListener("click", () => {
    postJson("/api/board/custom", {
      length_mm: parseFloat($("customBoardW").value) || 1200,
      width_mm: parseFloat($("customBoardH").value) || 800,
      thickness_mm: parseFloat($("customBoardT").value) || 22,
      angle_deg: parseFloat($("customBoardA").value) || 0,
    });
  });

  $("btnSbNudgeRight").addEventListener("click", () =>
    postJson("/api/sandbox/nudge-board", { dx_mm: 40, dy_mm: 0, d_angle_deg: 0 })
  );
  $("btnSbAutoFeed").addEventListener("click", () => {
    if (!state || !state.sandbox) return;
    postJson("/api/sandbox/auto-feed", {
      enabled: !state.sandbox.auto_feed_enabled,
      mode: "cycle",
      interval_s: 3.0,
    });
  });

  $("btnAlignAngle").addEventListener("click", () =>
    postJson("/api/transform", { action: "align_board_angle" })
  );
  $("btnFlipX").addEventListener("click", () => {
    if (!state) return;
    postJson("/api/transform", { flip_x: !state.transform.flip_x });
  });
  $("btnClearDesign").addEventListener("click", () => postJson("/api/design/clear"));
  $("dxfUnitSelect").addEventListener("change", (ev) =>
    postJson("/api/design/dxf-units", { unit: ev.target.value })
  );
  $("pdfPageSelect").addEventListener("change", (ev) =>
    postJson("/api/design/pdf-page", { page_index: parseInt(ev.target.value, 10) || 0 })
  );
  $("rasterModeSelect").addEventListener("change", (ev) =>
    postJson("/api/projector/display", { raster_mode: ev.target.value })
  );
  $("btnVectorizeRaster").addEventListener("click", () =>
    postJson("/api/design/vectorize", { threshold: 160, invert: true, simplify_mm: 1.2 })
  );

  $("btnOpenProjectorWindow").addEventListener("click", openProjectorWindow);
  $("chkShowBoard").addEventListener("change", (ev) =>
    postJson("/api/projector/display", { show_board_contour: ev.target.checked })
  );
  $("btnProjMirrorX").addEventListener("click", () => {
    if (!state) return;
    postJson("/api/projector/display", { mirror_x: !state.projector_display.mirror_x });
  });
  $("btnProjMirrorY").addEventListener("click", () => {
    if (!state) return;
    postJson("/api/projector/display", { mirror_y: !state.projector_display.mirror_y });
  });
  $("fineOffX").addEventListener("change", (ev) =>
    postJson("/api/projector/display", { fine_offset_x_mm: parseFloat(ev.target.value) || 0 })
  );
  $("fineOffY").addEventListener("change", (ev) =>
    postJson("/api/projector/display", { fine_offset_y_mm: parseFloat(ev.target.value) || 0 })
  );
  $("btnConnectStream").addEventListener("click", () =>
    postJson("/api/stream/connect", {
      host: $("streamHostInput").value.trim() || "127.0.0.1",
      port: parseInt($("streamPortInput").value, 10) || 6203,
    })
  );
  $("btnDisconnectStream").addEventListener("click", () => postJson("/api/stream/disconnect"));
  $("btnExportProjectorJson").addEventListener("click", () => {
    window.open("/api/export/projector-json", "_blank");
  });

  // Keyboard shortcuts
  window.addEventListener("keydown", (ev) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (!state) return;
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      $("btnNextTile").click();
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      $("btnPrevTile").click();
    } else if (ev.key.toLowerCase() === "b") {
      $("btnBlankProjector").click();
    } else if (ev.key.toLowerCase() === "l") {
      $("btnToggleLock").click();
    } else if (ev.key.toLowerCase() === "r") {
      $("btnRescan").click();
    } else if (ev.key === "Escape") {
      $("settingsDrawer").classList.add("hidden");
      $("scaleModal").classList.add("hidden");
    }
  });

  window.addEventListener("resize", () => {
    fitOverviewCamera();
    renderAll();
  });

  // -------------------------------------------------------------------
  // WebSocket & Boot
  // -------------------------------------------------------------------
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

  applyLanguage(lang);
  if (["split", "overview", "projector", "parts"].includes(currentView)) {
    setView(currentView);
  }
  api("/api/state")
    .then((s) => applyState(s))
    .catch(() => {});
  connectWS();
})();
