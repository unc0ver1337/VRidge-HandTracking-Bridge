#import <Foundation/Foundation.h>
#import <CoreVideo/CoreVideo.h>
#include "MobReconMath.h"
@interface VHCoreMLTracker : NSObject
- (instancetype)initWithBundle:(NSBundle *)bundle error:(NSError **)error;
- (std::vector<corehands::Hand>)process:(CVPixelBufferRef)buffer capture:(double)capture error:(NSError **)error;
- (void)reset;
@end
