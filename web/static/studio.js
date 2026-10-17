/**
 * Kolam Interactive Drawing Studio - Frontend Logic
 * Full pointer events, touch protection, vector stroke recording,
 * independent reference image layer, and real-time generation polling.
 */

(() => {
    // Canvas & Layer Elements
    const drawingCanvas = document.getElementById('drawingCanvas');
    const ctx = drawingCanvas.getContext('2d');
    const dotGridCanvas = document.getElementById('dotGridCanvas');
    const dotCtx = dotGridCanvas.getContext('2d');
    const referenceLayer = document.getElementById('referenceLayer');
    const refImage = document.getElementById('refImage');
    const refPlaceholder = document.getElementById('refPlaceholder');
    const canvasWrapper = document.getElementById('canvasWrapper');

    // Controls
    const toolBrush = document.getElementById('toolBrush');
    const toolEraser = document.getElementById('toolEraser');
    const brushSizeSlider = document.getElementById('brushSizeSlider');
    const brushSizeVal = document.getElementById('brushSizeVal');
    const sizePresets = document.querySelectorAll('.preset-btn');
    const colorSwatches = document.querySelectorAll('.color-swatch');
    const refImageInput = document.getElementById('refImageInput');
    const btnUploadRef = document.getElementById('btnUploadRef');
    const btnRemoveRef = document.getElementById('btnRemoveRef');
    const uploadLabel = document.getElementById('uploadLabel');
    const refOpacitySlider = document.getElementById('refOpacitySlider');
    const opacityVal = document.getElementById('opacityVal');
    const refCorrectionToggle = document.getElementById('refCorrectionToggle');
    const btnUndo = document.getElementById('btnUndo');
    const btnRedo = document.getElementById('btnRedo');
    const btnFloatUndo = document.getElementById('btnFloatUndo');
    const btnFloatRedo = document.getElementById('btnFloatRedo');
    const btnClear = document.getElementById('btnClear');
    const dotGridSelect = document.getElementById('dotGridSelect');
    const videoTitle = document.getElementById('videoTitle');
    const btnGenerate = document.getElementById('btnGenerate');
    const lanIpText = document.getElementById('lanIpText');

    // Modals
    const jobModal = document.getElementById('jobModal');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalProgressView = document.getElementById('modalProgressView');
    const modalCompleteView = document.getElementById('modalCompleteView');
    const modalErrorView = document.getElementById('modalErrorView');
    const progressPercent = document.getElementById('progressPercent');
    const progressCircle = document.getElementById('progressCircle');
    const progressStage = document.getElementById('progressStage');
    const resultVideo = document.getElementById('resultVideo');
    const resultThumbnail = document.getElementById('resultThumbnail');
    const seoTitleText = document.getElementById('seoTitleText');
    const seoTagsText = document.getElementById('seoTagsText');
    const btnDownloadVideo = document.getElementById('btnDownloadVideo');
    const btnDownloadThumb = document.getElementById('btnDownloadThumb');
    const btnContinueDrawing = document.getElementById('btnContinueDrawing');
    const btnDismissError = document.getElementById('btnDismissError');
    const errorMessage = document.getElementById('errorMessage');

    const clearConfirmModal = document.getElementById('clearConfirmModal');
    const btnCancelClear = document.getElementById('btnCancelClear');
    const btnConfirmClear = document.getElementById('btnConfirmClear');

    // State Variables
    let currentTool = 'brush'; // 'brush' or 'eraser'
    let currentColor = '#FFFFFF';
    let currentBrushSize = 6;
    let strokes = []; // Array of { id, color, width, points: [{x, y, t}] }
    let undoStack = [];
    let redoStack = [];
    let activeStroke = null;
    let isDrawing = false;
    let sessionStartTime = performance.now();
    let pollInterval = null;
    let currentReferenceFilename = null;

    // --- LAN Discovery Info ---
    async function fetchSystemInfo() {
        try {
            const res = await fetch('/api/system-info');
            if (res.ok) {
                const data = await res.json();
                lanIpText.textContent = `${data.lan_ip}:${data.port}`;
            }
        } catch (e) {
            lanIpText.textContent = 'Localhost';
        }
    }
    fetchSystemInfo();

    // --- Coordinate Mapping ---
    function getCanvasCoords(e) {
        const rect = drawingCanvas.getBoundingClientRect();
        const scaleX = 1080 / rect.width;
        const scaleY = 1920 / rect.height;
        const x = Math.max(0, Math.min(1079, Math.round((e.clientX - rect.left) * scaleX)));
        const y = Math.max(0, Math.min(1919, Math.round((e.clientY - rect.top) * scaleY)));
        return { x, y };
    }

    // --- Rendering Drawing Canvas ---
    function redrawAllStrokes() {
        ctx.clearRect(0, 0, 1080, 1920);

        for (const stroke of strokes) {
            drawSingleStroke(ctx, stroke);
        }
        updateUndoRedoButtons();
    }

    function drawSingleStroke(targetCtx, stroke) {
        const pts = stroke.points;
        if (!pts || pts.length === 0) return;

        targetCtx.save();
        targetCtx.strokeStyle = stroke.color;
        targetCtx.fillStyle = stroke.color;
        targetCtx.lineWidth = stroke.width;
        targetCtx.lineCap = 'round';
        targetCtx.lineJoin = 'round';

        if (pts.length === 1) {
            targetCtx.beginPath();
            targetCtx.arc(pts[0].x, pts[0].y, stroke.width / 2, 0, Math.PI * 2);
            targetCtx.fill();
        } else {
            targetCtx.beginPath();
            targetCtx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) {
                targetCtx.lineTo(pts[i].x, pts[i].y);
            }
            targetCtx.stroke();
        }
        targetCtx.restore();
    }

    // =========================================================================
    // Strict Blueprint Tracing & Alignment Engine (In-Browser)
    // Every accepted stroke is constrained to the blueprint centerline geometry.
    // Movement in white areas or across gaps is strictly blocked.
    // =========================================================================
    const ReferenceSnapper = {
        geometry: null,         // { paths: [...], roi: [padX, padY, w, h], scale: 1.0 }
        pathsMap: new Map(),    // pathId -> { id, points, tangents, isClosed, length }
        spatialGrid: new Map(), // key -> Array of { x, y, tx, ty, pathId, ptIdx, isClosed }
        cellSize: 20,           // Grid cell size in logical canvas pixels
        snapRadius: 26,         // Strict maximum search radius from centerline (26px)
        maxStepDistance: 35,    // Maximum continuous step along path between events (35px)
        isEnabled: true,        // Controlled by refCorrectionToggle
        
        // Active stroke tracking state
        activePathId: null,
        activePtIdx: null,
        activeStartPathId: null,
        activeStartPtIdx: null,
        lastSnappedPoint: null,
        lastRawPoint: null,
        isPaused: false,
        
        hasGeometry() {
            return Boolean(this.geometry && this.geometry.paths && this.geometry.paths.length > 0);
        },

        setEnabled(enabled) {
            this.isEnabled = Boolean(enabled);
        },

        clear() {
            this.geometry = null;
            this.pathsMap.clear();
            this.spatialGrid.clear();
            this.resetActiveStroke();
        },

        resetActiveStroke() {
            this.activePathId = null;
            this.activePtIdx = null;
            this.activeStartPathId = null;
            this.activeStartPtIdx = null;
            this.lastSnappedPoint = null;
            this.lastRawPoint = null;
            this.isPaused = false;
        },

        _cellKey(cx, cy) {
            return `${cx},${cy}`;
        },

        _queryCandidates(coord, radius) {
            const cellSize = this.cellSize;
            const minCx = Math.floor((coord.x - radius) / cellSize);
            const maxCx = Math.floor((coord.x + radius) / cellSize);
            const minCy = Math.floor((coord.y - radius) / cellSize);
            const maxCy = Math.floor((coord.y + radius) / cellSize);

            const candidates = [];
            for (let cy = minCy; cy <= maxCy; cy++) {
                for (let cx = minCx; cx <= maxCx; cx++) {
                    const cell = this.spatialGrid.get(this._cellKey(cx, cy));
                    if (cell) {
                        for (let i = 0; i < cell.length; i++) {
                            const item = cell[i];
                            const d = Math.hypot(item.x - coord.x, item.y - coord.y);
                            if (d <= radius) {
                                candidates.push(item);
                            }
                        }
                    }
                }
            }
            return candidates;
        },

        loadGeometry(geomData) {
            this.clear();
            if (!geomData || !geomData.paths || !Array.isArray(geomData.paths)) return;

            this.geometry = geomData;
            let totalPoints = 0;

            for (const path of geomData.paths) {
                const pts = path.points;
                const tangents = path.tangents || [];
                const pathId = path.id;
                const isClosed = Boolean(path.is_closed);

                if (!pts || pts.length < 2) continue;

                // Index in pathsMap for polyline traversal
                this.pathsMap.set(pathId, {
                    id: pathId,
                    points: pts,
                    tangents: tangents,
                    isClosed: isClosed,
                    length: pts.length
                });

                for (let i = 0; i < pts.length; i++) {
                    const x = pts[i][0];
                    const y = pts[i][1];
                    let tx = 0, ty = 0;
                    if (tangents[i]) {
                        tx = tangents[i][0];
                        ty = tangents[i][1];
                    } else if (i < pts.length - 1) {
                        const dx = pts[i + 1][0] - x;
                        const dy = pts[i + 1][1] - y;
                        const len = Math.hypot(dx, dy) || 1.0;
                        tx = dx / len;
                        ty = dy / len;
                    }

                    const item = { x, y, tx, ty, pathId, ptIdx: i, isClosed };
                    const cx = Math.floor(x / this.cellSize);
                    const cy = Math.floor(y / this.cellSize);
                    const key = this._cellKey(cx, cy);

                    if (!this.spatialGrid.has(key)) {
                        this.spatialGrid.set(key, []);
                    }
                    this.spatialGrid.get(key).push(item);
                    totalPoints++;

                    // Dense sub-sampling along segments (every ~4px)
                    if (i > 0) {
                        const px = pts[i - 1][0];
                        const py = pts[i - 1][1];
                        const segDist = Math.hypot(x - px, y - py);
                        if (segDist > 6.0) {
                            const steps = Math.max(1, Math.floor(segDist / 4.0));
                            for (let s = 1; s < steps; s++) {
                                const frac = s / steps;
                                const ix = px + frac * (x - px);
                                const iy = py + frac * (y - py);
                                const icx = Math.floor(ix / this.cellSize);
                                const icy = Math.floor(iy / this.cellSize);
                                const ikey = this._cellKey(icx, icy);
                                if (!this.spatialGrid.has(ikey)) {
                                    this.spatialGrid.set(ikey, []);
                                }
                                this.spatialGrid.get(ikey).push({
                                    x: ix, y: iy, tx, ty, pathId, ptIdx: i, isClosed
                                });
                                totalPoints++;
                            }
                        }
                    }
                }
            }

            console.log(`[ReferenceSnapper] Strict Blueprint Indexed ${totalPoints} points across ${geomData.paths.length} paths.`);
        },

        extractFromImageElement(imgElement) {
            if (!imgElement || !imgElement.naturalWidth || !imgElement.naturalHeight) return;

            try {
                const offCanvas = document.createElement('canvas');
                const targetW = 1080;
                const targetH = 1920;
                offCanvas.width = targetW;
                offCanvas.height = targetH;
                const offCtx = offCanvas.getContext('2d', { willReadFrequently: true });

                const origW = imgElement.naturalWidth;
                const origH = imgElement.naturalHeight;
                const scale = Math.min(targetW / origW, targetH / origH);
                const fitW = Math.round(origW * scale);
                const fitH = Math.round(origH * scale);
                const padX = Math.round((targetW - fitW) / 2);
                const padY = Math.round((targetH - fitH) / 2);

                offCtx.fillStyle = '#FFFFFF';
                offCtx.fillRect(0, 0, targetW, targetH);
                offCtx.drawImage(imgElement, padX, padY, fitW, fitH);

                const imgData = offCtx.getImageData(0, 0, targetW, targetH);
                const data = imgData.data;

                // Estimate background luminance
                let totalLum = 0;
                let count = 0;
                const sampleInterval = 10;
                for (let y = padY; y < padY + fitH; y += sampleInterval) {
                    for (let x = padX; x < padX + fitW; x += sampleInterval) {
                        const idx = (y * targetW + x) * 4;
                        totalLum += 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
                        count++;
                    }
                }
                const meanLum = count > 0 ? (totalLum / count) : 180;
                const isLightBg = meanLum > 120;

                const paths = [];
                const sampleStep = 4;
                let currentPoints = [];
                let currentPathId = 1;

                for (let y = padY + 2; y < padY + fitH - 2; y += sampleStep) {
                    for (let x = padX + 2; x < padX + fitW - 2; x += sampleStep) {
                        const idx = (y * targetW + x) * 4;
                        const lum = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
                        const isLine = isLightBg ? (lum < meanLum - 28) : (lum > meanLum + 28);
                        if (isLine) {
                            const idxL = (y * targetW + (x - 2)) * 4;
                            const idxR = (y * targetW + (x + 2)) * 4;
                            const idxU = ((y - 2) * targetW + x) * 4;
                            const idxD = ((y + 2) * targetW + x) * 4;
                            const gx = (data[idxR] - data[idxL]);
                            const gy = (data[idxD] - data[idxU]);
                            const gLen = Math.hypot(-gy, gx) || 1.0;
                            currentPoints.push([x, y]);
                            if (currentPoints.length >= 80) {
                                paths.push({
                                    id: currentPathId++,
                                    is_closed: false,
                                    points: currentPoints,
                                    tangents: currentPoints.map(() => [-gy / gLen, gx / gLen])
                                });
                                currentPoints = [];
                            }
                        }
                    }
                }
                if (currentPoints.length > 5) {
                    paths.push({
                        id: currentPathId++,
                        is_closed: false,
                        points: currentPoints,
                        tangents: currentPoints.map(() => [1.0, 0.0])
                    });
                }

                this.loadGeometry({
                    paths: paths,
                    roi: [padX, padY, fitW, fitH],
                    scale: scale
                });
            } catch (err) {
                console.warn('[ReferenceSnapper] Client-side extraction error:', err);
            }
        },

        snapStart(rawCoord) {
            this.resetActiveStroke();
            if (!this.isEnabled || !this.hasGeometry()) {
                return { accepted: false, blocked: true, reason: 'no_blueprint' };
            }

            const cands = this._queryCandidates(rawCoord, this.snapRadius);
            if (!cands || cands.length === 0) {
                // Clicked in white area outside blueprint lines
                return { accepted: false, blocked: true, reason: 'outside_blueprint' };
            }

            // Find closest candidate centerline point
            let bestCand = null;
            let bestDist = Infinity;
            for (let i = 0; i < cands.length; i++) {
                const d = Math.hypot(cands[i].x - rawCoord.x, cands[i].y - rawCoord.y);
                if (d < bestDist) {
                    bestDist = d;
                    bestCand = cands[i];
                }
            }

            if (!bestCand || bestDist > this.snapRadius) {
                return { accepted: false, blocked: true, reason: 'outside_blueprint' };
            }

            const pt = { x: Math.round(bestCand.x), y: Math.round(bestCand.y) };
            this.activePathId = bestCand.pathId;
            this.activePtIdx = bestCand.ptIdx;
            this.activeStartPathId = bestCand.pathId;
            this.activeStartPtIdx = bestCand.ptIdx;
            this.lastSnappedPoint = pt;
            this.lastRawPoint = { x: rawCoord.x, y: rawCoord.y };
            this.isPaused = false;

            return {
                accepted: true,
                point: pt,
                pathId: bestCand.pathId,
                ptIdx: bestCand.ptIdx,
                intermediatePoints: [pt]
            };
        },

        snapMove(rawCoord) {
            if (!this.isEnabled || !this.hasGeometry() || this.activePathId === null || !this.lastSnappedPoint) {
                return { accepted: false, blocked: true, reason: 'no_active_stroke' };
            }

            const cands = this._queryCandidates(rawCoord, this.snapRadius);
            if (!cands || cands.length === 0) {
                // Pointer entered white area! Pause stroke at last valid point.
                this.isPaused = true;
                this.lastRawPoint = { x: rawCoord.x, y: rawCoord.y };
                return { accepted: false, blocked: true, reason: 'white_area' };
            }

            // Calculate user movement vector
            let dirUser = null;
            if (this.lastRawPoint) {
                const dx = rawCoord.x - this.lastRawPoint.x;
                const dy = rawCoord.y - this.lastRawPoint.y;
                const len = Math.hypot(dx, dy);
                if (len >= 1.5) {
                    dirUser = [dx / len, dy / len];
                }
            }

            const activePath = this.pathsMap.get(this.activePathId);
            if (!activePath) {
                this.isPaused = true;
                return { accepted: false, blocked: true, reason: 'invalid_path' };
            }

            let bestCand = null;
            let bestScore = Infinity;

            for (let i = 0; i < cands.length; i++) {
                const cand = cands[i];
                const dRaw = Math.hypot(cand.x - rawCoord.x, cand.y - rawCoord.y);
                const dStep = Math.hypot(cand.x - this.lastSnappedPoint.x, cand.y - this.lastSnappedPoint.y);
                const isSamePath = (cand.pathId === this.activePathId);

                if (isSamePath) {
                    // Strict continuity along active path: step must not exceed maxStepDistance
                    if (dStep > this.maxStepDistance) {
                        continue;
                    }
                } else {
                    // Transition to different path: ONLY allowed at an intersection right at lastSnappedPoint (<= 14px)
                    if (dStep > 14.0) {
                        continue; // Forbid jumping to parallel or disconnected lines!
                    }
                }

                // Tangent / movement alignment
                let alignPenalty = 0.0;
                if (dirUser && (cand.tx !== 0 || cand.ty !== 0)) {
                    const dot = dirUser[0] * cand.tx + dirUser[1] * cand.ty;
                    const absDot = Math.abs(dot);
                    alignPenalty = 25.0 * (1.0 - absDot);

                    // If crossing to another path at junction, movement must align strongly with new branch
                    if (!isSamePath && absDot < 0.70) {
                        continue; // Ambiguous intersection - pause instead of guessing!
                    }
                }

                let score = dRaw + 0.08 * dStep + alignPenalty;
                if (isSamePath) {
                    score -= 15.0; // Path continuity bonus
                } else {
                    score += 25.0; // Branch switch penalty
                }

                if (score < bestScore) {
                    bestScore = score;
                    bestCand = cand;
                }
            }

            if (!bestCand) {
                // No candidate meets strict continuity: user jumped across gap or ambiguous intersection
                this.isPaused = true;
                this.lastRawPoint = { x: rawCoord.x, y: rawCoord.y };
                return { accepted: false, blocked: true, reason: 'discontinuity_blocked' };
            }

            // Valid candidate on centerline! Extract intermediate points if multiple steps occurred
            const intermediatePoints = [];
            if (bestCand.pathId === this.activePathId && this.activePtIdx !== null) {
                const fromIdx = this.activePtIdx;
                const toIdx = bestCand.ptIdx;
                const pts = activePath.points;
                const total = pts.length;

                if (toIdx !== fromIdx && Math.abs(toIdx - fromIdx) > 1) {
                    let step = (toIdx > fromIdx) ? 1 : -1;
                    if (activePath.isClosed && total > 2) {
                        const directDist = Math.abs(toIdx - fromIdx);
                        const wrapDist = total - directDist;
                        if (wrapDist < directDist) {
                            step = (toIdx > fromIdx) ? -1 : 1;
                        }
                    }
                    let curr = fromIdx + step;
                    let count = 0;
                    while (curr !== toIdx && count < 8) {
                        if (curr < 0) {
                            if (activePath.isClosed) curr = total - 1; else break;
                        } else if (curr >= total) {
                            if (activePath.isClosed) curr = 0; else break;
                        }
                        if (curr === toIdx) break;
                        intermediatePoints.push({ x: Math.round(pts[curr][0]), y: Math.round(pts[curr][1]) });
                        curr += step;
                        count++;
                    }
                }
            }

            const targetPt = { x: Math.round(bestCand.x), y: Math.round(bestCand.y) };
            if (!this.lastSnappedPoint || targetPt.x !== this.lastSnappedPoint.x || targetPt.y !== this.lastSnappedPoint.y) {
                intermediatePoints.push(targetPt);
            }

            // Advance state
            this.activePathId = bestCand.pathId;
            this.activePtIdx = bestCand.ptIdx;
            this.lastSnappedPoint = targetPt;
            this.lastRawPoint = { x: rawCoord.x, y: rawCoord.y };
            this.isPaused = false;

            return {
                accepted: true,
                point: targetPt,
                intermediatePoints: intermediatePoints,
                pathId: bestCand.pathId,
                ptIdx: bestCand.ptIdx
            };
        },

        snapPoint(rawCoord, relTime, isNewStroke = false) {
            if (isNewStroke) {
                const res = this.snapStart(rawCoord);
                if (res.accepted) {
                    return {
                        point: res.point,
                        snapped: true,
                        confidence: 1.0,
                        pathId: res.pathId,
                        accepted: true,
                        intermediatePoints: res.intermediatePoints
                    };
                } else {
                    return {
                        point: rawCoord,
                        snapped: false,
                        confidence: 0,
                        accepted: false,
                        blocked: true,
                        reason: res.reason
                    };
                }
            } else {
                const res = this.snapMove(rawCoord);
                if (res.accepted) {
                    return {
                        point: res.point,
                        snapped: true,
                        confidence: 1.0,
                        pathId: res.pathId,
                        accepted: true,
                        intermediatePoints: res.intermediatePoints
                    };
                } else {
                    return {
                        point: this.lastSnappedPoint || rawCoord,
                        snapped: false,
                        confidence: 0,
                        accepted: false,
                        blocked: true,
                        reason: res.reason
                    };
                }
            }
        },

        finishStroke(strokePoints) {
            if (!strokePoints || strokePoints.length < 6) {
                this.resetActiveStroke();
                return;
            }

            // Only close a loop when both ends lie on the same closed reference path
            // and the remaining gap is small enough that a direct pixel correction
            // cannot cut across a corner or unrelated geometry.
            const p0 = strokePoints[0];
            const pN = strokePoints[strokePoints.length - 1];
            const gap = Math.hypot(p0.x - pN.x, p0.y - pN.y);
            const activePath = this.pathsMap.get(this.activePathId);
            if (activePath && activePath.isClosed && this.activePathId === this.activeStartPathId && gap <= 3.0) {
                strokePoints[strokePoints.length - 1].x = p0.x;
                strokePoints[strokePoints.length - 1].y = p0.y;
            }

            this.resetActiveStroke();
        }
    };

    // --- Toast / Feedback Indicator ---
    function showToast(msg) {
        let toast = document.getElementById('tracingToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'tracingToast';
            toast.className = 'tracing-toast';
            if (canvasWrapper) {
                canvasWrapper.appendChild(toast);
            }
        }
        if (toast) {
            toast.textContent = msg;
            toast.classList.add('visible');
            clearTimeout(toast._timeout);
            toast._timeout = setTimeout(() => {
                toast.classList.remove('visible');
            }, 2200);
        }
    }

    // --- Pointer Events for Strict Blueprint Tracing with Real-Time Snapping ---
    function onPointerDown(e) {
        if (e.button !== 0 && e.pointerType === 'mouse') return;

        const coords = getCanvasCoords(e);
        const relTime = Math.round(performance.now() - sessionStartTime);

        if (currentTool === 'brush') {
            if (!ReferenceSnapper.hasGeometry()) {
                showToast("Strict Blueprint Mode: Please upload a reference image to trace.");
                return;
            }

            const snapResult = ReferenceSnapper.snapStart(coords);
            if (!snapResult.accepted) {
                // Clicked outside blueprint lines (white area)
                showToast("Start tracing directly on a reference line.");
                return;
            }

            drawingCanvas.setPointerCapture(e.pointerId);
            isDrawing = true;

            const pt = snapResult.point;
            activeStroke = {
                id: `stroke_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
                color: currentColor,
                width: currentBrushSize,
                points: [{ x: pt.x, y: pt.y, t: relTime }],
                rawPoints: [{ x: coords.x, y: coords.y, t: relTime }]
            };

            ctx.save();
            ctx.strokeStyle = currentColor;
            ctx.fillStyle = currentColor;
            ctx.lineWidth = currentBrushSize;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, currentBrushSize / 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        } else if (currentTool === 'eraser') {
            drawingCanvas.setPointerCapture(e.pointerId);
            isDrawing = true;
            eraseNearPoint(coords.x, coords.y);
        }
    }

    function onPointerMove(e) {
        if (!isDrawing) return;
        const coords = getCanvasCoords(e);
        const relTime = Math.round(performance.now() - sessionStartTime);

        if (currentTool === 'brush' && activeStroke) {
            activeStroke.rawPoints.push({ x: coords.x, y: coords.y, t: relTime });

            const snapResult = ReferenceSnapper.snapMove(coords);
            if (!snapResult.accepted) {
                // Pointer in white area or gap: stroke pauses, NO segment drawn across gap
                return;
            }

            const newPts = snapResult.intermediatePoints || [snapResult.point];
            const pts = activeStroke.points;
            const lastPt = pts[pts.length - 1];

            ctx.save();
            ctx.strokeStyle = activeStroke.color;
            ctx.lineWidth = activeStroke.width;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.beginPath();
            ctx.moveTo(lastPt.x, lastPt.y);

            for (let i = 0; i < newPts.length; i++) {
                const p = newPts[i];
                const prev = pts[pts.length - 1];
                if (!prev || prev.x !== p.x || prev.y !== p.y) {
                    pts.push({ x: p.x, y: p.y, t: relTime });
                    ctx.lineTo(p.x, p.y);
                }
            }

            ctx.stroke();
            ctx.restore();
        } else if (currentTool === 'eraser') {
            eraseNearPoint(coords.x, coords.y);
        }
    }

    function onPointerUp(e) {
        if (!isDrawing && !activeStroke) return;
        isDrawing = false;
        try {
            drawingCanvas.releasePointerCapture(e.pointerId);
        } catch (_) {}

        if (currentTool === 'brush' && activeStroke) {
            if (activeStroke.points.length >= 2) {
                ReferenceSnapper.finishStroke(activeStroke.points);
                strokes.push(activeStroke);
                undoStack.push({ type: 'stroke', stroke: activeStroke });
                redoStack = [];
                updateUndoRedoButtons();
            }
            activeStroke = null;
            redrawAllStrokes();
        }
    }

    function onPointerCancel(e) {
        onPointerUp(e);
    }

    // --- Vector Eraser Tool ---
    function eraseNearPoint(x, y, radius = 22) {
        let changed = false;
        const remaining = [];
        const erased = [];

        for (const stroke of strokes) {
            let hit = false;
            for (const pt of stroke.points) {
                const dist = Math.hypot(pt.x - x, pt.y - y);
                if (dist <= radius) {
                    hit = true;
                    break;
                }
            }
            if (hit) {
                changed = true;
                erased.push(stroke);
            } else {
                remaining.push(stroke);
            }
        }

        if (changed) {
            undoStack.push({ type: 'erase', strokes: erased });
            strokes = remaining;
            redoStack = [];
            redrawAllStrokes();
        }
    }

    drawingCanvas.addEventListener('pointerdown', onPointerDown);
    drawingCanvas.addEventListener('pointermove', onPointerMove);
    drawingCanvas.addEventListener('pointerup', onPointerUp);
    drawingCanvas.addEventListener('pointercancel', onPointerCancel);

    // --- Undo & Redo History ---
    function undo() {
        if (strokes.length === 0 && undoStack.length === 0) return;

        if (undoStack.length > 0) {
            const action = undoStack.pop();
            if (action.type === 'erase') {
                strokes.push(...action.strokes);
                redoStack.push(action);
            } else if (action.type === 'stroke') {
                const idx = strokes.findIndex(s => s.id === action.stroke.id);
                if (idx !== -1) {
                    strokes.splice(idx, 1);
                } else {
                    strokes.pop();
                }
                redoStack.push(action);
            }
        } else if (strokes.length > 0) {
            const popped = strokes.pop();
            redoStack.push({ type: 'stroke', stroke: popped });
        }
        redrawAllStrokes();
    }

    function redo() {
        if (redoStack.length === 0) return;
        const action = redoStack.pop();
        if (action.type === 'stroke') {
            if (!strokes.some(s => s.id === action.stroke.id)) {
                strokes.push(action.stroke);
            }
            undoStack.push(action);
        } else if (action.type === 'erase') {
            const idsToRemove = new Set(action.strokes.map(s => s.id));
            strokes = strokes.filter(s => !idsToRemove.has(s.id));
            undoStack.push(action);
        }
        redrawAllStrokes();
    }

    function updateUndoRedoButtons() {
        const canUndo = (strokes.length > 0 || undoStack.length > 0);
        const canRedo = (redoStack.length > 0);
        btnUndo.disabled = !canUndo;
        btnRedo.disabled = !canRedo;
        if (btnFloatUndo) btnFloatUndo.disabled = !canUndo;
        if (btnFloatRedo) btnFloatRedo.disabled = !canRedo;
    }

    btnUndo.addEventListener('click', undo);
    btnRedo.addEventListener('click', redo);
    if (btnFloatUndo) btnFloatUndo.addEventListener('click', undo);
    if (btnFloatRedo) btnFloatRedo.addEventListener('click', redo);

    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
            if (e.shiftKey) redo();
            else undo();
            e.preventDefault();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
            redo();
            e.preventDefault();
        } else if (e.key.toLowerCase() === 'b' && !['INPUT', 'SELECT'].includes(document.activeElement.tagName)) {
            setTool('brush');
        } else if (e.key.toLowerCase() === 'e' && !['INPUT', 'SELECT'].includes(document.activeElement.tagName)) {
            setTool('eraser');
        }
    });

    // --- Tool Switching ---
    function setTool(tool) {
        currentTool = tool;
        if (tool === 'brush') {
            toolBrush.classList.add('active');
            toolEraser.classList.remove('active');
            drawingCanvas.style.cursor = 'crosshair';
        } else {
            toolEraser.classList.add('active');
            toolBrush.classList.remove('active');
            drawingCanvas.style.cursor = 'cell';
        }
    }
    toolBrush.addEventListener('click', () => setTool('brush'));
    toolEraser.addEventListener('click', () => setTool('eraser'));

    // --- Brush Size Controls ---
    function setBrushSize(size) {
        currentBrushSize = parseInt(size, 10);
        brushSizeSlider.value = currentBrushSize;
        brushSizeVal.textContent = `${currentBrushSize} px`;
        sizePresets.forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.size, 10) === currentBrushSize);
        });
    }

    brushSizeSlider.addEventListener('input', (e) => setBrushSize(e.target.value));
    sizePresets.forEach(btn => {
        btn.addEventListener('click', () => setBrushSize(btn.dataset.size));
    });

    // --- Palette Swatches ---
    colorSwatches.forEach(swatch => {
        swatch.addEventListener('click', () => {
            colorSwatches.forEach(s => s.classList.remove('active'));
            swatch.classList.add('active');
            currentColor = swatch.dataset.color;
            if (currentTool !== 'brush') setTool('brush');
        });
    });

    // --- Reference Image Upload & Opacity ---
    btnUploadRef.addEventListener('click', () => refImageInput.click());

    refImageInput.addEventListener('change', async () => {
        const file = refImageInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('reference_image', file);

        uploadLabel.textContent = 'Uploading...';
        btnUploadRef.disabled = true;

        try {
            const res = await fetch('/api/upload-reference', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                currentReferenceFilename = data.filename;
                refImage.src = data.image_url;
                refImage.style.display = 'block';
                refPlaceholder.style.display = 'none';
                btnRemoveRef.style.display = 'inline-flex';
                uploadLabel.textContent = 'Change Image';

                // Invalidate old strokes and geometry when a new blueprint is loaded
                strokes = [];
                undoStack = [];
                redoStack = [];
                redrawAllStrokes();

                // Load reference geometry for live browser snapping
                if (data.geometry && data.geometry.paths && data.geometry.paths.length > 0) {
                    ReferenceSnapper.loadGeometry(data.geometry);
                } else {
                    refImage.onload = () => {
                        ReferenceSnapper.extractFromImageElement(refImage);
                    };
                }
            } else {
                alert(`Upload failed: ${data.error}`);
                uploadLabel.textContent = 'Upload Image';
            }
        } catch (err) {
            alert(`Error uploading image: ${err.message}`);
            uploadLabel.textContent = 'Upload Image';
        } finally {
            btnUploadRef.disabled = false;
            refImageInput.value = '';
        }
    });

    btnRemoveRef.addEventListener('click', () => {
        currentReferenceFilename = null;
        ReferenceSnapper.clear();
        strokes = [];
        undoStack = [];
        redoStack = [];
        redrawAllStrokes();
        refImage.src = '';
        refImage.style.display = 'none';
        refPlaceholder.style.display = 'flex';
        btnRemoveRef.style.display = 'none';
        uploadLabel.textContent = 'Upload Image';
    });

    if (refCorrectionToggle) {
        refCorrectionToggle.addEventListener('change', (e) => {
            ReferenceSnapper.setEnabled(e.target.checked);
        });
    }

    refOpacitySlider.addEventListener('input', (e) => {
        const val = e.target.value;
        opacityVal.textContent = `${val}%`;
        referenceLayer.style.opacity = (val / 100);
    });

    // --- Clear Canvas Confirmation Modal ---
    btnClear.addEventListener('click', () => {
        if (strokes.length === 0) return;
        clearConfirmModal.style.display = 'flex';
    });

    btnCancelClear.addEventListener('click', () => {
        clearConfirmModal.style.display = 'none';
    });

    btnConfirmClear.addEventListener('click', () => {
        strokes = [];
        undoStack = [];
        redoStack = [];
        redrawAllStrokes();
        clearConfirmModal.style.display = 'none';
    });

    // --- Dot Grid Overlay Preview ---
    function drawDotGrid(gridType) {
        dotCtx.clearRect(0, 0, 1080, 1920);
        if (!gridType || gridType === 'none') return;

        let rows = [];
        let spacing = 110;
        let topY = 480;

        if (gridType === '8x2') {
            rows = [2, 4, 6, 8, 8, 6, 4, 2];
            spacing = 110;
            topY = 480;
        } else if (gridType === '6x2') {
            rows = [2, 4, 6, 6, 4, 2];
            spacing = 120;
            topY = 550;
        }

        dotCtx.fillStyle = '#FFFFFF';
        rows.forEach((count, rIdx) => {
            const y = topY + rIdx * spacing;
            const startX = 540 - ((count - 1) * spacing) / 2;
            for (let c = 0; c < count; c++) {
                const x = startX + c * spacing;
                dotCtx.beginPath();
                dotCtx.arc(x, y, 6, 0, Math.PI * 2);
                dotCtx.fill();
            }
        });
    }

    dotGridSelect.addEventListener('change', (e) => {
        drawDotGrid(e.target.value);
    });

    // --- Video Generation & Job Polling ---
    btnGenerate.addEventListener('click', async () => {
        if (btnGenerate.disabled) return;
        if (strokes.length === 0) {
            alert('Please draw something on the canvas before generating a video!');
            return;
        }

        btnGenerate.disabled = true;

        const payload = {
            canvas: { width: 1080, height: 1920 },
            title: videoTitle.value.trim() || 'AK Kolam',
            dot_grid: dotGridSelect.value,
            strokes: strokes,
            reference_image: currentReferenceFilename,
            correction_enabled: refCorrectionToggle ? refCorrectionToggle.checked : true,
            live_aligned: Boolean(ReferenceSnapper.hasGeometry() && (refCorrectionToggle ? refCorrectionToggle.checked : true)),
            drawing_speed: 1.2
        };

        jobModal.style.display = 'flex';
        modalProgressView.style.display = 'flex';
        modalCompleteView.style.display = 'none';
        modalErrorView.style.display = 'none';
        modalCloseBtn.style.display = 'none';
        updateProgress(5, 'Submitting drawing data...');

        try {
            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!data.success) {
                btnGenerate.disabled = false;
                showError(data.error || 'Failed to submit generation job.');
                return;
            }

            pollJob(data.job_id);
        } catch (err) {
            btnGenerate.disabled = false;
            showError(`Network error: ${err.message}`);
        }
    });

    function pollJob(jobId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/jobs/${jobId}`);
                if (!res.ok) {
                    clearInterval(pollInterval);
                    showError('Failed to retrieve job status.');
                    return;
                }
                const job = await res.json();
                if (!job.success) {
                    clearInterval(pollInterval);
                    showError(job.error || 'Job not found.');
                    return;
                }

                if (job.status === 'running' || job.status === 'queued') {
                    updateProgress(job.progress, job.stage);
                } else if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    showComplete(job);
                } else if (job.status === 'failed') {
                    clearInterval(pollInterval);
                    showError(job.error || 'Video rendering failed.');
                }
            } catch (err) {
                // Keep polling
            }
        }, 800);
    }

    function updateProgress(percent, stageText) {
        progressPercent.textContent = `${percent}%`;
        progressStage.textContent = stageText || 'Rendering...';
        const offset = 264 - (264 * percent) / 100;
        progressCircle.style.strokeDashoffset = offset;
    }

    function showComplete(job) {
        btnGenerate.disabled = false;
        modalProgressView.style.display = 'none';
        modalCompleteView.style.display = 'block';
        modalCloseBtn.style.display = 'block';

        resultVideo.src = job.video_url;
        resultVideo.load();

        if (job.thumbnail_url) {
            resultThumbnail.src = job.thumbnail_url;
            document.getElementById('thumbWrapper').style.display = 'flex';
            btnDownloadThumb.style.display = 'inline-flex';
            btnDownloadThumb.href = job.thumbnail_url;
        } else {
            document.getElementById('thumbWrapper').style.display = 'none';
            btnDownloadThumb.style.display = 'none';
        }

        btnDownloadVideo.href = job.video_url;

        if (job.meta_dict) {
            seoTitleText.textContent = job.meta_dict.title || 'N/A';
            seoTagsText.textContent = job.meta_dict.tags || 'N/A';
        }
    }

    function showError(errText) {
        btnGenerate.disabled = false;
        modalProgressView.style.display = 'none';
        modalCompleteView.style.display = 'none';
        modalErrorView.style.display = 'block';
        modalCloseBtn.style.display = 'block';
        errorMessage.textContent = errText;
    }

    modalCloseBtn.addEventListener('click', () => {
        btnGenerate.disabled = false;
        jobModal.style.display = 'none';
        if (resultVideo) resultVideo.pause();
    });

    btnContinueDrawing.addEventListener('click', () => {
        btnGenerate.disabled = false;
        jobModal.style.display = 'none';
        if (resultVideo) resultVideo.pause();
    });

    btnDismissError.addEventListener('click', () => {
        btnGenerate.disabled = false;
        jobModal.style.display = 'none';
    });
})();
