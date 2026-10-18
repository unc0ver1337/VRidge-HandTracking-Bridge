#pragma once
// Native adaptation of Vimal Mollyn's fasthands pipeline (MIT).
// See third_party/FastHands-LICENSE.txt. Model weights: Google, Apache-2.0.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace corehands {
constexpr float pi=3.14159265358979323846f;
struct Point {float x=0,y=0,z=0;};
struct Rect {float cx,cy,w,h,rotation;}; // Normalized image coordinates.
struct Detection {float x,y,w,h,score;std::array<Point,7> kp;};
struct Hand {std::array<Point,21> landmarks,world;int side=0;float score=0;uint32_t identity=0;};
inline float radians(float x){return x-2*pi*std::floor((x+pi)/(2*pi));}
inline std::vector<Point> anchors(){
    std::vector<Point> out;out.reserve(2016);
    for(int layer=0;layer<2;layer++){
        int grid=layer==0?24:12,count=layer==0?2:6;
        for(int y=0;y<grid;y++)for(int x=0;x<grid;x++)for(int k=0;k<count;k++)
            out.push_back({(x+.5f)/grid,(y+.5f)/grid,0});
    }return out;
}
inline float iou(float ax,float ay,float aw,float ah,float bx,float by,float bw,float bh){
    float w=std::min(ax+aw,bx+bw)-std::max(ax,bx),h=std::min(ay+ah,by+bh)-std::max(ay,by);
    if(w<=0||h<=0)return 0;float area=w*h,den=aw*ah+bw*bh-area;
    return den>0?area/den:0;
}
inline float iou(const Detection&a,const Detection&b){return iou(a.x,a.y,a.w,a.h,b.x,b.y,b.w,b.h);}
inline float iou(const Rect&a,const Rect&b){return iou(a.cx-a.w/2,a.cy-a.h/2,a.w,a.h,b.cx-b.w/2,b.cy-b.h/2,b.w,b.h);}
inline std::vector<Detection> decode(const float*boxes,const float*scores){
    static const auto aa=anchors();std::vector<Detection> out;
    for(int i=0;i<2016;i++){
        if(!std::isfinite(scores[i]))continue;
        float score=1/(1+std::exp(-double(std::clamp(scores[i],-100.f,100.f))));
        if(score<.5f)continue;const float*b=boxes+i*18;
        bool finite=true;for(int k=0;k<18;k++)finite=finite&&std::isfinite(b[k]);
        if(!finite||b[2]<=0||b[3]<=0)continue;
        float cx=b[0]/192+aa[i].x,cy=b[1]/192+aa[i].y,w=b[2]/192,h=b[3]/192;
        Detection d{cx-w/2,cy-h/2,w,h,score,{}};
        for(int k=0;k<7;k++)d.kp[k]={b[4+2*k]/192+aa[i].x,b[5+2*k]/192+aa[i].y,0};
        out.push_back(d);
    }return out;
}
inline std::vector<Detection> nms(std::vector<Detection> remaining){
    std::stable_sort(remaining.begin(),remaining.end(),[](auto&a,auto&b){return a.score>b.score;});
    std::vector<Detection> out;
    while(!remaining.empty()){
        const auto top=remaining.front();Detection m{};m.score=top.score;float total=0,rx=0,by=0;
        std::vector<Detection> next;
        for(const auto&d:remaining){
            if(iou(d,top)<=.3f){next.push_back(d);continue;}
            total+=d.score;m.x+=d.x*d.score;m.y+=d.y*d.score;rx+=(d.x+d.w)*d.score;by+=(d.y+d.h)*d.score;
            for(int k=0;k<7;k++){m.kp[k].x+=d.kp[k].x*d.score;m.kp[k].y+=d.kp[k].y*d.score;}
        }
        if(total<=0){out.push_back(top);remaining.erase(remaining.begin());continue;}
        m.x/=total;m.y/=total;m.w=rx/total-m.x;m.h=by/total-m.y;
        for(auto&p:m.kp){p.x/=total;p.y/=total;}out.push_back(m);remaining=std::move(next);
    }return out;
}
inline Rect palmRect(Detection d,int iw,int ih){
    float side=std::max(iw,ih),sx=side/iw,sy=side/ih,ox=(.5f*iw-.5f*side)/iw,oy=(.5f*ih-.5f*side)/ih;
    d.x=d.x*sx+ox;d.y=d.y*sy+oy;d.w*=sx;d.h*=sy;
    for(auto&p:d.kp){p.x=p.x*sx+ox;p.y=p.y*sy+oy;}
    // Upstream Tasks graph's target_angle is 90 radians (not target_angle_degrees).
    float r=radians(90.f-std::atan2(-(d.kp[2].y-d.kp[0].y)*ih,(d.kp[2].x-d.kp[0].x)*iw));
    float cx=d.x+d.w/2+.5f*ih*d.h*std::sin(r)/iw,cy=d.y+d.h/2-.5f*d.h*std::cos(r);
    float longest=std::max(d.w*iw,d.h*ih)*2.6f;
    return {cx,cy,longest/iw,longest/ih,r};
}
inline Hand project(const float*lm,const float*world,float handedness,const Rect&r){
    Hand h;h.side=handedness>=.5f?2:1;h.score=std::max(handedness,1-handedness);
    float c=std::cos(r.rotation),s=std::sin(r.rotation);
    for(int k=0;k<21;k++){
        float x=lm[3*k]/224-.5f,y=lm[3*k+1]/224-.5f;
        h.landmarks[k]={(c*x-s*y)*r.w+r.cx,(s*x+c*y)*r.h+r.cy,lm[3*k+2]/224/.4f*r.w};
        h.world[k]={c*world[3*k]-s*world[3*k+1],s*world[3*k]+c*world[3*k+1],world[3*k+2]};
    }return h;
}
inline Rect nextRect(const Hand&h,int iw,int ih){
    constexpr int ids[12]={0,1,2,3,5,6,9,10,13,14,17,18};const auto&lm=h.landmarks;
    float x1=((lm[5].x+lm[13].x)/2+lm[9].x)/2*iw,y1=((lm[5].y+lm[13].y)/2+lm[9].y)/2*ih;
    float r=radians(pi/2-std::atan2(-(y1-lm[0].y*ih),x1-lm[0].x*iw)),c=std::cos(r),s=std::sin(r);
    float xmin=INFINITY,xmax=-INFINITY,ymin=INFINITY,ymax=-INFINITY;
    for(int j:ids){xmin=std::min(xmin,lm[j].x);xmax=std::max(xmax,lm[j].x);ymin=std::min(ymin,lm[j].y);ymax=std::max(ymax,lm[j].y);}
    float cx=(xmin+xmax)/2,cy=(ymin+ymax)/2,px0=INFINITY,px1=-INFINITY,py0=INFINITY,py1=-INFINITY;
    for(int j:ids){float x=(lm[j].x-cx)*iw,y=(lm[j].y-cy)*ih,px=c*x+s*y,py=-s*x+c*y;px0=std::min(px0,px);px1=std::max(px1,px);py0=std::min(py0,py);py1=std::max(py1,py);}
    float px=(px0+px1)/2,py=(py0+py1)/2,hp=py1-py0,longest=std::max(px1-px0,hp)*2;
    return {(c*px-s*py+iw*cx+.1f*hp*s)/iw,(s*px+c*py+ih*cy-.1f*hp*c)/ih,longest/iw,longest/ih,r};
}
inline bool duplicate(const Hand&a,const Hand&b,int iw,int ih){
    auto distance=[&](const Point&p,const Point&q){return std::hypot((p.x-q.x)*iw,(p.y-q.y)*ih);};
    float baseline=0;for(auto*h:{&a,&b})baseline=std::max({baseline,distance(h->landmarks[0],h->landmarks[5]),distance(h->landmarks[5],h->landmarks[17]),distance(h->landmarks[17],h->landmarks[0])});
    int count=0;for(int j=0;j<21;j++)count+=distance(a.landmarks[j],b.landmarks[j])<baseline*.2f;
    if(count<10)return false;
    auto box=[](const Hand&h){Rect r{INFINITY,INFINITY,-INFINITY,-INFINITY,0};for(auto&p:h.landmarks){r.cx=std::min(r.cx,p.x);r.cy=std::min(r.cy,p.y);r.w=std::max(r.w,p.x);r.h=std::max(r.h,p.y);}return r;};
    auto x=box(a),y=box(b);return iou(x.cx,x.cy,x.w-x.cx,x.h-x.cy,y.cx,y.cy,y.w-y.cx,y.h-y.cy)>.2f;
}
inline bool usable(const Rect&r){return std::isfinite(r.cx+r.cy+r.w+r.h+r.rotation)&&r.w>1e-5&&r.h>1e-5&&r.w<8&&r.h<8;}
// BGRA uint8 -> NHWC RGB float32, rotated ROI, OpenCV-compatible 1/32 linear
// interpolation. Constant zero padding for detector, replicate for landmarks.
inline void crop(const uint8_t*bgra,int iw,int ih,int stride,const Rect&r,int size,bool replicate,float*out){
    float c=std::cos(r.rotation),s=std::sin(r.rotation);
    for(int y=0;y<size;y++)for(int x=0;x<size;x++){
        double dx=(double(x)/size-.5)*r.w*iw,dy=(double(y)/size-.5)*r.h*ih;
        double xx=r.cx*iw+c*dx-s*dy,yy=r.cy*ih+s*dx+c*dy;
        int ix=std::lrint(xx*32),iy=std::lrint(yy*32),x0=int(std::floor(ix/32.)),y0=int(std::floor(iy/32.)),fx=ix-x0*32,fy=iy-y0*32;
        for(int channel=0;channel<3;channel++){
            int value=0;
            for(int j=0;j<2;j++)for(int i=0;i<2;i++){
                int xx=x0+i,yy=y0+j,weight=(i?fx:32-fx)*(j?fy:32-fy);
                if(replicate){xx=std::clamp(xx,0,iw-1);yy=std::clamp(yy,0,ih-1);}
                if(xx>=0&&xx<iw&&yy>=0&&yy<ih)value+=weight*bgra[yy*stride+xx*4+(2-channel)];
            }out[(y*size+x)*3+channel]=((value+512)>>10)*(1.f/255);
        }
    }
}
}
