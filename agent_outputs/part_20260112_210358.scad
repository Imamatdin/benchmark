module cad_part() {
    $fn=64;
    union() {
        cylinder(h=20, r=10);
        translate([0, 0, 20])
        sphere(r=10);
        translate([-15, 0, 10])
        cube([30, 10, 10]);
    }
}

cad_part();