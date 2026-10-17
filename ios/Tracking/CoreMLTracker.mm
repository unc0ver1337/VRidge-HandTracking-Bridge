#import "CoreMLTracker.h"
#import <CoreML/CoreML.h>
#import <TargetConditionals.h>
#include <chrono>

namespace {
void fail(NSError **error,NSString *message){if(error)*error=[NSError errorWithDomain:@"VRidge.CoreML" code:1 userInfo:@{NSLocalizedDescriptionKey:message}];}
std::vector<float> flatten(MLMultiArray *array){
    std::vector<float> out(array.count);bool contiguous=true;NSInteger stride=1;
    for(NSInteger i=array.shape.count-1;i>=0;i--){contiguous=contiguous&&array.strides[i].integerValue==stride;stride*=array.shape[i].integerValue;}
    if(contiguous&&array.dataType==MLMultiArrayDataTypeFloat32)std::copy_n((float *)array.dataPointer,array.count,out.data());
    else for(NSInteger i=0;i<array.count;i++)out[i]=array[i].floatValue;
    return out;
}
bool finite(const std::vector<float>&values){for(float x:values)if(!std::isfinite(x))return false;return true;}
bool outputs(id<MLFeatureProvider> result,NSArray<NSString *> *names,const std::vector<int>&counts,std::vector<std::vector<float>>&out,NSError **error){
    if(!result)return false;out.clear();
    for(NSUInteger i=0;i<names.count;i++){
        MLMultiArray *a=[result featureValueForName:names[i]].multiArrayValue;
        if(!a||a.count!=counts[i]){fail(error,@"Core ML output shape/name mismatch");return false;}
        auto values=flatten(a);if(!finite(values)){fail(error,@"Core ML output contains NaN/Inf");return false;}out.push_back(std::move(values));
    }return true;
}
bool inputLayout(MLMultiArray*a){
    NSInteger stride=1;for(NSInteger i=a.shape.count-1;i>=0;i--){if(a.strides[i].integerValue!=stride)return false;stride*=a.shape[i].integerValue;}
    return a.dataType==MLMultiArrayDataTypeFloat32;
}
struct PixelLock {
    CVPixelBufferRef pixel;bool locked;
    explicit PixelLock(CVPixelBufferRef p):pixel(p),locked(CVPixelBufferLockBaseAddress(p,kCVPixelBufferLock_ReadOnly)==kCVReturnSuccess){}
    ~PixelLock(){if(locked)CVPixelBufferUnlockBaseAddress(pixel,kCVPixelBufferLock_ReadOnly);}
};
}
@implementation VHCoreMLTracker {
    MLModel *_detector,*_landmarker;
    MLMultiArray *_detectorInput,*_landmarkInput;
    MLDictionaryFeatureProvider *_detectorFeatures,*_landmarkFeatures;
    std::vector<corehands::Rect> _tracked;
    double _lastCapture,_totalMS;NSUInteger _frames;
}
- (instancetype)initWithBundle:(NSBundle *)bundle error:(NSError **)error {
    if((self=[super init])){
        MLModelConfiguration *config=[MLModelConfiguration new];
        // Keep GPU available for VRidge. Core ML may use CPU for unsupported ops;
        // this enables ANE, it does not prove which hardware the planner chose.
        config.computeUnits=MLComputeUnitsCPUAndNeuralEngine;
#if TARGET_OS_OSX
        config.computeUnits=MLComputeUnitsCPUOnly; // CI reference parity, no ANE benchmark.
#endif
        NSURL *det=[bundle URLForResource:@"hand_detector" withExtension:@"mlmodelc"];
        NSURL *lm=[bundle URLForResource:@"hand_landmarks_detector" withExtension:@"mlmodelc"];
        if(!det||!lm){fail(error,@"Missing compiled Core ML models");return nil;}
        _detector=[MLModel modelWithContentsOfURL:det configuration:config error:error];if(!_detector)return nil;
        _landmarker=[MLModel modelWithContentsOfURL:lm configuration:config error:error];if(!_landmarker)return nil;
        _detectorInput=[[MLMultiArray alloc]initWithShape:@[@1,@192,@192,@3] dataType:MLMultiArrayDataTypeFloat32 error:error];
        _landmarkInput=[[MLMultiArray alloc]initWithShape:@[@1,@224,@224,@3] dataType:MLMultiArrayDataTypeFloat32 error:error];
        if(!_detectorInput||!_landmarkInput||!inputLayout(_detectorInput)||!inputLayout(_landmarkInput)){fail(error,@"Core ML input layout allocation failed");return nil;}
        _detectorFeatures=[[MLDictionaryFeatureProvider alloc]initWithDictionary:@{@"image":[MLFeatureValue featureValueWithMultiArray:_detectorInput]} error:error];
        _landmarkFeatures=[[MLDictionaryFeatureProvider alloc]initWithDictionary:@{@"image":[MLFeatureValue featureValueWithMultiArray:_landmarkInput]} error:error];
        if(!_detectorFeatures||!_landmarkFeatures)return nil;
        NSLog(@"Core ML preview loaded fp16 models; computeUnits=CPUAndNeuralEngine, numHands=2");
    }return self;
}
- (void)reset {_tracked.clear();_lastCapture=0;}
- (std::vector<corehands::Hand>)process:(CVPixelBufferRef)buffer capture:(double)capture error:(NSError **)error {
    using namespace corehands;std::vector<Hand> hands;
    if(!std::isfinite(capture)){fail(error,@"Invalid capture timestamp");return hands;}
    if(_lastCapture&&(capture<=_lastCapture||capture-_lastCapture>.35))_tracked.clear();_lastCapture=capture;
    const auto start=std::chrono::steady_clock::now();PixelLock lock(buffer);
    if(!lock.locked||CVPixelBufferGetPixelFormatType(buffer)!=kCVPixelFormatType_32BGRA){fail(error,@"Core ML expects readable BGRA frame");_tracked.clear();return hands;}
    const uint8_t *image=(const uint8_t *)CVPixelBufferGetBaseAddress(buffer);
    int iw=(int)CVPixelBufferGetWidth(buffer),ih=(int)CVPixelBufferGetHeight(buffer),stride=(int)CVPixelBufferGetBytesPerRow(buffer);
    std::vector<Rect> rects=_tracked;std::vector<std::vector<float>> raw;
    if(rects.size()<2){
        float side=std::max(iw,ih);crop(image,iw,ih,stride,{.5f,.5f,side/iw,side/ih,0},192,false,(float *)_detectorInput.dataPointer);
        auto result=[_detector predictionFromFeatures:_detectorFeatures error:error];
        if(!outputs(result,@[@"Identity",@"Identity_1"],{2016*18,2016},raw,error)){_tracked.clear();return hands;}
        for(const auto&d:nms(decode(raw[0].data(),raw[1].data()))){
            auto r=palmRect(d,iw,ih);if(!usable(r))continue;
            bool overlap=false;for(const auto&t:rects)if(iou(r,t)>.5f){overlap=true;break;}
            if(!overlap)rects.push_back(r);if(rects.size()==2)break;
        }
    }
    for(const auto&r:rects){
        if(!usable(r))continue;crop(image,iw,ih,stride,r,224,true,(float *)_landmarkInput.dataPointer);
        auto result=[_landmarker predictionFromFeatures:_landmarkFeatures error:error];
        if(!outputs(result,@[@"Identity",@"Identity_1",@"Identity_2",@"Identity_3"],{63,1,1,63},raw,error)){_tracked.clear();return {};}
        if(raw[1][0]<=.5f)continue;
        auto hand=project(raw[0].data(),raw[3].data(),std::clamp(raw[2][0],0.f,1.f),r);
        bool overlap=false;for(const auto&h:hands)if(duplicate(hand,h,iw,ih)){overlap=true;break;}
        if(!overlap)hands.push_back(hand);
    }
    _tracked.clear();for(const auto&h:hands){auto r=nextRect(h,iw,ih);if(usable(r))_tracked.push_back(r);}
    _totalMS+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    if(++_frames==120){NSLog(@"Core ML CPU+ANE preview: inference+crop mean %.2f ms, hands=%lu",_totalMS/_frames,(unsigned long)hands.size());_frames=0;_totalMS=0;}
    return hands;
}
@end
