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
    for (let i = 0; i < pos.length; i++) {
        let p1 = pos[i];
        for (let j = pos.length - 1; j >= 0; j--) {
            let p2 = pos[j];
            let dis = dist(p1.x, p1.y, p2.x, p2.y);
            if (dis > 200 && dis < 450 && i < j) {
                // strokeWeight(1);
                // line(p1.x, p1.y, p2.x, p2.y);
                strokeWeight(1);
                connect(p1.x, p1.y, p2.x, p2.y);
            }
        }
    }
    for (let p of pos) {
        let col = color('#000000');
        fill(col);
        noStroke();

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

        col.setAlpha(500);
        noFill();
        // fill('#ffffff');
        stroke(col);
        // strokeWeight(random(1, 5));
        strokeWeight(5);

        erase(255);


        // circle(p.x, p.y, 5);
        // Random larger shapes
        shape = random(['circle', 'triangle', 'square']);
        let size = random(width * 0.5);
        if (shape === 'circle') {
            circle(p.x, p.y, size);
            // Add lines through circle if random
            if (random() < 0.2) {
                if (random() < 0.5) {
                    line(p.x - size / 2, p.y, p.x + size / 2, p.y); // horizontal middle
                } else {
                    line(p.x, p.y - size / 2, p.x, p.y + size / 2); // vertical middle
                } if (random() < 0.9) {
                    let minAngle = PI / 12; // 15 degrees
                    let angle = random(minAngle, TWO_PI - minAngle); // Angle between 15 and 345 degrees
                    let x1 = p.x + cos(angle) * size / 2;
                    let y1 = p.y + sin(angle) * size / 2;
                    let x2 = p.x + cos(angle) * -size / 2;
                    let y2 = p.y + sin(angle) * -size / 2;
                    line(x1, y1, p.x, p.y); // Draw half line through circle
                }
            }
        } else if (shape === 'triangle') {
            // Calculate points for equilateral triangle
            let height = size * sqrt(3) / 2; // Height of equilateral triangle
            let x1 = p.x - size / 2;
            let x2 = p.x + size / 2;
            let x3 = p.x;
            let y1 = p.y + height / 3;
            let y2 = p.y + height / 3;
            let y3 = p.y - 2 * height / 3;
            triangle(x1, y1, x2, y2, x3, y3);
            // Add line from middle of base to top point if random
            if (random() < 0.2) {
                line(p.x, p.y + height / 3, p.x, p.y - 2 * height / 3);
            }
        } else {
            rectMode(CENTER);
            square(p.x, p.y, size);
            // Add lines through square if random
            if (random() < 0.2) {
                // Draw either thirds, middle line, or diagonal
                let choice = random();
                if (choice < 0.2) {
                    line(p.x - size / 2, p.y, p.x + size / 2, p.y); // middle
                } else if (choice < 0.4) {
                    // Draw either top or bottom third
                    if (random() < 0.5) {
                        line(p.x - size / 2, p.y - size / 6, p.x + size / 2, p.y - size / 6);
                    } else {
                        line(p.x - size / 2, p.y + size / 6, p.x + size / 2, p.y + size / 6);
                    }
                } else {
                    // Draw diagonal line from corner to corner
                    if (random() < 0.5) {
                        // Top-left to bottom-right
                        line(p.x - size / 2, p.y - size / 2, p.x + size / 2, p.y + size / 2);
                    } else {
                        // Top-right to bottom-left
                        line(p.x + size / 2, p.y - size / 2, p.x - size / 2, p.y + size / 2);
                    }
                }
            }
        }
        noErase();
        // for (let i = 0; i < pos.length; i++) {
        //     let p1 = pos[i];
        //     for (let j = pos.length - 1; j >= 0; j--) {
        //         let p2 = pos[j];
        //         let dis = dist(p1.x, p1.y, p2.x, p2.y);
        //         if (dis > 200 && dis < 450 && i < j) {
        //             strokeWeight(1);
        //             line(p1.x, p1.y, p2.x, p2.y);
        //             // strokeWeight(1);
        //             // connect(p1.x, p1.y, p2.x, p2.y);
        //         }
        //     }
        // }
    }

}

function draw() {

}

function connect(x1, y1, x2, y2) {
    let ang = atan2(y2 - y1, x2 - x1);
    let dst = dist(x1, y1, x2, y2);
    let n = int(random(8) + 1);
    let col = color('#000000');
    let yy = [];
    for (let i = 0; i < n; i++) {
        yy.push(random(-1, 1) * dst * 0.25);
    }
    // fill(128);
    noFill();
    push();
    translate(x1, y1);
    rotate(ang);

    for (let j = 0; j < 50; j++) {
        // Use exponential spacing between lines
        alpha = 255
        col.setAlpha(alpha);
        stroke(col);
        beginShape();

        for (let i = 0; i < n; i++) {
            let xx = map(i, -1, n, 0, dst);
            // Exponentially increase the noise offset based on j
            let noiseScale = pow(j / 50, 2); // Exponential scaling factor
            let offx = (noise(j * 0.01, i, xx) * dst * noiseScale) - (dst / 5);
            let offy = (noise(j * 0.01, i, yy[i]) * dst * noiseScale) - (dst / 5);
            curveVertex(xx + offx, yy[i] + offy);
        }
        curveVertex(dst, 0);
        curveVertex(dst, 0);
        endShape();
    }
    pop();
}

function keyPressed() {
    if (key === 's') {
        // Save the SVG
        save("my_blobs_" + Date.now() + ".svg");
    }
}