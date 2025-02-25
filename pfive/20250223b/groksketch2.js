let shapes = [];

function setup() {
    createCanvas(1200, 1800);
    background(255); // White background

    // Generate k random shapes
    let k = floor(random(10, 15)); // Random number of total shapes
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
    blendMode(DIFFERENCE);
    // Step 1: Draw fills without stroke
    noStroke();
    for (let shape of shapes) {
        fill(shape.color);
        drawShapeFill(shape);
    }
    // Reset blend mode to BLEND for outlines
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
    strokeWeight(5);
    for (let seg of outerSegments) {
        line(seg.start.x, seg.start.y, seg.end.x, seg.end.y);
    }

    noLoop(); // Static sketch
}

// Draw the fill of a shape
function drawShapeFill(shape) {
    beginShape();
    fill(50);
    let points = getShapePoints(shape);
    for (let p of points) {
        vertex(p.x, p.y);
    }
    endShape(CLOSE);
}

// function drawShapeFill(shape, type = 'dots') {
//     beginShape();
//     fill(50);
//     let points = getShapePoints(shape);
//     for (let p of points) {
//         vertex(p.x, p.y);
//     }
//     endShape(CLOSE);

//     let minX = Infinity, minY = Infinity;
//     let maxX = -Infinity, maxY = -Infinity;
//     for (let p of points) {
//         minX = min(minX, p.x);
//         minY = min(minY, p.y);
//         maxX = max(maxX, p.x);
//         maxY = max(maxY, p.y);
//     }

//     push();
//     fill(shape.color);
//     noStroke();
//     let spacing = 5;
//     for (let x = minX; x < maxX; x += spacing) {
//         for (let y = minY; y < maxY; y += spacing) {
//             if (pointInShape(x, y, shape)) {
//                 circle(x, y, 3);
//             }
//         }
//     }
//     pop();
// }

// function drawShapeFill(shape) {
//     // First create a clipping mask with the shape
//     beginShape();
//     fill(50)
//     let points = getShapePoints(shape);
//     for (let p of points) {
//         vertex(p.x, p.y);
//     }
//     endShape(CLOSE);

//     // Get bounding box of the shape
//     let minX = Infinity, minY = Infinity;
//     let maxX = -Infinity, maxY = -Infinity;
//     for (let p of points) {
//         minX = min(minX, p.x);
//         minY = min(minY, p.y);
//         maxX = max(maxX, p.x);
//         maxY = max(maxY, p.y);
//     }

//     // Draw hatching lines at 45 degrees
//     push(); // Save current drawing state
//     stroke(shape.color);
//     strokeWeight(2);
//     let spacing = 10; // Space between hatch lines
//     let diagonal = spacing * sqrt(2); // Adjust spacing for 45 degree lines

//     // Calculate how many lines we need to cover the shape diagonally
//     let width = maxX - minX;
//     let height = maxY - minY;
//     let numLines = ceil((width + height) / diagonal) + 4; // Add padding

//     // Start offset to ensure we cover the whole shape
//     let startOffset = -diagonal * numLines / 2;

//     for (let i = 0; i < numLines; i++) {
//         let offset = startOffset + i * diagonal;

//         // Calculate start and end points for a 45-degree line
//         let startX = minX + offset;
//         let startY = minY;
//         let endX = startX + height;
//         let endY = maxY;

//         // Binary search from top
//         let topFound = false;
//         let top = 0, bottom = 1;
//         for (let j = 0; j < 10; j++) { // 10 iterations for precision
//             let mid = (top + bottom) / 2;
//             let testX = startX + (endX - startX) * mid;
//             let testY = startY + (endY - startY) * mid;
//             if (pointInShape(testX, testY, shape)) {
//                 bottom = mid;
//                 topFound = true;
//             } else {
//                 top = mid;
//             }
//         }

//         // Binary search from bottom
//         let bottomFound = false;
//         top = 0; bottom = 1;
//         for (let j = 0; j < 10; j++) {
//             let mid = (top + bottom) / 2;
//             let testX = endX - (endX - startX) * mid;
//             let testY = endY - (endY - startY) * mid;
//             if (pointInShape(testX, testY, shape)) {
//                 bottom = mid;
//                 bottomFound = true;
//             } else {
//                 top = mid;
//             }
//         }

//         if (topFound && bottomFound) {
//             let lineStartX = startX + (endX - startX) * bottom;
//             let lineStartY = startY + (endY - startY) * bottom;
//             let lineEndX = endX - (endX - startX) * bottom;
//             let lineEndY = endY - (endY - startY) * bottom;
//             line(lineStartX, lineStartY, lineEndX, lineEndY);
//         }
//     }
//     pop(); // Restore drawing state
// }


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

function keyPressed() {
    if (key === 's') {
        // Save the SVG
        save("my_blobs_" + Date.now() + ".svg");
    }
}