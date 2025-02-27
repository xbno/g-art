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

// Improved function to draw bounding boxes around shapes of the same color
function drawColorBoundingBoxes() {
    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // For each color group, calculate and draw a bounding box
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color
        const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Calculate a bounding box for all shapes with this color
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;

        for (const shape of shapesWithColor) {
            const bbox = getShapeBoundingBox(shape);
            minX = min(minX, bbox.x);
            minY = min(minY, bbox.y);
            maxX = max(maxX, bbox.x + bbox.width);
            maxY = max(maxY, bbox.y + bbox.height);
        }

        // Draw the bounding box as a dotted red rectangle
        push(); // Save current style settings
        stroke(255, 0, 0); // Red outline
        strokeWeight(3);
        noFill();
        drawingContext.setLineDash([8, 8]); // More visible dotted pattern
        rect(minX, minY, maxX - minX, maxY - minY);
        drawingContext.setLineDash([]); // Reset dash pattern

        // Add a label with the color index
        noStroke();
        fill(255, 0, 0);
        textSize(24); // Larger text
        textAlign(LEFT, TOP);
        text(`Color ${colorIndex}`, minX + 10, minY + 10);
        pop(); // Restore previous style settings
    }
}

// Function to highlight all shapes of the same color
function highlightColorGroups() {
    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // For each color group
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color
        const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Draw a semi-transparent highlight over these shapes
        push(); // Save current style settings
        noStroke();

        // Choose a highlight color based on colorIndex
        const highlightColors = [
            color(255, 0, 0, 50),   // Red with 50 alpha
            color(0, 255, 0, 50),   // Green with 50 alpha
            color(0, 0, 255, 50),   // Blue with 50 alpha
            color(255, 255, 0, 50), // Yellow with 50 alpha
            color(255, 0, 255, 50)  // Magenta with 50 alpha
        ];

        fill(highlightColors[colorIndex % highlightColors.length]);

        // Draw each shape with this color
        for (const shape of shapesWithColor) {
            if (shape.type === 'circle') {
                ellipse(shape.x, shape.y, shape.size);
            } else if (shape.type === 'square') {
                rectMode(CENTER);
                rect(shape.x, shape.y, shape.size, shape.size);
            } else if (shape.type === 'triangle') {
                const points = getShapePoints(shape);
                beginShape();
                for (const p of points) {
                    vertex(p.x, p.y);
                }
                endShape(CLOSE);
            }
        }

        // Add a label in the center of the first shape
        if (shapesWithColor.length > 0) {
            const firstShape = shapesWithColor[0];
            fill(255, 0, 0);
            stroke(255);
            strokeWeight(2);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, firstShape.x, firstShape.y);
        }

        pop(); // Restore previous style settings
    }
}

// Alternative approach - draw outline around all shapes of each color
function outlineColorGroups() {
    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    push(); // Save current drawing settings

    // For each color group
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color
        const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Set styling for this color group's outline
        stroke(255, 0, 0); // Red outline
        strokeWeight(3);
        noFill();
        drawingContext.setLineDash([5, 5]); // Dotted line

        // Draw outline for each shape in this color group
        for (const shape of shapesWithColor) {
            if (shape.type === 'circle') {
                ellipse(shape.x, shape.y, shape.size);
            } else if (shape.type === 'square') {
                rectMode(CENTER);
                rect(shape.x, shape.y, shape.size, shape.size);
            } else if (shape.type === 'triangle') {
                const points = getShapePoints(shape);
                beginShape();
                for (const p of points) {
                    vertex(p.x, p.y);
                }
                endShape(CLOSE);
            }

            // Add a label
            push();
            noStroke();
            fill(255, 0, 0);
            textSize(18);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, shape.x, shape.y);
            pop();
        }
    }

    // Reset line dash and restore drawing settings
    drawingContext.setLineDash([]);
    pop();
}

// function draw() {
//     // Clear the canvas
//     background(255);

//     // Process shape colors
//     let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]; // Pleasant color palette

//     // Assign a specific color to each shape for consistency
//     for (let i = 0; i < shapes.length; i++) {
//         shapes[i].fillColor = colors[i % colors.length];
//         shapes[i].colorIndex = i % colors.length; // Store color index for hatching pattern
//     }

//     // Use the more advanced visualization that shows precise non-overlapping areas
//     extractEffectiveHatchingAreas();

