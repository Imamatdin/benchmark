module rounded_box(width, depth, height, radius) {
  minkowski() {
    cube([width - 2 * radius, depth - 2 * radius, height - 2 * radius]);
    sphere(r = radius);
  }
}

$fn=64;
rounded_box(40, 30, 20, 3);