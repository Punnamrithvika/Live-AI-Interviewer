import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Volume2, Brain, Send, Clock, Home } from 'lucide-react';
import { sendMessage, transcribeAudio } from '../services/api';
import useWebSocket from '../hooks/useWebSocket';

const AudioInterviewPage = ({ sessionId: propSessionId, firstQuestion }) => {
  const { sessionId: paramSessionId } = useParams();
  const sessionId = propSessionId || paramSessionId;
  const navigate = useNavigate();
  
  // Config
  const THINK_SECONDS = 3; // time to think before recording starts (was 5)

  // State Management
  const [currentQuestion, setCurrentQuestion] = useState(firstQuestion || '');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [thinkingTime, setThinkingTime] = useState(THINK_SECONDS);
  const [isThinking, setIsThinking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [cameraStream, setCameraStream] = useState(null);
  const [audioLevel, setAudioLevel] = useState(0);
  
  // Refs
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);
  const utteranceRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);
  const isRecordingRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const ttsWaitIntervalRef = useRef(null);
  const ttsWaitTimeoutRef = useRef(null);
  const hasStartedThinkingRef = useRef(false);
  const speakQuestionRef = useRef(null);
  const autoStopTimeoutRef = useRef(null);
  // Live refs to avoid stale closures
  const micStreamRef = useRef(null);
  const startRecordingRef = useRef(() => {});
  // (Video recording disabled per request; keep only live camera preview)
  const avRecorderRef = useRef(null); // unused now
  const avChunksRef = useRef([]); // unused now
  // Track last question to avoid incrementing counter on duplicates
  const lastQuestionRef = useRef('');
  const hasSpokenInitialRef = useRef(false);
  // Stable ref to video element to avoid resetting srcObject each render
  const cameraVideoRef = useRef(null);
  
  // WebSocket connection
  const { isConnected, messages: wsMessages, sendAnswer } = useWebSocket(sessionId);

  // Initialize camera and mic, and setup audio monitoring
  useEffect(() => {
    let localVideoStream;
    let localAudioStream;

    const initDevices = async () => {
      try {
        // Optional: observe microphone permission state (not supported in all browsers)
        try {
          if (navigator.permissions && navigator.permissions.query) {
            const perm = await navigator.permissions.query({ name: 'microphone' });
            console.log('[devices] Microphone permission state:', perm.state);
            perm.onchange = () => console.log('[devices] Microphone permission changed:', perm.state);
          }
        } catch (e) {
          // permissions API may not be available; ignore
        }

        localVideoStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, frameRate: { ideal: 15, max: 20 } },
          audio: false
        });
        setCameraStream(localVideoStream);
        console.log('[devices] Camera stream acquired:', {
          tracks: localVideoStream.getTracks().map(t => ({ kind: t.kind, enabled: t.enabled, readyState: t.readyState }))
        });

        localAudioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        micStreamRef.current = localAudioStream;
        console.log('[devices] Microphone stream acquired:', {
          tracks: localAudioStream.getTracks().map(t => ({ kind: t.kind, enabled: t.enabled, readyState: t.readyState }))
        });

        // Setup audio monitoring
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = audioContext.createAnalyser();
        const microphone = audioContext.createMediaStreamSource(localAudioStream);

        analyser.fftSize = 256;
        microphone.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateLevel = () => {
          if (isRecordingRef.current) {
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            setAudioLevel(Math.min(100, (average / 255) * 100));
          }
          animationFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (err) {
        console.error('Error accessing devices:', err);
      }
    };

    initDevices();

    return () => {
      if (localVideoStream) {
        localVideoStream.getTracks().forEach(track => track.stop());
      }
      if (localAudioStream) {
        localAudioStream.getTracks().forEach(track => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Attach camera stream to video element only when stream changes (prevents flicker)
  useEffect(() => {
    const el = cameraVideoRef.current;
    if (el && cameraStream && el.srcObject !== cameraStream) {
      el.srcObject = cameraStream;
      const p = el.play?.();
      if (p && typeof p.catch === 'function') {
        p.catch(() => {});
      }
    }
  }, [cameraStream]);

  

  // Keep ref in sync for recording state
  useEffect(() => {
    isRecordingRef.current = isRecording;
    console.log('[State] isRecording changed:', isRecording);
  }, [isRecording]);

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
    console.log('[State] isSpeaking changed:', isSpeaking);
  }, [isSpeaking]);

  // Submit audio to backend (transcribe with Whisper) - memoized so startRecording can depend on it
  const submitAnswer = useCallback(async (audioBlob) => {
    console.log('[submitAnswer] Starting...', { blobSize: audioBlob.size, isConnected });
    try {
      // Convert to WAV in-browser to avoid server ffmpeg dependency
      const toWav = async (blob) => {
        try {
          const arrayBuf = await blob.arrayBuffer();
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const decoded = await audioCtx.decodeAudioData(arrayBuf.slice(0));
          // Downmix to mono
          const channelData = decoded.numberOfChannels > 1
            ? (() => {
                const L = decoded.getChannelData(0);
                const R = decoded.getChannelData(1);
                const mono = new Float32Array(decoded.length);
                for (let i = 0; i < decoded.length; i++) mono[i] = (L[i] + R[i]) / 2;
                return mono;
              })()
            : decoded.getChannelData(0);
          // Resample to 16kHz using OfflineAudioContext if needed
          const targetRate = 16000;
          let pcm;
          if (decoded.sampleRate !== targetRate) {
            const frames = Math.ceil(decoded.duration * targetRate);
            const offline = new OfflineAudioContext(1, frames, targetRate);
            const buffer = offline.createBuffer(1, decoded.length, decoded.sampleRate);
            buffer.copyToChannel(channelData, 0);
            const src = offline.createBufferSource();
            src.buffer = buffer;
            src.connect(offline.destination);
            src.start(0);
            const resampled = await offline.startRendering();
            pcm = resampled.getChannelData(0);
          } else {
            pcm = channelData;
          }

          // Encode PCM 16-bit WAV
          const wavBuf = (() => {
            const bytesPerSample = 2;
            const blockAlign = 1 * bytesPerSample;
            const byteRate = targetRate * blockAlign;
            const buffer = new ArrayBuffer(44 + pcm.length * bytesPerSample);
            const view = new DataView(buffer);
            let offset = 0;
            const writeString = (s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset++, s.charCodeAt(i)); };
            const writeUint32 = (v) => { view.setUint32(offset, v, true); offset += 4; };
            const writeUint16 = (v) => { view.setUint16(offset, v, true); offset += 2; };

            writeString('RIFF');
            writeUint32(36 + pcm.length * bytesPerSample);
            writeString('WAVE');
            writeString('fmt ');
            writeUint32(16); // PCM chunk size
            writeUint16(1);  // PCM format
            writeUint16(1);  // mono
            writeUint32(targetRate);
            writeUint32(byteRate);
            writeUint16(blockAlign);
            writeUint16(16); // bits per sample
            writeString('data');
            writeUint32(pcm.length * bytesPerSample);
            // PCM samples
            for (let i = 0; i < pcm.length; i++) {
              const s = Math.max(-1, Math.min(1, pcm[i]));
              view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
              offset += 2;
            }
            return buffer;
          })();

          return new Blob([wavBuf], { type: 'audio/wav' });
        } catch (e) {
          console.warn('[submitAnswer] WAV conversion failed, sending original blob', e);
          return blob;
        }
      };

      // Send audio to backend for transcription
      console.log('[submitAnswer] Sending to transcription API...');
      const wavBlob = await toWav(audioBlob);
      const resp = await transcribeAudio(wavBlob, sessionId);
      console.log('[submitAnswer] Transcription response:', resp);
      let text = resp?.text || `[Audio answer recorded - ${audioBlob.size} bytes]`;

      // If backend STT failed (placeholder returned), ask user to type their answer
      const isPlaceholder = typeof text === 'string' && /\[\s*Audio received[^\]]*transcription unavailable\s*\]/i.test(text);
      if (isPlaceholder) {
        console.log('[submitAnswer] Transcription failed, prompting for typed input');
        // Minimal UI impact: prompt for typed answer
        const typed = window.prompt('Transcription failed. Please type your answer to submit:', '');
        if (typed && typed.trim().length > 0) {
          text = typed.trim();
        }
      }
      console.log('[submitAnswer] Final text to submit:', text.substring(0, 100));
      try {
        if (isConnected) {
          console.log('[submitAnswer] Sending via WebSocket...');
          sendAnswer(text);
        } else {
          console.log('[submitAnswer] Sending via HTTP...');
          const r = await sendMessage(sessionId, text);
          // Handle next question immediately when using HTTP fallback
          const nq = r?.next_question?.question || r?.question;
          if (nq) {
            if (nq !== lastQuestionRef.current) {
              lastQuestionRef.current = nq;
              setCurrentQuestion(nq);
              setQuestionNumber(prev => prev + 1);
              if (speakQuestionRef.current) speakQuestionRef.current(nq);
            }
          }
        }
        console.log('[submitAnswer] Answer submitted successfully');
      } catch (err) {
        console.error('[submitAnswer] Error submitting answer:', err);
      }
    } catch (err) {
      console.error('[submitAnswer] Error processing audio:', err);
    }
  }, [isConnected, sendAnswer, sessionId]);

  // Retry counter for starting recording when mic isn't ready yet
  const recordRetryRef = useRef(0);

  // STEP 4: Automatically Start Audio Recording (defined before timers to avoid TDZ issues)
  const startRecording = useCallback(() => {
    console.log('[startRecording] Called', { 
      isSpeaking: isSpeakingRef.current, 
      speechSynthSpeaking: window.speechSynthesis?.speaking 
    });
    
    // Ensure we never start recording while TTS is still speaking
    if (typeof window !== 'undefined' && window.speechSynthesis && (window.speechSynthesis.speaking || isSpeakingRef.current)) {
      console.log('[startRecording] TTS still speaking, retrying...');
      // Retry shortly after TTS finishes
      setTimeout(() => startRecording(), 150);
      return;
    }

    console.log('[startRecording] Attempting to start recording...');
    setIsThinking(false);
    setAudioLevel(0);

    // Always read the latest mic stream from ref to avoid stale state in timeouts
    const liveMicStream = micStreamRef.current;
    const hasLiveTrack = !!liveMicStream && liveMicStream.getAudioTracks && liveMicStream.getAudioTracks().some(t => t.enabled && t.readyState === 'live');
    if (!hasLiveTrack) {
      recordRetryRef.current += 1;
      console.warn('[startRecording] No microphone stream yet. Will retry shortly.', { attempt: recordRetryRef.current });
      if (recordRetryRef.current <= 20) {
        setTimeout(() => startRecordingRef.current(), 300);
      } else {
        console.error('[startRecording] Microphone not available after multiple attempts. Check permissions.');
      }
      return;
    }
    // Reset retry counter once we have a mic stream
    recordRetryRef.current = 0;
    
    audioChunksRef.current = [];
    
    try {
      const mediaRecorder = new MediaRecorder(liveMicStream, {
        mimeType: 'audio/webm',
        audioBitsPerSecond: 64000
      });
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        console.log('Audio recorder stopped, processing audio...', { chunks: audioChunksRef.current.length });
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        console.log('Audio blob created', { size: audioBlob.size });
        await submitAnswer(audioBlob);
      };
      
  mediaRecorderRef.current = mediaRecorder;
  mediaRecorder.start(500); // larger timeslice reduces main-thread churn
      // Only mark recording as started after MediaRecorder starts successfully
      setIsRecording(true);
      isRecordingRef.current = true;

      // Safety: auto-stop after ~55s to stay under free Google STT limits
      if (autoStopTimeoutRef.current) clearTimeout(autoStopTimeoutRef.current);
      autoStopTimeoutRef.current = setTimeout(() => {
        try {
          if (mediaRecorderRef.current && isRecordingRef.current) {
            console.log('[AutoStop] Max answer duration reached, stopping recorder');
            mediaRecorderRef.current.stop();
          }
        } catch (e) {
          console.warn('AutoStop failed:', e);
        }
      }, 55000);

      // Video recording disabled: keep camera preview only (no upload attempts)
    } catch (err) {
      console.error('Error starting recording:', err);
      setIsRecording(false);
    }
  }, [cameraStream, submitAnswer, questionNumber, sessionId]);

  // Keep the latest startRecording in a ref to avoid stale closures in timeouts
  useEffect(() => {
    startRecordingRef.current = startRecording;
  }, [startRecording]);

  // STEP 2: Thinking timer
  const startThinkingTimer = useCallback(() => {
    setIsThinking(true);
    // Clear any existing timer to avoid overlap
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }
    setThinkingTime(THINK_SECONDS);
    
    timerIntervalRef.current = setInterval(() => {
      setThinkingTime((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current);
          // STEP 4: Auto-start recording when timer reaches 0
          startRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [startRecording]);

  // STEP 2: Text-to-Speech Function
  const startThinkingAfterTTS = useCallback(() => {
    // Clear any existing watchers
    if (ttsWaitIntervalRef.current) clearInterval(ttsWaitIntervalRef.current);
    if (ttsWaitTimeoutRef.current) clearTimeout(ttsWaitTimeoutRef.current);
    hasStartedThinkingRef.current = false;

    // Poll until speech synthesis reports not speaking, then start thinking
    ttsWaitIntervalRef.current = setInterval(() => {
      const speaking = typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.speaking : false;
      if (!speaking && !isSpeakingRef.current && !hasStartedThinkingRef.current) {
        hasStartedThinkingRef.current = true;
        clearInterval(ttsWaitIntervalRef.current);
        ttsWaitIntervalRef.current = null;
        startThinkingTimer();
      }
    }, 150);

    // Failsafe in case onend never fires on some browsers
    ttsWaitTimeoutRef.current = setTimeout(() => {
      if (!hasStartedThinkingRef.current) {
        if (ttsWaitIntervalRef.current) clearInterval(ttsWaitIntervalRef.current);
        ttsWaitIntervalRef.current = null;
        hasStartedThinkingRef.current = true;
        startThinkingTimer();
      }
    }, 30000);
  }, [startThinkingTimer]);

  const speakQuestionFn = useCallback((text) => {
    if ('speechSynthesis' in window) {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      
      // Wait for voices to load
      const setVoice = () => {
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => 
          v.lang.startsWith('en') && (v.name.includes('Female') || v.name.includes('Samantha'))
        ) || voices[0];
        if (preferredVoice) {
          utterance.voice = preferredVoice;
        }
      };

      if (window.speechSynthesis.getVoices().length > 0) {
        setVoice();
      } else {
        window.speechSynthesis.onvoiceschanged = setVoice;
      }
      
      utterance.onstart = () => {
        setIsSpeaking(true);
      };

      // When TTS finishes, only mark as not speaking; actual start of thinking is gated
      utterance.onend = () => {
        setIsSpeaking(false);
      };

      utterance.onerror = (e) => {
        console.error('Speech error:', e);
        setIsSpeaking(false);
      };
      
      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
      // Ensure thinking starts strictly after TTS completes
      startThinkingAfterTTS();
    } else {
      // Browser doesn't support TTS - skip to thinking
      console.warn('Speech synthesis not supported');
      startThinkingTimer();
    }
  }, [startThinkingAfterTTS, startThinkingTimer]);

  // Keep latest speakQuestion in a ref for stable usage across effects/callbacks
  useEffect(() => {
    speakQuestionRef.current = speakQuestionFn;
  }, [speakQuestionFn]);

  // Handle WebSocket messages for new questions (placed after speakQuestion to avoid TDZ)
  useEffect(() => {
    if (wsMessages.length > 0) {
      const lastMessage = wsMessages[wsMessages.length - 1];
      
      if (lastMessage.type === 'question') {
        const questionData = lastMessage.data;
        if (questionData && questionData.question) {
          const newQuestion = questionData.question;
          // Only update if it's actually a new question
          if (newQuestion !== lastQuestionRef.current) {
            lastQuestionRef.current = newQuestion;
            setCurrentQuestion(newQuestion);
            setQuestionNumber(prev => prev + 1);
            
            // Speak the new question
            if (speakQuestionRef.current) speakQuestionRef.current(newQuestion);
          }
        } else if (questionData === null) {
          // Interview completed
          navigate(`/results/${sessionId}`);
        }
      }
    }
  }, [wsMessages, sessionId, navigate]);

  // STEP 1: Initialize with first question
  useEffect(() => {
    if (currentQuestion && !hasSpokenInitialRef.current) {
      hasSpokenInitialRef.current = true;
      lastQuestionRef.current = currentQuestion;
      if (speakQuestionRef.current) speakQuestionRef.current(currentQuestion);
    }
  }, [currentQuestion]);

  


  // STEP 5: Submit Answer (Stop Recording)
  const handleSubmitAnswer = () => {
    console.log('Submit Answer clicked', { isRecording, hasRecorder: !!mediaRecorderRef.current });
    if (mediaRecorderRef.current && isRecording) {
      console.log('Stopping audio recorder...');
      mediaRecorderRef.current.stop();
      // A/V recorder removed
      setIsRecording(false);
      isRecordingRef.current = false;
      setAudioLevel(0);
    } else {
      console.warn('Cannot submit: not recording or no recorder', { 
        isRecording, 
        hasRecorder: !!mediaRecorderRef.current 
      });
    }
  };


  // Cleanup
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
      if (utteranceRef.current) {
        window.speechSynthesis.cancel();
      }
      if (ttsWaitIntervalRef.current) {
        clearInterval(ttsWaitIntervalRef.current);
      }
      if (ttsWaitTimeoutRef.current) {
        clearTimeout(ttsWaitTimeoutRef.current);
      }
      if (autoStopTimeoutRef.current) {
        clearTimeout(autoStopTimeoutRef.current);
      }
      // A/V recorder removed
    };
  }, []);

  // Format timer display
  const formatTime = (seconds) => {
    return `00:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="h-screen flex flex-col bg-stone-50">
      {/* Header */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">
              AI Audio Interview
            </h1>
            <p className="text-sm text-slate-600">
              Listen carefully and answer after the timer
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs text-slate-600">Question</p>
              <p className="text-lg font-bold text-slate-800">{questionNumber}</p>
            </div>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg flex items-center gap-2 transition-colors"
            >
              <Home className="h-4 w-4" />
              Exit
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
        <div className="max-w-4xl w-full">
          
          {/* Question Display */}
          <div className="bg-white rounded-xl shadow-lg border-2 border-stone-200 p-8 mb-8">
            <div className="flex items-center gap-3 mb-4">
              {isSpeaking && (
                <Volume2 className="h-6 w-6 text-blue-600 animate-pulse" />
              )}
              <h2 className="text-2xl font-bold text-slate-800">
                Question {questionNumber}
              </h2>
            </div>
            
            <p className="text-xl text-slate-700 leading-relaxed mb-4">
              {currentQuestion || 'Loading question...'}
            </p>
            
            {isSpeaking && (
              <div className="flex items-center gap-2 text-blue-600 bg-blue-50 px-4 py-2 rounded-lg">
                <Volume2 className="h-5 w-5 animate-pulse" />
                <span className="text-sm font-medium">Reading question aloud...</span>
              </div>
            )}
          </div>

          {/* Thinking Timer */}
          {isThinking && (
            <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-8 mb-8 text-center animate-fade-in">
              <div className="flex items-center justify-center gap-3 mb-4">
                <Brain className="h-8 w-8 text-amber-700" />
                <h3 className="text-2xl font-semibold text-amber-900">
                  Time to Think
                </h3>
              </div>
              
              <div className="text-7xl font-bold text-amber-700 mb-3 tabular-nums">
                {formatTime(thinkingTime)}
              </div>
              
              <p className="text-lg text-amber-800 mb-4">
                Prepare your answer. Recording will start automatically.
              </p>
              
              {/* Visual countdown progress */}
              <div className="w-full h-4 bg-amber-200 rounded-full overflow-hidden shadow-inner">
                <div
                  className="h-full bg-gradient-to-r from-amber-600 to-amber-500 transition-all duration-1000 ease-linear"
                  style={{ width: `${(thinkingTime / THINK_SECONDS) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Recording Indicator */}
          {isRecording && (
            <div className="bg-red-50 border-2 border-red-300 rounded-xl p-8 text-center animate-fade-in">
              <div className="flex items-center justify-center gap-3 mb-6">
                <div className="relative">
                  <div className="h-6 w-6 bg-red-600 rounded-full animate-pulse" />
                  <div className="absolute inset-0 h-6 w-6 bg-red-600 rounded-full animate-ping opacity-75" />
                </div>
                <h3 className="text-2xl font-semibold text-red-900">
                  Recording Your Answer
                </h3>
              </div>
              
              {/* Audio Level Indicator */}
              <div className="mb-6">
                <div className="w-full h-6 bg-red-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-red-500 to-red-600 transition-all duration-100"
                    style={{ width: `${audioLevel}%` }}
                  />
                </div>
                <p className="text-xs text-red-700 mt-1">Audio Level: {Math.round(audioLevel)}%</p>
              </div>
              
              <p className="text-lg text-red-800 mb-6">
                Speak clearly into your microphone. Click "Submit Answer" when you're done.
              </p>
              
              <button
                onClick={handleSubmitAnswer}
                disabled={!isRecording}
                className={`px-8 py-4 text-white text-lg font-semibold rounded-lg flex items-center gap-3 mx-auto transition-all shadow-lg ${
                  isRecording 
                    ? 'bg-slate-700 hover:bg-slate-800 hover:scale-105 cursor-pointer' 
                    : 'bg-gray-400 cursor-not-allowed'
                }`}
              >
                <Send className="h-6 w-6" />
                Submit Answer
              </button>
            </div>
          )}

          {/* Waiting State */}
          {!isSpeaking && !isThinking && !isRecording && (
            <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-8 text-center">
              <Clock className="h-12 w-12 text-blue-600 mx-auto mb-4 animate-pulse" />
              <p className="text-lg text-blue-800">
                Please wait while the question is being read...
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Camera Feed (Small corner) */}
      <div className="fixed bottom-6 right-6 w-48 h-36 bg-slate-900 rounded-lg overflow-hidden shadow-2xl border-2 border-amber-300">
        <video
          ref={cameraVideoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />
        <div className="absolute top-2 left-2 px-2 py-1 bg-black/50 rounded text-white text-xs">
          You
        </div>
      </div>
    </div>
  );
};

export default AudioInterviewPage;
