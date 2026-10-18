#import <UIKit/UIKit.h>
#import <UserNotifications/UserNotifications.h>
#import "../Network/Network.h"
#import "../Tracking/Tracker.h"

// A single opt-in system alert; status uses standard local notifications. No extra window.
@interface VHNotice : NSObject <UNUserNotificationCenterDelegate>
@property(nonatomic,weak) id<UNUserNotificationCenterDelegate> previous;
- (void)show:(NSString *)text;
@end
@implementation VHNotice
- (void)show:(NSString *)text {
    NSLog(@"VH: %@",text);
    UNMutableNotificationContent *c=[UNMutableNotificationContent new]; c.title=@"VRidge Hand Tracking 3.0"; c.body=text;
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
@property BOOL decided;
@property BOOL enabled;
@property BOOL presenting;
@end
@implementation VHRuntime
- (instancetype)init {
    if((self=[super init])){
        [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(active:) name:UIApplicationDidBecomeActiveNotification object:nil];
        [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(inactive:) name:UIApplicationWillResignActiveNotification object:nil];
        if(UIApplication.sharedApplication.applicationState==UIApplicationStateActive)[self active:nil];
    }return self;
}
- (void)enable {
    if(_enabled)return;_enabled=YES;
        NSDictionary *settings=[NSDictionary dictionaryWithContentsOfFile:[NSBundle.mainBundle pathForResource:@"VHBridge" ofType:@"plist"]]?:@{};
        _notice=[VHNotice new]; _tracker=[[VHTracker alloc]initWithSettings:settings];_network=[[VHNetwork alloc]initWithSettings:settings];
        __weak VHRuntime *weak=self;
        _network.status=^(NSString *text){[weak.notice show:text];}; _tracker.status=^(NSString *text){[weak.notice show:text];};
        _network.connectionChanged=^(BOOL connected){if(connected)[weak.tracker start];else [weak.tracker stop];};
        _tracker.frame=^(NSData *data){[weak.network sendFrame:data];};
    [self active:nil];
}
- (void)askToStart {
    if(_decided||_presenting||UIApplication.sharedApplication.applicationState!=UIApplicationStateActive)return;
    UIViewController *root=nil;
    for(UIScene *scene in UIApplication.sharedApplication.connectedScenes){
        if(scene.activationState!=UISceneActivationStateForegroundActive||![scene isKindOfClass:UIWindowScene.class])continue;
        for(UIWindow *window in ((UIWindowScene *)scene).windows)if(window.isKeyWindow){root=window.rootViewController;break;}
        if(root)break;
    }
    // VRidge 2.7.8 predates UIScene and may use the legacy app delegate window.
    if(!root)for(UIWindow *window in UIApplication.sharedApplication.windows){
        if(window.isKeyWindow){root=window.rootViewController;break;}
    }
    while(root.presentedViewController)root=root.presentedViewController;
    if(!root||![root isViewLoaded]||!root.view.window||[root isKindOfClass:UIAlertController.class]){
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{[self askToStart];});return;
    }
    _presenting=YES;
    UIAlertController *alert=[UIAlertController alertControllerWithTitle:@"Запустить твик?" message:@"Vision + Core ML: отслеживание рук для SteamVR" preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Нет" style:UIAlertActionStyleCancel handler:^(UIAlertAction *a){
        self.decided=YES;self.presenting=NO;NSLog(@"VH declined; VRidge continues without tracking");
    }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Да" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a){
        self.decided=YES;self.presenting=NO;
        dispatch_async(dispatch_get_main_queue(),^{[self enable];});
    }]];
    [root presentViewController:alert animated:YES completion:nil];
}
- (void)active:(NSNotification *)n {
    if(!_decided){[self askToStart];return;}
    if(!_enabled)return;
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
