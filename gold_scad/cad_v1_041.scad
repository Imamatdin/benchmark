module slot_plate(w, d, t, slot_len, r){
  difference(){
    cube([w, d, t], center=true);
    hull(){
      translate([slot_len/2, 0, 0]) cylinder(r=r, h=t+2, center=true);
      translate([-slot_len/2, 0, 0]) cylinder(r=r, h=t+2, center=true);
    }
  }
}
slot_plate(W, D, T, SLOT, R);
