module plate() {
  difference() {
    cube([60, 40, 6], center=true);
    cylinder(h=6, r=5, center=true, $fn=64);
  }
}

plate();