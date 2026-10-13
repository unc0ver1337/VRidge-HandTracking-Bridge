#import "Tracker.h"
#import "../Network/Wire.h"
#import <AVFoundation/AVFoundation.h>
#import <Vision/Vision.h>
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>
#import <simd/simd.h>
#include <atomic>

@interface VHTracker () <AVCaptureVideoDataOutputSampleBufferDelegate>
@end
@implementation VHTracker {
    AVCaptureSession *_session; AVCaptureDevice *_camera;
    dispatch_queue_t _captureQueue; dispatch_queue_t _visionQueue;
    VNDetectHumanHandPoseRequest *_request; CIContext *_context;
    NSDictionary *_settings; std::atomic_bool _busy; std::atomic_bool _wanted;
    uint32_t _sequence; double _meanMS; unsigned _samples;
    CVPixelBufferPoolRef _pool; int _width,_height;
    float _previous[2][2]; BOOL _hasPrevious[2];
}
- (instancetype)initWithSettings:(NSDictionary *)settings {
    if((self=[super init])){
        _settings=settings; _captureQueue=dispatch_queue_create("vh.capture",DISPATCH_QUEUE_SERIAL); _visionQueue=dispatch_queue_create("vh.vision",DISPATCH_QUEUE_SERIAL);
        _busy=false; _wanted=false; _pool=nullptr; _width=[settings[@"Width"] intValue]?:640; _height=[settings[@"Height"] intValue]?:480;
        _width=MAX(64,MIN(1280,_width));_height=MAX(64,MIN(960,_height));
        _request=[VNDetectHumanHandPoseRequest new]; _request.maximumHandCount=2;
        _context=[CIContext contextWithOptions:@{kCIContextCacheIntermediates:@NO}];
        NSNotificationCenter *nc=NSNotificationCenter.defaultCenter;
        [nc addObserver:self selector:@selector(interrupted:) name:AVCaptureSessionWasInterruptedNotification object:nil];
        [nc addObserver:self selector:@selector(interrupted:) name:AVCaptureSessionRuntimeErrorNotification object:nil];
        [nc addObserver:self selector:@selector(resume:) name:AVCaptureSessionInterruptionEndedNotification object:nil];
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
    _camera=[AVCaptureDevice defaultDeviceWithDeviceType:AVCaptureDeviceTypeBuiltInUltraWideCamera mediaType:AVMediaTypeVideo position:AVCaptureDevicePositionBack];
    if(!_camera){[self emit:@"Ultra-wide camera unavailable"];return;}
    NSError *error=nil; AVCaptureDeviceInput *input=[AVCaptureDeviceInput deviceInputWithDevice:_camera error:&error];
    if(!input){[self emit:error.localizedDescription];return;}
    AVCaptureSession *s=[AVCaptureSession new]; [s beginConfiguration]; s.sessionPreset=AVCaptureSessionPresetInputPriority;
    if(![s canAddInput:input]){[s commitConfiguration];[self emit:@"Camera busy; VRidge preserved"];return;}
    [s addInput:input];
    AVCaptureDeviceFormat *best=nil; double score=DBL_MAX; double bestFPS=30;
    double desired=[_settings[@"FPS"] intValue]==30?30:60;
    for(AVCaptureDeviceFormat *format in _camera.formats){
        CMVideoDimensions d=CMVideoFormatDescriptionGetDimensions(format.formatDescription);
        double maxFPS=0; for(AVFrameRateRange *r in format.videoSupportedFrameRateRanges)maxFPS=MAX(maxFPS,r.maxFrameRate);
        if(maxFPS<30)continue;
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
    // Keep native sensor orientation regardless of interface rotation. Vision Up and
    // packet coordinates refer to that SAME image; UI autorotation cannot move hands.
    if(connection.isVideoMirroringSupported){connection.automaticallyAdjustsVideoMirroring=NO;connection.videoMirrored=NO;}
    if(connection.isCameraIntrinsicMatrixDeliverySupported)connection.cameraIntrinsicMatrixDeliveryEnabled=YES;
    [s commitConfiguration]; _session=s;
    NSDictionary *attributes=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32BGRA),(id)kCVPixelBufferWidthKey:@(_width),(id)kCVPixelBufferHeightKey:@(_height),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
    CVPixelBufferPoolCreate(kCFAllocatorDefault,nullptr,(__bridge CFDictionaryRef)attributes,&_pool);
    [s startRunning]; if(s.running)[self emit:@"Hand tracking started"];
}
- (void)stop {
    _wanted=NO;
    dispatch_async(_captureQueue,^{
        [self->_session stopRunning]; self->_session=nil; self->_camera=nil;
        // Drain the single retained inference before destroying the pixel pool.
        dispatch_sync(self->_visionQueue,^{});
        if(self->_pool){CVPixelBufferPoolRelease(self->_pool);self->_pool=nullptr;}
        self->_samples=0;self->_meanMS=0; self->_hasPrevious[0]=self->_hasPrevious[1]=NO;
    });
}
- (void)interrupted:(NSNotification *)n {
    if(n.object!=_session)return;
    [self emit:@"Camera interrupted; tracking suspended, VRidge preserved"];
    // Never stop/reconfigure any host session. Keep this session for interruption-end.
}
- (void)resume:(NSNotification *)n {
    if(n.object!=_session||!_wanted)return;
    dispatch_async(_captureQueue,^{[self->_session startRunning];});
}
- (void)captureOutput:(AVCaptureOutput *)output didOutputSampleBuffer:(CMSampleBufferRef)sample fromConnection:(AVCaptureConnection *)connection {
    if(_busy.exchange(true))return;
    CVPixelBufferRef source=CMSampleBufferGetImageBuffer(sample); size_t sw=CVPixelBufferGetWidth(source),sh=CVPixelBufferGetHeight(source);
    CVPixelBufferRef scaled=nullptr;
    if(!_pool||CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault,_pool,&scaled)!=kCVReturnSuccess){_busy=false;return;}
    // Centre-crop preserving aspect. Apply the identical affine transform to K.
    double scale=MAX((double)_width/sw,(double)_height/sh); double ox=(_width-sw*scale)/2,oy=(_height-sh*scale)/2;
    CIImage *image=[CIImage imageWithCVPixelBuffer:source];
    image=[image imageByApplyingTransform:CGAffineTransformMake(scale,0,0,scale,ox,oy)];
    [_context render:image toCVPixelBuffer:scaled bounds:CGRectMake(0,0,_width,_height) colorSpace:nil];
    VHHeader header={}; memcpy(header.magic,"VHBR",4);header.version=1;header.sequence=_sequence++; header.width=_width;header.height=_height;
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
    dispatch_async(_visionQueue,^{ @autoreleasepool {
        double begin=CFAbsoluteTimeGetCurrent(); NSError *error=nil;
        VNImageRequestHandler *handler=[[VNImageRequestHandler alloc]initWithCVPixelBuffer:scaled orientation:kCGImagePropertyOrientationUp options:@{}];
        BOOL ok=[handler performRequests:@[self->_request] error:&error]; CVPixelBufferRelease(scaled);
        if(ok){
            VHHeader h=header; NSMutableData *body=[NSMutableData data]; unsigned observationIndex=0;
            NSArray *names=@[VNHumanHandPoseObservationJointNameWrist,
                VNHumanHandPoseObservationJointNameThumbCMC,VNHumanHandPoseObservationJointNameThumbMP,VNHumanHandPoseObservationJointNameThumbIP,VNHumanHandPoseObservationJointNameThumbTip,
                VNHumanHandPoseObservationJointNameIndexMCP,VNHumanHandPoseObservationJointNameIndexPIP,VNHumanHandPoseObservationJointNameIndexDIP,VNHumanHandPoseObservationJointNameIndexTip,
                VNHumanHandPoseObservationJointNameMiddleMCP,VNHumanHandPoseObservationJointNameMiddlePIP,VNHumanHandPoseObservationJointNameMiddleDIP,VNHumanHandPoseObservationJointNameMiddleTip,
                VNHumanHandPoseObservationJointNameRingMCP,VNHumanHandPoseObservationJointNameRingPIP,VNHumanHandPoseObservationJointNameRingDIP,VNHumanHandPoseObservationJointNameRingTip,
                VNHumanHandPoseObservationJointNameLittleMCP,VNHumanHandPoseObservationJointNameLittlePIP,VNHumanHandPoseObservationJointNameLittleDIP,VNHumanHandPoseObservationJointNameLittleTip];
            for(VNHumanHandPoseObservation *obs in self->_request.results){
                if(h.count>=2)break; VHHand hand={};
                if(@available(iOS 15.0,*)){hand.side=obs.chirality==VNChiralityLeft?1:obs.chirality==VNChiralityRight?2:0;}
                NSDictionary *points=[obs recognizedPointsForGroupKey:VNHumanHandPoseObservationJointsGroupNameAll error:nil];
                for(unsigned j=0;j<21;j++){
                    VNRecognizedPoint *p=points[names[j]];
                    if(p){hand.landmarks[j][0]=fmax(0,fmin(1,p.location.x));hand.landmarks[j][1]=fmax(0,fmin(1,1-p.location.y));hand.landmarks[j][2]=p.confidence;}
                }
                // Chirality is semantic evidence. Persistent spatial identity is resolved
                // by the PC with velocity association; no left/right guess from screen X.
                hand.identity=hand.side?:10+observationIndex; observationIndex++;
                // Chirality + palm triangle winding gives a WEAK front/back cue.
                // Suppress edge-on/low-confidence cases. PC never treats it as exact.
                float ax=hand.landmarks[5][0]-hand.landmarks[0][0],ay=hand.landmarks[5][1]-hand.landmarks[0][1];
                float bx=hand.landmarks[17][0]-hand.landmarks[0][0],by=hand.landmarks[17][1]-hand.landmarks[0][1];
                float area=ax*by-ay*bx,den=hypotf(ax,ay)*hypotf(bx,by);
                if(hand.side&&den>1e-6&&fabsf(area)/den>.2&&MIN(hand.landmarks[5][2],MIN(hand.landmarks[17][2],hand.landmarks[0][2]))>.5){
                    float winding=area*(hand.side==1?-1:1);hand.palm=winding>0?1:-1;
                }
                [body appendBytes:&hand length:sizeof(hand)];h.count++;
            }
            NSMutableData *data=[NSMutableData dataWithBytes:&h length:sizeof(h)];[data appendData:body]; if(self.frame)self.frame(data);
        }else NSLog(@"VH Vision error: %@",error);
        double ms=(CFAbsoluteTimeGetCurrent()-begin)*1000; self->_meanMS=self->_samples?self->_meanMS*.9+ms*.1:ms;
        self->_samples++;
        if(self->_samples==120&&self->_meanMS>25){
            dispatch_async(self->_captureQueue,^{
                NSError *e=nil;if([self->_camera lockForConfiguration:&e]){
                    self->_camera.activeVideoMinFrameDuration=CMTimeMake(1,30);self->_camera.activeVideoMaxFrameDuration=CMTimeMake(1,30);[self->_camera unlockForConfiguration];
                }
            });
        }
        self->_busy=false;
    }});
}
- (void)dealloc { [NSNotificationCenter.defaultCenter removeObserver:self]; if(_pool)CVPixelBufferPoolRelease(_pool); }
@end
