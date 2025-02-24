let shapes = [];

function setup() {
    // Create a canvas of 800x600 pixels
    createCanvas(800, 600);
    background(255); // White background

    // Generate 3 circles, 3 squares, and 3 triangles
    for (let i = 0; i < 3; i++) {
        // Circles
        let x = random(100, width - 100); // Margin to keep shapes inside canvas
        let y = random(100, height - 100);
        let diameter = random(50, 200); // Random diameter between 50 and 200
        shapes.push({
            type: 'circle',
            x: x,
            y: y,
            diameter: diameter,
            color: color(random(255), random(255), random(255)) // Random fill color
        });

        // Squares
        x = random(100, width - 100);
        y = random(100, height - 100);
        let size = random(50, 200); // Random size between 50 and 200
        shapes.push({
            type: 'square',
            x: x,
            y: y,
            size: size,
            color: color(random(255), random(255), random(255))
        });

        // Equilateral Triangles
        x = random(100, width - 100);
        y = random(100, height - 100);
        let R = random(25, 100); // Radius from center to vertex
        // let rotation = random(TWO_PI); // Random rotation
        shapes.push({
            type: 'triangle',
            x: x,
            y: y,
            size: R,
            // rotation: rotation,
            color: color(random(255), random(255), random(255))
        });
    }
}

function draw() {
    // Draw all shape fills first
    blendMode(DIFFERENCE);
    for (let shape of shapes) {
        fill(shape.color);
        // noStroke(); // No stroke for fills
        stroke(0);
        strokeWeight(1);
        defineShapePath(shape);
    }

    // Draw outlines with clipping to make outer edges bold
    for (let S of shapes) {
        push(); // Isolate transformations and clipping
        // Start clipping region: outside of all other shapes
        beginClip({ invert: true });
        for (let O of shapes) {
            if (O !== S) {
                defineShapePath(O); // Define clipping path for other shapes
            }
        }
        endClip();
        // Draw the outline of the current shape
        noFill();
        stroke(0); // Black outline
        strokeWeight(5); // Bold stroke for outer edges
        defineShapePath(S);
        pop(); // Reset transformations and clipping
    }

    noLoop(); // Stop draw loop since the sketch is static
}

// Helper function to define the path of a shape
function defineShapePath(shape) {
    if (shape.type === 'circle') {
        // Draw circle using ellipse
        ellipse(shape.x, shape.y, shape.diameter);
    } else if (shape.type === 'square') {
        // Draw square using rect with center mode
        rectMode(CENTER);
        rect(shape.x, shape.y, shape.size, shape.size);
    } else if (shape.type === 'triangle') {
        // Draw equilateral triangle using beginShape
        beginShape();
        for (let i = 0; i < 3; i++) {
            let angle = TWO_PI / 3 * i;
            let x = shape.x + shape.size * cos(angle);
            let y = shape.y + shape.size * sin(angle);
            vertex(x, y);
        }
        endShape(CLOSE);
    }
}