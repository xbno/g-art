let shapes = [];
let canvas;
let svg = false; // Flag to determine rendering mode

function setup() {
    // Create regular canvas by default
    canvas = createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(10, 45)); // Random number of total shapes
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
            // Triangle points are at (x,y-R), (x-R*cos(PI/6),y+R*sin(PI/6)), (x+R*cos(PI/6),y+R*sin(PI/6))
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
    // blendMode(DIFFERENCE); // Not all blend modes are supported in SVG

    // Step 1: Draw fills without stroke
    noStroke();
    let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]; // Pleasant color palette
    for (let shape of shapes) {
        fill(random(colors));
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
    // Make segments progressively darker
    for (let i = 0; i < splitSegments.length; i++) {
        let grayValue = map(i, 0, splitSegments.length - 1, 200, 50);
        splitSegments[i].color = color(grayValue);
    }

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

// Generate SVG string with layers for Inkscape
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

    // Get the colors we're using
    const colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];

    // Group shapes by color
    const colorGroups = {};
    for (const color of colors) {
        colorGroups[color] = [];
    }

    // Assign shapes to their color groups
    for (let i = 0; i < shapes.length; i++) {
        const shape = shapes[i];
        const fillColor = colors[i % colors.length];
        shape.fillColor = fillColor;

        if (!colorGroups[fillColor]) {
            colorGroups[fillColor] = [];
        }
        colorGroups[fillColor].push(shape);
    }

    // Create a separate layer for each color
    let layerIndex = 1;
    for (const color in colorGroups) {
        if (colorGroups[color].length > 0) {
            const colorName = color.substring(1); // Remove # from color code
            svgString += `  <g id="layer${layerIndex}" 
       inkscape:label="Fill ${color}" 
       inkscape:groupmode="layer"
       sodipodi:insensitive="false">
  `;

            // Add all shapes with this fill color
            for (let shape of colorGroups[color]) {
                if (shape.type === 'circle') {
                    svgString += `    <circle cx="${shape.x}" cy="${shape.y}" r="${shape.size / 2}" fill="${color}" stroke="none" />
  `;
                }
                else if (shape.type === 'square') {
                    const x = shape.x - shape.size / 2;
                    const y = shape.y - shape.size / 2;
                    svgString += `    <rect x="${x}" y="${y}" width="${shape.size}" height="${shape.size}" fill="${color}" stroke="none" />
  `;
                }
                else if (shape.type === 'triangle') {
                    const points = getShapePoints(shape);
                    const pointsStr = points.map(p => `${p.x},${p.y}`).join(' ');
                    svgString += `    <polygon points="${pointsStr}" fill="${color}" stroke="none" />
  `;
                }
            }

            // Close the color layer
            svgString += `  </g>
  `;
            layerIndex++;
        }
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
    svgString += `  <g id="layer${layerIndex}" 
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
        // Generate SVG string with layers
        const svgContent = generateSVG();

        // Create a Blob with the SVG content
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });

        // Create a download link
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = "layered_blobs_" + Date.now() + ".svg";

        // Append to body, click and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Clean up
        URL.revokeObjectURL(url);

        console.log("Layered SVG saved!");
    }
}