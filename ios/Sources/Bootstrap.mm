#import <UIKit/UIKit.h>
#import <UserNotifications/UserNotifications.h>
#import "../Network/Network.h"
#import "../Tracking/Tracker.h"

// Standard local notifications only. No overlay, view controller or extra window.
@interface VHNotice : NSObject <UNUserNotificationCenterDelegate>
@property(nonatomic,weak) id<UNUserNotificationCenterDelegate> previous;
- (void)show:(NSString *)text;
@end
@implementation VHNotice
- (void)show:(NSString *)text {
    NSLog(@"VH: %@",text);
    UNMutableNotificationContent *c=[UNMutableNotificationContent new]; c.title=@"VRidge Hand Tracking 2.5"; c.body=text;
    UNNotificationRequest *r=[UNNotificationRequest requestWithIdentifier:@"VHBridge.status" content:c trigger:nil];
    [UNUserNotificationCenter.currentNotificationCenter addNotificationRequest:r withCompletionHandler:^(NSError *e){if(e)NSLog(@"VH notification: %@",e);}];
}
- (void)userNotificationCenter:(UNUserNotificationCenter *)center willPresentNotification:(UNNotification *)notification withCompletionHandler:(void (^)(UNNotificationPresentationOptions))completion {
    if([notification.request.identifier hasPrefix:@"VHBridge."])completion(UNNotificationPresentationOptionBanner);
    else if([self.previous respondsToSelector:_cmd])[self.previous userNotificationCenter:center willPresentNotification:notification withCompletionHandler:completion];
    else completion(UNNotificationPresentationOptionNone);
}
- (void)userNotificationCenter:(UNUserNotificationCenter *)center didReceiveNotificationResponse:(UNNotificationResponse *)response withCompletionHandler:(void (^)(void))completion {
    if([self.previous respondsToSelector:_cmd])[self.previous userNotificationCenter:center didReceiveNotificationResponse:response withCompletionHandler:completion];else completion();
}
- (void)userNotificationCenter:(UNUserNotificationCenter *)center openSettingsForNotification:(UNNotification *)notification {
    if([self.previous respondsToSelector:_cmd])[self.previous userNotificationCenter:center openSettingsForNotification:notification];
}
@end

@interface VHRuntime : NSObject
@property VHNetwork *network;
@property VHTracker *tracker;
@property VHNotice *notice;
@end
@implementation VHRuntime
- (instancetype)init {
    if((self=[super init])){
        NSDictionary *settings=[NSDictionary dictionaryWithContentsOfFile:[NSBundle.mainBundle pathForResource:@"VHBridge" ofType:@"plist"]]?:@{};
        _notice=[VHNotice new]; _tracker=[[VHTracker alloc]initWithSettings:settings];_network=[[VHNetwork alloc]initWithSettings:settings];
        __weak VHRuntime *weak=self;
        _network.status=^(NSString *text){[weak.notice show:text];}; _tracker.status=^(NSString *text){[weak.notice show:text];};
        _network.connectionChanged=^(BOOL connected){if(connected)[weak.tracker start];else [weak.tracker stop];};
        _tracker.frame=^(NSData *data){[weak.network sendFrame:data];};
        [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(active:) name:UIApplicationDidBecomeActiveNotification object:nil];
        [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(inactive:) name:UIApplicationWillResignActiveNotification object:nil];
        if(UIApplication.sharedApplication.applicationState==UIApplicationStateActive)[self active:nil];
    }return self;
}
- (void)active:(NSNotification *)n {
    UNUserNotificationCenter *center=UNUserNotificationCenter.currentNotificationCenter;
    if(center.delegate!=_notice){_notice.previous=center.delegate;center.delegate=_notice;}
    [center requestAuthorizationWithOptions:UNAuthorizationOptionAlert completionHandler:^(BOOL ok,NSError *error){if(!ok)NSLog(@"VH notifications disabled");if(error)NSLog(@"VH authorization: %@",error);}];
    [_network start];
}
- (void)inactive:(NSNotification *)n { [_tracker stop];[_network stop]; }
@end

__attribute__((constructor)) static void VHLoad() {
    dispatch_async(dispatch_get_main_queue(),^{
        if(@available(iOS 15.0,*)){static VHRuntime *runtime;if(!runtime)runtime=[VHRuntime new];}
        else NSLog(@"VH requires iOS 15 or later; VRidge left untouched");
    });
}
