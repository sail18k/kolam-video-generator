/**
 * Automated Test Suite for Strict Blueprint Tracing Engine (ReferenceSnapper)
 * Verifies all 13 strict blueprint requirements:
 * 1. Straight-line centerline snapping
 * 2. Curved-line centerline snapping
 * 3. Pointer down in white area (strict blocking / no freehand)
 * 4. Moving outside snapping radius (pauses at last valid point)
 * 5. White gap jump prevention (never bridge gaps)
 * 6. Resume on valid connected path continuity
 * 7. Disconnected path jump prevention (no hopping between components)
 * 8. Parallel contours (preserves active line identity)
 * 9. Intersections (branch stability along movement vector)
 * 10. Rapid pointer movement (dense intermediate centerline points)
 * 11. Closed-loop gap recovery on stroke finish
 * 12. Reference replacement & invalidation
 * 13. Independent strokes separation
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Read studio.js and extract ReferenceSnapper definition
const studioJs = fs.readFileSync(path.join(__dirname, '..', 'web', 'static', 'studio.js'), 'utf8');

const snapperMatch = studioJs.match(/const ReferenceSnapper = \{[\s\S]*?\n    \};/);
if (!snapperMatch) {
    console.error("FAIL: Could not locate ReferenceSnapper in studio.js");
    process.exit(1);
}

const snapperCode = snapperMatch[0];
const ReferenceSnapper = eval(`(() => { ${snapperCode}; return ReferenceSnapper; })()`);

console.log("========================================================================");
console.log("  STRICT BLUEPRINT TRACING ENGINE TEST SUITE");
console.log("========================================================================");

// --- TEST 1: Straight-Line Centerline Snapping ---
(() => {
    console.log("[TEST 1] Straight-Line Centerline Snapping...");
    // Horizontal line at y = 500 from x = 200 to x = 800
    const linePoints = [];
    const tangents = [];
    for (let x = 200; x <= 800; x += 10) {
        linePoints.push([x, 500]);
        tangents.push([1.0, 0.0]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: linePoints, tangents: tangents }]
    });

    // Pointer is at y = 512 (+12px offset from centerline)
    const p1 = ReferenceSnapper.snapStart({ x: 250, y: 512 });
    assert.strictEqual(p1.accepted, true, "Valid start point must be accepted");
    assert.strictEqual(p1.point.y, 500, `Point y (${p1.point.y}) must snap to exact centerline y=500`);

    const p2 = ReferenceSnapper.snapMove({ x: 270, y: 514 });
    assert.strictEqual(p2.accepted, true, "Move along line must be accepted");
    assert.strictEqual(p2.point.y, 500, `Move point y (${p2.point.y}) must stay on exact centerline y=500`);

    const p3 = ReferenceSnapper.snapMove({ x: 290, y: 508 });
    assert.strictEqual(p3.accepted, true, "Continuation must be accepted");
    assert.strictEqual(p3.point.y, 500, `Point y (${p3.point.y}) must remain on centerline y=500`);
    console.log("  -> Passed! Wobbly pointer at y=[512, 514, 508] snapped exactly to centerline y=500");
})();

// --- TEST 2: Curved-Line Centerline Snapping ---
(() => {
    console.log("[TEST 2] Curved-Line Centerline Snapping (Circle)...");
    const circlePoints = [];
    const tangents = [];
    const cx = 540, cy = 960, r = 200;
    for (let deg = 0; deg <= 360; deg += 4) {
        const rad = (deg * Math.PI) / 180;
        const x = cx + r * Math.cos(rad);
        const y = cy + r * Math.sin(rad);
        circlePoints.push([x, y]);
        tangents.push([-Math.sin(rad), Math.cos(rad)]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 2, is_closed: true, points: circlePoints, tangents: tangents }]
    });

    // Human draws with wobbly radius (r = 215 instead of 200, within 26px snap radius)
    const rad45 = (45 * Math.PI) / 180;
    const humanRaw = { x: Math.round(cx + 215 * Math.cos(rad45)), y: Math.round(cy + 215 * Math.sin(rad45)) };
    const snapped = ReferenceSnapper.snapStart(humanRaw);

    assert.strictEqual(snapped.accepted, true, "Circle start must be accepted");
    const snappedDist = Math.hypot(snapped.point.x - cx, snapped.point.y - cy);
    assert(Math.abs(snappedDist - 200) <= 2, `Snapped distance ${snappedDist} must match circle radius 200`);
    console.log(`  -> Passed! Pointer at radius 215.0px snapped to exact circle radius ${snappedDist.toFixed(1)}px`);
})();

// --- TEST 3: Pointer in White Area (Strict Blocking / No Freehand) ---
(() => {
    console.log("[TEST 3] Pointer Down in White Area (Strict Blocking)...");
    // Single line at (100, 100) -> (300, 100)
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: [[100, 100], [300, 100]], tangents: [[1, 0], [1, 0]] }]
    });

    // User attempts to draw at (500, 500) - white area, 400px away from reference
    const rawFar = { x: 500, y: 500 };
    const res = ReferenceSnapper.snapStart(rawFar);
    assert.strictEqual(res.accepted, false, "Must reject pointerdown in white area");
    assert.strictEqual(res.blocked, true, "Must flag movement as blocked");
    assert.strictEqual(ReferenceSnapper.activePathId, null, "Active path must remain null");
    console.log("  -> Passed! Pointer down in white area blocked; no stroke started.");
})();

// --- TEST 4: Moving Outside Snapping Radius (Pause at Last Valid Point) ---
(() => {
    console.log("[TEST 4] Moving Outside Snap Radius (Stroke Pauses)...");
    const linePoints = [];
    for (let x = 100; x <= 400; x += 10) {
        linePoints.push([x, 200]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: linePoints }]
    });

    // Start on line at (150, 200)
    const s1 = ReferenceSnapper.snapStart({ x: 150, y: 205 });
    assert.strictEqual(s1.accepted, true);
    assert.strictEqual(s1.point.y, 200);

    // Move along line to (170, 200)
    const s2 = ReferenceSnapper.snapMove({ x: 170, y: 204 });
    assert.strictEqual(s2.accepted, true);
    assert.strictEqual(s2.point.x, 170);

    // Pointer leaves line into white area at y = 260 (+60px away)
    const s3 = ReferenceSnapper.snapMove({ x: 190, y: 260 });
    assert.strictEqual(s3.accepted, false, "Movement outside radius must be rejected");
    assert.strictEqual(s3.blocked, true, "Movement must be marked blocked");
    assert.strictEqual(ReferenceSnapper.isPaused, true, "Snapper state must be paused");
    assert.strictEqual(ReferenceSnapper.lastSnappedPoint.x, 170, "Last valid point must remain frozen at (170, 200)");
    console.log("  -> Passed! Stroke paused at last valid point (170, 200); raw white-area points rejected.");
})();

// --- TEST 5: Never Bridge White Gaps ---
(() => {
    console.log("[TEST 5] White Gap Jump Prevention (Never Bridge Gaps)...");
    const linePoints = [];
    for (let x = 100; x <= 600; x += 10) {
        linePoints.push([x, 300]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: linePoints }]
    });

    // Start at (120, 300)
    ReferenceSnapper.snapStart({ x: 120, y: 300 });

    // User attempts a sudden jump to (350, 300) (> 200px gap jump along line)
    const jump = ReferenceSnapper.snapMove({ x: 350, y: 300 });
    assert.strictEqual(jump.accepted, false, "Large jump along line must be blocked");
    assert.strictEqual(jump.blocked, true);
    assert.strictEqual(ReferenceSnapper.lastSnappedPoint.x, 120, "Must not connect across gap");
    console.log("  -> Passed! 200px gap jump blocked; no bridge segment created.");
})();

// --- TEST 6: Resume on Valid Path Continuity ---
(() => {
    console.log("[TEST 6] Resume on Valid Path Continuity...");
    const linePoints = [];
    for (let x = 100; x <= 500; x += 10) {
        linePoints.push([x, 300]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: linePoints }]
    });

    // Start at (150, 300) and advance to (180, 300)
    ReferenceSnapper.snapStart({ x: 150, y: 300 });
    ReferenceSnapper.snapMove({ x: 180, y: 300 });

    // Pointer strays into white space at (180, 350)
    const stray = ReferenceSnapper.snapMove({ x: 180, y: 350 });
    assert.strictEqual(stray.accepted, false);
    assert.strictEqual(ReferenceSnapper.isPaused, true);

    // Pointer returns near last valid point: (195, 305) (within 20px step)
    const resume = ReferenceSnapper.snapMove({ x: 195, y: 305 });
    assert.strictEqual(resume.accepted, true, "Must resume when returning near last valid point");
    assert.strictEqual(ReferenceSnapper.isPaused, false);
    assert.strictEqual(resume.point.y, 300, "Resumed point must be on centerline");
    console.log("  -> Passed! Tracing resumed cleanly after returning to valid path continuation.");
})();

// --- TEST 7: Disconnected Line Jump Prevention ---
(() => {
    console.log("[TEST 7] Disconnected Line Jump Prevention...");
    // Path 1 at y = 100; Path 2 at y = 300 (separated by 200px white space)
    ReferenceSnapper.loadGeometry({
        paths: [
            { id: 1, is_closed: false, points: [[100, 100], [200, 100], [300, 100]] },
            { id: 2, is_closed: false, points: [[100, 300], [200, 300], [300, 300]] }
        ]
    });

    // Start on Path 1 at (200, 100)
    ReferenceSnapper.snapStart({ x: 200, y: 100 });

    // User moves pointer all the way to Path 2 at (200, 302) without releasing pointer
    const jumpToPath2 = ReferenceSnapper.snapMove({ x: 200, y: 302 });
    assert.strictEqual(jumpToPath2.accepted, false, "Must not jump to disconnected path 2");
    assert.strictEqual(ReferenceSnapper.activePathId, 1, "Must remain on path 1");
    console.log("  -> Passed! Pointer move to disconnected line blocked; no jump occurred.");
})();

// --- TEST 8: Nearby Parallel Contours (No Hopping) ---
(() => {
    console.log("[TEST 8] Nearby Parallel Contours (No Path Switching)...");
    // Two parallel horizontal lines: Line 10 at y = 400, Line 20 at y = 425 (25px apart)
    const line1 = [], line2 = [];
    for (let x = 100; x <= 600; x += 10) {
        line1.push([x, 400]);
        line2.push([x, 425]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [
            { id: 10, is_closed: false, points: line1 },
            { id: 20, is_closed: false, points: line2 }
        ]
    });

    // Start on Line 10
    const s1 = ReferenceSnapper.snapStart({ x: 200, y: 403 });
    assert.strictEqual(s1.pathId, 10, "Should lock to Path 10");

    // Move along Line 10 while pointer wanders toward Line 20 (y = 412)
    const s2 = ReferenceSnapper.snapMove({ x: 230, y: 412 });
    assert.strictEqual(s2.accepted, true);
    assert.strictEqual(s2.pathId, 10, "Must stay locked to Path 10, never switch to parallel Path 20");
    assert.strictEqual(s2.point.y, 400, "Point must stay on Line 10 centerline y=400");
    console.log("  -> Passed! Tracing locked onto Line 10 without hopping to parallel Line 20.");
})();

// --- TEST 9: Intersections (Branch Stability) ---
(() => {
    console.log("[TEST 9] Intersections (Stable Traversal)...");
    const horizPts = [], horizTang = [];
    const vertPts = [], vertTang = [];
    for (let i = 400; i <= 600; i += 10) {
        horizPts.push([i, 500]); horizTang.push([1.0, 0.0]);
        vertPts.push([500, i]); vertTang.push([0.0, 1.0]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [
            { id: 100, is_closed: false, points: horizPts, tangents: horizTang },
            { id: 200, is_closed: false, points: vertPts, tangents: vertTang }
        ]
    });

    // User draws horizontally through intersection: x goes from 460 -> 500 -> 530
    ReferenceSnapper.snapStart({ x: 460, y: 504 });
    ReferenceSnapper.snapMove({ x: 480, y: 504 });
    const atInter = ReferenceSnapper.snapMove({ x: 500, y: 503 });
    assert.strictEqual(atInter.pathId, 100, "Should stay on horizontal path at intersection");

    const pastInter = ReferenceSnapper.snapMove({ x: 520, y: 502 });
    assert.strictEqual(pastInter.pathId, 100, "Should continue along horizontal path past intersection");
    console.log("  -> Passed! Tracing stably traversed intersection along movement vector.");
})();

// --- TEST 10: Rapid Pointer Movement (Intermediate Curve Interpolation) ---
(() => {
    console.log("[TEST 10] Rapid Movement (Dense Intermediate Centerline Points)...");
    // Curved quarter circle
    const pts = [];
    for (let a = 0; a <= 90; a += 5) {
        const rad = (a * Math.PI) / 180;
        pts.push([Math.round(200 + 100 * Math.cos(rad)), Math.round(200 + 100 * Math.sin(rad))]);
    }
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 5, is_closed: false, points: pts }]
    });

    // Start at index 0: (300, 200)
    ReferenceSnapper.snapStart({ x: 300, y: 200 });

    // Rapid pointer move to near index 3
    const move = ReferenceSnapper.snapMove({ x: pts[3][0], y: pts[3][1] });
    assert.strictEqual(move.accepted, true);
    assert(move.intermediatePoints && move.intermediatePoints.length >= 2, "Must emit intermediate points");
    console.log(`  -> Passed! Fast move generated ${move.intermediatePoints.length} centerline points along the curve.`);
})();

// --- TEST 11: Closed-Loop Completion Stays on the Active Reference Path ---
(() => {
    console.log("[TEST 11] Closed-Loop Completion Stays on the Active Reference Path...");
    const loop = [[300, 300], [350, 250], [400, 300], [400, 350], [350, 400], [300, 350]];
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 7, is_closed: true, points: loop }]
    });
    ReferenceSnapper.snapStart({ x: 300, y: 300 });
    const strokePoints = [
        { x: 300, y: 300, t: 0 },
        { x: 350, y: 250, t: 50 },
        { x: 400, y: 300, t: 100 },
        { x: 400, y: 350, t: 150 },
        { x: 350, y: 400, t: 200 },
        { x: 302, y: 301, t: 250 } // small raster gap on the same closed path
    ];

    ReferenceSnapper.finishStroke(strokePoints);
    assert.strictEqual(strokePoints[strokePoints.length - 1].x, 300, "Last X should close to start X");
    assert.strictEqual(strokePoints[strokePoints.length - 1].y, 300, "Last Y should close to start Y");

    ReferenceSnapper.snapStart({ x: 300, y: 300 });
    const incomplete = [
        { x: 300, y: 300, t: 0 }, { x: 350, y: 250, t: 50 },
        { x: 400, y: 300, t: 100 }, { x: 400, y: 350, t: 150 },
        { x: 350, y: 400, t: 200 }, { x: 310, y: 308, t: 250 }
    ];
    ReferenceSnapper.finishStroke(incomplete);
    assert.strictEqual(incomplete[incomplete.length - 1].x, 310, "A larger gap must not be replaced by a straight shortcut");
    assert.strictEqual(incomplete[incomplete.length - 1].y, 308, "A larger gap must remain unmodified");
    console.log("  -> Passed! Tiny same-path raster gaps close; larger incomplete loops are not shortcut.");
})();

// --- TEST 12: Reference Replacement & Invalidation ---
(() => {
    console.log("[TEST 12] Reference Replacement & Geometry Invalidation...");
    ReferenceSnapper.loadGeometry({
        paths: [{ id: 1, is_closed: false, points: [[100, 100], [200, 100]] }]
    });
    assert(ReferenceSnapper.hasGeometry(), "Geometry must be present");

    ReferenceSnapper.clear();
    assert.strictEqual(ReferenceSnapper.hasGeometry(), false, "Geometry must be cleared");

    const testPt = ReferenceSnapper.snapStart({ x: 150, y: 100 });
    assert.strictEqual(testPt.accepted, false, "Must reject tracing when blueprint is cleared");
    assert.strictEqual(testPt.blocked, true);
    console.log("  -> Passed! Clearing blueprint successfully prevents any tracing.");
})();

// --- TEST 13: Independent Strokes Separation ---
(() => {
    console.log("[TEST 13] Independent Strokes Separation...");
    ReferenceSnapper.loadGeometry({
        paths: [
            { id: 1, is_closed: false, points: [[100, 100], [200, 100]] },
            { id: 2, is_closed: false, points: [[100, 300], [200, 300]] }
        ]
    });

    // Stroke 1 on Path 1
    const s1Start = ReferenceSnapper.snapStart({ x: 100, y: 100 });
    const s1End = ReferenceSnapper.snapMove({ x: 150, y: 100 });
    ReferenceSnapper.finishStroke([s1Start.point, s1End.point]);

    // Stroke 2 on Path 2 (Pointer lifted and placed down on Path 2)
    const s2Start = ReferenceSnapper.snapStart({ x: 100, y: 300 });
    assert.strictEqual(s2Start.accepted, true);
    assert.strictEqual(s2Start.pathId, 2, "Second stroke starts independently on Path 2");
    assert.strictEqual(s2Start.point.y, 300, "Second stroke begins at Path 2 centerline");
    console.log("  -> Passed! Independent strokes on separate components are cleanly separated.");
})();

console.log("========================================================================");
console.log("  ALL 13 STRICT BLUEPRINT TRACING TESTS PASSED!");
console.log("========================================================================");
