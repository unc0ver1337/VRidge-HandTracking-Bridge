#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace corehands {
constexpr float pi=3.14159265358979323846f;
struct Point {float x=0,y=0,z=0;};
struct Hand {std::array<Point,21> landmarks,world;int side=0;float score=0;};
struct Roi {float cx=0,cy=0,size=0,rotation=0;bool mirror=false;}; // Pixels, radians.

inline Point projectUV(Point p,const Roi&r,int width,int height){
    float x=(p.x-.5f)*r.size*(r.mirror?-1.f:1.f),y=(p.y-.5f)*r.size;
    float c=std::cos(r.rotation),s=std::sin(r.rotation);
    return {(r.cx+c*x-s*y)/width,(r.cy+s*x+c*y)/height,1};
}
inline Point projectWorld(Point p,const Roi&r){
    float x=p.x*(r.mirror?-1.f:1.f),c=std::cos(r.rotation),s=std::sin(r.rotation);
    return {c*x-s*p.y,s*x+c*p.y,p.z};
}
inline bool roi(const std::array<Point,21>&uv,const std::array<float,21>&confidence,
                int w,int h,bool left,Roi&out){
    if(w<=0||h<=0||confidence[0]<.15f||confidence[9]<.15f)return false;
    float dx=(uv[9].x-uv[0].x)*w,dy=(uv[9].y-uv[0].y)*h;
    if(std::hypot(dx,dy)<3)return false;
    float r=std::atan2(dy,dx)+pi/2,c=std::cos(r),s=std::sin(r);
    float minx=INFINITY,miny=INFINITY,maxx=-INFINITY,maxy=-INFINITY;int count=0;
    for(int i=0;i<21;i++)if(confidence[i]>=.15f){
        float x=uv[i].x*w,y=uv[i].y*h;
        if(!std::isfinite(x+y))return false;
        float a=c*x+s*y,b=-s*x+c*y;
        minx=std::min(minx,a);maxx=std::max(maxx,a);miny=std::min(miny,b);maxy=std::max(maxy,b);count++;
    }
    // The official training crop uses 1.3x silhouette bounds. Vision joint
    // bounds approximate that support; image padding is constant black.
    float size=1.3f*std::max(maxx-minx,maxy-miny);
    if(count<8||!std::isfinite(size)||size<24||size>2*std::max(w,h))return false;
    float a=(minx+maxx)/2,b=(miny+maxy)/2;
    out={c*a-s*b,s*a+c*b,size,r,left};return true;
}
inline void crop(const uint8_t*bgra,int w,int h,int stride,const Roi&r,float*out){
    constexpr int size=128;float c=std::cos(r.rotation),s=std::sin(r.rotation);
    for(int y=0;y<size;y++)for(int x=0;x<size;x++){
        float dx=((x+.5f)/size-.5f)*r.size*(r.mirror?-1.f:1.f),dy=((y+.5f)/size-.5f)*r.size;
        float sx=r.cx+c*dx-s*dy-.5f,sy=r.cy+s*dx+c*dy-.5f;
        int ix=(int)std::floor(sx),iy=(int)std::floor(sy);float fx=sx-ix,fy=sy-iy;
        for(int channel=0;channel<3;channel++){
            float value=0;
            for(int j=0;j<2;j++)for(int i=0;i<2;i++){
                int px=ix+i,py=iy+j;
                if(px>=0&&px<w&&py>=0&&py<h)value+=bgra[py*stride+px*4+2-channel]*(i?fx:1-fx)*(j?fy:1-fy);
            }
            out[channel*size*size+y*size+x]=value*(2.f/255)-1;
        }
    }
}
}
