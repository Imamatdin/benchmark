W = 100;
D = 100;
T = 10;
R = 5;
$fn = 64;

difference() {
    cube([W, D, T], center = true);
    cylinder(h = T + 0.2, r = R, center = true);
}