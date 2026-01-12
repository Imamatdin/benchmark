module plate() {
  difference() {
    cube([80, 50, 5], center=true);
    cylinder(h=5.1, r=10, center=true, $fn=64);
  }
}
plate();