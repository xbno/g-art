let pos = [];
let colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];


function setup() {
    createCanvas(1100, 1700, SVG);

    let shapes = []; // Array to store shape information
    for (let i = 0; i < 10; i++) {
        let x = Math.round(random(width) / 5) * 5;
        let y = Math.round(random(height) / 5) * 5;
        pos.push(createVector(x, y));
    }
    background(245);
    for (let p of pos) {
        let col = color('#000000');
        fill(col);
        noStroke();

        // Randomly choose between circle, triangle and square
        let shape = random(['circle', 'triangle', 'square']);
        if (shape === 'circle') {
            circle(p.x, p.y, 5);
            shapes.push({ type: 'circle', x: p.x, y: p.y, size: 5 });
        } else if (shape === 'triangle') {
            triangle(p.x - 3, p.y + 3, p.x + 3, p.y + 3, p.x, p.y - 3);
            shapes.push({ type: 'triangle', x: p.x, y: p.y, size: 6 });
        } else {
            rectMode(CENTER);
            square(p.x, p.y, 5);
            shapes.push({ type: 'square', x: p.x, y: p.y, size: 5 });
        }

        col.setAlpha(500);
        noFill();
        stroke(col);

        // Random larger shapes
        shape = random(['circle', 'triangle', 'square']);
        let size = Math.round(random(width * 0.5) / 15) * 15;
        if (shape === 'circle') {
            circle(p.x, p.y, size);
            shapes.push({ type: 'circle', x: p.x, y: p.y, size: size });
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
                    line(x2, y2, p.x, p.y); // Draw half line through circle
                }
            }
        } else if (shape === 'triangle') {
            let x1 = p.x - size / 2;
            let x2 = p.x + size / 2;
            let x3 = p.x
            let y1 = p.y + size / 2;
            let y2 = p.y + size / 2;
            let y3 = p.y - size / 2;
            triangle(x1, y1, x2, y2, x3, y3);
            shapes.push({
                type: 'triangle',
                x: p.x,
                y: p.y,
                size: size,
                points: [{ x: x1, y: y1 }, { x: x2, y: y2 }, { x: x3, y: y3 }]
            });
            // Add line from middle of base to top point if random
            if (random() < 0.2) {
                line(p.x, p.y + size / 2, p.x, p.y - size / 2);
            }
        } else {
            rectMode(CENTER);
            square(p.x, p.y, size);
            shapes.push({ type: 'square', x: p.x, y: p.y, size: size });
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
    }
    for (let i = 0; i < pos.length; i++) {
        let p1 = pos[i];
        for (let j = pos.length - 1; j >= 0; j--) {
            let p2 = pos[j];
            let dis = dist(p1.x, p1.y, p2.x, p2.y);
            if (dis < 250 && i < j) {
                connect(p1.x, p1.y, p2.x, p2.y);
            }
        }
    }
    // Store shapes array in a global variable for later use
    window.allShapes = shapes;
}


function checkShapeOverlap(shape1, shape2) {
    // Get centers and sizes of shapes
    let x1 = shape1.x;
    let y1 = shape1.y;
    let x2 = shape2.x;
    let y2 = shape2.y;

    // Calculate distance between centers
    let distance = dist(x1, y1, x2, y2);

    // For circles, check if distance is less than sum of radii
    if (shape1.type === 'circle' && shape2.type === 'circle') {
        return distance < (shape1.size / 2 + shape2.size / 2);
    }

    // For squares, use bounding box intersection
    if (shape1.type === 'square' && shape2.type === 'square') {
        let halfSize1 = shape1.size / 2;
        let halfSize2 = shape2.size / 2;
        return !(x1 + halfSize1 < x2 - halfSize2 ||
            x1 - halfSize1 > x2 + halfSize2 ||
            y1 + halfSize1 < y2 - halfSize2 ||
            y1 - halfSize1 > y2 + halfSize2);
    }

    // For triangles, use approximate circular bounds
    if (shape1.type === 'triangle' && shape2.type === 'triangle') {
        let radius1 = shape1.size / 2;
        let radius2 = shape2.size / 2;
        return distance < (radius1 + radius2);
    }

    // For mixed shapes, use the more conservative circular bounds
    let size1 = shape1.type === 'triangle' ? shape1.size / 2 : shape1.size / 2;
    let size2 = shape2.type === 'triangle' ? shape2.size / 2 : shape2.size / 2;
    return distance < (size1 + size2);
}


