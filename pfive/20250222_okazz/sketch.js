let rects = [];
let colors = ['#FE93C2', '#3BD89F', '#0045E8', '#DE183C', '#FFC247', '#ffffff', '#000000', '#00aeff'];
let gridW;
let gridH;
let rows = 11;
let cols = 11;
let rectCorner;

function setup() {
    createCanvas(1400, 1400);
    gridW = width * 0.75;
    gridH = height * 0.75;
    let cellW = gridW / cols;
    let cellH = gridH / rows;
    let sep = 8;
    for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
            let x = i * cellW + cellW / 2;
            let y = j * cellH + cellH / 2;
            let rectSize = cellW * 2;
            let opt = int(random(4))
            shuffle(colors, true);
            if (opt == 0) rects.push(new SuperRect(x - (rectSize / 2), y - (rectSize / 2), rectSize, rectSize, 0, sep, colors[1]));
            if (opt == 1) rects.push(new SuperRect(x + (rectSize / 2), y - (rectSize / 2), rectSize, rectSize, PI * 0.5, sep, colors[2]));
            if (opt == 2) rects.push(new SuperRect(x + (rectSize / 2), y + (rectSize / 2), rectSize, rectSize, PI, sep, colors[3]));
            if (opt == 3) rects.push(new SuperRect(x - (rectSize / 2), y + (rectSize / 2), rectSize, rectSize, PI * 1.5, sep, colors[4]));
        }
    }
    rectCorner = width * 0.006;
    shuffle(rects, true);
}

function draw() {
    translate((width - gridW) / 2, (height - gridH) / 2);

    background('#ffffff');
    noStroke();
    for (let i = 0; i < rects.length; i++) {
        let r = rects[i];
        push();
        translate(r.x, r.y);
        rotate(r.a);
        fill(r.clr);
        rect(0, 0, r.w, r.h, rectCorner);
        pop();
    }

    strokeWeight(width * 0.002);
    stroke('#000000');
    for (let i = 0; i < rects.length; i++) {
        let r = rects[i];
        push();
        translate(r.x, r.y);
        rotate(r.a);
        noFill();
        rect(0, 0, r.w, r.h, rectCorner);

        pop();
    }

    for (let i of rects) {
        i.move();
    }
}

function easeInOutQuint(x) {
    return x < 0.5 ? 16 * x * x * x * x * x : 1 - Math.pow(-2 * x + 2, 5) / 2;
}

class SuperRect {
    constructor(x, y, w, h, a, sep, clr) {
        this.x = x;
        this.y = y;
        this.w = w;
        this.h = h;
        this.a = a;
        this.clr = clr;
        this.separate = sep;
        this.originW = w;
        this.originH = h;
        this.setValues();
        this.w = this.toW;
        this.h = this.toH;
        this.setValues();
        this.toggle = false;
    }

    move() {
        if (this.toggle) {
            this.time++;
            if (0 < this.time && this.time < this.duration) {
                let n = norm(this.time, 0, this.duration);
                this.w = lerp(this.fromW, this.toW, easeInOutQuint(n));
                this.h = lerp(this.fromH, this.toH, easeInOutQuint(n));
            } else if (this.duration < this.time) {
                this.toggle = false
            }
        }

        if ((this.toggle == false) && (random() < 0.005)) {
            this.toggle = true;
            this.time = 0;
            this.setValues();
        }
    }

    setValues() {
        this.fromW = this.w;
        this.toW = ((this.originW / this.separate) * int(random(this.separate) + 1));
        this.fromH = this.h;
        this.toH = (this.originH / this.separate) * int(random(this.separate) + 1);
        this.time = 0;
        this.duration = int(random(30, 120));

    }
}