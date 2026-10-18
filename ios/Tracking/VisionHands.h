#pragma once
#import <Vision/Vision.h>
#include "CoreMLMath.h"
#include "../Network/Wire.h"
namespace hybrid {
struct Observation {VHHand wire;corehands::Hand region;};
inline std::vector<Observation> extract(NSArray<VNHumanHandPoseObservation *> *observations){
    std::vector<Observation> result;NSError *error=nil;
        static NSArray<VNHumanHandPoseObservationJointName> *names;
        static dispatch_once_t once;dispatch_once(&once,^{names=@[
            VNHumanHandPoseObservationJointNameWrist,
            VNHumanHandPoseObservationJointNameThumbCMC,VNHumanHandPoseObservationJointNameThumbMP,VNHumanHandPoseObservationJointNameThumbIP,VNHumanHandPoseObservationJointNameThumbTip,
            VNHumanHandPoseObservationJointNameIndexMCP,VNHumanHandPoseObservationJointNameIndexPIP,VNHumanHandPoseObservationJointNameIndexDIP,VNHumanHandPoseObservationJointNameIndexTip,
            VNHumanHandPoseObservationJointNameMiddleMCP,VNHumanHandPoseObservationJointNameMiddlePIP,VNHumanHandPoseObservationJointNameMiddleDIP,VNHumanHandPoseObservationJointNameMiddleTip,
            VNHumanHandPoseObservationJointNameRingMCP,VNHumanHandPoseObservationJointNameRingPIP,VNHumanHandPoseObservationJointNameRingDIP,VNHumanHandPoseObservationJointNameRingTip,
            VNHumanHandPoseObservationJointNameLittleMCP,VNHumanHandPoseObservationJointNameLittlePIP,VNHumanHandPoseObservationJointNameLittleDIP,VNHumanHandPoseObservationJointNameLittleTip];});
    for(VNHumanHandPoseObservation *observation in observations){
            VHHand hand={};corehands::Hand region;
            hand.side=observation.chirality==VNChiralityLeft?1:(observation.chirality==VNChiralityRight?2:0);
            if(!hand.side)continue;hand.identity=hand.side;hand.rotation[3]=1;region.side=hand.side;
            auto points=[observation recognizedPointsForGroupKey:VNHumanHandPoseObservationJointsGroupNameAll error:&error];
            bool palmValid=true;
            for(int j=0;j<21;j++){
                VNRecognizedPoint *point=points[names[j]];
                float x=point?point.location.x:0,y=point?1-point.location.y:0,c=point?point.confidence:0;
                hand.landmarks[j][0]=std::clamp(x,0.f,1.f);hand.landmarks[j][1]=std::clamp(y,0.f,1.f);hand.landmarks[j][2]=std::clamp(c,0.f,1.f);
                region.landmarks[j]={x,y,0};
                if((j==0||j==5||j==9||j==13||j==17)&&c<.35f)palmValid=false;
            }
            if(!palmValid)continue;
            result.push_back({hand,region});
    }return result;
}
}
