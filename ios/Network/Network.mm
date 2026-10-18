#import "Network.h"
#import "Wire.h"
#import <UIKit/UIKit.h>
#import <CoreMedia/CoreMedia.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <unistd.h>
#include <atomic>

static double ClockNow(){ return CMTimeGetSeconds(CMClockGetTime(CMClockGetHostTimeClock())); }
@implementation VHNetwork {
    NSNetServiceBrowser *_browser; NSMutableArray<NSNetService *> *_services;
    dispatch_queue_t _queue; dispatch_source_t _timer;
    int _fd; NSData *_address; uint64_t _session; NSString *_nonce;
    double _lastReply,_searchStart,_deadline,_retryAfter; BOOL _connected,_running;
    NSDictionary *_settings;
    std::atomic_bool _sendBusy;
}
- (instancetype)initWithSettings:(NSDictionary *)settings {
    if ((self=[super init])) { _fd=-1; _sendBusy=false; _queue=dispatch_queue_create("vh.network",DISPATCH_QUEUE_SERIAL); _settings=settings; _services=[NSMutableArray array]; }
    return self;
}
- (void)emit:(NSString *)s { dispatch_async(dispatch_get_main_queue(),^{ if(self.status)self.status(s); }); }
- (void)setConnected:(BOOL)value {
    if(_connected==value)return; _connected=value;
    dispatch_async(dispatch_get_main_queue(),^{ if(self.connectionChanged)self.connectionChanged(value); });
}
- (void)start {
    if(_running)return; _running=YES;
    _browser=[NSNetServiceBrowser new]; _browser.delegate=self;
    [_browser searchForServicesOfType:@"_mpbridge._udp." inDomain:@"local."];
    dispatch_async(_queue,^{
        self->_fd=socket(AF_INET,SOCK_DGRAM,0);
        if(self->_fd<0){[self emit:@"Network socket unavailable"];return;}
        fcntl(self->_fd,F_SETFL,O_NONBLOCK);
        self->_nonce=NSUUID.UUID.UUIDString;
        self->_searchStart=ClockNow(); self->_deadline=[self->_settings[@"DiscoveryTimeoutSeconds"] doubleValue]?:15;
        self->_deadline=MAX(1,MIN(120,self->_deadline));
        self->_timer=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,self->_queue);
        dispatch_source_set_timer(self->_timer,DISPATCH_TIME_NOW,100*NSEC_PER_MSEC,10*NSEC_PER_MSEC);
        __weak VHNetwork *weak=self;
        dispatch_source_set_event_handler(self->_timer,^{[weak tick];}); dispatch_resume(self->_timer);
        [self emit:@"Searching for PC"];
    });
}
- (void)stop {
    if(!_running)return; _running=NO; [_browser stop]; _browser=nil;
    for(NSNetService *s in _services){s.delegate=nil;[s stop];} [_services removeAllObjects];
    dispatch_async(_queue,^{
        if(self->_timer){dispatch_source_cancel(self->_timer);self->_timer=nil;}
        if(self->_fd>=0){close(self->_fd);self->_fd=-1;}
        self->_address=nil; self->_session=0; [self setConnected:NO];
    });
}
- (void)netServiceBrowser:(NSNetServiceBrowser *)browser didFindService:(NSNetService *)service moreComing:(BOOL)more {
    service.delegate=self; [_services addObject:service]; [service resolveWithTimeout:5];
}
- (void)netServiceBrowser:(NSNetServiceBrowser *)browser didRemoveService:(NSNetService *)service moreComing:(BOOL)more {
    [service stop]; [_services removeObject:service];
}
- (void)netServiceDidResolveAddress:(NSNetService *)service {
    NSDictionary *txt=[NSNetService dictionaryFromTXTRecordData:service.TXTRecordData?:[NSData data]];
    NSString *proto=[[NSString alloc]initWithData:txt[@"protocol"] encoding:NSUTF8StringEncoding];
    NSString *version=[[NSString alloc]initWithData:txt[@"version"] encoding:NSUTF8StringEncoding];
    if(![proto isEqual:@"MPBR"]||![version isEqual:@"3"])return;
    for(NSData *address in service.addresses){
        if(address.length>=sizeof(sockaddr_in)&&((const sockaddr *)address.bytes)->sa_family==AF_INET){
            dispatch_async(_queue,^{
                if(!self->_connected&&!self->_address){self->_address=address; self->_searchStart=ClockNow(); [self emit:@"PC found"];}
            }); break;
        }
    }
}
- (void)json:(NSDictionary *)object {
    if(!_address||_fd<0)return;
    NSMutableDictionary *o=[object mutableCopy]; o[@"protocol"]=@"MPBR"; o[@"v"]=@3;
    NSData *data=[NSJSONSerialization dataWithJSONObject:o options:0 error:nil];
    sendto(_fd,data.bytes,data.length,0,(const sockaddr *)_address.bytes,(socklen_t)_address.length);
}
- (void)tick {
    if(_fd<0)return;
    double now=ClockNow();
    uint8_t buf[2048]; sockaddr_in from={}; socklen_t len=sizeof(from); ssize_t size;
    while((size=recvfrom(_fd,buf,sizeof(buf),0,(sockaddr *)&from,&len))>0){
        if(!_address)continue;
        const sockaddr_in *expected=(const sockaddr_in *)_address.bytes;
        if(from.sin_addr.s_addr!=expected->sin_addr.s_addr||from.sin_port!=expected->sin_port)continue;
        id o=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:buf length:(NSUInteger)size] options:0 error:nil];
        if(![o isKindOfClass:NSDictionary.class]||![o[@"protocol"] isEqual:@"MPBR"]||[o[@"v"] intValue]!=3)continue;
        if([o[@"type"] isEqual:@"welcome"]&&[o[@"nonce"] isEqual:_nonce]&&[o[@"session"] isKindOfClass:NSNumber.class]){
            _session=[o[@"session"] unsignedLongLongValue]; _lastReply=now;
            if(!_connected){[self emit:@"Connected to PC"]; [self setConnected:YES];}
        }else if([o[@"type"] isEqual:@"pong"]&&[o[@"session"] unsignedLongLongValue]==_session){
            _lastReply=now;
            if(o[@"t0"]&&o[@"s1"]&&o[@"s2"])[self json:@{@"type":@"sync",@"session":@(_session),@"t0":o[@"t0"],@"t3":@(ClockNow()),@"s1":o[@"s1"],@"s2":o[@"s2"]}];
        }
        len=sizeof(from);
    }
    if(_connected&&now-_lastReply>3){
        [self setConnected:NO]; [self emit:@"Connection lost"]; _session=0; _address=nil; _nonce=NSUUID.UUID.UUIDString; _searchStart=now;
        dispatch_async(dispatch_get_main_queue(),^{for(NSNetService *s in self->_services)[s resolveWithTimeout:5];});
    }
    if(!_connected&&now-_searchStart>_deadline){
        [self setConnected:NO]; _address=nil; _session=0;
        // No process termination. Pause discovery five seconds, then start a new bounded window.
        if(_retryAfter==0){_retryAfter=now+5;[self emit:@"PC search timed out; tracking stopped"];}
        if(now>=_retryAfter){_retryAfter=0;_searchStart=now;
            dispatch_async(dispatch_get_main_queue(),^{ for(NSNetService *s in self->_services)[s resolveWithTimeout:5]; });
        }
        return;
    }
    // 500ms control cadence, receive polling stays 100ms.
    static unsigned tick=0;
    if((tick++%5)==0){
        if(_connected)[self json:@{@"type":@"ping",@"session":@(_session),@"t0":@(ClockNow())}];
        else [self json:@{@"type":@"hello",@"nonce":_nonce,@"device":UIDevice.currentDevice.name}];
    }
}
- (void)sendFrame:(NSData *)data {
    if(_sendBusy.exchange(true))return; // retain at most one outgoing frame
    dispatch_async(_queue,^{
        if(self->_connected&&data.length>=sizeof(VHHeader)){
            NSMutableData *packet=[data mutableCopy]; VHHeader *header=(VHHeader *)packet.mutableBytes; header->session=self->_session;
            sendto(self->_fd,packet.bytes,packet.length,0,(const sockaddr *)self->_address.bytes,(socklen_t)self->_address.length);
        }
        self->_sendBusy=false;
    });
}
@end
