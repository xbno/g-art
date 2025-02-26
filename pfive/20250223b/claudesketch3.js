let shapes = [];

function setup() {
    createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(15, 45)); // Random number of total shapes
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
                    color: color(random(255), random(255), random(255))
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
                    color: color(random(255), random(255), random(255))
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
                    color: color(random(255), random(255), random(255))
                });
            }
        }
    }
}

function draw() {
    // Set blend mode to DIFFERENCE for fills
    // blendMode(DIFFERENCE);

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

// Generate hatching lines at a specific angle for a shape
function generateHatchingLines(shape, angle, spacing) {
    // Get the shape's bounding box
    const bbox = getShapeBoundingBox(shape);

    // Add some padding to ensure we cover the entire shape
    const padding = 50; // Adjust as needed
    bbox.x -= padding;
    bbox.y -= padding;
    bbox.width += padding * 2;
    bbox.height += padding * 2;

    // Calculate the angle in radians
    const angleRad = angle * (Math.PI / 180);

    // Determine the length of the diagonal of the bounding box
    const diagonalLength = Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height);

    // Calculate the perpendicular direction to find parallel lines
    const perpAngle = angleRad + Math.PI / 2;
    const perpX = Math.cos(perpAngle);
    const perpY = Math.sin(perpAngle);

    // Calculate the start position (corner of bbox)
    const centerX = bbox.x + bbox.width / 2;
    const centerY = bbox.y + bbox.height / 2;

    // Calculate how many lines we need
    const numLines = Math.ceil(diagonalLength / spacing) * 2;
    const startOffset = -diagonalLength;

    // Store all hatch lines
    const hatchLines = [];

    // Generate lines
    for (let i = 0; i < numLines; i++) {
        const offset = startOffset + i * spacing;

        // Calculate start point of the line
        const startX = centerX + perpX * offset;
        const startY = centerY + perpY * offset;

        // Calculate direction vector of the line
        const dirX = Math.cos(angleRad);
        const dirY = Math.sin(angleRad);

        // Calculate endpoints of the line (extending beyond the bounding box)
        const lineStartX = startX - dirX * diagonalLength;
        const lineStartY = startY - dirY * diagonalLength;
        const lineEndX = startX + dirX * diagonalLength;
        const lineEndY = startY + dirY * diagonalLength;

        // Clip the line against the shape's boundary
        // We'll use an array to collect intersection points
        const intersections = [];

        // Get the shape's outline segments
        const outlineSegments = getOutlineSegments(shape);

        // Check for intersections with each segment
        for (const seg of outlineSegments) {
            const intersection = findIntersection({
                start: { x: lineStartX, y: lineStartY },
                end: { x: lineEndX, y: lineEndY }
            }, seg);

            if (intersection) {
                intersections.push(intersection);
            }
        }

        // If we have at least 2 intersections, we can draw a line segment
        if (intersections.length >= 2) {
            // Sort intersections by distance from line start
            intersections.sort((a, b) => {
                const distA = Math.pow(a.x - lineStartX, 2) + Math.pow(a.y - lineStartY, 2);
                const distB = Math.pow(b.x - lineStartX, 2) + Math.pow(b.y - lineStartY, 2);
                return distA - distB;
            });

            // Group intersections into pairs
            for (let j = 0; j < intersections.length - 1; j += 2) {
                const int1 = intersections[j];
                const int2 = intersections[j + 1];

                // Skip if we don't have a pair
                if (!int2) continue;

                // Calculate midpoint of the line segment
                const midX = (int1.x + int2.x) / 2;
                const midY = (int1.y + int2.y) / 2;

                // Check if midpoint is inside the shape
                if (pointInShape(midX, midY, shape)) {
                    hatchLines.push({
                        x1: int1.x,
                        y1: int1.y,
                        x2: int2.x,
                        y2: int2.y
                    });
                }
            }
        }
    }

    return hatchLines;
}

// Generate SVG string with hatching for plotter art
function generateSVG() {
    // Start SVG with proper header and Inkscape namespaces
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
  xmlns="http://www.w3.org/2000/svg"
  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
  xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  
  <!-- Background -->
  <rect width="${width}" height="${height}" fill="white"/>
`;

    // Define hatching patterns (8 patterns as requested)
    const hatchingPatterns = [
        { angles: [45], spacing: 6 },   // Pattern 1: diagonal crosshatch
        { angles: [-45], spacing: 6 },   // Pattern 1: diagonal crosshatch
        { angles: [0], spacing: 6 },     // Pattern 2: grid
        { angles: [90], spacing: 6 },     // Pattern 2: grid
        { angles: [-15], spacing: 6 },   // Pattern 3: shallow crosshatch
        { angles: [15], spacing: 6 },   // Pattern 3: shallow crosshatch
        { angles: [-60], spacing: 6 },   // Pattern 4: steep crosshatch
        { angles: [60], spacing: 6 },   // Pattern 4: steep crosshatch
        { angles: [-30], spacing: 6 },   // Pattern 5: mixed angle
        { angles: [30], spacing: 6 },   // Pattern 5: mixed angle
        // { angles: [0], spacing: 8 },          // Pattern 6: horizontal (denser)
        // { angles: [45], spacing: 8 },         // Pattern 7: diagonal (denser)
        // { angles: [-75, 15], spacing: 12 }    // Pattern 8: uneven angles
    ];

    // Create a separate layer for each shape with its hatching
    for (let i = 0; i < shapes.length; i++) {
        const shape = shapes[i];
        const patternIndex = i % hatchingPatterns.length;
        const pattern = hatchingPatterns[patternIndex];

        // Create a layer for this shape
        svgString += `  <g id="shape${i}" 
     inkscape:label="Shape ${i}" 
     inkscape:groupmode="layer"
     sodipodi:insensitive="false">
`;

        // Create hatch pattern lines for this shape
        for (const angle of pattern.angles) {
            const hatchLines = generateHatchingLines(shape, angle, pattern.spacing);

            // Add all hatching lines for this angle
            for (const line of hatchLines) {
                svgString += `    <line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" stroke="black" stroke-width="1" />
`;
            }
        }

        // Close the shape layer
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
    svgString += `  <g id="outlines" 
     inkscape:label="Outlines" 
     inkscape:groupmode="layer"
     sodipodi:insensitive="false">
`;

    // Add SVG for each outline segment
    for (let seg of outerSegments) {
        svgString += `    <line x1="${seg.start.x}" y1="${seg.start.y}" x2="${seg.end.x}" y2="${seg.end.y}" stroke="black" stroke-width="10" />
`;
    }

    // Close the outlines layer
    svgString += `  </g>
`;

    // Close SVG
    svgString += `</svg>`;
    return svgString;
}

// Handle saving SVG
function keyPressed() {
    if (key === 's') {
        // Generate SVG string with hatching
        const svgContent = generateSVG();

        // Create a Blob with the SVG content
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });

        // Create a download link
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = "hatched_blobs_" + Date.now() + ".svg";

        // Append to body, click and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Clean up
        URL.revokeObjectURL(url);

        console.log("Hatched SVG saved!");
    }
}