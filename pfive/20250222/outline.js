function getStrokeLines(x, y, width, height, type) {
    let lines = [];

    if (type === 'rect') {
        // Rectangle corners
        lines.push({ x1: x, y1: y, x2: x + width, y2: y }); // top
        lines.push({ x1: x + width, y1: y, x2: x + width, y2: y + height }); // right
        lines.push({ x1: x + width, y1: y + height, x2: x, y2: y + height }); // bottom
        lines.push({ x1: x, y1: y + height, x2: x, y2: y }); // left
    } else if (type === 'ellipse') {
        // Approximate ellipse with points around circumference
        const steps = 4; // Number of points to approximate ellipse
        for (let i = 0; i < steps; i++) {
            let angle = (TWO_PI / steps) * i;
            let nextAngle = (TWO_PI / steps) * ((i + 1) % steps);

            let x1 = x + (width / 2 * cos(angle));
            let y1 = y + (height / 2 * sin(angle));
            let x2 = x + (width / 2 * cos(nextAngle));
            let y2 = y + (height / 2 * sin(nextAngle));

            lines.push({ x1, y1, x2, y2 });
        }
    }

    return lines;
}


function setup() {
    createCanvas(2000, 2000, SVG);
    // background('#ffffff');
    background(245);

    // let colorPalette = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];
    // let rectColor = color(colorPalette[floor(random(colorPalette.length))]);
    // rectColor.setAlpha(200);
    // fill(rectColor);
    // noStroke();
    // rect(0, 0, width, height);

    // let rectLines = getStrokeLines(0, 0, width, height, 'rect');
    // stroke(255);
    // strokeWeight(4);
    // for (let line of rectLines) {
    //     line(line.x1, line.y1, line.x2, line.y2);
    // }

    let colorPalette = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];
    let ellipseColor = color(colorPalette[floor(random(colorPalette.length))]);
    ellipseColor.setAlpha(200);

    // Draw circle
    let circleX = random(width);
    let circleY = random(height);
    // let circleX = width / 2;
    // let circleY = height / 2;
    let circleSize = 400;

    fill(ellipseColor);
    noStroke();
    ellipse(circleX, circleY, circleSize, circleSize);

    // Draw circle outline
    let circleLines = getStrokeLines(circleX, circleY, circleSize, circleSize, 'ellipse');
    console.log(circleLines);
    stroke(100);
    strokeWeight(10);
    for (let line of circleLines) {
        // Use line() function instead of trying to call line object as function
        // beginShape();
        // stroke(0);
        // strokeWeight(20);
        // point(line.x1, line.y1);
        // // strokeWeight(10);
        // // vertex(line.x1, line.y1);
        // // vertex(line.x2, line.y2);
        // // curveVertex(line.x1, line.y1);
        // // curveVertex(line.x2, line.y2);
        // endShape();






        // Draw circle using curveVertex
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = 100;
        const points = 36; // Number of points to create smooth circle

        noFill();
        beginShape();

        // Add extra points at start and end to ensure smooth curve closure
        const firstX = centerX + radius * cos(0);
        const firstY = centerY + radius * sin(0);
        strokeWeight(20);
        curveVertex(firstX, firstY); // First control point
        strokeWeight(1);

        // Create points around the circle
        for (let angle = 0; angle <= TWO_PI; angle += TWO_PI / points) {
            const x = centerX + radius * cos(angle);
            const y = centerY + radius * sin(angle);
            curveVertex(x, y);
        }

        // Add extra control points at the end to close the shape smoothly
        curveVertex(firstX, firstY);
        curveVertex(firstX, firstY);

        endShape();
    }
}