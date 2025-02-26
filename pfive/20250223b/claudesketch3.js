// Global hatching patterns - modify once and used everywhere
const hatchingPatterns = [
    // Single angles at 15° increments
    { angles: [0], spacing: 6 },           // Pattern 0: Horizontal
    { angles: [-15], spacing: 6 },          // Pattern 1: 15°
    { angles: [30], spacing: 6 },          // Pattern 2: 30°
    { angles: [-45], spacing: 6 },          // Pattern 3: 45°
    { angles: [60], spacing: 6 },          // Pattern 4: 60°
    { angles: [-75], spacing: 6 },          // Pattern 5: 75°
    { angles: [90], spacing: 6 },          // Pattern 6: Vertical

    // Perpendicular pairs (90° difference)
    { angles: [0, 90], spacing: 6 },       // Pattern 7: Grid
    { angles: [15, 105], spacing: 6 },     // Pattern 8: 15°/105° grid
    { angles: [30, 60], spacing: 6 },     // Pattern 9: 30°/120° grid
    { angles: [45, 135], spacing: 6 },     // Pattern 10: 45°/135° grid (diagonal crosshatch)

    // More random combinations
    { angles: [0, 45], spacing: 6 },       // Pattern 11: Mixed horizontal/diagonal
    { angles: [30, 75], spacing: 6 },      // Pattern 12: Mixed angles
    { angles: [15, 60], spacing: 6 },      // Pattern 13: Asymmetric angles
    { angles: [0, 30, 60, 90], spacing: 20 }, // Pattern 14: Multiple angles
    { angles: [15, 45, 75], spacing: 18 }   // Pattern 15: Triple angles
];

let shapes = [];
let renderMode = 5; // Default: 5 = truly continuous hatching

function setup() {
    createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(15, 35)); // Random number of total shap5ses
    for (let i = 0; i < k; i++) {
        let x = random(100, width - 200);
        let y = random(100, height - 200);

        // Randomly choose shape type
        let shapeType = random(['circle', 'square', 'triangle']);
        let pad = 50;

        if (shapeType === 'circle') {
            let diameter = random(50, 240);
            // Check if circle fits within canvas with padding
            if (x - diameter / 2 >= pad && x + diameter / 2 <= width - pad &&
                y - diameter / 2 >= pad && y + diameter / 2 <= height - pad) {
                shapes.push({
                    type: 'circle',
                    x: x,
                    y: y,
                    size: diameter,
                    color: color(random(255), random(255), random(255)),
                    zIndex: i // Higher zIndex means the shape is on top
                });
            }
        } else if (shapeType === 'square') {
            let size = random(50, 400);
            // Check if square fits within canvas with padding
            if (x - size / 2 >= pad && x + size / 2 <= width - pad &&
                y - size / 2 >= pad && y + size / 2 <= height - pad) {
                shapes.push({
                    type: 'square',
                    x: x,
                    y: y,
                    size: size,
                    color: color(random(255), random(255), random(255)),
                    zIndex: i
                });
            }
        } else { // triangle
            let R = random(25, 400);
            let rotation = floor(random(4)) * HALF_PI;
            // Check if triangle fits within canvas with padding
            let points = [
                { x: x, y: y - R },
                { x: x - R * cos(PI / 6), y: y + R * sin(PI / 6) },
                { x: x + R * cos(PI / 6), y: y + R * sin(PI / 6) }
            ];
            let fits = points.every(p => p.x >= pad && p.x <= width - pad && p.y >= pad && p.y <= height - pad);
            if (fits) {
                shapes.push({
                    type: 'triangle',
                    x: x,
                    y: y,
                    size: R,
                    rotation: rotation,
                    color: color(random(255), random(255), random(255)),
                    zIndex: i
                });
            }
        }
    }
}

