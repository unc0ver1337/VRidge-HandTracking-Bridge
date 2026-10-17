#import "Tracker.h"
#import "../Network/Wire.h"
#import <AVFoundation/AVFoundation.h>
#import <MediaPipeTasksVision/MediaPipeTasksVision.h>
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>
#import <simd/simd.h>
#include "TranslationFit.h"
#include <atomic>

@interface VHTracker () <AVCaptureVideoDataOutputSampleBufferDelegate>
@end
@implementation VHTracker {
    AVCaptureSession *_session; AVCaptureDevice *_camera;
    dispatch_queue_t _captureQueue; dispatch_queue_t _inferenceQueue;
    MPPHandLandmarker *_request; NSInteger _lastTimestamp; CIContext *_context;
    NSDictionary *_settings; std::atomic_bool _busy; std::atomic_bool _wanted;
    uint32_t _sequence;
    CVPixelBufferPoolRef _pool; int _width,_height;
    NSHashTable<AVCaptureSession *> *_hostSessions;
    NSHashTable<AVCaptureSession *> *_ownedSessions;
}
- (instancetype)initWithSettings:(NSDictionary *)settings {
    if((self=[super init])){
        _settings=settings; _captureQueue=dispatch_queue_create("vh.capture",DISPATCH_QUEUE_SERIAL); _inferenceQueue=dispatch_queue_create("vh.mediapipe",DISPATCH_QUEUE_SERIAL);
        _busy=false; _wanted=false; _pool=nullptr; _width=640; _height=480;
        dispatch_async(_inferenceQueue,^{
        NSError *modelError=nil;
        MPPHandLandmarkerOptions *options=[MPPHandLandmarkerOptions new];
        options.baseOptions.modelAssetPath=[[NSBundle mainBundle] pathForResource:@"hand_landmarker" ofType:@"task"];
        options.runningMode=MPPRunningModeVideo;options.numHands=2;
        options.minHandDetectionConfidence=.5;options.minHandPresenceConfidence=.5;options.minTrackingConfidence=.5;
        self->_request=[[MPPHandLandmarker alloc] initWithOptions:options error:&modelError];
        if(!self->_request)NSLog(@"MediaPipe model unavailable: %@",modelError);
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
    if(_busy.exchange(true))return;
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
    VHHeader header={}; memcpy(header.magic,"MPBR",4);header.version=2;header.sequence=_sequence++; header.width=_width;header.height=_height;
    // Convert sample time from capture session clock into host clock used by sync.
    CMTime pts=CMSampleBufferGetPresentationTimeStamp(sample);
    CMClockRef clock=_session.masterClock;
    header.capture=CMTimeGetSeconds(clock?CMSyncConvertTime(pts,clock,CMClockGetHostTimeClock()):pts);
    CFTypeRef attachment=CMGetAttachment(sample,kCMSampleBufferAttachmentKey_CameraIntrinsicMatrix,nullptr);
    if(attachment&&CFGetTypeID(attachment)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)attachment)>=(CFIndex)sizeof(matrix_float3x3)){
        matrix_float3x3 k;memcpy(&k,CFDataGetBytePtr((CFDataRef)attachment),sizeof(k));
        header.fx=k.columns[0][0]*scale;header.fy=k.columns[1][1]*scale;
        header.cx=k.columns[2][0]*scale+ox; header.cy=k.columns[2][1]*scale+oy;
    }else{
        header.flags=1;float f=(float)(sw/(2*tan(_camera.activeFormat.videoFieldOfView*M_PI/360)));
        header.fx=header.fy=f*scale;header.cx=_width*.5;header.cy=_height*.5;
    }
    dispatch_async(_inferenceQueue,^{ @autoreleasepool {
        NSError *error=nil;
        MPPImage *image=[[MPPImage alloc] initWithPixelBuffer:scaled error:&error];
        CVPixelBufferRelease(scaled);
        NSInteger stamp=MAX(self->_lastTimestamp+1,(NSInteger)(header.capture*1000));self->_lastTimestamp=stamp;
        MPPHandLandmarkerResult *result=image?[self->_request detectVideoFrame:image timestampInMilliseconds:stamp error:&error]:nil;
        if(result){
            VHHeader h=header;NSMutableData *body=[NSMutableData data];
            for(NSUInteger i=0;i<MIN((NSUInteger)2,result.landmarks.count);i++){
                if(i>=result.worldLandmarks.count||result.landmarks[i].count!=21||result.worldLandmarks[i].count!=21)continue;
                VHHand hand={};
                MPPCategory *category=(i<result.handedness.count)?result.handedness[i].firstObject:nil;
                hand.side=[category.categoryName isEqualToString:@"Left"]?1:[category.categoryName isEqualToString:@"Right"]?2:0;
                hand.identity=(uint32_t)(i+1);
                bool finite=true;
                for(NSUInteger j=0;j<21;j++){
                    MPPNormalizedLandmark *p=result.landmarks[i][j];MPPLandmark *w=result.worldLandmarks[i][j];
                    finite=finite&&isfinite(p.x)&&isfinite(p.y)&&isfinite(w.x)&&isfinite(w.y)&&isfinite(w.z);
                    hand.landmarks[j][0]=fmax(0,fmin(1,p.x));hand.landmarks[j][1]=fmax(0,fmin(1,p.y));
                    hand.landmarks[j][2]=1; // Availability, NOT a measured per-joint confidence.
                    hand.world[j][0]=w.x;hand.world[j][1]=w.y;hand.world[j][2]=w.z;
                }
                if(!finite)continue;
                // MediaPipe world points already carry camera-relative orientation.
                // Solve translation from 2D rays and metric model points on the phone.
                mpbridge::Fit fit;
                hand.rotation[3]=1;
                bool translationValid=mpbridge::translationFit(hand.world,hand.landmarks,h.width,h.height,h.fx,h.fy,h.cx,h.cy,fit);
                hand.reprojection=fit.error;
                if(translationValid){
                    vector_float3 translation={fit.translation[0],fit.translation[1],fit.translation[2]};
                    vector_float3 wrist={hand.world[0][0],hand.world[0][1],hand.world[0][2]};
                    vector_float3 index={hand.world[5][0],hand.world[5][1],hand.world[5][2]};
                    vector_float3 little={hand.world[17][0],hand.world[17][1],hand.world[17][2]};
                    vector_float3 middle={hand.world[9][0],hand.world[9][1],hand.world[9][2]};
                    vector_float3 x=(index-little)*(hand.side==1?-1.f:1.f);vector_float3 y=middle-wrist;
                    bool valid=simd_length(x)>.005&&simd_length(y)>.005;
                    if(valid){x=simd_normalize(x);y-=x*simd_dot(x,y);valid=simd_length(y)>.005;}
                    vector_float3 position=wrist+translation;
                    if(valid){
                        y=simd_normalize(y);vector_float3 z=simd_cross(x,y);matrix_float3x3 basis={x,y,z};
                        simd_quatf q=simd_quaternion(basis);
                        for(int c=0;c<3;c++)hand.position[c]=position[c];
                        for(int c=0;c<4;c++)hand.rotation[c]=q.vector[c];hand.poseValid=1;
                    }
                }
                [body appendBytes:&hand length:sizeof(hand)];h.count++;
            }
            NSMutableData *data=[NSMutableData dataWithBytes:&h length:sizeof(h)];[data appendData:body];if(self.frame)self.frame(data);
        }else NSLog(@"MediaPipe frame error: %@",error);
        self->_busy=false;
    }});
}
- (void)dealloc { [NSNotificationCenter.defaultCenter removeObserver:self]; if(_pool)CVPixelBufferPoolRelease(_pool); }
@end
