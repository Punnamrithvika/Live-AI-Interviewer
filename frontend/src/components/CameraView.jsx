import React, { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, Mic, MicOff } from 'lucide-react';

const CameraView = ({ onPermissionGranted, onPermissionDenied }) => {
  const videoRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    requestMediaPermissions();
    
    return () => {
      // Cleanup: stop all tracks when component unmounts
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestMediaPermissions = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        },
        audio: true
      });
      
      setStream(mediaStream);
      
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      
      if (onPermissionGranted) {
        onPermissionGranted(mediaStream);
      }
    } catch (err) {
      console.error('Error accessing media devices:', err);
      setError(err.message);
      
      if (onPermissionDenied) {
        onPermissionDenied(err);
      }
    }
  };

  const toggleAudio = () => {
    if (stream) {
      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsAudioEnabled(audioTrack.enabled);
      }
    }
  };

  const toggleVideo = () => {
    if (stream) {
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        setIsVideoEnabled(videoTrack.enabled);
      }
    }
  };

  if (error) {
    return (
      <div className="relative w-full h-full bg-slate-800 rounded-lg overflow-hidden flex items-center justify-center">
        <div className="text-center text-slate-300 p-4">
          <CameraOff className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Camera access denied</p>
          <button 
            onClick={requestMediaPermissions}
            className="mt-2 text-xs text-amber-600 hover:text-amber-700 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-slate-900 rounded-lg overflow-hidden shadow-lg border border-slate-700">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-cover"
      />
      
      {/* Status badge */}
      <div className="absolute top-3 left-3 px-3 py-1 bg-emerald-600 text-white text-xs font-medium rounded-full flex items-center gap-1.5">
        <span className="w-2 h-2 bg-white rounded-full animate-pulse"></span>
        Interview in progress
      </div>
      
      {/* Controls */}
      <div className="absolute bottom-3 right-3 flex gap-2">
        <button
          onClick={toggleAudio}
          className={`p-2 rounded-full transition-colors ${
            isAudioEnabled 
              ? 'bg-slate-700/80 hover:bg-slate-600 text-white' 
              : 'bg-red-600 hover:bg-red-700 text-white'
          }`}
          title={isAudioEnabled ? 'Mute' : 'Unmute'}
        >
          {isAudioEnabled ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
        </button>
        
        <button
          onClick={toggleVideo}
          className={`p-2 rounded-full transition-colors ${
            isVideoEnabled 
              ? 'bg-slate-700/80 hover:bg-slate-600 text-white' 
              : 'bg-red-600 hover:bg-red-700 text-white'
          }`}
          title={isVideoEnabled ? 'Turn off camera' : 'Turn on camera'}
        >
          {isVideoEnabled ? <Camera className="w-4 h-4" /> : <CameraOff className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};

export default CameraView;
