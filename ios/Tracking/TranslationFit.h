#pragma once
#include <cmath>

namespace mpbridge {
struct Fit { float translation[3]{}; float error = 1000000; };

// Least squares of Tx-u*Tz=u*Wz-Wx and Ty-v*Tz=v*Wz-Wy.
// Eliminate Tx,Ty analytically; centred double-precision sums avoid forming
// an ill-conditioned 3x3 normal matrix for small palms near image centre.
inline bool translationFit(const float world[21][3], const float uv[21][3],
                           int width, int height, double fx, double fy,
                           double cx, double cy, Fit &out) {
    constexpr int anchors[5] = {0,5,9,13,17};
    if (!(fx>0 && fy>0) || !std::isfinite(fx+fy+cx+cy)) return false;
    double u[5],v[5],a[5],b[5],mu=0,mv=0,ma=0,mb=0;
    for (int k=0;k<5;k++) {
        int j=anchors[k];
        u[k]=(uv[j][0]*width-cx)/fx; v[k]=(uv[j][1]*height-cy)/fy;
        a[k]=u[k]*world[j][2]-world[j][0]; b[k]=v[k]*world[j][2]-world[j][1];
        if (!std::isfinite(u[k]+v[k]+a[k]+b[k])) return false;
        mu+=u[k]/5;mv+=v[k]/5;ma+=a[k]/5;mb+=b[k]/5;
    }
    double variance=0,covariance=0;
    for (int k=0;k<5;k++) {
        variance+=(u[k]-mu)*(u[k]-mu)+(v[k]-mv)*(v[k]-mv);
        covariance+=(u[k]-mu)*(a[k]-ma)+(v[k]-mv)*(b[k]-mb);
    }
    if (variance<1e-10) return false; // Numerically unobservable translation.
    double tz=-covariance/variance,tx=ma+mu*tz,ty=mb+mv*tz,error=0;
    if (!std::isfinite(tx+ty+tz)) return false;
    for (int j:anchors) {
        double z=world[j][2]+tz;
        if (z<.04) return false;
        double dx=fx*(world[j][0]+tx)/z+cx-uv[j][0]*width;
        double dy=fy*(world[j][1]+ty)/z+cy-uv[j][1]*height;
        error+=dx*dx+dy*dy;
    }
    out.error=static_cast<float>(std::sqrt(error/5));
    if (!std::isfinite(out.error)) { out.error=1000000; return false; }
    out.translation[0]=tx;out.translation[1]=ty;out.translation[2]=tz;
    double depth=world[0][2]+tz;
    return out.error<=20 && depth>=.08 && depth<=2.5;
}
}
