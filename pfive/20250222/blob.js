class Blob {
    constructor(x, y, rad) {
        this.x = x;
        this.y = y;
        this.rad = rad;
        this.szDelta = this.rad * 0.35;
        this.blobObj = [];
        // constants
        this.res = 16; // the number of points 
        this.angle = 360 / this.res; // angular distance between each point
        // Add a color from the palette
        this.blobColor = getColorFromPalette();
    }

    display() {
        this.blobObj = [];
        push(); // It's a good practice to use push and pop whenevewer you translate screen coordinates
        translate(this.x, this.y); // translate the screen coordinate from top-left to middle of the canvas

        // Use color from palette instead of no fill
        fill(this.blobColor);
        stroke(0);

        beginShape(); // start to draw custom shape

        var d = dist(this.x, this.y, width * 0.5, height * 0.5);
        strokeWeight(max(0, 5 - d * 0.01));

        for (var i = 0; i < this.res; i++) {
            var randRad = min(this.rad, this.rad + random(-this.szDelta, this.szDelta));

            var nRad = this.rad + randRad;
            this.blobObj.push({
                "rad": randRad,
                "x": randRad * cos(this.angle * i),
                "y": randRad * sin(this.angle * i)
            });
            //circle(this.blobObj[i].x, this.blobObj[i].y, 5);
            curveVertex(this.blobObj[i].x, this.blobObj[i].y); // add points to the custom shape
        }
        curveVertex(this.blobObj[0].x, this.blobObj[0].y);
        curveVertex(this.blobObj[1].x, this.blobObj[1].y);
        curveVertex(this.blobObj[2].x, this.blobObj[2].y);
        endShape(); // we finish adding points
        pop();
    }
}