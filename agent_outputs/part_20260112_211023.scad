module mounting_bracket() {
  difference() {
    union() {
      cube([60, 5, 40], center = true);
      cube([5, 60, 5], center = true);
    }
    translate([20, 0, 0]) cylinder(h = 10, d = 4, center = true, $fn = 64);
    translate([-20, 0, 0]) cylinder(h = 10, d = 4, center = true, $fn = 64);
  }
}

mounting_bracket();