function draw() {
    // Step 1: Draw fills without stroke
    noStroke();
    let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]; // Pleasant color palette

    // Assign a specific color to each shape for consistency
    for (let i = 0; i < shapes.length; i++) {
        shapes[i].fillColor = colors[i % colors.length];
        shapes[i].colorIndex = i % colors.length; // Store color index for hatching pattern
    }

    // Draw all shapes
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

    // Reset blend mode
    blendMode(BLEND);

    // Step 2: Get all outline segments
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }

    // Step 3: Split segments at intersections
    let splitSegments = splitSegmentsAtIntersections(allSegments);

    // Step 4: Filter out inner segments
    let outerSegments = filterOuterSegments(splitSegments);

    // Step 5: Draw bold outlines
    stroke(0);
    strokeWeight(10);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    noLoop(); // Static sketch
}

// Draw the fill of a shape
function drawShapeFill(shape) {
    beginShape();
    let points = getShapePoints(shape);
    for (let p of points) {
        vertex(p.x, p.y);
    }
    endShape(CLOSE);
}

// Get the points defining a shape's outline
function getShapePoints(shape) {
    let points = [];
    if (shape.type === 'circle') {
        let numSides = 32;
        let radius = shape.size / 2;
        for (let i = 0; i < numSides; i++) {
            let angle = TWO_PI / numSides * i;
            let x = shape.x + radius * cos(angle);
            let y = shape.y + radius * sin(angle);
            points.push({ x, y });
        }
    } else if (shape.type === 'square') {
        let halfSize = shape.size / 2;
        points = [
            { x: shape.x - halfSize, y: shape.y - halfSize },
            { x: shape.x + halfSize, y: shape.y - halfSize },
            { x: shape.x + halfSize, y: shape.y + halfSize },
            { x: shape.x - halfSize, y: shape.y + halfSize }
        ];
    } else if (shape.type === 'triangle') {
        for (let i = 0; i < 3; i++) {
            let angle = TWO_PI / 3 * i + shape.rotation;
            let x = shape.x + shape.size * cos(angle);
            let y = shape.y + shape.size * sin(angle);
            points.push({ x, y });
        }
    }
    return points;
}

// Get outline segments as vectors
function getOutlineSegments(shape) {
    let segments = [];
    let points = getShapePoints(shape);
    for (let i = 0; i < points.length; i++) {
        let start = points[i];
        let end = points[(i + 1) % points.length];
        segments.push({ start: { ...start }, end: { ...end } });
    }
    return segments;
}

// Find intersection between two line segments
function findIntersection(seg1, seg2) {
    let p0 = seg1.start;
    let p1 = seg1.end;
    let p2 = seg2.start;
    let p3 = seg2.end;

    let s1_x = p1.x - p0.x;
    let s1_y = p1.y - p0.y;
    let s2_x = p3.x - p2.x;
    let s2_y = p3.y - p2.y;

    let denom = (-s2_x * s1_y + s1_x * s2_y);
    if (abs(denom) < 0.0001) return null; // Parallel

    let s = (-s1_y * (p0.x - p2.x) + s1_x * (p0.y - p2.y)) / denom;
    let t = (s2_x * (p0.y - p2.y) - s2_y * (p0.x - p2.x)) / denom;

    if (s >= 0 && s <= 1 && t >= 0 && t <= 1) {
        return {
            x: p0.x + (t * s1_x),
            y: p0.y + (t * s1_y)
        };
    }
    return null;
}

// Split segments at intersection points
function splitSegmentsAtIntersections(segments) {
    let result = [];
    for (let i = 0; i < segments.length; i++) {
        let seg = segments[i];
        let intersections = [];
        for (let j = 0; j < segments.length; j++) {
            if (i !== j && seg.parent !== segments[j].parent) {
                let inter = findIntersection(seg, segments[j]);
                if (inter) intersections.push(inter);
            }
        }
        if (intersections.length === 0) {
            result.push(seg);
        } else {
            intersections.sort((a, b) => {
                let d1 = dist(seg.start.x, seg.start.y, a.x, a.y);
                let d2 = dist(seg.start.x, seg.start.y, b.x, b.y);
                return d1 - d2;
            });
            let current = { ...seg.start };
            for (let inter of intersections) {
                result.push({ start: current, end: { ...inter }, parent: seg.parent });
                current = { ...inter };
            }
            result.push({ start: current, end: { ...seg.end }, parent: seg.parent });
        }
    }
    return result;
}

