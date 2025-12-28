module plate(w, d, t){
  difference(){
    cube([w, d, t], center=true);
    translate([w*0.25, d*0.0, 0]) cylinder(r=3.5, h=t+2, center=true);
    translate([w*0.0, d*0.25, 0]) cylinder(r=3.5, h=t+2, center=true);
    translate([w*-0.25, d*0, 0]) cylinder(r=3.5, h=t+2, center=true);
    translate([w*0, d*-0.25, 0]) cylinder(r=3.5, h=t+2, center=true);
  }
}
plate(W, D, T);
