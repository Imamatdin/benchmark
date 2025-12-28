module plate(w, d, t){
  difference(){
    cube([w, d, t], center=true);
    translate([w*0.2, d*0.2, 0]) cylinder(r=4, h=t+2, center=true);
    translate([w*-0.2, d*0.2, 0]) cylinder(r=4, h=t+2, center=true);
    translate([w*0.2, d*-0.2, 0]) cylinder(r=4, h=t+2, center=true);
    translate([w*-0.2, d*-0.2, 0]) cylinder(r=4, h=t+2, center=true);
  }
}
plate(W, D, T);
