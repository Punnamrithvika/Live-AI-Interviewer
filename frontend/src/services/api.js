import axios from 'axios';

// Use explicit API base including /api so endpoint paths below don't repeat it
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error
      console.error('API Error:', error.response.data);
      throw new Error(error.response.data.detail || 'Server error occurred');
    } else if (error.request) {
      // Request made but no response
      console.error('Network Error:', error.message);
      throw new Error('Network error - please check your connection');
    } else {
      console.error('Error:', error.message);
      throw error;
    }
  }
);

// ==================== API METHODS ====================

/**
 * Upload resume file
 * @param {File} file - Resume file (PDF, DOCX, TXT)
 * @returns {Promise} Processed resume data
 */
export const uploadResume = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload-resume', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

/**
 * Start new interview session
 * @param {Object} params - Interview parameters
 * @param {string} params.candidate_name - Candidate name
 * @param {string} params.job_title - Job title
 * @param {Array<string>} params.recruiter_skills - Skills to evaluate
 * @param {Object} params.target_skill_difficulties - Difficulty levels per skill
 * @param {string} params.resume_text - Optional resume text
 * @returns {Promise} Session ID and first question
 */
export const startInterview = async (params) => {
  const response = await api.post('/start-interview', params);
  return response.data;
};

/**
 * Send candidate message/answer
 * @param {string} sessionId - Session ID
 * @param {string} message - Candidate's answer
 * @returns {Promise} Evaluation and next question
 */
export const sendMessage = async (sessionId, message) => {
  const response = await api.post('/send-message', {
    session_id: sessionId,
    message: message,
  });
  return response.data;
};

/**
 * Get interview session status
 * @param {string} sessionId - Session ID
 * @returns {Promise} Current session status
 */
export const getInterviewStatus = async (sessionId) => {
  const response = await api.get(`/interview-status/${sessionId}`);
  return response.data;
};

/**
 * Evaluate candidate response
 * @param {string} sessionId - Session ID
 * @param {string} answer - Candidate's answer
 * @returns {Promise} Evaluation result
 */
export const evaluateResponse = async (sessionId, answer) => {
  const response = await api.post('/evaluate-response', {
    session_id: sessionId,
    answer: answer,
  });
  return response.data;
};

/**
 * End interview session
 * @param {string} sessionId - Session ID
 * @returns {Promise} Final summary with detailed results
 */
export const endInterview = async (sessionId) => {
  const response = await api.delete(`/end-interview/${sessionId}`);
  return response.data;
};

/**
 * Get detailed interview results
 * @param {string} sessionId - Session ID
 * @returns {Promise} Comprehensive evaluation data
 */
export const getInterviewResults = async (sessionId) => {
  const response = await api.get(`/interview-results/${sessionId}`);
  return response.data;
};

/**
 * Download interview report PDF
 * @param {string} sessionId - Session ID
 * @returns {Promise} PDF blob
 */
export const downloadReport = async (sessionId) => {
  const response = await api.get(`/download-report/${sessionId}`, {
    responseType: 'blob'
  });
  return response.data;
};

/**
 * Transcribe audio blob to text
 * @param {Blob} audioBlob - Audio in webm/ogg/wav format
 * @param {string} sessionId - Optional session id
 * @returns {Promise<{text: string}>}
 */
export const transcribeAudio = async (audioBlob, sessionId) => {
  const formData = new FormData();
  // Pick sensible filename based on blob type to help backend branch logic
  const isWav = (audioBlob && (audioBlob.type?.includes('wav') || audioBlob.type === 'audio/wave'));
  const filename = isWav ? 'answer.wav' : 'answer.webm';
  const type = isWav ? 'audio/wav' : (audioBlob?.type || 'audio/webm');
  const file = new File([audioBlob], filename, { type });
  formData.append('file', file);
  if (sessionId) formData.append('session_id', sessionId);

  const response = await api.post('/transcribe', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

/**
 * Upload recorded video blob.
 * @param {Blob} videoBlob - Video (webm/mp4)
 * @param {string} sessionId - Optional session id
 * @returns {Promise<{success:boolean, filename:string, url:string}>}
 */
export const uploadVideo = async (videoBlob, sessionId) => {
  const formData = new FormData();
  const isMp4 = videoBlob?.type?.includes('mp4');
  const filename = isMp4 ? 'recording.mp4' : 'recording.webm';
  const file = new File([videoBlob], filename, { type: videoBlob.type || (isMp4 ? 'video/mp4' : 'video/webm') });
  formData.append('file', file);
  if (sessionId) formData.append('session_id', sessionId);
  const response = await api.post('/upload-video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

/**
 * Get system status
 * @returns {Promise} System status
 */
export const getSystemStatus = async () => {
  const response = await api.get('/system/status');
  return response.data;
};

/**
 * Health check
 * @returns {Promise} Service status
 */
export const healthCheck = async () => {
  // With API base including /api, check the explicit status endpoint
  const response = await api.get('/system/status');
  return response.data;
};

export default api;
