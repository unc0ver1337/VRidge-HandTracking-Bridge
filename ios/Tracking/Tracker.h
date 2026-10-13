#import <Foundation/Foundation.h>
@interface VHTracker : NSObject
@property(nonatomic,copy) void (^frame)(NSData *data);
@property(nonatomic,copy) void (^status)(NSString *text);
- (instancetype)initWithSettings:(NSDictionary *)settings;
- (void)start;
- (void)stop;
@end