// Check if a point is inside a shape
function pointInShape(px, py, shape) {
    let points = getShapePoints(shape);
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        let xi = points[i].x, yi = points[i].y;
        let xj = points[j].x, yj = points[j].y;
        let intersect = ((yi > py) !== (yj > py)) &&
            (px < (xj - xi) * (py - yi) / (yj - yi + 0.0001) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

// Filter out segments that are inside other shapes
function filterOuterSegments(segments) {
    return segments.filter(seg => {
        let midX = (seg.start.x + seg.end.x) / 2;
        let midY = (seg.start.y + seg.end.y) / 2;
        for (let shape of shapes) {
            if (shape !== seg.parent && pointInShape(midX, midY, shape)) {
                return false; // Segment is inside another shape
            }
        }
        return true; // Segment is on the outer edge
    });
}

// Get a bounding box for a shape
function getShapeBoundingBox(shape) {
    const points = getShapePoints(shape);
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    for (const p of points) {
        minX = min(minX, p.x);
        minY = min(minY, p.y);
        maxX = max(maxX, p.x);
        maxY = max(maxY, p.y);
    }

    return {
        x: minX,
        y: minY,
        width: maxX - minX,
        height: maxY - minY
    };
}

// Generate the SVG shape path definition
function getShapePath(shape) {
    if (shape.type === 'circle') {
        return `<circle cx="${shape.x}" cy="${shape.y}" r="${shape.size / 2}"/>`;
    } else {
        const points = getShapePoints(shape);
        let pathData = '';

        points.forEach((p, i) => {
            if (i === 0) {
                pathData += `M ${p.x} ${p.y} `;
            } else {
                pathData += `L ${p.x} ${p.y} `;
            }
        });

        pathData += 'Z';
        return `<path d="${pathData}"/>`;
    }
}

// Generate a global set of hatching lines for the entire canvas
function generateGlobalHatchingLines(angle, spacing) {
    // Calculate padding to ensure we cover the entire canvas
    const padding = 200;
    const totalWidth = width + padding * 2;
    const totalHeight = height + padding * 2;

    // Calculate the angle in radians
    const angleRad = angle * (Math.PI / 180);

    // Get the diagonal length of the canvas
    const diagonalLength = Math.sqrt(totalWidth * totalWidth + totalHeight * totalHeight);

    // Calculate perpendicular direction
    const perpAngle = angleRad + Math.PI / 2;
    const perpX = Math.cos(perpAngle);
    const perpY = Math.sin(perpAngle);

    // Center of canvas
    const centerX = width / 2;
    const centerY = height / 2;

    // Calculate number of lines needed
    const numLines = Math.ceil(diagonalLength / spacing) * 2;
    const startOffset = -diagonalLength;

    let lines = [];

    // Generate all hatch lines across the entire canvas
    for (let i = 0; i < numLines; i++) {
        const offset = startOffset + i * spacing;

        // Calculate start point
        const startX = centerX + perpX * offset;
        const startY = centerY + perpY * offset;

        // Calculate direction vector
        const dirX = Math.cos(angleRad);
        const dirY = Math.sin(angleRad);

        // Calculate line endpoints (extending beyond canvas)
        const lineStartX = startX - dirX * diagonalLength;
        const lineStartY = startY - dirY * diagonalLength;
        const lineEndX = startX + dirX * diagonalLength;
        const lineEndY = startY + dirY * diagonalLength;

        lines.push({
            x1: lineStartX,
            y1: lineStartY,
            x2: lineEndX,
            y2: lineEndY
        });
    }

    return lines;
}

// Map a given color to a hatching pattern index consistently
function getHatchingPatternByColor(colorIndex) {
    // This ensures that the same color always gets the same pattern
    return hatchingPatterns[colorIndex % hatchingPatterns.length];
}

// Generate SVG string with layered hatching (Mode 1)
function generateLayeredSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
  <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
    
    <!-- Background -->
    <rect width="${width}" height="${height}" fill="white"/>
    
    <!-- Mode: Layered Hatching -->
    
    <defs>
  `;

    // Create clip paths for each shape
    for (let i = 0; i < shapes.length; i++) {
        const shape = shapes[i];
        svgString += `    <clipPath id="shape_clip_${i}">
        ${getShapePath(shape)}
      </clipPath>
  `;
    }

    svgString += `  </defs>
  `;

    // Draw each shape with its hatching pattern
    for (let i = 0; i < shapes.length; i++) {
        const shape = shapes[i];
        const pattern = getHatchingPatternByColor(shape.colorIndex);

        svgString += `  <g id="shape_${i}" inkscape:label="Shape ${i}" inkscape:groupmode="layer">
      <g clip-path="url(#shape_clip_${i})">
  `;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            // Generate hatching centered on this shape
            const bbox = getShapeBoundingBox(shape);
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;

            // Calculate lines centered at this shape
            const angleRad = angle * (Math.PI / 180);
            const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height) + 100; // Add padding
            const perpAngle = angleRad + Math.PI / 2;
            const perpX = Math.cos(perpAngle);
            const perpY = Math.sin(perpAngle);

            const numLines = Math.ceil(diagonalLength / pattern.spacing) * 2;
            const startOffset = -diagonalLength;

            for (let j = 0; j < numLines; j++) {
                const offset = startOffset + j * pattern.spacing;

                // Calculate start point
                const startX = centerX + perpX * offset;
                const startY = centerY + perpY * offset;

                // Calculate direction vector
                const dirX = Math.cos(angleRad);
                const dirY = Math.sin(angleRad);

                // Calculate line endpoints
                const lineStartX = startX - dirX * diagonalLength;
                const lineStartY = startY - dirY * diagonalLength;
                const lineEndX = startX + dirX * diagonalLength;
                const lineEndY = startY + dirY * diagonalLength;

                svgString += `      <line x1="${lineStartX}" y1="${lineStartY}" x2="${lineEndX}" y2="${lineEndY}" stroke="black" stroke-width="1"/>
  `;
            }
        }

        svgString += `    </g>
    </g>
  `;
    }

    // Get segments for outlines
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);

    // Create a separate layer for outlines (on top)
    svgString += `  <g id="outlines" inkscape:label="Outlines" inkscape:groupmode="layer">
  `;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10"/>
  `;
    }

    // Close the outlines layer
    svgString += `  </g>
  `;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Generate SVG string with grid effect (Mode 2)
function generateGridEffectSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
  <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
    
    <!-- Background -->
    <rect width="${width}" height="${height}" fill="white"/>
    
    <!-- Mode: Grid Effect Hatching -->
  `;

    // Sort shapes by zIndex, from bottom to top
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Process each shape
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];
        const pattern = getHatchingPatternByColor(shape.colorIndex);

        svgString += `  <g id="shape_${i}" inkscape:label="Shape ${shape.zIndex}" inkscape:groupmode="layer">
      <defs>
        <clipPath id="clip_${i}">
          ${getShapePath(shape)}
        </clipPath>
      </defs>
      <g clip-path="url(#clip_${i})">
  `;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            // Generate hatching centered on this shape
            const bbox = getShapeBoundingBox(shape);
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;

            // Calculate lines centered at this shape
            const angleRad = angle * (Math.PI / 180);
            const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height) + 100; // Add padding
            const perpAngle = angleRad + Math.PI / 2;
            const perpX = Math.cos(perpAngle);
            const perpY = Math.sin(perpAngle);

            const numLines = Math.ceil(diagonalLength / pattern.spacing) * 2;
            const startOffset = -diagonalLength;

            for (let j = 0; j < numLines; j++) {
                const offset = startOffset + j * pattern.spacing;

                // Calculate start point
                const startX = centerX + perpX * offset;
                const startY = centerY + perpY * offset;

                // Calculate direction vector
                const dirX = Math.cos(angleRad);
                const dirY = Math.sin(angleRad);

                // Calculate line endpoints
                const lineStartX = startX - dirX * diagonalLength;
                const lineStartY = startY - dirY * diagonalLength;
                const lineEndX = startX + dirX * diagonalLength;
                const lineEndY = startY + dirY * diagonalLength;

                svgString += `      <line x1="${lineStartX}" y1="${lineStartY}" x2="${lineEndX}" y2="${lineEndY}" stroke="black" stroke-width="1"/>
  `;
            }
        }

        svgString += `    </g>
    </g>
  `;
    }

    // Get segments for outlines
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);

    // Create a separate layer for outlines (on top)
    svgString += `  <g id="outlines" inkscape:label="Outlines" inkscape:groupmode="layer">
  `;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10"/>
  `;
    }

    // Close the outlines layer
    svgString += `  </g>
  `;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Generate SVG with true non-overlapping hatching (Mode 3)
function generateExclusiveHatchingSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
  <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
    
    <!-- Background -->
    <rect width="${width}" height="${height}" fill="white"/>
    
    <!-- Mode: True Exclusive Hatching -->
  `;

    // Sort shapes by zIndex, from bottom to top
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Create visible areas using difference operations
    svgString += `  <defs>
  `;

    // For each shape, create a visible region by subtracting higher shapes
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];

        // Create path for this shape
        svgString += `    <clipPath id="visibleArea_${i}">
        <path d="`;

        // Start with the current shape's path
        const shapePoints = getShapePoints(shape);
        svgString += `M ${shapePoints[0].x} ${shapePoints[0].y} `;
        for (let j = 1; j < shapePoints.length; j++) {
            svgString += `L ${shapePoints[j].x} ${shapePoints[j].y} `;
        }
        svgString += `Z" />
      </clipPath>
      
      <!-- Mask for overlapping areas -->
      <mask id="overlap_mask_${i}" maskUnits="userSpaceOnUse" x="0" y="0" width="${width}" height="${height}">
        <!-- White background = allow drawing -->
        <rect x="0" y="0" width="${width}" height="${height}" fill="white" />
        
        <!-- Black shapes = prevent drawing -->
  `;

        // Add higher-zIndex shapes as black shapes in the mask
        for (let j = 0; j < sortedShapes.length; j++) {
            const otherShape = sortedShapes[j];
            if (otherShape.zIndex > shape.zIndex) {
                svgString += `      <g fill="black">
          ${getShapePath(otherShape)}
        </g>
  `;
            }
        }

        svgString += `    </mask>
  `;
    }

    svgString += `  </defs>
  `;

    // Draw each shape with its non-overlapping hatching
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];
        const pattern = getHatchingPatternByColor(shape.colorIndex);

        svgString += `  <g id="shape_${i}" inkscape:label="Shape ${shape.zIndex}" inkscape:groupmode="layer">
      <!-- Clip to this shape and mask out higher shapes -->
      <g clip-path="url(#visibleArea_${i})" mask="url(#overlap_mask_${i})">
  `;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            // Generate hatching centered on this shape
            const bbox = getShapeBoundingBox(shape);
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;

            // Calculate lines centered at this shape
            const angleRad = angle * (Math.PI / 180);
            const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height) + 100; // Add padding
            const perpAngle = angleRad + Math.PI / 2;
            const perpX = Math.cos(perpAngle);
            const perpY = Math.sin(perpAngle);

            const numLines = Math.ceil(diagonalLength / pattern.spacing) * 2;
            const startOffset = -diagonalLength;

            for (let j = 0; j < numLines; j++) {
                const offset = startOffset + j * pattern.spacing;

                // Calculate start point
                const startX = centerX + perpX * offset;
                const startY = centerY + perpY * offset;

                // Calculate direction vector
                const dirX = Math.cos(angleRad);
                const dirY = Math.sin(angleRad);

                // Calculate line endpoints
                const lineStartX = startX - dirX * diagonalLength;
                const lineStartY = startY - dirY * diagonalLength;
                const lineEndX = startX + dirX * diagonalLength;
                const lineEndY = startY + dirY * diagonalLength;

                svgString += `      <line x1="${lineStartX}" y1="${lineStartY}" x2="${lineEndX}" y2="${lineEndY}" stroke="black" stroke-width="1"/>
  `;
            }
        }

        svgString += `    </g>
    </g>
  `;
    }

    // Get segments for outlines
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);

    // Create a separate layer for outlines (on top)
    svgString += `  <g id="outlines" inkscape:label="Outlines" inkscape:groupmode="layer">
  `;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10"/>
  `;
    }

    // Close the outlines layer
    svgString += `  </g>
  `;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Generate SVG with color-consistent hatching (Mode 4)
function generateColorConsistentSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
  <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
    
    <!-- Background -->
    <rect width="${width}" height="${height}" fill="white"/>
    
    <!-- Mode: Color-consistent Exclusive Hatching -->
  `;

    // Sort shapes by zIndex, from bottom to top
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Create visible areas using difference operations
    svgString += `  <defs>
  `;

    // For each shape, create a visible region by subtracting higher shapes
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];

        // Create path for this shape
        svgString += `    <clipPath id="visibleArea_${i}">
        <path d="`;

        // Start with the current shape's path
        const shapePoints = getShapePoints(shape);
        svgString += `M ${shapePoints[0].x} ${shapePoints[0].y} `;
        for (let j = 1; j < shapePoints.length; j++) {
            svgString += `L ${shapePoints[j].x} ${shapePoints[j].y} `;
        }
        svgString += `Z" />
      </clipPath>
      
      <!-- Mask for overlapping areas -->
      <mask id="overlap_mask_${i}" maskUnits="userSpaceOnUse" x="0" y="0" width="${width}" height="${height}">
        <!-- White background = allow drawing -->
        <rect x="0" y="0" width="${width}" height="${height}" fill="white" />
        
        <!-- Black shapes = prevent drawing -->
  `;

        // Add higher-zIndex shapes as black shapes in the mask
        for (let j = 0; j < sortedShapes.length; j++) {
            const otherShape = sortedShapes[j];
            if (otherShape.zIndex > shape.zIndex) {
                svgString += `      <g fill="black">
          ${getShapePath(otherShape)}
        </g>
  `;
            }
        }

        svgString += `    </mask>
  `;
    }

    svgString += `  </defs>
  `;

    // Draw each shape with its non-overlapping hatching
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];
        // Get pattern based on colorIndex, not shape index
        const pattern = getHatchingPatternByColor(shape.colorIndex);

        svgString += `  <g id="shape_${i}" inkscape:label="Shape ${shape.zIndex} (Color ${shape.colorIndex})" inkscape:groupmode="layer">
      <!-- Clip to this shape and mask out higher shapes -->
      <g clip-path="url(#visibleArea_${i})" mask="url(#overlap_mask_${i})">
  `;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            // Generate hatching centered on this shape
            const bbox = getShapeBoundingBox(shape);
            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;

            // Calculate lines centered at this shape
            const angleRad = angle * (Math.PI / 180);
            const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height) + 100; // Add padding
            const perpAngle = angleRad + Math.PI / 2;
            const perpX = Math.cos(perpAngle);
            const perpY = Math.sin(perpAngle);

            const numLines = Math.ceil(diagonalLength / pattern.spacing) * 2;
            const startOffset = -diagonalLength;

            for (let j = 0; j < numLines; j++) {
                const offset = startOffset + j * pattern.spacing;

                // Calculate start point
                const startX = centerX + perpX * offset;
                const startY = centerY + perpY * offset;

                // Calculate direction vector
                const dirX = Math.cos(angleRad);
                const dirY = Math.sin(angleRad);

                // Calculate line endpoints
                const lineStartX = startX - dirX * diagonalLength;
                const lineStartY = startY - dirY * diagonalLength;
                const lineEndX = startX + dirX * diagonalLength;
                const lineEndY = startY + dirY * diagonalLength;

                svgString += `      <line x1="${lineStartX}" y1="${lineStartY}" x2="${lineEndX}" y2="${lineEndY}" stroke="black" stroke-width="1"/>
  `;
            }
        }

        svgString += `    </g>
    </g>
  `;
    }

    // Get segments for outlines
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);

    // Create a separate layer for outlines (on top)
    svgString += `  <g id="outlines" inkscape:label="Outlines" inkscape:groupmode="layer">
  `;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10"/>
  `;
    }

    // Close the outlines layer
    svgString += `  </g>
  `;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Generate SVG with truly continuous hatching (Mode 5)
function generateContinuousHatchingSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
  <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
    
    <!-- Background -->
    <rect width="${width}" height="${height}" fill="white"/>
    
    <!-- Mode: True Continuous Hatching -->
  `;

    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // Create masks and clip paths for each shape
    svgString += `  <defs>
  `;

    // Sort shapes by zIndex, from bottom to top
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // For each shape, create a clip path and mask for its visible area
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];

        // Create clip path for this shape
        svgString += `    <clipPath id="shape_clip_${i}">
        ${getShapePath(shape)}
      </clipPath>
      
      <!-- Mask to hide overlapped areas -->
      <mask id="overlap_mask_${i}">
        <rect width="${width}" height="${height}" fill="white"/>
  `;

        // Add higher shapes as black areas to mask them out
        for (let j = 0; j < sortedShapes.length; j++) {
            const otherShape = sortedShapes[j];
            if (otherShape.zIndex > shape.zIndex) {
                svgString += `      <g fill="black">
          ${getShapePath(otherShape)}
        </g>
  `;
            }
        }

        svgString += `    </mask>
  `;
    }

    svgString += `  </defs>
  `;

    // For each color, create a group with the global hatching pattern
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color, sorted by zIndex
        const shapesWithColor = sortedShapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Get the pattern for this color
        const pattern = getHatchingPatternByColor(colorIndex);

        svgString += `  <!-- Color group ${colorIndex} -->
    <g inkscape:label="Color ${colorIndex}" inkscape:groupmode="layer">
  `;

        // For each angle in the pattern, create global hatch lines
        for (const angle of pattern.angles) {
            // Generate global hatching lines
            const globalLines = generateGlobalHatchingLines(angle, pattern.spacing);

            // For each shape with this color
            for (let i = 0; i < shapesWithColor.length; i++) {
                const shape = shapesWithColor[i];
                const shapeIndex = sortedShapes.findIndex(s => s === shape);

                svgString += `    <!-- Shape ${shape.zIndex} -->
      <g clip-path="url(#shape_clip_${shapeIndex})" mask="url(#overlap_mask_${shapeIndex})">
  `;

                // Add all global lines
                for (const line of globalLines) {
                    svgString += `      <line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" stroke="black" stroke-width="1"/>
  `;
                }

                svgString += `    </g>
  `;
            }
        }

        svgString += `  </g>
  `;
    }

    // Get segments for outlines
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);

    // Create a separate layer for outlines (on top)
    svgString += `  <g id="outlines" inkscape:label="Outlines" inkscape:groupmode="layer">
  `;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10"/>
  `;
    }

    // Close the outlines layer
    svgString += `  </g>
  `;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Handle saving SVG using direct browser download
function keyPressed() {
    if (key === '1') {
        // Switch to Mode 1: Layered Hatching
        renderMode = 1;
        console.log("Switched to Mode 1: Layered Hatching");
    } else if (key === '2') {
        // Switch to Mode 2: Grid Effect Hatching
        renderMode = 2;
        console.log("Switched to Mode 2: Grid Effect Hatching");
    } else if (key === '3') {
        // Switch to Mode 3: True Exclusive Hatching
        renderMode = 3;
        console.log("Switched to Mode 3: True Exclusive Hatching");
    } else if (key === '4') {
        // Switch to Mode 4: Color-consistent Exclusive Hatching
        renderMode = 4;
        console.log("Switched to Mode 4: Color-consistent Exclusive Hatching");
    } else if (key === '5') {
        // Switch to Mode 5: True Continuous Hatching
        renderMode = 5;
        console.log("Switched to Mode 5: True Continuous Hatching");
    } else if (key === 's') {
        // Generate SVG string with the current mode
        let svgContent;
        if (renderMode === 1) {
            svgContent = generateLayeredSVG();
        } else if (renderMode === 2) {
            svgContent = generateGridEffectSVG();
        } else if (renderMode === 3) {
            svgContent = generateExclusiveHatchingSVG();
        } else if (renderMode === 4) {
            svgContent = generateColorConsistentSVG();
        } else if (renderMode === 5) {
            svgContent = generateContinuousHatchingSVG();
        }

        // Create a Blob with the SVG content
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });

        // Create a download link with the mode indicated in the filename
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `hatched_blobs_mode${renderMode}_${Date.now()}.svg`;

        // Append to body, click and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Clean up
        URL.revokeObjectURL(url);

        console.log(`Mode ${renderMode} SVG saved!`);
    }
}