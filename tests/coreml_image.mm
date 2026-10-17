#import <Foundation/Foundation.h>
#import "../ios/Tracking/CoreMLTracker.h"
#include <fstream>
#include <iterator>
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=5)return 2;int w=atoi(argv[3]),h=atoi(argv[4]);std::ifstream input(argv[2],std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)),{});if(bytes.size()!=size_t(w*h*4))return 3;
    NSBundle *bundle=[NSBundle bundleWithPath:[NSString stringWithUTF8String:argv[1]]];NSError *error=nil;
    VHCoreMLTracker *tracker=[[VHCoreMLTracker alloc]initWithBundle:bundle error:&error];if(!tracker){NSLog(@"%@",error);return 4;}
    CVPixelBufferRef pixel=nullptr;if(CVPixelBufferCreateWithBytes(kCFAllocatorDefault,w,h,kCVPixelFormatType_32BGRA,bytes.data(),w*4,nullptr,nullptr,nullptr,&pixel)!=kCVReturnSuccess)return 5;
    NSMutableArray *frames=[NSMutableArray new];
    for(int frame=0;frame<3;frame++){
        auto hands=[tracker process:pixel capture:1.+frame/30. error:&error];if(error){NSLog(@"%@",error);CVPixelBufferRelease(pixel);return 6;}
        NSMutableArray *result=[NSMutableArray new];
        for(auto&hand:hands){NSMutableArray *lm=[NSMutableArray new],*world=[NSMutableArray new];for(auto&p:hand.landmarks)[lm addObject:@[@(p.x),@(p.y),@(p.z)]];for(auto&p:hand.world)[world addObject:@[@(p.x),@(p.y),@(p.z)]];[result addObject:@{@"side":@(hand.side),@"landmarks":lm,@"world":world}];}
        [frames addObject:result];
    }CVPixelBufferRelease(pixel);NSData *json=[NSJSONSerialization dataWithJSONObject:frames options:0 error:&error];if(!json)return 7;
    fwrite(json.bytes,1,json.length,stdout);return 0;
}}
