#import <Foundation/Foundation.h>
@interface VHNetwork : NSObject <NSNetServiceBrowserDelegate, NSNetServiceDelegate>
@property(nonatomic,copy) void (^connectionChanged)(BOOL connected);
@property(nonatomic,copy) void (^status)(NSString *text);
- (instancetype)initWithSettings:(NSDictionary *)settings;
- (void)start;
- (void)stop;
- (void)sendFrame:(NSData *)data;
@end
