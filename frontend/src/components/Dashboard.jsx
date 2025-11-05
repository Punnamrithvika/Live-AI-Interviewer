import React, { useState, useEffect } from 'react';
import { 
  Target, 
  CheckCircle, 
  XCircle,
  Activity
} from 'lucide-react';
import { getInterviewStatus } from '../services/api';

const Dashboard = ({ sessionId }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) return;

    const fetchStatus = async () => {
      try {
        setLoading(true);
        const response = await getInterviewStatus(sessionId);
        
        if (response.success) {
          setStatus(response.status);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    
    // Refresh status every 10 seconds
    const interval = setInterval(fetchStatus, 10000);
    
    return () => clearInterval(interval);
  }, [sessionId]);

  if (loading && !status) {
    return (
      <div className="card">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="text-center text-red-600 dark:text-red-400">
          <XCircle className="h-12 w-12 mx-auto mb-4" />
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="card">
        <p className="text-center text-gray-500 dark:text-gray-400">
          No interview data available
        </p>
      </div>
    );
  }

  const skillsArray = Object.entries(status.skills_summary || {});

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Interview Dashboard
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Session ID: {status.session_id?.substring(0, 8)}...
            </p>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            status.current_phase === 'completed'
              ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
              : 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
          }`}>
            {status.current_phase}
          </div>
        </div>
      </div>

      {/* Skills Evaluation */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Target className="h-5 w-5" />
          Skills Evaluation
        </h3>
        
        {skillsArray.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            No skills evaluated yet
          </p>
        ) : (
          <div className="space-y-3">
            {skillsArray.map(([skillName, skillData]) => (
              <div key={skillName} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white">
                      {skillName}
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {skillData.questions_asked} questions asked
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {skillData.target_reached ? (
                      <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                    ) : (
                      <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    )}
                    <span className="text-lg font-bold text-gray-900 dark:text-white">
                      {skillData.percentage_score?.toFixed(1)}%
                    </span>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all duration-300 ${
                      skillData.percentage_score >= 80
                        ? 'bg-green-600'
                        : skillData.percentage_score >= 50
                        ? 'bg-yellow-600'
                        : 'bg-red-600'
                    }`}
                    style={{ width: `${Math.min(skillData.percentage_score || 0, 100)}%` }}
                  />
                </div>
                
                <div className="mt-2 flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
                  <span className={`px-2 py-1 rounded ${
                    skillData.status === 'completed'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                      : skillData.status === 'in_progress'
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
                      : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400'
                  }`}>
                    {skillData.status}
                  </span>
                  {skillData.target_reached && (
                    <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                      <CheckCircle className="h-3 w-3" />
                      Target Reached
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
