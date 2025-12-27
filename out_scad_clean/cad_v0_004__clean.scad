W = 10;
D = 10;
H = 10;

module part(w, d, h) {
    cube([w, d, h], center = true);
}

part(W, D, H);