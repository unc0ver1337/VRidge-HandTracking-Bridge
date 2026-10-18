#import "CoreMLTracker.h"
#import <CoreML/CoreML.h>
#import <Vision/Vision.h>
#import <ImageIO/ImageIO.h>
#import <TargetConditionals.h>
#include <chrono>

namespace {
void fail(NSError **error,NSString *message){if(error)*error=[NSError errorWithDomain:@"VRidge.MobRecon" code:1 userInfo:@{NSLocalizedDescriptionKey:message}];}
std::vector<float> values(MLMultiArray *array){
    std::vector<float> out(array.count);
    for(NSInteger i=0;i<array.count;i++)out[i]=array[i].floatValue;
    return out;
}
struct Lock {
    CVPixelBufferRef buffer;bool locked;
    explicit Lock(CVPixelBufferRef p):buffer(p),locked(CVPixelBufferLockBaseAddress(p,kCVPixelBufferLock_ReadOnly)==kCVReturnSuccess){}
    ~Lock(){if(locked)CVPixelBufferUnlockBaseAddress(buffer,kCVPixelBufferLock_ReadOnly);}
};
NSArray<NSString *> *jointNames(){return @[VNHumanHandPoseObservationJointNameWrist,
VNHumanHandPoseObservationJointNameThumbCMC,VNHumanHandPoseObservationJointNameThumbMP,VNHumanHandPoseObservationJointNameThumbIP,VNHumanHandPoseObservationJointNameThumbTip,
VNHumanHandPoseObservationJointNameIndexMCP,VNHumanHandPoseObservationJointNameIndexPIP,VNHumanHandPoseObservationJointNameIndexDIP,VNHumanHandPoseObservationJointNameIndexTip,
VNHumanHandPoseObservationJointNameMiddleMCP,VNHumanHandPoseObservationJointNameMiddlePIP,VNHumanHandPoseObservationJointNameMiddleDIP,VNHumanHandPoseObservationJointNameMiddleTip,
VNHumanHandPoseObservationJointNameRingMCP,VNHumanHandPoseObservationJointNameRingPIP,VNHumanHandPoseObservationJointNameRingDIP,VNHumanHandPoseObservationJointNameRingTip,
VNHumanHandPoseObservationJointNameLittleMCP,VNHumanHandPoseObservationJointNameLittlePIP,VNHumanHandPoseObservationJointNameLittleDIP,VNHumanHandPoseObservationJointNameLittleTip];}
}
@implementation VHCoreMLTracker {
    MLModel *_model;MLMultiArray *_input;MLDictionaryFeatureProvider *_features;
    VNDetectHumanHandPoseRequest *_vision;
    double _totalMS;NSUInteger _frames;
}
- (instancetype)initWithBundle:(NSBundle *)bundle error:(NSError **)error {
    if((self=[super init])){
        MLModelConfiguration *config=[MLModelConfiguration new];config.computeUnits=MLComputeUnitsCPUAndNeuralEngine;
#if TARGET_OS_OSX
        config.computeUnits=MLComputeUnitsCPUOnly;
#endif
        NSURL *url=[bundle URLForResource:@"mobrecon" withExtension:@"mlmodelc"];
        if(!url){fail(error,@"Missing compiled MobRecon model");return nil;}
        _model=[MLModel modelWithContentsOfURL:url configuration:config error:error];if(!_model)return nil;
        _input=[[MLMultiArray alloc]initWithShape:@[@1,@3,@128,@128] dataType:MLMultiArrayDataTypeFloat32 error:error];
        if(!_input)return nil;
        NSInteger stride=1;
        for(NSInteger i=_input.shape.count-1;i>=0;i--){if(_input.strides[i].integerValue!=stride){fail(error,@"Unsupported MobRecon input layout");return nil;}stride*=_input.shape[i].integerValue;}
        _features=[[MLDictionaryFeatureProvider alloc]initWithDictionary:@{@"image":[MLFeatureValue featureValueWithMultiArray:_input]} error:error];if(!_features)return nil;
        _vision=[VNDetectHumanHandPoseRequest new];_vision.maximumHandCount=2;
        NSLog(@"MobRecon DenseStack SpConv loaded; Vision supplies ROI/side only; computeUnits=%ld",(long)config.computeUnits);
    }return self;
}
- (void)reset {_vision=[VNDetectHumanHandPoseRequest new];_vision.maximumHandCount=2;}
- (std::vector<corehands::Hand>)process:(CVPixelBufferRef)buffer capture:(double)capture error:(NSError **)error {
    using namespace corehands;std::vector<Hand> hands;
    if(!std::isfinite(capture)||CVPixelBufferGetPixelFormatType(buffer)!=kCVPixelFormatType_32BGRA){fail(error,@"Invalid MobRecon frame");return hands;}
    const auto start=std::chrono::steady_clock::now();
    VNImageRequestHandler *handler=[[VNImageRequestHandler alloc]initWithCVPixelBuffer:buffer orientation:kCGImagePropertyOrientationUp options:@{}];
    if(![handler performRequests:@[_vision] error:error])return hands;
    Lock lock(buffer);if(!lock.locked){fail(error,@"Cannot read camera frame");return hands;}
    int w=(int)CVPixelBufferGetWidth(buffer),h=(int)CVPixelBufferGetHeight(buffer),row=(int)CVPixelBufferGetBytesPerRow(buffer);
    const uint8_t *pixels=(const uint8_t *)CVPixelBufferGetBaseAddress(buffer);NSArray *names=jointNames();
    for(VNHumanHandPoseObservation *observation in _vision.results){
        int side=observation.chirality==VNChiralityLeft?1:observation.chirality==VNChiralityRight?2:0;
        if(!side)continue;
        NSError *local=nil;NSDictionary *points=[observation recognizedPointsForGroupKey:VNHumanHandPoseObservationJointsGroupNameAll error:&local];if(!points)continue;
        std::array<corehands::Point,21> vision;std::array<float,21> confidence;
        for(NSUInteger i=0;i<21;i++){
            VNRecognizedPoint *p=points[names[i]];vision[i]={(float)p.location.x,1.f-(float)p.location.y,0};confidence[i]=p?p.confidence:0;
        }
        Roi r;if(!roi(vision,confidence,w,h,side==1,r))continue;
        crop(pixels,w,h,row,r,(float *)_input.dataPointer);
        auto prediction=[_model predictionFromFeatures:_features error:&local];
        if(!prediction){NSLog(@"Isolated MobRecon hand error: %@",local);continue;}
        MLMultiArray *j=[prediction featureValueForName:@"joints"].multiArrayValue;
        MLMultiArray *uv=[prediction featureValueForName:@"landmarks2d"].multiArrayValue;
        if(j.count!=63||uv.count!=42){fail(error,@"MobRecon model output shape mismatch");return {};}
        auto xyz=values(j),xy=values(uv);bool finite=true;Hand hand;hand.side=side;hand.score=observation.confidence;
        for(int i=0;i<21;i++){
            finite=finite&&std::isfinite(xyz[3*i]+xyz[3*i+1]+xyz[3*i+2]+xy[2*i]+xy[2*i+1]);
            hand.world[i]=projectWorld({xyz[3*i],xyz[3*i+1],xyz[3*i+2]},r);
            hand.landmarks[i]=projectUV({xy[2*i],xy[2*i+1],0},r,w,h);
        }
        if(finite)hands.push_back(hand);
    }
    _totalMS+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    if(++_frames==120){NSLog(@"MobRecon Vision+crop+inference mean %.2f ms, hands=%lu",_totalMS/_frames,(unsigned long)hands.size());_totalMS=0;_frames=0;}
    return hands;
}
@end
