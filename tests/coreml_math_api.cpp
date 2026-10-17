#include "../ios/Tracking/CoreMLMath.h"
using namespace corehands;
extern "C" {
void native_anchors(float*out){int k=0;for(auto&p:anchors()){out[k++]=p.x;out[k++]=p.y;}}
void native_next(const float*points,int w,int h,float*out){Hand hand;for(int i=0;i<21;i++)hand.landmarks[i]={points[i*3],points[i*3+1],points[i*3+2]};auto r=nextRect(hand,w,h);float a[5]={r.cx,r.cy,r.w,r.h,r.rotation};std::copy_n(a,5,out);}
void native_project(const float*lm,const float*world,float side,const float*rr,float*out){Rect r{rr[0],rr[1],rr[2],rr[3],rr[4]};auto h=project(lm,world,side,r);for(int i=0;i<21;i++){out[i*3]=h.landmarks[i].x;out[i*3+1]=h.landmarks[i].y;out[i*3+2]=h.landmarks[i].z;out[63+i*3]=h.world[i].x;out[63+i*3+1]=h.world[i].y;out[63+i*3+2]=h.world[i].z;}}
int native_decode(const float*boxes,const float*scores,int iw,int ih,float*out){auto result=nms(decode(boxes,scores));int k=0;for(const auto&d:result){auto r=palmRect(d,iw,ih);float a[5]={r.cx,r.cy,r.w,r.h,r.rotation};std::copy_n(a,5,out+5*k++);}return k;}
void native_crop(const uint8_t*p,int w,int h,int stride,const float*rr,int size,int replicate,float*out){crop(p,w,h,stride,{rr[0],rr[1],rr[2],rr[3],rr[4]},size,replicate!=0,out);}
}
