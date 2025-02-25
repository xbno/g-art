let pos = [];
let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];

function setup() {
    createCanvas(1100, 1700, SVG);
    for (let i = 0; i < 15; i++) {
        let x = random(width);
        let y = random(height);
        pos.push(createVector(x, y));
    }
    background(255);
    let W = 5; // Number of columns in grid
    let H = 10; // Number of rows in grid
    pos = []; // Clear existing random positions

    // Create diagonal grid-based positions
    for (let i = 0; i < W; i++) {
        for (let j = 0; j < H; j++) {
            let x = (width / (W - 1)) * i;
            let y = (height / (H - 1)) * j;

            // Offset x position for every other row to create diagonal pattern
            if (j % 2 === 1) {
                x += (width / (W - 1)) / 2;
            }

            if (random() < 0.5) { // 50% chance
                pos.push(createVector(x, y));
            }
        }
    }

    // Connect points within distance threshold
    for (let i = 0; i < pos.length; i++) {
        let p1 = pos[i];
        for (let j = pos.length - 1; j >= 0; j--) {
            let p2 = pos[j];
            let dis = dist(p1.x, p1.y, p2.x, p2.y);
            if (dis > 200 && dis < 450 && i < j) {
                strokeWeight(1);
                // connect(p1.x, p1.y, p2.x, p2.y);
            }
        }
    }


    for (let p of pos) {
        // let col = color('#000000');
        let col = color(random(colors));
        // fill(0);
        noStroke();
        // strokeWeight(1);

        blendMode(DIFFERENCE);

        // Randomly choose between circle, triangle and square
        let shape = random(['circle', 'triangle', 'square']);
        if (shape === 'circle') {
            circle(p.x, p.y, 5);
        } else if (shape === 'triangle') {
            triangle(p.x - 3, p.y + 3, p.x + 3, p.y + 3, p.x, p.y - 3);
        } else {
            rectMode(CENTER);
            square(p.x, p.y, 5);
        }

        col.setAlpha(255); // Fix alpha value to valid range 0-255
        // noFill();
        fill(col);
        // stroke(0);
        strokeWeight(1);

        // Random larger shapes
        shape = random(['circle', 'triangle', 'square']);
        let sizeMultiplier = random([1, 1, 1, 2, 2, 3]); // More 1s and 2s make 3 rarer
        let baseSize = width * 0.1;
        let size = baseSize * pow(1.5, sizeMultiplier); // Exponential growth makes larger sizes rarer
        if (shape === 'circle') {
            circle(p.x, p.y, size);
            // Add lines through circle if random
            if (random() < 0.2) {
                if (random() < 0.5) {
                    line(p.x - size / 2, p.y, p.x + size / 2, p.y); // horizontal middle
                } else {
                    line(p.x, p.y - size / 2, p.x, p.y + size / 2); // vertical middle
                }
                if (random() < 0.9) {
                    let minAngle = PI / 12; // 15 degrees
                    let angle = random(minAngle, TWO_PI - minAngle); // Angle between 15 and 345 degrees
                    let x1 = p.x + cos(angle) * size / 2;
                    let y1 = p.y + sin(angle) * size / 2;
                    line(x1, y1, p.x, p.y); // Draw half line through circle
                }
            }
        } else if (shape === 'triangle') {
            // Calculate points for equilateral triangle with random 90 degree rotation
            let height = size * sqrt(3) / 2; // Height of equilateral triangle
            let rotation = floor(random(4)) * PI / 2; // Random multiple of 90 degrees

            // Base triangle points before rotation
            let x1 = -height / 3;
            let x2 = -height / 3;
            let x3 = 2 * height / 3;
            let y1 = -size / 2;
            let y2 = size / 2;
            let y3 = 0;

            push();
            translate(p.x, p.y);
            rotate(rotation);

            triangle(x1, y1, x2, y2, x3, y3);

            // Add line from middle of base to point if random
            if (random() < 0.2) {
                line(-height / 3, 0, 2 * height / 3, 0);
            }

            pop();
        } else {
            rectMode(CENTER);
            square(p.x, p.y, size);
        }

        blendMode(BLEND);
    }
}


function draw() {

}

function keyPressed() {
    if (key === 's') {
        save("my_blobs_" + Date.now() + ".svg");
    }
}

function equallySpacedPoints(x1, y1, x2, y2, numLines) {
    let ang = atan2(y2 - y1, x2 - x1);
    let dst = dist(x1, y1, x2, y2);
    let points = [];

    push();
    translate(x1, y1);
    rotate(ang);

    for (let i = 0; i < numLines; i++) {
        let x = map(i, 0, numLines - 1, 0, dst);
        points.push({ x: x, y: 0 });
    }

    pop();
    return points;
}
