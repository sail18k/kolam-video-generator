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
    const btnUndo = document.getElementById('btnUndo');
    const btnRedo = document.getElementById('btnRedo');
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

    // --- Pointer Events for Freehand Drawing ---
    function onPointerDown(e) {
        if (e.button !== 0 && e.pointerType === 'mouse') return;

        drawingCanvas.setPointerCapture(e.pointerId);
        isDrawing = true;
        const coords = getCanvasCoords(e);
        const relTime = Math.round(performance.now() - sessionStartTime);

        if (currentTool === 'brush') {
            activeStroke = {
                id: `stroke_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
                color: currentColor,
                width: currentBrushSize,
                points: [{ x: coords.x, y: coords.y, t: relTime }]
            };

            ctx.save();
            ctx.strokeStyle = currentColor;
            ctx.fillStyle = currentColor;
            ctx.lineWidth = currentBrushSize;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.beginPath();
            ctx.arc(coords.x, coords.y, currentBrushSize / 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        } else if (currentTool === 'eraser') {
            eraseNearPoint(coords.x, coords.y);
        }
    }

    function onPointerMove(e) {
        if (!isDrawing) return;
        const coords = getCanvasCoords(e);
        const relTime = Math.round(performance.now() - sessionStartTime);

        if (currentTool === 'brush' && activeStroke) {
            const pts = activeStroke.points;
            const lastPt = pts[pts.length - 1];

            if (lastPt.x === coords.x && lastPt.y === coords.y) return;

            pts.push({ x: coords.x, y: coords.y, t: relTime });

            ctx.save();
            ctx.strokeStyle = activeStroke.color;
            ctx.lineWidth = activeStroke.width;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.beginPath();
            ctx.moveTo(lastPt.x, lastPt.y);
            ctx.lineTo(coords.x, coords.y);
            ctx.stroke();
            ctx.restore();
        } else if (currentTool === 'eraser') {
            eraseNearPoint(coords.x, coords.y);
        }
    }

    function onPointerUp(e) {
        if (!isDrawing) return;
        isDrawing = false;
        try {
            drawingCanvas.releasePointerCapture(e.pointerId);
        } catch (_) {}

        if (currentTool === 'brush' && activeStroke) {
            if (activeStroke.points.length > 0) {
                strokes.push(activeStroke);
                redoStack = [];
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
            strokes.push(action.stroke);
        } else if (action.type === 'erase') {
            const idsToRemove = new Set(action.strokes.map(s => s.id));
            strokes = strokes.filter(s => !idsToRemove.has(s.id));
            undoStack.push(action);
        }
        redrawAllStrokes();
    }

    function updateUndoRedoButtons() {
        btnUndo.disabled = (strokes.length === 0 && undoStack.length === 0);
        btnRedo.disabled = (redoStack.length === 0);
    }

    btnUndo.addEventListener('click', undo);
    btnRedo.addEventListener('click', redo);

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
                refImage.src = data.image_url;
                refImage.style.display = 'block';
                refPlaceholder.style.display = 'none';
                btnRemoveRef.style.display = 'inline-flex';
                uploadLabel.textContent = 'Change Image';
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
        refImage.src = '';
        refImage.style.display = 'none';
        refPlaceholder.style.display = 'flex';
        btnRemoveRef.style.display = 'none';
        uploadLabel.textContent = 'Upload Image';
    });

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
        if (strokes.length === 0) {
            alert('Please draw something on the canvas before generating a video!');
            return;
        }

        const payload = {
            canvas: { width: 1080, height: 1920 },
            title: videoTitle.value.trim() || 'AK Kolam',
            dot_grid: dotGridSelect.value,
            strokes: strokes
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
                showError(data.error || 'Failed to submit generation job.');
                return;
            }

            pollJob(data.job_id);
        } catch (err) {
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
        modalProgressView.style.display = 'none';
        modalCompleteView.style.display = 'none';
        modalErrorView.style.display = 'block';
        modalCloseBtn.style.display = 'block';
        errorMessage.textContent = errText;
    }

    modalCloseBtn.addEventListener('click', () => {
        jobModal.style.display = 'none';
        if (resultVideo) resultVideo.pause();
    });

    btnContinueDrawing.addEventListener('click', () => {
        jobModal.style.display = 'none';
        if (resultVideo) resultVideo.pause();
    });

    btnDismissError.addEventListener('click', () => {
        jobModal.style.display = 'none';
    });
})();
