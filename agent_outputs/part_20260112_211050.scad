module gear() {
  difference() {
    cylinder(h = 10, r = 20, $fn = 64);
    for (i = [0 : 7]) {
      rotate([0, 0, i * 360 / 8])
      translate([15, 0, 0])
      cylinder(h = 12, r = 3, $fn = 64);
    }
  }
}

gear();