function checkAndFillOverlaps() {
    // Get the first shape
    let firstShape = window.allShapes[0];

    // Compare with all other shapes
    for (let i = 1; i < window.allShapes.length; i++) {
        let otherShape = window.allShapes[i];

        // Check for overlap
        if (checkShapeOverlap(firstShape, otherShape)) {
            // Make overlapping shapes have thicker outlines
            push();
            strokeWeight(8); // Much thicker stroke
            noFill();
            stroke(0);

            // Draw thick outline for first shape
            if (firstShape.type === 'circle') {
                circle(firstShape.x, firstShape.y, firstShape.size);
            } else if (firstShape.type === 'square') {
                rectMode(CENTER);
                square(firstShape.x, firstShape.y, firstShape.size);
            } else if (firstShape.type === 'triangle') {
                triangle(
                    firstShape.x - firstShape.size / 2, firstShape.y + firstShape.size / 2,
                    firstShape.x + firstShape.size / 2, firstShape.y + firstShape.size / 2,
                    firstShape.x, firstShape.y - firstShape.size / 2
                );
            }

            // Draw thick outline for second shape
            if (otherShape.type === 'circle') {
                circle(otherShape.x, otherShape.y, otherShape.size);
            } else if (otherShape.type === 'square') {
                rectMode(CENTER);
                square(otherShape.x, otherShape.y, otherShape.size);
            } else if (otherShape.type === 'triangle') {
                triangle(
                    otherShape.x - otherShape.size / 2, otherShape.y + otherShape.size / 2,
                    otherShape.x + otherShape.size / 2, otherShape.y + otherShape.size / 2,
                    otherShape.x, otherShape.y - otherShape.size / 2
                );
            }
            pop();
            // If overlap found, fill first shape with grey
            push();
            fill(128); // Grey fill
            noStroke();

            // Draw the first shape filled
            if (firstShape.type === 'circle') {
                circle(firstShape.x, firstShape.y, firstShape.size);
            } else if (firstShape.type === 'square') {
                rectMode(CENTER);
                square(firstShape.x, firstShape.y, firstShape.size);
            } else if (firstShape.type === 'triangle') {
                triangle(
                    firstShape.x - firstShape.size / 2, firstShape.y + firstShape.size / 2,
                    firstShape.x + firstShape.size / 2, firstShape.y + firstShape.size / 2,
                    firstShape.x, firstShape.y - firstShape.size / 2
                );
            }
            pop();

            // Exit after first overlap is found and filled
            return;
        }
    }
}

// Call the function after shapes are created
checkAndFillOverlaps();



function draw() {

}

// function connect(x1, y1, x2, y2) {
//     let ang = atan2(y2 - y1, x2 - x1);
//     let dst = dist(x1, y1, x2, y2);
//     let n = int(random(8) + 1);
//     let col = color('#000000');
//     let yy = [];
//     for (let i = 0; i < n; i++) {
//         yy.push(random(-1, 1) * dst * 0.25);
//     }
//     noFill();
//     push();
//     translate(x1, y1);
//     rotate(ang);

//     for (let j = 0; j < 100; j++) {
//         // Use exponential spacing between lines
//         let alpha = map(pow(j / 100, 2), 0, 1, 200, 10); // Exponentially decrease alpha
//         col.setAlpha(alpha);
//         stroke(col);
//         beginShape();

//         for (let i = 0; i < n; i++) {
//             let xx = map(i, -1, n, 0, dst);
//             // Exponentially increase the noise offset based on j
//             let noiseScale = pow(j / 50, 2); // Exponential scaling factor
//             let offx = (noise(j * 0.01, i, xx) * dst * noiseScale) - (dst / 5);
//             let offy = (noise(j * 0.01, i, yy[i]) * dst * noiseScale) - (dst / 5);
//             curveVertex(xx + offx, yy[i] + offy);
//         }
//         curveVertex(dst, 0);
//         curveVertex(dst, 0);
//         endShape();
//     }
//     pop();
// }

function keyPressed() {
    if (key === 's') {
        // Save the SVG
        save("my_blobs_" + Date.now() + ".svg");
    }
}