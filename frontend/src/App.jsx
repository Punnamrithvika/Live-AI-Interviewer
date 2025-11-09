import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useParams, useLocation } from 'react-router-dom';
import { Moon, Sun, LogOut } from 'lucide-react';
import ResumeUpload from './components/ResumeUpload';
import ChatInterface from './components/ChatInterface';
import Dashboard from './components/Dashboard';
import EvaluationResults from './components/EvaluationResults';
import CameraView from './components/CameraView';
import ResultsPage from './components/ResultsPage';
import PreInterviewCheck from './components/PreInterviewCheck';
import AudioInterviewPage from './components/AudioInterviewPage';
import { endInterview, healthCheck } from './services/api';

// Home/Setup Page
const SetupPage = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    candidateName: '',
    jobTitle: '',
    skills: [],
    currentSkill: '',
    skillDifficulty: 'INTERMEDIATE',
    resumeData: null,
  });
  const [error, setError] = useState(null);
  const hasResume = !!formData.resumeData;

  const handleAddSkill = () => {
    if (formData.currentSkill.trim()) {
      const newSkill = {
        name: formData.currentSkill.trim(),
        difficulty: formData.skillDifficulty,
      };
      
      setFormData(prev => ({
        ...prev,
        skills: [...prev.skills, newSkill],
        currentSkill: '',
        skillDifficulty: 'INTERMEDIATE',
      }));
    }
  };

  const handleRemoveSkill = (index) => {
    setFormData(prev => ({
      ...prev,
      skills: prev.skills.filter((_, i) => i !== index),
    }));
  };

  const handleResumeUpload = (data) => {
    setFormData(prev => ({ ...prev, resumeData: data }));
  };

  const handleStartInterview = async () => {
    if (!formData.candidateName || !formData.jobTitle || formData.skills.length === 0) {
      setError('Please fill in all required fields and add at least one skill');
      return;
    }

    // Enforce resume upload before proceeding
    if (!formData.resumeData) {
      setError('Please upload your resume before starting the interview');
      try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) {}
      return;
    }

    // Navigate to hardware check page with form data (no API call yet)
    navigate('/pre-check', {
      state: { formData }
    });
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-slate-800 mb-3">
          AI Interview System
        </h1>
        <p className="text-lg text-slate-600">
          Set up your interview session
        </p>
      </div>

      {/* Resume Upload */}
      <ResumeUpload onUploadSuccess={handleResumeUpload} />

      {/* Interview Setup Form */}
      <div className="card max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">
          Interview Details
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Candidate Name *
            </label>
            <input
              type="text"
              value={formData.candidateName}
              onChange={(e) => setFormData(prev => ({ ...prev, candidateName: e.target.value }))}
              className="input-field"
              placeholder="John Doe"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Job Title *
            </label>
            <input
              type="text"
              value={formData.jobTitle}
              onChange={(e) => setFormData(prev => ({ ...prev, jobTitle: e.target.value }))}
              className="input-field"
              placeholder="Senior Python Developer"
            />
          </div>

          {/* Skills */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Skills to Evaluate *
            </label>
            
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={formData.currentSkill}
                onChange={(e) => setFormData(prev => ({ ...prev, currentSkill: e.target.value }))}
                onKeyPress={(e) => e.key === 'Enter' && handleAddSkill()}
                className="input-field flex-1"
                placeholder="Python Programming"
              />
              <select
                value={formData.skillDifficulty}
                onChange={(e) => setFormData(prev => ({ ...prev, skillDifficulty: e.target.value }))}
                className="input-field w-40"
              >
                <option value="BEGINNER">Beginner</option>
                <option value="INTERMEDIATE">Intermediate</option>
                <option value="ADVANCED">Advanced</option>
              </select>
              <button
                onClick={handleAddSkill}
                className="btn-primary"
              >
                Add
              </button>
            </div>

            {formData.skills.length > 0 && (
              <div className="space-y-2">
                {formData.skills.map((skill, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between bg-gray-50 dark:bg-gray-700 px-4 py-2 rounded-lg"
                  >
                    <span className="font-medium text-gray-900 dark:text-white">
                      {skill.name}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        skill.difficulty === 'BEGINNER' ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400' :
                        skill.difficulty === 'INTERMEDIATE' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400' :
                        'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                      }`}>
                        {skill.difficulty}
                      </span>
                      <button
                        onClick={() => handleRemoveSkill(index)}
                        className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {error && (
            <div className="p-4 bg-white dark:bg-white border border-red-200 dark:border-red-300 rounded-lg text-red-800 dark:text-red-800">
              {error}
            </div>
          )}

          <button
            onClick={handleStartInterview}
            disabled={!hasResume}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
            title={!hasResume ? 'Please upload your resume to enable this button' : ''}
          >
            Start Interview
          </button>
        </div>
      </div>
    </div>
  );
};

// Interview Page
const InterviewPage = ({ sessionId, firstQuestion }) => {
  const navigate = useNavigate();
  // eslint-disable-next-line no-unused-vars
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);

  const handleEndInterview = async () => {
    try {
      const response = await endInterview(sessionId);
      // Navigate to results page with the evaluation data
      navigate(`/results/${sessionId}`, {
        state: { results: response.results }
      });
    } catch (err) {
      console.error('Error ending interview:', err);
      navigate('/');
    }
  };

  return (
    <div className="h-screen flex flex-col bg-stone-50">
      {/* Header */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">
              AI Interviewer
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right mr-4">
              <p className="text-xs text-slate-600">Time Elapsed</p>
              <p className="text-sm font-semibold text-slate-800">1:45 / 20:00</p>
            </div>
            <button
              onClick={() => setShowConfirmEnd(true)}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center gap-2 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              End Interview
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden p-6">
        <div className="h-full flex gap-6">
          {/* Chat - Main Content */}
          <div className="flex-1 bg-white rounded-xl shadow-sm border border-stone-200">
            <ChatInterface sessionId={sessionId} firstQuestion={firstQuestion} />
          </div>

          {/* Right Sidebar */}
          <div className="w-96 flex flex-col gap-6">
            {/* Camera View */}
            <div className="h-64 bg-slate-900 rounded-xl overflow-hidden shadow-lg">
              <CameraView />
            </div>

            {/* Dashboard */}
            <div className="flex-1 overflow-y-auto">
              <Dashboard sessionId={sessionId} />
              {currentEvaluation && (
                <div className="mt-6">
                  <EvaluationResults evaluation={currentEvaluation} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Confirm End Dialog */}
      {showConfirmEnd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="card max-w-md">
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              End Interview?
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Are you sure you want to end this interview session? This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleEndInterview}
                className="btn-primary flex-1"
              >
                Yes, End Interview
              </button>
              <button
                onClick={() => setShowConfirmEnd(false)}
                className="btn-secondary flex-1"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Main App Component
function App() {
  const [darkMode, setDarkMode] = useState(false);
  // eslint-disable-next-line no-unused-vars
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    // Check system health
    healthCheck().then(data => {
      setSystemStatus(data);
    }).catch(err => {
      console.error('Backend health check failed:', err);
    });

    // Check for dark mode preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setDarkMode(true);
    }
  }, []);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <Router>
      <div className="min-h-screen bg-stone-50">
        {/* Theme Toggle - Hidden for old-money aesthetic */}
        {false && (
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="fixed top-4 right-4 z-50 p-2 rounded-lg bg-white shadow-lg"
          >
            {darkMode ? (
              <Sun className="h-5 w-5 text-yellow-500" />
            ) : (
              <Moon className="h-5 w-5 text-slate-700" />
            )}
          </button>
        )}

        <Routes>
          <Route path="/" element={
            <div className="container mx-auto px-4 py-8">
              <SetupPage />
            </div>
          } />
          <Route path="/pre-check" element={<PreInterviewCheck />} />
          <Route path="/interview/:sessionId" element={<InterviewPageWrapper />} />
          <Route path="/audio-interview/:sessionId" element={<AudioInterviewPageWrapper />} />
          <Route path="/results/:sessionId" element={<ResultsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

// Wrapper to extract sessionId from URL params
const InterviewPageWrapper = () => {
  const { sessionId } = useParams();
  const location = useLocation();
  const firstQuestion = location.state?.firstQuestion;
  return <InterviewPage sessionId={sessionId} firstQuestion={firstQuestion} />;
};

// Wrapper for Audio Interview Page
const AudioInterviewPageWrapper = () => {
  const { sessionId } = useParams();
  const location = useLocation();
  const firstQuestion = location.state?.firstQuestion;
  return <AudioInterviewPage sessionId={sessionId} firstQuestion={firstQuestion} />;
};

export default App;
