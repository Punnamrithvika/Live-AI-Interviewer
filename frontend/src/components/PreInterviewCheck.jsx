import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Mic, Video, Check, AlertCircle, ArrowLeft } from 'lucide-react';
import { startInterview } from '../services/api';

const PreInterviewCheck = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const formData = location.state?.formData;

  // State Management
  const [cameraStream, setCameraStream] = useState(null);
  const [micStream, setMicStream] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedAudio, setRecordedAudio] = useState(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [errors, setErrors] = useState({});
  const [isStartingInterview, setIsStartingInterview] = useState(false);
  
  // Refs
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const audioChunksRef = useRef([]);
  const animationFrameRef = useRef(null);

  // Redirect if no form data
  useEffect(() => {
    if (!formData) {
      navigate('/');
    }
  }, [formData, navigate]);

  // STEP 1: Request Camera & Microphone Access
  useEffect(() => {
    const requestDevices = async () => {
      try {
        // Request camera
        const videoStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
          audio: false
        });
        setCameraStream(videoStream);
        if (videoRef.current) {
          videoRef.current.srcObject = videoStream;
        }

        // Request microphone with audio monitoring
        const audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        setMicStream(audioStream);
        
        // Setup audio level monitoring (VU meter)
        setupAudioMonitoring(audioStream);
        
      } catch (err) {
        setErrors({ 
          devices: 'Camera or microphone access denied. Please allow access and refresh.' 
        });
      }
    };

    requestDevices();

    // Cleanup on unmount
    return () => {
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
      }
      if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // STEP 2: Audio Level Monitoring (VU Meter)
  const setupAudioMonitoring = (stream) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    const microphone = audioContext.createMediaStreamSource(stream);
    
    analyser.fftSize = 256;
    microphone.connect(analyser);
    
    audioContextRef.current = audioContext;
    analyserRef.current = analyser;
    
    // Monitor audio levels
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const updateLevel = () => {
      analyser.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
      setAudioLevel(Math.min(100, (average / 255) * 100));
      animationFrameRef.current = requestAnimationFrame(updateLevel);
    };
    updateLevel();
  };

  // STEP 3: Start Test Recording
  const startTestRecording = () => {
    if (!micStream) return;
    
    audioChunksRef.current = [];
    const mediaRecorder = new MediaRecorder(micStream);
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };
    
    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      const audioUrl = URL.createObjectURL(audioBlob);
      setRecordedAudio(audioUrl);
    };
    
    mediaRecorderRef.current = mediaRecorder;
    mediaRecorder.start();
    setIsRecording(true);
  };

  // STEP 4: Stop Test Recording
  const stopTestRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // STEP 5: Confirm and Start Interview
  const handleConfirmProceed = async () => {
    if (!recordedAudio || !cameraStream || !micStream || !formData) return;
    
    setIsStartingInterview(true);
    setErrors({});
    
    try {
      // Build skill difficulties object
      const skillDifficulties = {};
      formData.skills.forEach(skill => {
        skillDifficulties[skill.name] = skill.difficulty;
      });

      // Build payload and add lightweight debug to help verify projects are sent
      const payload = {
        candidate_name: formData.candidateName,
        job_title: formData.jobTitle,
        recruiter_skills: formData.skills.map(s => s.name),
        target_skill_difficulties: skillDifficulties,
        resume_text: formData.resumeData?.data?.raw_text || null,
        projects: formData.resumeData?.data?.projects || null,
      };

      try {
        const projCount = Array.isArray(payload.projects) ? payload.projects.length : 0;
        // Avoid logging raw resume text; just lengths/counts
        console.log('[start-interview] sending', {
          candidate: payload.candidate_name,
          job: payload.job_title,
          skills: payload.recruiter_skills,
          projects_count: projCount,
          has_resume_text: !!payload.resume_text,
        });
      } catch (e) {
        // no-op
      }

      // Call backend to start interview
      const response = await startInterview(payload);

      if (response.success) {
        // Extract first question
        const questionText = typeof response.question === 'string' 
          ? response.question 
          : response.question?.question || 'Question not available';
        
        // Navigate to audio interview with session and first question only
        // Note: Do NOT pass MediaStream objects via navigation state (they can't be cloned by history.pushState)
        navigate(`/audio-interview/${response.session_id}`, {
          state: {
            firstQuestion: questionText
          }
        });
      }
    } catch (err) {
      setErrors({ api: err.message || 'Failed to start interview' });
    } finally {
      setIsStartingInterview(false);
    }
  };

  // Dummy question
  const dummyQuestion = "Please state your name and tell us one fun fact about yourself.";

  if (!formData) {
    return null; // Will redirect via useEffect
  }

  return (
    <div className="min-h-screen bg-stone-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Back Button */}
        <button
          onClick={() => navigate('/')}
          className="mb-6 flex items-center gap-2 text-slate-600 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
          Back to Setup
        </button>

        <h1 className="text-3xl font-bold text-slate-800 mb-2">
          Pre-Interview Hardware Check
        </h1>
        <p className="text-slate-600 mb-8">
          Let's make sure your camera and microphone are working properly
        </p>
        
        {/* Camera Feed */}
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Video className="h-5 w-5 text-blue-600" />
            Camera Check
          </h2>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-64 bg-slate-900 rounded-lg object-cover"
          />
          {cameraStream && (
            <p className="text-green-600 mt-2 flex items-center gap-2">
              <Check className="h-4 w-4" /> Camera connected successfully
            </p>
          )}
        </div>

        {/* Microphone Check with VU Meter */}
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Mic className="h-5 w-5 text-red-600" />
            Microphone Check
          </h2>
          
          {/* VU Meter */}
          <div className="mb-4">
            <p className="text-sm text-slate-600 mb-2">Speak to see audio levels:</p>
            <div className="w-full h-8 bg-stone-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 transition-all duration-100"
                style={{ width: `${audioLevel}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Silent</span>
              <span>Perfect</span>
              <span>Too Loud</span>
            </div>
          </div>
          
          {micStream && (
            <p className="text-green-600 flex items-center gap-2">
              <Check className="h-4 w-4" /> Microphone connected successfully
            </p>
          )}
        </div>

        {/* Test Recording Section */}
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Test Recording</h2>
          
          {/* Dummy Question */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
            <p className="text-sm font-medium text-amber-900 mb-2">Practice Question:</p>
            <p className="text-lg text-slate-800">{dummyQuestion}</p>
          </div>

          {/* Recording Controls */}
          <div className="flex items-center gap-4 mb-4">
            {!isRecording && !recordedAudio && (
              <button
                onClick={startTestRecording}
                disabled={!micStream}
                className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Mic className="h-5 w-5" />
                Start Test Recording
              </button>
            )}
            
            {isRecording && (
              <button
                onClick={stopTestRecording}
                className="px-6 py-3 bg-slate-700 hover:bg-slate-800 text-white rounded-lg flex items-center gap-2 transition-colors"
              >
                <div className="h-3 w-3 bg-red-500 rounded-full animate-pulse" />
                Stop Recording
              </button>
            )}
          </div>

          {/* Audio Playback */}
          {recordedAudio && (
            <div className="bg-stone-50 rounded-lg p-4 border border-stone-200">
              <p className="text-sm font-medium text-slate-700 mb-3">Listen to your recording:</p>
              <audio src={recordedAudio} controls className="w-full mb-4" />
              
              <button
                onClick={() => {
                  setRecordedAudio(null);
                  audioChunksRef.current = [];
                }}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Record Again
              </button>
            </div>
          )}
        </div>

        {/* Errors */}
        {errors.devices && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-red-800">{errors.devices}</p>
          </div>
        )}
        
        {errors.api && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-red-800">{errors.api}</p>
          </div>
        )}

        {/* Confirm and Proceed */}
        <button
          onClick={handleConfirmProceed}
          disabled={!recordedAudio || !cameraStream || !micStream || isStartingInterview}
          className="w-full py-4 bg-green-600 hover:bg-green-700 text-white text-lg font-semibold rounded-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Check className="h-6 w-6" />
          {isStartingInterview ? 'Starting Interview...' : 'Everything sounds good! Proceed to Interview'}
        </button>
      </div>
    </div>
  );
};

export default PreInterviewCheck;
