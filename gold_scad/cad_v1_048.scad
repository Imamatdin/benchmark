module fillet_box(l, w, h, r){
  minkowski(){
    cube([l, w, h], center=true);
    sphere(r=r);
  }
}
fillet_box(L, W, H, R);
