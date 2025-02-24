function setup() {
    createCanvas(2000, 2000);
    blendMode(DIFFERENCE);
    for (let i = 0; i < 10; i++) {
        // Generate random pastel colors for each shape
        let colorPalette = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"];
        let rectColor = color(colorPalette[floor(random(colorPalette.length))]);
        let ellipseColor = color(colorPalette[floor(random(colorPalette.length))]);
        rectColor.setAlpha(200);
        ellipseColor.setAlpha(200);

        // Set fill for rectangle
        fill(rectColor);
        noStroke();
        rect(random(width), random(height), 400, 400);

        // Set fill for ellipse
        fill(ellipseColor);
        noStroke();
        ellipse(random(width), random(height), 400, 400);
    }
}

// function draw() {
//     background(255);
//     rect(20, 20, 100, 100);
//     ellipse(80, 80, 100, 100);
// }