//     // No need to loop since this is a static visualization
//     noLoop();
// }

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
        let numSides = 64;
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

// Function to draw bounding boxes around shapes of the same color
function drawColorBoundingBoxes() {
    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // Set drawing style for bounding boxes
    stroke(255, 0, 0); // Red outline
    strokeWeight(2);
    noFill();

    // For each color group, calculate and draw a bounding box
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color
        const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Calculate a bounding box for all shapes with this color
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;

        for (const shape of shapesWithColor) {
            const bbox = getShapeBoundingBox(shape);
            minX = Math.min(minX, bbox.x);
            minY = Math.min(minY, bbox.y);
            maxX = Math.max(maxX, bbox.x + bbox.width);
            maxY = Math.max(maxY, bbox.y + bbox.height);
        }

        // Draw the bounding box as a dotted red rectangle
        drawingContext.setLineDash([5, 5]); // Set dotted line pattern
        rect(minX, minY, maxX - minX, maxY - minY);

        // Add a label with the color index
        noStroke();
        fill(255, 0, 0);
        textSize(16);
        text(`Color ${colorIndex}`, minX + 5, minY + 15);
    }

    // Reset line dash to solid for other drawings
    drawingContext.setLineDash([]);
}

// Function to draw more precise polygons around shapes of the same color
function drawColorPolygons() {
    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // Set drawing style
    stroke(255, 0, 0); // Red outline
    strokeWeight(2);
    noFill();

    // For each color group, find the outlines
    for (const colorIndex of colorIndices) {
        // Get all shapes with this color
        const shapesWithColor = shapes.filter(shape => shape.colorIndex === colorIndex);

        if (shapesWithColor.length === 0) continue;

        // Get all segments for these shapes
        let allSegments = [];
        for (let shape of shapesWithColor) {
            let segments = getOutlineSegments(shape);
            allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
        }

        // Set dotted line style
        drawingContext.setLineDash([5, 5]);

        // Draw all segments
        for (let seg of allSegments) {
            line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
        }

        // Reset line dash
        drawingContext.setLineDash([]);

        // Add a label near the first shape
        if (shapesWithColor.length > 0) {
            const firstShape = shapesWithColor[0];
            noStroke();
            fill(255, 0, 0);
            textSize(16);
            text(`Color ${colorIndex}`, firstShape.x, firstShape.y);
        }
    }
}

