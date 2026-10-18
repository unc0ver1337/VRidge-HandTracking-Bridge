#import <Foundation/Foundation.h>
#import <CoreVideo/CoreVideo.h>
#include "CoreMLMath.h"
@interface VHCoreMLTracker : NSObject
- (instancetype)initWithBundle:(NSBundle *)bundle error:(NSError **)error;
- (std::vector<corehands::Hand>)process:(CVPixelBufferRef)buffer capture:(double)capture error:(NSError **)error;
- (instancetype)initWithBundle:(NSBundle *)bundle skeletonOnly:(BOOL)skeletonOnly error:(NSError **)error;
- (std::vector<corehands::Hand>)fingers:(CVPixelBufferRef)buffer regions:(const std::vector<corehands::Hand>&)regions error:(NSError **)error;
- (void)reset;
@end
