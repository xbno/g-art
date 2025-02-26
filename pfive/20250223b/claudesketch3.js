let shapes = [];
let renderMode = 1; // Default: 1 = layered hatching, 2 = exclusive hatching

function setup() {
    createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(15, 35)); // Random number of total shapes
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

// Generate hatching lines data for a shape
function generateHatchingData(shape, angle, spacing) {
    // Get the shape's bounding box
    const bbox = getShapeBoundingBox(shape);

    // Add some padding to ensure we cover the entire shape
    const padding = 50;
    bbox.x -= padding;
    bbox.y -= padding;
    bbox.width += padding * 2;
    bbox.height += padding * 2;

    // Calculate the angle in radians
    const angleRad = angle * (Math.PI / 180);

    // Get the diagonal length
    const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height);

    // Calculate perpendicular direction
    const perpAngle = angleRad + Math.PI / 2;
    const perpX = Math.cos(perpAngle);
    const perpY = Math.sin(perpAngle);

    // Center of bounding box
    const centerX = bbox.x + bbox.width / 2;
    const centerY = bbox.y + bbox.height / 2;

    // Calculate number of lines
    const numLines = Math.ceil(diagonalLength / spacing) * 2;
    const startOffset = -diagonalLength;

    let lines = [];

    // Generate all hatch lines
    for (let i = 0; i < numLines; i++) {
        const offset = startOffset + i * spacing;

        // Calculate start point
        const startX = centerX + perpX * offset;
        const startY = centerY + perpY * offset;

        // Calculate direction vector
        const dirX = Math.cos(angleRad);
        const dirY = Math.sin(angleRad);

        // Calculate line endpoints (extending beyond bbox)
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

    // Define hatching patterns
    const hatchingPatterns = [
        { angles: [-45, 45], spacing: 12 },   // Pattern 1: diagonal crosshatch
        { angles: [0, 90], spacing: 12 },     // Pattern 2: grid
        { angles: [-15, 15], spacing: 12 },   // Pattern 3: shallow crosshatch
        { angles: [-60, 60], spacing: 12 },   // Pattern 4: steep crosshatch
        { angles: [-30, 60], spacing: 12 },   // Pattern 5: mixed angle
        { angles: [0], spacing: 8 },          // Pattern 6: horizontal (denser)
        { angles: [45], spacing: 8 },         // Pattern 7: diagonal (denser)
        { angles: [-75, 15], spacing: 12 }    // Pattern 8: uneven angles
    ];

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
        const patternIndex = i % hatchingPatterns.length;
        const pattern = hatchingPatterns[patternIndex];

        svgString += `  <g id="shape_${i}" inkscape:label="Shape ${i}" inkscape:groupmode="layer">
    <g clip-path="url(#shape_clip_${i})">
`;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            const lines = generateHatchingData(shape, angle, pattern.spacing);

            for (const line of lines) {
                svgString += `      <line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" stroke="black" stroke-width="1"/>
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

// Generate SVG string with exclusive hatching (Mode 2)
function generateExclusiveSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
  xmlns="http://www.w3.org/2000/svg"
  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
  xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  
  <!-- Background -->
  <rect width="${width}" height="${height}" fill="white"/>
  
  <!-- Mode: Exclusive Hatching -->
`;

    // Define hatching patterns
    const hatchingPatterns = [
        { angles: [-45, 45], spacing: 12 },   // Pattern 1: diagonal crosshatch
        { angles: [0, 90], spacing: 12 },     // Pattern 2: grid
        { angles: [-15, 15], spacing: 12 },   // Pattern 3: shallow crosshatch
        { angles: [-60, 60], spacing: 12 },   // Pattern 4: steep crosshatch
        { angles: [-30, 60], spacing: 12 },   // Pattern 5: mixed angle
        { angles: [0], spacing: 8 },          // Pattern 6: horizontal (denser)
        { angles: [45], spacing: 8 },         // Pattern 7: diagonal (denser)
        { angles: [-75, 15], spacing: 12 }    // Pattern 8: uneven angles
    ];

    // Sort shapes by zIndex, from bottom to top
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Process each visible region
    // We'll create a composite path for each region of overlapping shapes
    // For each shape, we need to subtract all higher shapes from it
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];
        const patternIndex = i % hatchingPatterns.length;
        const pattern = hatchingPatterns[patternIndex];

        // Get all higher shapes (shapes that would be on top of this one)
        const higherShapes = sortedShapes.filter(s => s.zIndex > shape.zIndex);

        // Create a shape definition that excludes all higher shapes
        // We'll use the "non-zero" fill rule
        let shapePathDef = `<path d="`;

        // First add the current shape with clockwise winding (positive area)
        const shapePoints = getShapePoints(shape);
        shapePathDef += `M ${shapePoints[0].x} ${shapePoints[0].y} `;
        for (let j = 1; j < shapePoints.length; j++) {
            shapePathDef += `L ${shapePoints[j].x} ${shapePoints[j].y} `;
        }
        shapePathDef += `Z `;

        // Then subtract all higher shapes (counter-clockwise winding)
        for (const higherShape of higherShapes) {
            const higherPoints = getShapePoints(higherShape);
            // Start at last point and go backwards
            shapePathDef += `M ${higherPoints[higherPoints.length - 1].x} ${higherPoints[higherPoints.length - 1].y} `;
            for (let j = higherPoints.length - 2; j >= 0; j--) {
                shapePathDef += `L ${higherPoints[j].x} ${higherPoints[j].y} `;
            }
            shapePathDef += `Z `;
        }

        shapePathDef += `" fill="none" fill-rule="evenodd"/>`;

        // Create a group for this shape's visible region
        svgString += `  <!-- Shape ${i} (zIndex=${shape.zIndex}) -->
  <g clip-path="url(#clip_path_${i})">
`;

        // Add the clip path definition to the SVG
        svgString += `    <defs>
      <clipPath id="clip_path_${i}">
        ${shapePathDef}
      </clipPath>
    </defs>
`;

        // Add each hatching direction
        for (const angle of pattern.angles) {
            const lines = generateHatchingData(shape, angle, pattern.spacing);

            for (const line of lines) {
                svgString += `    <line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" stroke="black" stroke-width="1"/>
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
        // Switch to Mode 2: Exclusive Hatching
        renderMode = 2;
        console.log("Switched to Mode 2: Exclusive Hatching");
    } else if (key === 's') {
        // Generate SVG string with the current mode
        let svgContent;
        if (renderMode === 1) {
            svgContent = generateLayeredSVG();
        } else {
            svgContent = generateExclusiveSVG();
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