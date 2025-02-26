// Global hatching patterns - modify once and used everywhere
const hatchingPatterns = [
    // Single angles at 15° increments
    { angles: [0], spacing: 12 },           // Pattern 0: Horizontal
    { angles: [15], spacing: 12 },          // Pattern 1: 15°
    { angles: [30], spacing: 12 },          // Pattern 2: 30°
    { angles: [45], spacing: 12 },          // Pattern 3: 45°
    { angles: [60], spacing: 12 },          // Pattern 4: 60°
    { angles: [75], spacing: 12 },          // Pattern 5: 75°
    { angles: [90], spacing: 12 },          // Pattern 6: Vertical

    // Perpendicular pairs (90° difference)
    { angles: [0, 90], spacing: 12 },       // Pattern 7: Grid
    { angles: [15, 105], spacing: 12 },     // Pattern 8: 15°/105° grid
    { angles: [30, 120], spacing: 12 },     // Pattern 9: 30°/120° grid
    { angles: [45, 135], spacing: 12 },     // Pattern 10: 45°/135° grid (diagonal crosshatch)

    // More random combinations
    { angles: [0, 45], spacing: 12 },       // Pattern 11: Mixed horizontal/diagonal
    { angles: [30, 75], spacing: 12 },      // Pattern 12: Mixed angles
    { angles: [15, 60], spacing: 12 },      // Pattern 13: Asymmetric angles
    { angles: [0, 30, 60, 90], spacing: 20 }, // Pattern 14: Multiple angles
    { angles: [15, 45, 75], spacing: 18 }   // Pattern 15: Triple angles
];

let shapes = [];
let renderMode = 5; // Default: 5 = truly continuous hatching

function setup() {
    createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(10, 35)); // Random number of total shapes
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

// Calculate truly clipped hatching lines for a shape
function calculateTrulyClippedHatchingLines(shapes, colorIndex, angle, spacing) {
    // Get all shapes with this color
    const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

    // If no shapes, return empty array
    if (shapesWithColor.length === 0) {
        return [];
    }

    // Calculate a global bounding box that encompasses all shapes of this color
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    for (const shape of shapesWithColor) {
        const bbox = getShapeBoundingBox(shape);
        minX = Math.min(minX, bbox.x);
        minY = Math.min(minY, bbox.y);
        maxX = Math.max(maxX, bbox.x + bbox.width);
        maxY = Math.max(maxY, bbox.y + bbox.height);
    }

    // Add padding to ensure coverage
    const padding = 100;
    minX -= padding;
    minY -= padding;
    maxX += padding;
    maxY += padding;

    // Calculate angle in radians
    const angleRad = angle * (Math.PI / 180);

    // Calculate perpendicular direction
    const perpAngle = angleRad + Math.PI / 2;
    const perpX = Math.cos(perpAngle);
    const perpY = Math.sin(perpAngle);

    // Calculate diagonal length for full coverage
    const diagonalLength = Math.sqrt(
        Math.pow(maxX - minX, 2) + Math.pow(maxY - minY, 2)
    );

    // Calculate center point
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    // Calculate number of lines needed
    const numLines = Math.ceil(diagonalLength / spacing) * 2;
    const startOffset = -diagonalLength / 2;

    // Result - will store all line segments
    let allLineSegments = [];

    // For each hatching line
    for (let i = 0; i < numLines; i++) {
        const offset = startOffset + i * spacing;

        // Calculate line start point perpendicular to hatching direction
        const offsetX = perpX * offset;
        const offsetY = perpY * offset;

        // Calculate line direction vector
        const dirX = Math.cos(angleRad);
        const dirY = Math.sin(angleRad);

        // Create a very long line that passes through the entire area
        const hatchLine = {
            start: {
                x: centerX + offsetX - dirX * diagonalLength,
                y: centerY + offsetY - dirY * diagonalLength
            },
            end: {
                x: centerX + offsetX + dirX * diagonalLength,
                y: centerY + offsetY + dirY * diagonalLength
            }
        };

        // For each shape, find intersection points
        for (const shape of shapesWithColor) {
            const outlineSegments = getOutlineSegments(shape);
            let intersections = [];

            // Find all intersections with shape boundary
            for (const segment of outlineSegments) {
                const intersection = findIntersection(hatchLine, segment);
                if (intersection) {
                    intersections.push(intersection);
                }
            }

            // Need at least 2 intersections (enter and exit shape)
            if (intersections.length >= 2) {
                // Sort intersections by distance from hatch line start
                intersections.sort((a, b) => {
                    const distA = Math.pow(a.x - hatchLine.start.x, 2) + Math.pow(a.y - hatchLine.start.y, 2);
                    const distB = Math.pow(b.x - hatchLine.start.x, 2) + Math.pow(b.y - hatchLine.start.y, 2);
                    return distA - distB;
                });

                // Process intersections in pairs (enter/exit)
                for (let j = 0; j < intersections.length - 1; j += 2) {
                    const p1 = intersections[j];
                    const p2 = intersections[j + 1];

                    // Check if we have a valid pair
                    if (!p1 || !p2) continue;

                    // Calculate midpoint to check if it's inside the shape
                    const midX = (p1.x + p2.x) / 2;
                    const midY = (p1.y + p2.y) / 2;

                    if (pointInShape(midX, midY, shape)) {
                        // We need to check if this segment is obscured by a higher z-index shape
                        let isObscured = false;
                        for (const otherShape of shapes) {
                            if (otherShape.zIndex > shape.zIndex && pointInShape(midX, midY, otherShape)) {
                                isObscured = true;
                                break;
                            }
                        }

                        if (!isObscured) {
                            // Add this line segment to our result
                            allLineSegments.push({
                                x1: p1.x,
                                y1: p1.y,
                                x2: p2.x,
                                y2: p2.y
                            });
                        }
                    }
                }
            }
        }
    }

    return allLineSegments;
}

// Generate SVG with truly clipped lines that will work with plotter software
function generatePlotterOptimizedSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
  xmlns="http://www.w3.org/2000/svg">
  
  <!-- Background -->
  <rect width="${width}" height="${height}" fill="white"/>
  
  <!-- Hatching lines by color -->
`;

    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // For each color, create a group with the hatching lines
    for (const colorIndex of colorIndices) {
        // Get the pattern for this color
        const pattern = hatchingPatterns[colorIndex % hatchingPatterns.length];

        svgString += `  <!-- Color group ${colorIndex} -->
  <g id="color-${colorIndex}">
`;

        // For each angle in the pattern, create hatching lines
        for (const angle of pattern.angles) {
            // Calculate all truly clipped line segments for this color and angle
            const lineSegments = calculateTrulyClippedHatchingLines(shapes, colorIndex, angle, pattern.spacing);

            // Add each line segment to the SVG
            for (const segment of lineSegments) {
                svgString += `    <line x1="${segment.x1}" y1="${segment.y1}" x2="${segment.x2}" y2="${segment.y2}" stroke="black" stroke-width="1"/>
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
    svgString += `  <!-- Outlines -->
  <g id="outlines">
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

// Map a given color to a hatching pattern index consistently
function getHatchingPatternByColor(colorIndex) {
    // This ensures that the same color always gets the same pattern
    return hatchingPatterns[colorIndex % hatchingPatterns.length];
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
        let svgContent = generatePlotterOptimizedSVG();

        // Create a Blob with the SVG content
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });

        // Create a download link with the mode indicated in the filename
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `plotter_optimized_hatching_${Date.now()}.svg`;

        // Append to body, click and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Clean up
        URL.revokeObjectURL(url);

        console.log(`Plotter-optimized SVG saved!`);
    }
}