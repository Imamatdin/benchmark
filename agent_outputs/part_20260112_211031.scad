module cylindrical_tube() {
  difference() {
    cylinder(h = 50, r = 15, $fn = 64, center = true);
    cylinder(h = 50, r = 10, $fn = 64, center = true);
  }
}

cylindrical_tube();