// This function is ONLY used for SVG export, not for canvas drawing
// Generate consistent hatching lines by processing shapes from back to front
function generateConsistentHatchingLines() {
    // Result array for all line segments
    let allLineSegments = [];

    // Sort shapes by z-index (lowest to highest)
    const sortedShapes = [...shapes].sort((a, b) => a.zIndex - b.zIndex);

    // Process each shape from back to front
    for (const shape of sortedShapes) {
        // Get the hatching pattern for this shape's color
        const pattern = hatchingPatterns[shape.colorIndex % hatchingPatterns.length];

        // Create hatching lines for each angle in the pattern
        for (const angle of pattern.angles) {
            // Generate candidate line segments for this shape and angle
            const shapeSegments = generateShapeHatchingSegments(shape, angle, pattern.spacing);

            // For each candidate segment, check if it's obscured by any higher z-index shape
            for (const segment of shapeSegments) {
                let isObscured = false;
                const midX = (segment.x1 + segment.x2) / 2;
                const midY = (segment.y1 + segment.y2) / 2;

                // Check against all shapes with higher z-index
                for (const otherShape of shapes) {
                    if (otherShape.zIndex > shape.zIndex && pointInShape(midX, midY, otherShape)) {
                        isObscured = true;
                        break;
                    }
                }

                if (!isObscured) {
                    allLineSegments.push(segment);
                }
            }
        }
    }

    return allLineSegments;
}

// Generate hatching line segments for a single shape
function generateShapeHatchingSegments(shape, angle, spacing) {
    // Get bounding box for this shape
    const bbox = getShapeBoundingBox(shape);
    let minX = bbox.x - 50; // Add padding
    let minY = bbox.y - 50;
    let maxX = bbox.x + bbox.width + 50;
    let maxY = bbox.y + bbox.height + 50;

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

    // Result array
    let segments = [];

    // Generate all potential line segments
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

        // Find intersections with shape
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
                    // Add this line segment to our result
                    segments.push({
                        x1: p1.x,
                        y1: p1.y,
                        x2: p2.x,
                        y2: p2.y
                    });
                }
            }
        }
    }

    return segments;
}

// Modified draw function that avoids showing hatches in the canvas
function draw() {
    // Clear background
    background(255);

    // Step 1: Draw color fills without hatching
    noStroke();
    for (let shape of shapes) {
        fill(shape.fillColor);
        drawShapeFill(shape);
    }

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

// Update the SVG generation function to use our new approach
function generatePlotterOptimizedSVG() {
    // Start SVG with proper header
    let svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" 
  xmlns="http://www.w3.org/2000/svg">
  
  <!-- Background -->
  <rect width="${width}" height="${height}" fill="white"/>
  
  <!-- Hatching lines -->
  <g id="hatching-lines">
`;

    // Generate all hatching lines with the improved algorithm
    const lineSegments = generateConsistentHatchingLines();

    // Add each line segment to the SVG
    for (const segment of lineSegments) {
        svgString += `    <line x1="${segment.x1}" y1="${segment.y1}" x2="${segment.x2}" y2="${segment.y2}" stroke="black" stroke-width="1"/>
`;
    }

    svgString += `  </g>
`;

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