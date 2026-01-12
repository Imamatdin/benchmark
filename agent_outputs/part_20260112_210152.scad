module L_bracket(width, height, thickness) {
  union() {
    cube([width, thickness, height]);
    cube([thickness, width, height]);
  }
}

L_bracket(50, 40, 5);