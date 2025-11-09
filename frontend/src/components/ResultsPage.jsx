import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { Download, Home, CheckCircle, XCircle, Award, TrendingUp, Clock, Target } from 'lucide-react';
import { getInterviewResults, downloadReport } from '../services/api';

const ResultsPage = () => {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [results, setResults] = useState(location.state?.results || null);
  const [loading, setLoading] = useState(!location.state?.results);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  const fetchResults = async () => {
    try {
      setLoading(true);
      const response = await getInterviewResults(sessionId);
      setResults(response.results);
    } catch (err) {
      setError(err.message || 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!results && sessionId) {
      fetchResults();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, results]);

  const handleDownloadReport = async () => {
    try {
      setDownloading(true);
      const blob = await downloadReport(sessionId);
      // Pick file extension based on blob content type to avoid corrupt PDF errors
      const ct = blob?.type || '';
      const ext = ct === 'application/pdf' ? 'pdf' : (ct === 'text/plain' ? 'txt' : 'bin');
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interview_report_${sessionId.substring(0, 8)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Error downloading report:', err);
      alert('Failed to download report. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-blue-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBgColor = (score) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-blue-100';
    if (score >= 40) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-700 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading results...</p>
        </div>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <XCircle className="h-12 w-12 text-red-600 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-800 mb-2">Error Loading Results</h2>
          <p className="text-slate-600 mb-4">{error || 'Results not found'}</p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-amber-700 hover:bg-amber-800 text-white rounded-lg"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  const { summary, evaluations, skills_breakdown } = results;
  const overallScore = evaluations && evaluations.length > 0
    ? (evaluations.reduce((sum, e) => sum + (e.score || 0), 0) / evaluations.length).toFixed(1)
    : 0;

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-6 shadow-sm">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-800 mb-2">Interview Results</h1>
              <p className="text-slate-600">
                {summary?.candidate_name} • {summary?.job_title}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleDownloadReport}
                disabled={downloading}
                className="px-6 py-2 bg-amber-700 hover:bg-amber-800 text-white rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                <Download className="h-5 w-5" />
                {downloading ? 'Downloading...' : 'Download Report'}
              </button>
              <button
                onClick={() => navigate('/')}
                className="px-6 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg flex items-center gap-2 transition-colors"
              >
                <Home className="h-5 w-5" />
                Home
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
            <div className="flex items-center gap-3 mb-2">
              <Award className="h-6 w-6 text-amber-700" />
              <p className="text-sm text-slate-600 font-medium">Overall Score</p>
            </div>
            <p className={`text-3xl font-bold ${getScoreColor(overallScore)}`}>
              {overallScore}%
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
            <div className="flex items-center gap-3 mb-2">
              <Target className="h-6 w-6 text-blue-600" />
              <p className="text-sm text-slate-600 font-medium">Questions</p>
            </div>
            <p className="text-3xl font-bold text-slate-800">
              {summary?.total_questions || 0}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="h-6 w-6 text-green-600" />
              <p className="text-sm text-slate-600 font-medium">Skills Tested</p>
            </div>
            <p className="text-3xl font-bold text-slate-800">
              {Object.keys(skills_breakdown || {}).length}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="h-6 w-6 text-purple-600" />
              <p className="text-sm text-slate-600 font-medium">Duration</p>
            </div>
            <p className="text-3xl font-bold text-slate-800">
              {summary?.total_answers || 0}m
            </p>
          </div>
        </div>

        {/* Skills Breakdown */}
        {skills_breakdown && Object.keys(skills_breakdown).length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6 mb-8">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Skills Performance</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Object.entries(skills_breakdown).map(([skillName, skillData]) => (
                <div key={skillName} className="border border-stone-200 rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-slate-800">{skillName}</h3>
                    {skillData.target_reached ? (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
                    )}
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-600">Score:</span>
                      <span className={`font-semibold ${getScoreColor(skillData.percentage_score)}`}>
                        {skillData.percentage_score.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">Questions:</span>
                      <span className="font-semibold text-slate-800">{skillData.questions_asked}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">Level:</span>
                      <span className="font-semibold text-slate-800 capitalize">
                        {skillData.highest_difficulty}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="mt-3">
                    <div className="w-full bg-stone-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${getScoreBgColor(skillData.percentage_score)} transition-all`}
                        style={{ width: `${Math.min(skillData.percentage_score, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Detailed Q&A with Feedback */}
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
          <h2 className="text-xl font-bold text-slate-800 mb-6">Question-by-Question Feedback</h2>
          <div className="space-y-6">
            {evaluations && evaluations.map((evaluation, index) => (
              <div 
                key={index} 
                className="border-l-4 border-stone-200 pl-6 py-4 hover:border-amber-500 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="px-3 py-1 bg-stone-100 text-slate-700 rounded-full text-sm font-medium">
                        Q{evaluation.question_number}
                      </span>
                      {evaluation.skill && (
                        <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium">
                          {evaluation.skill}
                        </span>
                      )}
                      {evaluation.difficulty && (
                        <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium capitalize">
                          {evaluation.difficulty}
                        </span>
                      )}
                    </div>
                    <p className="text-lg font-semibold text-slate-800 mb-3">
                      {evaluation.question}
                    </p>
                  </div>
                  <div className={`ml-4 px-4 py-2 rounded-lg ${getScoreBgColor(evaluation.score)}`}>
                    <span className={`text-2xl font-bold ${getScoreColor(evaluation.score)}`}>
                      {evaluation.score}
                    </span>
                    <span className="text-sm text-slate-600">/100</span>
                  </div>
                </div>

                <div className="mb-3">
                  <p className="text-sm font-medium text-slate-600 mb-1">Your Answer:</p>
                  <p className="text-slate-700 bg-stone-50 p-3 rounded-lg">
                    {evaluation.answer || 'No answer provided'}
                  </p>
                </div>

                {evaluation.feedback && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <p className="text-sm font-medium text-amber-900 mb-1">Feedback:</p>
                    <p className="text-sm text-amber-800">
                      {evaluation.feedback}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;
