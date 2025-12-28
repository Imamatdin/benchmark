module bracket(w, h, t){
  union(){
    cube([w, t, t]);
    cube([t, h, t]);
  }
}
bracket(W, H, T);
