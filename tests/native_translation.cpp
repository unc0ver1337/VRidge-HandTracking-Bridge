#include "../ios/Tracking/TranslationFit.h"
#include <cassert>
#include <limits>
#include <cstdio>
#include <initializer_list>

int main() {
    float world[21][3]{},uv[21][3]{};
    const int anchors[5]={0,5,9,13,17};
    const float xy[5][2]={{0,0},{-.04f,-.07f},{-.01f,-.09f},{.02f,-.08f},{.04f,-.06f}};
    int cases=0;
    // Both signs of yaw/roll, translations and depth, with nonplanar geometry.
    for (int yaw=-3;yaw<=3;yaw++) for(int roll=-3;roll<=3;roll++)
    for(int distance=2;distance<=20;distance+=2) for(int sign:{-1,1}) {
        double angle=yaw*.35,r=roll*.4,tz=distance*.1,tx=sign*.07,ty=-.03;
        for(int k=0;k<5;k++) {
            int j=anchors[k];double x=xy[k][0],y=xy[k][1],z=k*.001;
            double xx=std::cos(angle)*x+std::sin(angle)*z,zz=-std::sin(angle)*x+std::cos(angle)*z;
            world[j][0]=std::cos(r)*xx-std::sin(r)*y;world[j][1]=std::sin(r)*xx+std::cos(r)*y;world[j][2]=zz;
            uv[j][0]=(420*(world[j][0]+tx)/(world[j][2]+tz)+320)/640;
            uv[j][1]=(415*(world[j][1]+ty)/(world[j][2]+tz)+240)/480;
        }
        mpbridge::Fit fit;
        assert(mpbridge::translationFit(world,uv,640,480,420,415,320,240,fit));
        assert(std::abs(fit.translation[0]-tx)<1e-5 && std::abs(fit.translation[1]-ty)<1e-5);
        assert(std::abs(fit.translation[2]-tz)<1e-4 && fit.error<.001);
        cases++;
    }
    mpbridge::Fit fit;
    assert(!mpbridge::translationFit(world,uv,640,480,0,415,320,240,fit));
    for(int j:anchors) {uv[j][0]=.5;uv[j][1]=.5;}
    assert(!mpbridge::translationFit(world,uv,640,480,420,415,320,240,fit));
    uv[0][0]=std::numeric_limits<float>::quiet_NaN();
    assert(!mpbridge::translationFit(world,uv,640,480,420,415,320,240,fit));
    std::printf("PASS: %d synthetic translation poses; invalid camera, degenerate rays, NaN rejected\n",cases);
}
