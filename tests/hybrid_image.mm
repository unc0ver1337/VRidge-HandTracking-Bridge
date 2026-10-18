#import <Foundation/Foundation.h>
#import "../ios/Tracking/CoreMLTracker.h"
#import "../ios/Tracking/VisionHands.h"
#include <fstream>
#include <iterator>
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=5)return 2;int w=atoi(argv[3]),h=atoi(argv[4]);std::ifstream input(argv[2],std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)),{});if(bytes.size()!=size_t(w*h*4))return 3;
    NSBundle *bundle=[NSBundle bundleWithPath:[NSString stringWithUTF8String:argv[1]]];NSError *error=nil;
    VHCoreMLTracker *tracker=[[VHCoreMLTracker alloc]initWithBundle:bundle skeletonOnly:YES error:&error];if(!tracker){NSLog(@"%@",error);return 4;}
    CVPixelBufferRef pixel=nullptr;if(CVPixelBufferCreateWithBytes(kCFAllocatorDefault,w,h,kCVPixelFormatType_32BGRA,bytes.data(),w*4,nullptr,nullptr,nullptr,&pixel)!=kCVReturnSuccess)return 5;
    VNDetectHumanHandPoseRequest *vision=[VNDetectHumanHandPoseRequest new];vision.maximumHandCount=2;
    VNImageRequestHandler *handler=[[VNImageRequestHandler alloc]initWithCVPixelBuffer:pixel orientation:kCGImagePropertyOrientationUp options:@{}];
    if(![handler performRequests:@[vision] error:&error]){NSLog(@"%@",error);return 6;}
    auto observations=hybrid::extract(vision.results);std::vector<corehands::Hand> regions;
    for(const auto&observation:observations)regions.push_back(observation.region);
    auto fingers=[tracker fingers:pixel regions:regions error:&error];
    if(error){NSLog(@"%@",error);return 7;}
    NSMutableArray *records=[NSMutableArray new];
    for(const auto&observation:observations){
        NSMutableArray *lm=[NSMutableArray new],*world=[NSMutableArray new];
        for(int j=0;j<21;j++)[lm addObject:@[@(observation.wire.landmarks[j][0]),@(observation.wire.landmarks[j][1]),@(observation.wire.landmarks[j][2])]];
        for(const auto&finger:fingers)if(finger.side==observation.wire.side){for(const auto&p:finger.world)[world addObject:@[@(p.x),@(p.y),@(p.z)]];break;}
        [records addObject:@{@"side":@(observation.wire.side),@"vision":lm,@"world":world}];
    }
    CVPixelBufferRelease(pixel);
    NSData *json=[NSJSONSerialization dataWithJSONObject:records options:0 error:&error];if(!json)return 8;
    fwrite(json.bytes,1,json.length,stdout);return 0;
}}