// Function to visualize the actual non-overlapping areas for each color
function visualizeNonOverlappingColorAreas() {
    // Sort shapes by z-index (back to front)
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Create a canvas mask for each color
    const colorMasks = {};
    const colorIndices = [...new Set(shapes.map(s => s.colorIndex))];

    // Initialize a mask for each color
    for (const colorIndex of colorIndices) {
        colorMasks[colorIndex] = createGraphics(width, height);
        colorMasks[colorIndex].background(0, 0); // Transparent background
    }

    // Process shapes in z-index order
    for (const shape of sortedShapes) {
        const colorIndex = shape.colorIndex;
        const mask = colorMasks[colorIndex];

        // Set color to identify this area
        mask.fill(255);
        mask.noStroke();

        // Draw this shape on its color mask
        const points = getShapePoints(shape);
        mask.beginShape();
        for (const p of points) {
            mask.vertex(p.x, p.y);
        }
        mask.endShape(CLOSE);

        // Erase this shape from all colors with lower z-index
        for (const otherColorIndex of colorIndices) {
            if (otherColorIndex !== colorIndex) {
                const otherShapes = shapes.filter(s => s.colorIndex === otherColorIndex);

                // Check if we need to erase
                const needsErase = otherShapes.some(s => s.zIndex < shape.zIndex);

                if (needsErase) {
                    const otherMask = colorMasks[otherColorIndex];
                    otherMask.erase();
                    otherMask.beginShape();
                    for (const p of points) {
                        otherMask.vertex(p.x, p.y);
                    }
                    otherMask.endShape(CLOSE);
                    otherMask.noErase();
                }
            }
        }
    }

    // Now draw all the color masks with red dotted outlines
    for (const colorIndex of colorIndices) {
        const mask = colorMasks[colorIndex];

        // Get the mask's pixels to find the contour
        mask.loadPixels();

        // Draw the mask as a semi-transparent overlay
        push();
        image(mask, 0, 0);
        pop();

        // Find blob contours and draw them
        push();
        stroke(255, 0, 0);
        strokeWeight(3);
        drawingContext.setLineDash([8, 8]);
        noFill();

        // Draw the edges of the mask
        // This is simplified - ideally we'd extract contours from the mask
        // but we'll simulate by tracing all non-transparent pixels

        // Add label for this color group
        const shapesInColor = shapes.filter(s => s.colorIndex === colorIndex);
        if (shapesInColor.length > 0) {
            // Find center of first shape as a place to put the label
            const shape = shapesInColor[0];
            push();
            noStroke();
            fill(255, 0, 0);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, shape.x, shape.y);
            pop();
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

// Alternative approach using simplified polygon visualization
function drawClippedColorAreas() {
    // Sort shapes by z-index
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Create a buffer for processing
    const buffer = createGraphics(width, height);

    // For each color, calculate its visible area
    const colorIndices = [...new Set(shapes.map(s => s.colorIndex))];

    for (const colorIndex of colorIndices) {
        // Clear the buffer
        buffer.clear();
        buffer.background(0, 0); // Transparent

        // Find all shapes of this color
        const shapesWithColor = shapes.filter(s => s.colorIndex === colorIndex);

        // Draw all shapes of this color to the buffer
        buffer.fill(255);
        buffer.noStroke();

        for (const shape of shapesWithColor) {
            const points = getShapePoints(shape);
            buffer.beginShape();
            for (const p of points) {
                buffer.vertex(p.x, p.y);
            }
            buffer.endShape(CLOSE);
        }

        // Now erase any parts covered by higher z-index shapes
        buffer.erase();

        for (const shape of sortedShapes) {
            // If this shape has a higher z-index than any shape in our color group
            if (!shapesWithColor.includes(shape) &&
                shapesWithColor.some(s => shape.zIndex > s.zIndex)) {
                const points = getShapePoints(shape);
                buffer.beginShape();
                for (const p of points) {
                    buffer.vertex(p.x, p.y);
                }
                buffer.endShape(CLOSE);
            }
        }

        buffer.noErase();

        // Draw the resulting clipped area
        image(buffer, 0, 0);

        // Draw red dotted outlines around the visible area
        push();
        stroke(255, 0, 0);
        strokeWeight(3);
        drawingContext.setLineDash([8, 8]);
        noFill();

        // Here we would ideally trace the contour of the buffer
        // For simplicity, let's just outline the original shapes for now
        for (const shape of shapesWithColor) {
            if (shape.type === 'circle') {
                ellipse(shape.x, shape.y, shape.size);
            } else if (shape.type === 'square') {
                rectMode(CENTER);
                rect(shape.x, shape.y, shape.size, shape.size);
            } else if (shape.type === 'triangle') {
                const points = getShapePoints(shape);
                beginShape();
                for (const p of points) {
                    vertex(p.x, p.y);
                }
                endShape(CLOSE);
            }
        }

        // Add a label for this color
        if (shapesWithColor.length > 0) {
            const firstShape = shapesWithColor[0];
            push();
            noStroke();
            fill(255, 0, 0);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, firstShape.x, firstShape.y);
            pop();
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

// Improved function to visualize all non-overlapping regions by color
function visualizeNonOverlappingRegions() {
    // Clear the background first to start fresh
    background(255);

    // Draw all shapes with their proper fills
    for (let shape of shapes) {
        fill(shape.fillColor);
        noStroke();
        drawShapeFill(shape);
    }

    // Draw the main black outlines
    stroke(0);
    strokeWeight(10);
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    // Get unique color indices
    const colorIndices = [...new Set(shapes.map(shape => shape.colorIndex))];

    // Process each color
    for (const colorIndex of colorIndices) {
        // Create graphics buffer for this color
        const colorBuffer = createGraphics(width, height);
        colorBuffer.clear();

        // First, draw all shapes of this color to the buffer
        const colorShapes = shapes.filter(s => s.colorIndex === colorIndex);
        colorBuffer.fill(255);
        colorBuffer.noStroke();

        for (const shape of colorShapes) {
            const points = getShapePoints(shape);
            colorBuffer.beginShape();
            for (const p of points) {
                colorBuffer.vertex(p.x, p.y);
            }
            colorBuffer.endShape(CLOSE);
        }

        // Then erase any parts covered by higher z-index shapes
        colorBuffer.erase();
        for (const shape of shapes) {
            // If this shape has higher z-index than ANY shape in our color group
            if (colorShapes.some(cs => shape.zIndex > cs.zIndex)) {
                const points = getShapePoints(shape);
                colorBuffer.beginShape();
                for (const p of points) {
                    colorBuffer.vertex(p.x, p.y);
                }
                colorBuffer.endShape(CLOSE);
            }
        }
        colorBuffer.noErase();

        // Now trace the outline of this color's region
        // Use a different dash pattern and color for each color index to distinguish them
        push();

        // Define different colors and dash patterns for outlines
        const outlineColors = [
            [255, 0, 0],    // Red
            [0, 255, 0],    // Green
            [0, 0, 255],    // Blue
            [255, 128, 0],  // Orange
            [128, 0, 255]   // Purple
        ];

        const dashPatterns = [
            [8, 8],         // Standard dash
            [2, 6],         // Short dash, long gap
            [12, 4],        // Long dash, short gap
            [8, 4, 2, 4],   // Dash-dot
            [2, 2]          // Short dashes
        ];

        // Set style for this color's outline
        const colorIndexMod = colorIndex % outlineColors.length;
        stroke(outlineColors[colorIndexMod][0], outlineColors[colorIndexMod][1], outlineColors[colorIndexMod][2]);
        strokeWeight(3);
        drawingContext.setLineDash(dashPatterns[colorIndexMod]);
        noFill();

        // Draw border lines for the non-overlapping region
        // (This is a simple approach - in a full implementation you'd extract the contours)
        image(colorBuffer, 0, 0, 1, 1); // Draw 1x1 pixel to get it into the canvas

        // Get a center point for the first shape of this color for label placement
        if (colorShapes.length > 0) {
            const firstShape = colorShapes[0];

            // Handle different outline styles based on shape type
            // For actual implementation, we'd need contour tracing or an outline shader
            for (const shape of colorShapes) {
                const points = getShapePoints(shape);
                beginShape();
                for (const p of points) {
                    vertex(p.x, p.y);
                }
                endShape(CLOSE);
            }

            // Add label with the color index
            noStroke();
            fill(outlineColors[colorIndexMod][0], outlineColors[colorIndexMod][1], outlineColors[colorIndexMod][2]);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, firstShape.x, firstShape.y);
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

// Function to extract and visualize the actual effective hatching areas
function extractEffectiveHatchingAreas() {
    // Sort shapes by z-index (back to front)
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Create an array of graphics buffers to hold each color's effective area
    const colorIndices = [...new Set(shapes.map(s => s.colorIndex))];
    const colorBuffers = {};

    // Initialize a buffer for each color
    for (const colorIndex of colorIndices) {
        colorBuffers[colorIndex] = createGraphics(width, height);
        colorBuffers[colorIndex].clear();
    }

    // Process shapes in z-index order (back to front)
    for (let i = 0; i < sortedShapes.length; i++) {
        const shape = sortedShapes[i];
        const colorIndex = shape.colorIndex;
        const buffer = colorBuffers[colorIndex];

        // Draw this shape to its color buffer
        buffer.fill(255);
        buffer.noStroke();

        const points = getShapePoints(shape);
        buffer.beginShape();
        for (const p of points) {
            buffer.vertex(p.x, p.y);
        }
        buffer.endShape(CLOSE);

        // Now erase this shape from all lower z-index colors' buffers
        for (const otherShape of sortedShapes) {
            if (otherShape.zIndex < shape.zIndex) {
                const otherColorIndex = otherShape.colorIndex;
                const otherBuffer = colorBuffers[otherColorIndex];

                // Check if we need to erase (if point is inside both shapes)
                // This is a simple approximation - we'd ideally check for overlap
                otherBuffer.erase();
                otherBuffer.beginShape();
                for (const p of points) {
                    otherBuffer.vertex(p.x, p.y);
                }
                otherBuffer.endShape(CLOSE);
                otherBuffer.noErase();
            }
        }
    }

    // Draw the original shapes and outlines
    background(255);

    // Draw all shapes with their proper fills
    for (let shape of shapes) {
        fill(shape.fillColor);
        noStroke();
        drawShapeFill(shape);
    }

    // Draw the main black outlines
    stroke(0);
    strokeWeight(10);
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    // Now outline each color's effective area with a distinct colored dotted line
    const outlineColors = [
        [255, 0, 0],    // Red
        [0, 255, 0],    // Green
        [0, 0, 255],    // Blue
        [255, 128, 0],  // Orange
        [128, 0, 255]   // Purple
    ];

    const dashPatterns = [
        [8, 8],         // Standard dash
        [2, 6],         // Short dash, long gap
        [12, 4],        // Long dash, short gap
        [8, 4, 2, 4],   // Dash-dot
        [2, 2]          // Short dashes
    ];

    // Draw each color's effective hatching area
    for (const colorIndex of colorIndices) {
        // Get the buffer for this color
        const buffer = colorBuffers[colorIndex];

        // Set style for this color's outline
        const colorIndexMod = colorIndex % outlineColors.length;
        stroke(outlineColors[colorIndexMod][0], outlineColors[colorIndexMod][1], outlineColors[colorIndexMod][2]);
        strokeWeight(3);
        drawingContext.setLineDash(dashPatterns[colorIndexMod]);
        noFill();

        // Get the center of a shape with this color for label placement
        const shapesWithThisColor = shapes.filter(s => s.colorIndex === colorIndex);
        let labelX = width / 2, labelY = height / 2;

        if (shapesWithThisColor.length > 0) {
            labelX = shapesWithThisColor[0].x;
            labelY = shapesWithThisColor[0].y;
        }

        // Draw the buffer as an image
        image(buffer, 0, 0);

        // Add the color label
        push();
        noStroke();
        fill(outlineColors[colorIndexMod][0], outlineColors[colorIndexMod][1], outlineColors[colorIndexMod][2]);
        textSize(24);
        textAlign(CENTER, CENTER);
        text(`Color ${colorIndex}`, labelX, labelY);
        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

// Function to visualize color regions using pixel sampling
function visualizeColorRegionsByPixels() {
    // Step 1: Render all shapes to the canvas with their colors
    background(255);

    // Draw all shapes with fill but no stroke
    noStroke();
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

    // Step 2: Create offscreen buffer to sample colors without outlines
    const buffer = createGraphics(width, height);
    buffer.background(255);

    // Draw all shapes to buffer with colors assigned by colorIndex
    buffer.noStroke();
    for (let shape of shapes) {
        // Use a specific RGB color for each colorIndex to make detection easy
        const colorValue = shape.colorIndex + 1; // Add 1 to avoid black (0,0,0)
        buffer.fill(colorValue * 50, colorValue * 40, colorValue * 30);

        // Draw shape to buffer
        const points = getShapePoints(shape);
        buffer.beginShape();
        for (const p of points) {
            buffer.vertex(p.x, p.y);
        }
        buffer.endShape(CLOSE);
    }

    // Step 3: Process buffer to detect color regions
    buffer.loadPixels();

    // Step 4: Sample grid of points and check for color boundaries
    const gridSpacing = 5; // Small spacing for detailed detection
    const colorOutlines = {}; // Store points for each color region

    // Initialize color outlines object
    for (let i = 0; i < 5; i++) { // Assuming 5 colors max
        colorOutlines[i] = [];
    }

    // Check each grid point
    for (let x = 0; x < width; x += gridSpacing) {
        for (let y = 0; y < height; y += gridSpacing) {
            // Get color at this point
            const index = 4 * (y * buffer.width + x);
            const r = buffer.pixels[index];
            const g = buffer.pixels[index + 1];
            const b = buffer.pixels[index + 2];

            // Skip white background
            if (r === 255 && g === 255 && b === 255) continue;

            // Determine colorIndex from the RGB values
            // This is an approximation - we look at red channel primarily
            const colorIndex = Math.round(r / 50) - 1;

            // Check if this point is on a boundary by looking at adjacent pixels
            let isBoundary = false;

            // Check in 4 directions
            const directions = [[1, 0], [0, 1], [-1, 0], [0, -1]];

            for (const [dx, dy] of directions) {
                const nx = x + dx * gridSpacing;
                const ny = y + dy * gridSpacing;

                // Skip if out of bounds
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                    isBoundary = true; // Edge of canvas is a boundary
                    continue;
                }

                // Get color at the adjacent point
                const adjIndex = 4 * (ny * buffer.width + nx);
                const adjR = buffer.pixels[adjIndex];
                const adjG = buffer.pixels[adjIndex + 1];
                const adjB = buffer.pixels[adjIndex + 2];

                // If the adjacent pixel is different color or background, this is a boundary
                if (adjR !== r || adjG !== g || adjB !== b) {
                    isBoundary = true;
                    break;
                }
            }

            // If this is a boundary point and valid colorIndex, store it
            if (isBoundary && colorIndex >= 0 && colorIndex < 5) {
                colorOutlines[colorIndex].push({ x, y });
            }
        }
    }

    // Step 5: Draw original shapes with outlines
    background(255);

    // Draw all shapes with their colors
    noStroke();
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

    // Draw the main black outlines
    stroke(0);
    strokeWeight(10);
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    // Step 6: Draw the detected color region boundaries
    const outlineColors = [
        [255, 0, 0],    // Red
        [0, 255, 0],    // Green
        [0, 0, 255],    // Blue
        [255, 128, 0],  // Orange
        [128, 0, 255]   // Purple
    ];

    const dashPatterns = [
        [4, 4],         // Standard dash
        [2, 6],         // Short dash, long gap
        [12, 4],        // Long dash, short gap
        [6, 3, 2, 3],   // Dash-dot
        [2, 2]          // Short dashes
    ];

    // Draw each color's boundary points
    for (let colorIndex = 0; colorIndex < 5; colorIndex++) {
        const points = colorOutlines[colorIndex];

        // Skip if no points for this color
        if (points.length === 0) continue;

        // Set style for this color
        push();
        stroke(outlineColors[colorIndex][0], outlineColors[colorIndex][1], outlineColors[colorIndex][2]);
        strokeWeight(3);
        drawingContext.setLineDash(dashPatterns[colorIndex]);

        // Draw points as small dots
        for (const point of points) {
            point(point.x, point.y);
        }

        // Add a label near the center of this color region
        if (points.length > 0) {
            // Find center by averaging points
            let sumX = 0, sumY = 0;
            for (const point of points) {
                sumX += point.x;
                sumY += point.y;
            }
            const centerX = sumX / points.length;
            const centerY = sumY / points.length;

            // Draw label
            noStroke();
            fill(outlineColors[colorIndex][0], outlineColors[colorIndex][1], outlineColors[colorIndex][2]);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, centerX, centerY);
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

// Simplified approach - render all shapes, then highlight each color's region
function highlightEffectiveColorRegions() {
    // Step 1: Draw all shapes with their normal colors
    background(255);

    // Draw all shapes with fill but no stroke
    noStroke();
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

    // Draw the main black outlines
    stroke(0);
    strokeWeight(10);
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    // Step 2: Loop through each pixel and highlight regions
    loadPixels();

    // Create individual graphics buffers for each colorIndex
    const colorBuffers = {};
    const colorIndices = [...new Set(shapes.map(s => s.colorIndex))];

    for (const colorIndex of colorIndices) {
        colorBuffers[colorIndex] = createGraphics(width, height);
        colorBuffers[colorIndex].clear();
        colorBuffers[colorIndex].noStroke();
        colorBuffers[colorIndex].fill(255);
    }

    // Set a grid spacing to sample pixels (reduce computation)
    const gridSpacing = 4;

    // Create temporary buffer for color sampling
    const tempBuffer = createGraphics(width, height);
    tempBuffer.background(255);

    // Draw shapes with unique colors to the temp buffer
    for (let shape of shapes) {
        // Use a unique color based on colorIndex
        const colorValue = shape.colorIndex + 1; // Add 1 to avoid 0
        tempBuffer.fill(colorValue * 50, colorValue * 40, colorValue * 30);
        tempBuffer.noStroke();

        // Draw shape based on type
        if (shape.type === 'circle') {
            tempBuffer.ellipse(shape.x, shape.y, shape.size);
        } else if (shape.type === 'square') {
            tempBuffer.rectMode(CENTER);
            tempBuffer.rect(shape.x, shape.y, shape.size, shape.size);
        } else if (shape.type === 'triangle') {
            const points = getShapePoints(shape);
            tempBuffer.beginShape();
            for (const p of points) {
                tempBuffer.vertex(p.x, p.y);
            }
            tempBuffer.endShape(CLOSE);
        }
    }

    // Load buffer pixels for sampling
    tempBuffer.loadPixels();

    // Sample grid of pixels
    for (let x = 0; x < width; x += gridSpacing) {
        for (let y = 0; y < height; y += gridSpacing) {
            // Get pixel color at this position
            const idx = 4 * (y * tempBuffer.width + x);
            const r = tempBuffer.pixels[idx];
            const g = tempBuffer.pixels[idx + 1];
            const b = tempBuffer.pixels[idx + 2];

            // Skip white background
            if (r === 255 && g === 255 && b === 255) continue;

            // Determine colorIndex from the pixel color
            const colorIndex = Math.round(r / 50) - 1;

            // Check if valid colorIndex
            if (colorIndex >= 0 && colorIndex < 5 && colorBuffers[colorIndex]) {
                // Draw a dot at this position in the corresponding buffer
                colorBuffers[colorIndex].noStroke();
                colorBuffers[colorIndex].fill(255);
                colorBuffers[colorIndex].rect(x, y, gridSpacing, gridSpacing);
            }
        }
    }

    // Draw colored outlines around each color's effective region
    const outlineColors = [
        [255, 0, 0],    // Red
        [0, 255, 0],    // Green
        [0, 0, 255],    // Blue
        [255, 128, 0],  // Orange
        [128, 0, 255]   // Purple
    ];

    const dashPatterns = [
        [8, 8],         // Standard dash
        [2, 6],         // Short dash, long gap
        [12, 4],        // Long dash, short gap
        [8, 4, 2, 4],   // Dash-dot
        [2, 2]          // Short dashes
    ];

    // Step 3: Draw each color's region with a colored border
    for (const colorIndex of colorIndices) {
        push();
        stroke(outlineColors[colorIndex % outlineColors.length][0],
            outlineColors[colorIndex % outlineColors.length][1],
            outlineColors[colorIndex % outlineColors.length][2]);
        strokeWeight(3);
        drawingContext.setLineDash(dashPatterns[colorIndex % dashPatterns.length]);
        noFill();

        // Draw the buffer for this color
        image(colorBuffers[colorIndex], 0, 0);

        // Find a good spot for a label
        const shapes = [...shapes].filter(s => s.colorIndex === colorIndex);
        if (shapes.length > 0) {
            const shape = shapes[0];

            // Draw label
            noStroke();
            fill(outlineColors[colorIndex % outlineColors.length][0],
                outlineColors[colorIndex % outlineColors.length][1],
                outlineColors[colorIndex % outlineColors.length][2]);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, shape.x, shape.y);
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}


// A much simpler approach - just render visual boundaries based on pixel sampling
function visualizeColorBoundaries() {
    // Step 1: Clear the canvas
    background(255);

    // Step 2: Assign consistent colors to shapes
    let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]; // Pleasant color palette
    for (let i = 0; i < shapes.length; i++) {
        shapes[i].fillColor = colors[i % colors.length];
        shapes[i].colorIndex = i % colors.length;
    }

    // Step 3: Draw all shapes (filled with their colors, no outlines yet)
    noStroke();
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

    // Step 4: Create an off-screen buffer for color analysis
    const buffer = createGraphics(width, height);
    buffer.background(255);

    // Step 5: Draw shapes to buffer with unique colors per colorIndex
    for (let shape of shapes) {
        // Use separate R,G,B values to encode colorIndex
        // This creates visually distinct colors that are easy to identify
        const r = (shape.colorIndex * 50) + 50;
        const g = (shape.colorIndex * 40) + 40;
        const b = (shape.colorIndex * 30) + 30;

        buffer.fill(r, g, b);
        buffer.noStroke();

        // Draw shape in buffer
        if (shape.type === 'circle') {
            buffer.ellipse(shape.x, shape.y, shape.size);
        } else if (shape.type === 'square') {
            buffer.rectMode(CENTER);
            buffer.rect(shape.x, shape.y, shape.size, shape.size);
        } else if (shape.type === 'triangle') {
            const points = getShapePoints(shape);
            buffer.beginShape();
            for (const p of points) {
                buffer.vertex(p.x, p.y);
            }
            buffer.endShape(CLOSE);
        }
    }

    // Step 6: Sample buffer pixels to find edges between colors
    buffer.loadPixels();

    const colorPoints = {};
    const colorIndices = [...new Set(shapes.map(s => s.colorIndex))];

    // Initialize arrays for each color
    for (const colorIndex of colorIndices) {
        colorPoints[colorIndex] = [];
    }

    // Set sampling density (smaller = more detailed)
    const sampleSpacing = 4;

    // Check each pixel in a grid pattern
    for (let x = 0; x < width; x += sampleSpacing) {
        for (let y = 0; y < height; y += sampleSpacing) {
            // Get pixel color at this position
            const idx = 4 * (y * buffer.width + x);
            const r = buffer.pixels[idx];
            const g = buffer.pixels[idx + 1];
            const b = buffer.pixels[idx + 2];

            // Skip white background
            if (r === 255 && g === 255 && b === 255) continue;

            // Determine colorIndex from RGB values
            const colorIndex = Math.round((r - 50) / 50);

            // Check if this is an edge pixel by examining neighbors
            let isEdge = false;

            // Check in 4 directions
            const directions = [[1, 0], [0, 1], [-1, 0], [0, -1]];
            for (const [dx, dy] of directions) {
                const nx = x + dx * sampleSpacing;
                const ny = y + dy * sampleSpacing;

                // Skip if out of bounds
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                    isEdge = true; // Canvas edge counts as an edge
                    continue;
                }

                // Get adjacent pixel color
                const adjIdx = 4 * (ny * buffer.width + nx);
                const adjR = buffer.pixels[adjIdx];
                const adjG = buffer.pixels[adjIdx + 1];
                const adjB = buffer.pixels[adjIdx + 2];

                // If adjacent pixel is a different color or background, this is an edge
                if (Math.abs(r - adjR) > 20 || Math.abs(g - adjG) > 20 || Math.abs(b - adjB) > 20) {
                    isEdge = true;
                    break;
                }
            }

            // If this is an edge pixel, add it to the appropriate color array
            if (isEdge && colorIndex >= 0 && colorIndex < colors.length) {
                colorPoints[colorIndex].push({ x, y });
            }
        }
    }

    // Step 7: Draw the main black outlines
    stroke(0);
    strokeWeight(10);
    let allSegments = [];
    for (let shape of shapes) {
        let segments = getOutlineSegments(shape);
        allSegments.push(...segments.map(seg => ({ ...seg, parent: shape })));
    }
    let splitSegments = splitSegmentsAtIntersections(allSegments);
    let outerSegments = filterOuterSegments(splitSegments);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    // Step 8: Draw the edge points for each color with a different colored dotted line
    const outlineColors = [
        [255, 0, 0],    // Red
        [0, 255, 0],    // Green 
        [0, 0, 255],    // Blue
        [255, 165, 0],  // Orange
        [128, 0, 128]   // Purple
    ];

    const dashPatterns = [
        [5, 5],       // Standard dash
        [2, 4],       // Short dash, longer gap
        [8, 4],       // Long dash, short gap
        [5, 2, 2, 2], // Dash-dot
        [1, 3]        // Very short dash
    ];

    // Draw each color's edge points
    for (const colorIndex of colorIndices) {
        const points = colorPoints[colorIndex];
        if (points.length === 0) continue;

        // Set style for this color
        push();
        stroke(outlineColors[colorIndex % outlineColors.length][0],
            outlineColors[colorIndex % outlineColors.length][1],
            outlineColors[colorIndex % outlineColors.length][2]);
        strokeWeight(2);
        drawingContext.setLineDash(dashPatterns[colorIndex % dashPatterns.length]);

        // Draw points - simplified approach
        for (const point of points) {
            point(point.x, point.y);
        }

        // Add color label near center of a shape with this color
        const shapesWithColor = shapes.filter(s => s.colorIndex === colorIndex);
        if (shapesWithColor.length > 0) {
            const firstShape = shapesWithColor[0];
            noStroke();
            fill(outlineColors[colorIndex % outlineColors.length][0],
                outlineColors[colorIndex % outlineColors.length][1],
                outlineColors[colorIndex % outlineColors.length][2]);
            textSize(24);
            textAlign(CENTER, CENTER);
            text(`Color ${colorIndex}`, firstShape.x, firstShape.y);
        }

        pop();
    }

    // Reset line dash
    drawingContext.setLineDash([]);
}

function draw() {
    // Call our simplified visualization function
    visualizeColorBoundaries();

    noLoop(); // Static visualization
}