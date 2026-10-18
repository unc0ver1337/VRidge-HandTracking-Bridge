#include "../ios/Tracking/MobReconMath.h"
#include <cassert>
#include <iostream>
int main(){using namespace corehands;
    Roi r={320,240,200,.7f,false};Point p={.2f,.8f,0};
    for(bool left:{false,true}){
        r.mirror=left;auto image=projectUV(p,r,640,480);
        float dx=image.x*640-r.cx,dy=image.y*480-r.cy;
        float x=(std::cos(r.rotation)*dx+std::sin(r.rotation)*dy)*(left?-1:1)/r.size+.5f;
        float y=(-std::sin(r.rotation)*dx+std::cos(r.rotation)*dy)/r.size+.5f;
        assert(std::abs(x-p.x)<1e-6&&std::abs(y-p.y)<1e-6);
        auto w=projectWorld({.03f,.04f,.02f},r);
        assert(std::abs(w.x*w.x+w.y*w.y-.0025f)<1e-7&&w.z==.02f);
    }
    std::vector<uint8_t> bgra(640*480*4);for(size_t i=0;i<bgra.size();i+=4){bgra[i]=10;bgra[i+1]=20;bgra[i+2]=30;bgra[i+3]=255;}
    std::vector<float> tensor(3*128*128);crop(bgra.data(),640,480,640*4,{320,240,128,0,false},tensor.data());
    assert(std::abs(tensor[0]-(30.f*2/255-1))<1e-6);
    assert(std::abs(tensor[128*128]-(20.f*2/255-1))<1e-6);
    assert(std::abs(tensor[2*128*128]-(10.f*2/255-1))<1e-6);
    crop(bgra.data(),640,480,640*4,{-1000,-1000,128,0,false},tensor.data());for(float v:tensor)assert(v==-1);
    std::array<Point,21> uv;std::array<float,21> confidence;
    for(int i=0;i<21;i++){uv[i]={.4f+(i%5)*.04f,.3f+(i/5)*.05f,0};confidence[i]=1;}
    uv[0]={.5f,.7f,0};uv[9]={.5f,.4f,0};Roi box;
    assert(roi(uv,confidence,640,480,false,box));assert(std::abs(box.rotation)<1e-6);
    confidence[0]=0;assert(!roi(uv,confidence,640,480,false,box));
    std::cout<<"PASS: MobRecon ROI, left mirroring, 2D/world projection, NCHW RGB normalization and border padding\n";
}
