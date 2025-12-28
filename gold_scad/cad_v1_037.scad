module plate(w, d, t){
  difference(){
    cube([w, d, t], center=true);
    translate([w*0.3, d*-0.3, 0]) cylinder(r=5, h=t+2, center=true);
    translate([w*-0.3, d*0.3, 0]) cylinder(r=5, h=t+2, center=true);
    translate([w*0, d*0, 0]) cylinder(r=2.5, h=t+2, center=true);
  }
}
plate(W, D, T);
