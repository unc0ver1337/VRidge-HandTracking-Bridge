#import "Tracker.h"
#import "../Network/Wire.h"
#import <AVFoundation/AVFoundation.h>
#import "CoreMLTracker.h"
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>
#import <simd/simd.h>
#import <Vision/Vision.h>
#include <mutex>
#include <map>
#include <atomic>
#include <chrono>

@interface VHTracker () <AVCaptureVideoDataOutputSampleBufferDelegate>
@end
@implementation VHTracker {
    AVCaptureSession *_session; AVCaptureDevice *_camera;
    dispatch_queue_t _captureQueue; dispatch_queue_t _inferenceQueue; dispatch_queue_t _fingerQueue;
    VHCoreMLTracker *_request; CIContext *_context;
    VNDetectHumanHandPoseRequest *_vision;
    std::atomic_bool _fingerBusy; double _lastFinger;
    struct FingerSample {corehands::Hand hand;double capture;corehands::Point wrist;};
    std::mutex _fingerMutex;std::map<int,FingerSample> _fingers;
    NSDictionary *_settings; std::atomic_bool _busy; std::atomic_bool _wanted;
    uint32_t _sequence;
    CVPixelBufferPoolRef _pool; int _width,_height;
    NSHashTable<AVCaptureSession *> *_hostSessions;
    NSHashTable<AVCaptureSession *> *_ownedSessions;
}
- (instancetype)initWithSettings:(NSDictionary *)settings {
    if((self=[super init])){
        _settings=settings; _captureQueue=dispatch_queue_create("vh.capture",DISPATCH_QUEUE_SERIAL); _inferenceQueue=dispatch_queue_create("vh.mediapipe",DISPATCH_QUEUE_SERIAL);
        _fingerQueue=dispatch_queue_create("vh.fingers",DISPATCH_QUEUE_SERIAL);
        _vision=[VNDetectHumanHandPoseRequest new];_vision.maximumHandCount=2;
        _fingerBusy=false;_lastFinger=0;
        _busy=false; _wanted=false; _pool=nullptr; _width=640; _height=480;
        dispatch_async(_fingerQueue,^{
        NSError *modelError=nil;
        self->_request=[[VHCoreMLTracker alloc] initWithBundle:NSBundle.mainBundle skeletonOnly:YES error:&modelError];
        if(!self->_request)NSLog(@"Core ML model unavailable: %@",modelError);
        });
        _context=[CIContext contextWithOptions:@{kCIContextCacheIntermediates:@NO}];
        _hostSessions=[NSHashTable weakObjectsHashTable];
        _ownedSessions=[NSHashTable weakObjectsHashTable];
        NSNotificationCenter *nc=NSNotificationCenter.defaultCenter;
        [nc addObserver:self selector:@selector(interrupted:) name:AVCaptureSessionWasInterruptedNotification object:nil];
        [nc addObserver:self selector:@selector(interrupted:) name:AVCaptureSessionRuntimeErrorNotification object:nil];
        [nc addObserver:self selector:@selector(resume:) name:AVCaptureSessionInterruptionEndedNotification object:nil];
        [nc addObserver:self selector:@selector(hostStarted:) name:AVCaptureSessionDidStartRunningNotification object:nil];
        [nc addObserver:self selector:@selector(hostStopped:) name:AVCaptureSessionDidStopRunningNotification object:nil];
    } return self;
}
- (void)emit:(NSString *)text { dispatch_async(dispatch_get_main_queue(),^{if(self.status)self.status(text);}); }
- (void)start {
    _wanted=YES;
    AVAuthorizationStatus auth=[AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
    if(auth==AVAuthorizationStatusNotDetermined){
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted){ if(granted)dispatch_async(dispatch_get_main_queue(),^{if(self->_wanted)[self start];}); else [self emit:@"Camera permission denied"]; }]; return;
    }
    if(auth!=AVAuthorizationStatusAuthorized){[self emit:@"Camera permission denied"];return;}
    dispatch_async(_captureQueue,^{if(self->_wanted)[self configure];});
}
- (void)configure {
    if(_session)return;
    for(AVCaptureSession *host in _hostSessions){
        if(host.running){[self emit:@"VRidge is using camera; hand tracking waits"];return;}
    }
    _camera=[AVCaptureDevice defaultDeviceWithDeviceType:AVCaptureDeviceTypeBuiltInUltraWideCamera mediaType:AVMediaTypeVideo position:AVCaptureDevicePositionBack];
    if(!_camera){[self emit:@"Ultra-wide camera unavailable"];return;}
    NSError *error=nil; AVCaptureDeviceInput *input=[AVCaptureDeviceInput deviceInputWithDevice:_camera error:&error];
    if(!input){[self emit:error.localizedDescription];return;}
    AVCaptureSession *s=[AVCaptureSession new]; [s beginConfiguration]; s.sessionPreset=AVCaptureSessionPresetInputPriority;
    if(![s canAddInput:input]){[s commitConfiguration];[self emit:@"Camera busy; VRidge preserved"];return;}
    [s addInput:input];
    AVCaptureDeviceFormat *best=nil; double score=DBL_MAX; double bestFPS=30;
    double desired=30; // Stable 30 FPS capture and MediaPipe budget.
    for(AVCaptureDeviceFormat *format in _camera.formats){
        CMVideoDimensions d=CMVideoFormatDescriptionGetDimensions(format.formatDescription);
        double maxFPS=0;bool supports30=false;
        for(AVFrameRateRange *r in format.videoSupportedFrameRateRanges){
            maxFPS=MAX(maxFPS,r.maxFrameRate);if(r.minFrameRate<=30&&r.maxFrameRate>=30)supports30=true;
        }
        if(!supports30)continue;
        double v=fabs((double)d.width-_width)+fabs((double)d.height-_height)+(maxFPS<desired?2000:0);
        if(v<score){score=v; best=format;bestFPS=MIN(desired,maxFPS);}
    }
    if(!best||![_camera lockForConfiguration:&error]){[s commitConfiguration];[self emit:error.localizedDescription?:@"No compatible capture format"];return;}
    _camera.activeFormat=best; _camera.activeVideoMinFrameDuration=CMTimeMake(1,(int32_t)bestFPS); _camera.activeVideoMaxFrameDuration=CMTimeMake(1,(int32_t)bestFPS);
    [_camera unlockForConfiguration];
    AVCaptureVideoDataOutput *out=[AVCaptureVideoDataOutput new]; out.alwaysDiscardsLateVideoFrames=YES;
    out.videoSettings=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32BGRA)};
    [out setSampleBufferDelegate:self queue:_captureQueue];
    if(![s canAddOutput:out]){[s commitConfiguration];[self emit:@"Capture output unavailable"];return;}
    [s addOutput:out]; AVCaptureConnection *connection=[out connectionWithMediaType:AVMediaTypeVideo];
    // Keep native sensor orientation regardless of interface rotation. MediaPipe image orientation and
    // packet coordinates refer to that SAME image; UI autorotation cannot move hands.
    if(@available(iOS 17.0,*)){
        if([connection isVideoRotationAngleSupported:0])connection.videoRotationAngle=0;
    }else if(connection.isVideoOrientationSupported){connection.videoOrientation=AVCaptureVideoOrientationLandscapeRight;}
    if(connection.isVideoMirroringSupported){connection.automaticallyAdjustsVideoMirroring=NO;connection.videoMirrored=NO;}
    if(connection.isCameraIntrinsicMatrixDeliverySupported)connection.cameraIntrinsicMatrixDeliveryEnabled=YES;
    [s commitConfiguration]; _session=s;[_ownedSessions addObject:s];
    NSDictionary *attributes=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32BGRA),(id)kCVPixelBufferWidthKey:@(_width),(id)kCVPixelBufferHeightKey:@(_height),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
    CVPixelBufferPoolCreate(kCFAllocatorDefault,nullptr,(__bridge CFDictionaryRef)attributes,&_pool);
    [s startRunning]; if(s.running)[self emit:@"Hand tracking started"];
}
- (void)stop {
    _wanted=NO;
    dispatch_async(_captureQueue,^{
        [self teardown];
    });
}
- (void)teardown {
    // Only this tweak's own session. Existing host capture sessions are observed,
    // never stopped, swizzled, or reconfigured.
    [_session stopRunning]; _session=nil; _camera=nil;
    dispatch_sync(_inferenceQueue,^{});
    dispatch_sync(_fingerQueue,^{[self->_request reset];});
    {std::lock_guard<std::mutex> lock(_fingerMutex);_fingers.clear();}_lastFinger=0;
    if(_pool){CVPixelBufferPoolRelease(_pool);_pool=nullptr;}
}
- (void)hostStarted:(NSNotification *)n {
    AVCaptureSession *host=n.object;
    dispatch_async(_captureQueue,^{
        if([self->_ownedSessions containsObject:host])return;
        [self->_hostSessions addObject:host];
        if(self->_session){[self teardown];[self emit:@"VRidge camera takes priority; tracking paused"];}
    });
}
- (void)hostStopped:(NSNotification *)n {
    AVCaptureSession *host=n.object;
    dispatch_async(_captureQueue,^{
        if([self->_ownedSessions containsObject:host])return;
        [self->_hostSessions removeObject:host];
        if(self->_wanted&&!self->_session)[self configure];
    });
}
- (void)interrupted:(NSNotification *)n {
    dispatch_async(_captureQueue,^{
        if(n.object!=self->_session)return;
        [self emit:@"Camera interrupted; tracking suspended, VRidge preserved"];
        if([n.name isEqual:AVCaptureSessionRuntimeErrorNotification]){
            [self teardown];
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC),self->_captureQueue,^{if(self->_wanted)[self configure];});
        }
        // Ordinary interruptions retain the session until interruption-end.
    });
}
- (void)resume:(NSNotification *)n {
    dispatch_async(_captureQueue,^{if(n.object==self->_session&&self->_wanted)[self->_session startRunning];});
}
- (void)captureOutput:(AVCaptureOutput *)output didOutputSampleBuffer:(CMSampleBufferRef)sample fromConnection:(AVCaptureConnection *)connection {
    if(!_wanted||_busy.exchange(true))return;
    CVPixelBufferRef source=CMSampleBufferGetImageBuffer(sample); size_t sw=CVPixelBufferGetWidth(source),sh=CVPixelBufferGetHeight(source);
    CVPixelBufferRef scaled=nullptr;
    const bool nativeSize=(sw==(size_t)_width&&sh==(size_t)_height);
    if(nativeSize){scaled=source;CVPixelBufferRetain(scaled);}
    else if(!_pool||CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault,_pool,&scaled)!=kCVReturnSuccess){_busy=false;return;}
    // Centre-crop preserving aspect. Apply the identical affine transform to K.
    double scale=MAX((double)_width/sw,(double)_height/sh); double ox=(_width-sw*scale)/2,oy=(_height-sh*scale)/2;
    if(!nativeSize){
        CIImage *image=[CIImage imageWithCVPixelBuffer:source];
        image=[image imageByApplyingTransform:CGAffineTransformMake(scale,0,0,scale,ox,oy)];
        [_context render:image toCVPixelBuffer:scaled bounds:CGRectMake(0,0,_width,_height) colorSpace:nil];
    }
    VHHeader header={}; memcpy(header.magic,"MPBR",4);header.version=3;header.flags=2;header.sequence=_sequence++; header.width=_width;header.height=_height;
    // Convert sample time from capture session clock into host clock used by sync.
    CMTime pts=CMSampleBufferGetPresentationTimeStamp(sample);
    CMClockRef clock=_session.synchronizationClock;
    header.capture=CMTimeGetSeconds(clock?CMSyncConvertTime(pts,clock,CMClockGetHostTimeClock()):pts);
    CFTypeRef attachment=CMGetAttachment(sample,kCMSampleBufferAttachmentKey_CameraIntrinsicMatrix,nullptr);
    if(attachment&&CFGetTypeID(attachment)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)attachment)>=(CFIndex)sizeof(matrix_float3x3)){
        matrix_float3x3 k;memcpy(&k,CFDataGetBytePtr((CFDataRef)attachment),sizeof(k));
        header.fx=k.columns[0][0]*scale;header.fy=k.columns[1][1]*scale;
        header.cx=k.columns[2][0]*scale+ox; header.cy=k.columns[2][1]*scale+oy;
    }else{
        header.flags|=1;float f=(float)(sw/(2*tan(_camera.activeFormat.videoFieldOfView*M_PI/360)));
        header.fx=header.fy=f*scale;header.cx=_width*.5;header.cy=_height*.5;
    }
    dispatch_async(_inferenceQueue,^{ @autoreleasepool {
        if(!self->_wanted){CVPixelBufferRelease(scaled);self->_busy=false;return;}
        const auto begin=std::chrono::steady_clock::now();NSError *error=nil;
        VNImageRequestHandler *handler=[[VNImageRequestHandler alloc]initWithCVPixelBuffer:scaled orientation:kCGImagePropertyOrientationUp options:@{}];
        BOOL ok=[handler performRequests:@[self->_vision] error:&error];
        std::vector<corehands::Hand> regions;std::vector<VHHand> records;
        NSArray<VNHumanHandPoseObservation *> *observations=self->_vision.results;
        static NSArray<VNHumanHandPoseObservationJointName> *names;
        static dispatch_once_t once;dispatch_once(&once,^{names=@[
            VNHumanHandPoseObservationJointNameWrist,
            VNHumanHandPoseObservationJointNameThumbCMC,VNHumanHandPoseObservationJointNameThumbMP,VNHumanHandPoseObservationJointNameThumbIP,VNHumanHandPoseObservationJointNameThumbTip,
            VNHumanHandPoseObservationJointNameIndexMCP,VNHumanHandPoseObservationJointNameIndexPIP,VNHumanHandPoseObservationJointNameIndexDIP,VNHumanHandPoseObservationJointNameIndexTip,
            VNHumanHandPoseObservationJointNameMiddleMCP,VNHumanHandPoseObservationJointNameMiddlePIP,VNHumanHandPoseObservationJointNameMiddleDIP,VNHumanHandPoseObservationJointNameMiddleTip,
            VNHumanHandPoseObservationJointNameRingMCP,VNHumanHandPoseObservationJointNameRingPIP,VNHumanHandPoseObservationJointNameRingDIP,VNHumanHandPoseObservationJointNameRingTip,
            VNHumanHandPoseObservationJointNameLittleMCP,VNHumanHandPoseObservationJointNameLittlePIP,VNHumanHandPoseObservationJointNameLittleDIP,VNHumanHandPoseObservationJointNameLittleTip];});
        if(ok)for(VNHumanHandPoseObservation *observation in observations){
            VHHand hand={};corehands::Hand region;
            hand.side=observation.chirality==VNChiralityLeft?1:(observation.chirality==VNChiralityRight?2:0);
            if(!hand.side)continue;hand.identity=hand.side;hand.rotation[3]=1;region.side=hand.side;
            auto points=[observation recognizedPointsForGroupKey:VNHumanHandPoseObservationJointsGroupNameAll error:&error];
            bool palmValid=true;
            for(int j=0;j<21;j++){
                VNRecognizedPoint *point=points[names[j]];
                float x=point?point.location.x:0,y=point?1-point.location.y:0,c=point?point.confidence:0;
                hand.landmarks[j][0]=std::clamp(x,0.f,1.f);hand.landmarks[j][1]=std::clamp(y,0.f,1.f);hand.landmarks[j][2]=std::clamp(c,0.f,1.f);
                region.landmarks[j]={x,y,0};
                if((j==0||j==5||j==9||j==13||j==17)&&c<.35f)palmValid=false;
            }
            if(!palmValid)continue;
            // The cache is stamped with the inference SOURCE frame. A result is
            // never labelled as current just because it completed this frame.
            {std::lock_guard<std::mutex> lock(self->_fingerMutex);
                auto found=self->_fingers.find(hand.side);
                if(found!=self->_fingers.end()){
                    const auto&f=found->second;
                    double age=header.capture-f.capture;
                    double dx=f.wrist.x-region.landmarks[0].x,dy=f.wrist.y-region.landmarks[0].y;
                    if(age>=0&&age<=.25&&dx*dx+dy*dy<.0225){
                        hand.fingerCapture=f.capture;
                        for(int j=0;j<21;j++){const auto&w=f.hand.world[j];hand.world[j][0]=w.x;hand.world[j][1]=w.y;hand.world[j][2]=w.z;}
                    }
                }
            }
            records.push_back(hand);regions.push_back(region);
            if(records.size()==2)break;
        }
        // Pose packets leave before finger inference is scheduled. No second
        // full-image neural palm detector, no unbounded capture/inference queue.
        VHHeader h=header;h.count=(uint8_t)records.size();
        NSMutableData *data=[NSMutableData dataWithBytes:&h length:sizeof(h)];
        for(const auto&hand:records)[data appendBytes:&hand length:sizeof(hand)];
        if(self.frame&&self->_wanted)self.frame(data);
        if(ok&&!regions.empty()&&header.capture-self->_lastFinger>=1./15.&&!self->_fingerBusy.exchange(true)){
            self->_lastFinger=header.capture;CVPixelBufferRetain(scaled);
            dispatch_async(self->_fingerQueue,^{@autoreleasepool {
                NSError *fingerError=nil;
                if(self->_wanted&&self->_request){
                    auto results=[self->_request fingers:scaled regions:regions error:&fingerError];
                    if(!fingerError){std::lock_guard<std::mutex> lock(self->_fingerMutex);
                        for(const auto&hand:results)for(const auto&region:regions)if(hand.side==region.side){
                            self->_fingers[hand.side]={hand,header.capture,region.landmarks[0]};break;
                        }
                    }else NSLog(@"Finger inference: %@",fingerError);
                }
                CVPixelBufferRelease(scaled);self->_fingerBusy=false;
            }});
        }
        if(!ok)NSLog(@"Vision: %@",error);
        static double total=0;static unsigned count=0;
        total+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
        if(++count==120){NSLog(@"Vision pose mean %.2f ms; capture 30 FPS, fingers <=15 FPS independent",total/count);count=0;total=0;}
        CVPixelBufferRelease(scaled);self->_busy=false;
    }});
}

- (void)dealloc { [NSNotificationCenter.defaultCenter removeObserver:self]; if(_pool)CVPixelBufferPoolRelease(_pool); }
@end
