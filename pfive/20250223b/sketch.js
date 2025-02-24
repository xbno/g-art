let pos = [];
let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];

function setup() {
    createCanvas(1100, 1700, SVG);
    for (let i = 0; i < 4; i++) {
        let x = random(width);
        let y = random(height);
        pos.push(createVector(x, y));
    }
    background(255);
    for (let i = 0; i < pos.length; i++) {
        let p1 = pos[i];
        fill(0);
        noStroke();
        circle(p1.x, p1.y, 5);
        noFill();
        for (let j = 0; j < pos.length; j += 2) {
            let p2 = pos[j];
            let p3 = pos[j + 1];
            let points = equallySpacedPoints(p2.x, p2.y, p3.x, p3.y, 10);
            for (let i = 0; i < points.length; i++) {
                let p = points[i];
                // stroke(0);
                // strokeWeight(1);
                // noFill();
                circle(p.x, p.y, 3);
            }
            if (p3) { // Check if second point exists
                stroke(0);
                strokeWeight(0.5);
                // connect(p2.x, p2.y, p3.x, p3.y);
            }
            line(pos[0].x, pos[0].y, pos[1].x, pos[1].y);
        }
    }
}
function equallySpacedPoints(x1, y1, x2, y2, numLines) {
    let ang = atan2(y2 - y1, x2 - x1);
    let dst = dist(x1, y1, x2, y2);
    let spacing = dst / (numLines - 1);
    let points = [];

    push();
    translate(x1, y1);
    rotate(ang);

    // Calculate points at equal intervals
    for (let i = 0; i < numLines; i++) {
        let x = map(i, 0, numLines - 1, 0, dst);
        points.push({ x: x, y: 0 });
        // circle(x, 0, 3); // Draw a small circle at each point
    }

    // pop();

    return points;
}



function connect(x1, y1, x2, y2) {
    let ang = atan2(y2 - y1, x2 - x1);
    let dst = dist(x1, y1, x2, y2);
    let numCurves = int(random(2) + 1);
    let col = color('#000000');
    let startPoints = [];

    // Create starting points along the line with random spacing
    let currentX = 0;
    for (let i = 0; i < numCurves; i++) {
        let point = { x: currentX, y: 0 };
        startPoints.push(point);
        circle(point.x, point.y, 3); // Draw dot for the point

        // Random step size between points, but ensure we reach dst by the end
        let remainingDist = dst - currentX;
        let remainingPoints = numCurves - i - 1;
        if (remainingPoints > 0) {
            currentX += random(remainingDist / remainingPoints * 0.5, remainingDist / remainingPoints * 1.5);
        } else {
            currentX = dst; // Ensure last point is at end
        }
    }

    noFill();
    push();
    translate(x1, y1);
    rotate(ang);

    for (let j = 0; j < 10; j++) {
        alpha = 255;
        col.setAlpha(alpha);
        stroke(col);

        // Draw a curve from each starting point
        for (let start of startPoints) {
            beginShape();
            curveVertex(start.x, start.y);
            curveVertex(start.x, start.y);

            // Add some control points
            let numPoints = 3;
            for (let i = 1; i < numPoints; i++) {
                let t = i / numPoints;
                let x = lerp(start.x, dst, t);
                let noiseScale = 0.25;
                let offsetY = random(-1, 1) * dst * noiseScale;
                curveVertex(x, offsetY);
            }

            curveVertex(dst, 0);
            curveVertex(dst, 0);
            endShape();
        }
    }
    pop();
}