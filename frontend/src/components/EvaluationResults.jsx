import React from 'react';
import { Award, TrendingUp, TrendingDown, Minus, CheckCircle, XCircle } from 'lucide-react';

const EvaluationResults = ({ evaluation }) => {
  if (!evaluation) {
    return (
      <div className="card">
        <p className="text-center text-gray-500 dark:text-gray-400">
          No evaluation data available
        </p>
      </div>
    );
  }

  const score = evaluation.score || 0;
  const skill = evaluation.skill;
  const difficulty = evaluation.difficulty;
  const skillProgress = evaluation.skill_progress;

  // Determine score level
  const getScoreLevel = (score) => {
    if (score >= 80) return { label: 'Excellent', color: 'green', icon: TrendingUp };
    if (score >= 60) return { label: 'Good', color: 'blue', icon: Minus };
    if (score >= 40) return { label: 'Fair', color: 'yellow', icon: Minus };
    return { label: 'Needs Improvement', color: 'red', icon: TrendingDown };
  };

  const scoreLevel = getScoreLevel(score);

  // Color classes
  const colorClasses = {
    green: {
      bg: 'bg-green-100 dark:bg-green-900/20',
      text: 'text-green-800 dark:text-green-400',
      border: 'border-green-200 dark:border-green-800',
      progress: 'bg-green-600',
    },
    blue: {
      bg: 'bg-blue-100 dark:bg-blue-900/20',
      text: 'text-blue-800 dark:text-blue-400',
      border: 'border-blue-200 dark:border-blue-800',
      progress: 'bg-blue-600',
    },
    yellow: {
      bg: 'bg-yellow-100 dark:bg-yellow-900/20',
      text: 'text-yellow-800 dark:text-yellow-400',
      border: 'border-yellow-200 dark:border-yellow-800',
      progress: 'bg-yellow-600',
    },
    red: {
      bg: 'bg-red-100 dark:bg-red-900/20',
      text: 'text-red-800 dark:text-red-400',
      border: 'border-red-200 dark:border-red-800',
      progress: 'bg-red-600',
    },
  };

  const colors = colorClasses[scoreLevel.color];

  return (
    <div className="space-y-4">
      {/* Score Card */}
      <div className={`card border-2 ${colors.border}`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Award className="h-5 w-5" />
            Response Evaluation
          </h3>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${colors.bg} ${colors.text}`}>
            {scoreLevel.label}
          </div>
        </div>

        {/* Score Display */}
        <div className="flex items-center justify-center mb-6">
          <div className="relative">
            <svg className="transform -rotate-90 w-32 h-32">
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                className="text-gray-200 dark:text-gray-700"
              />
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                strokeDasharray={`${2 * Math.PI * 56}`}
                strokeDashoffset={`${2 * Math.PI * 56 * (1 - score / 100)}`}
                className={colors.text}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-gray-900 dark:text-white">
                {score}
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                / 100
              </span>
            </div>
          </div>
        </div>

        {/* Details */}
        {skill && (
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Skill</p>
              <p className="font-medium text-gray-900 dark:text-white">{skill}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Difficulty</p>
              <p className="font-medium text-gray-900 dark:text-white capitalize">{difficulty}</p>
            </div>
          </div>
        )}
      </div>

      {/* Skill Progress */}
      {skillProgress && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 dark:text-white mb-4">
            Skill Progress: {skill}
          </h4>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">Questions Answered</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {skillProgress.questions_asked}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">Total Score</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {skillProgress.total_score?.toFixed(1)}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">Average Performance</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {skillProgress.percentage?.toFixed(1)}%
              </span>
            </div>

            {/* Progress Bar */}
            <div className="pt-2">
              <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                <span>Progress</span>
                <span>{skillProgress.percentage?.toFixed(0)}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    scoreLevel.color === 'green' ? 'bg-green-600' :
                    scoreLevel.color === 'blue' ? 'bg-blue-600' :
                    scoreLevel.color === 'yellow' ? 'bg-yellow-600' :
                    'bg-red-600'
                  }`}
                  style={{ width: `${Math.min(skillProgress.percentage || 0, 100)}%` }}
                />
              </div>
            </div>

            {/* Status Badge */}
            <div className="pt-2">
              <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${
                skillProgress.status === 'completed'
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                  : skillProgress.status === 'in_progress'
                  ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
                  : skillProgress.status === 'failed'
                  ? 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                  : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400'
              }`}>
                {skillProgress.status === 'completed' ? (
                  <CheckCircle className="h-3 w-3" />
                ) : skillProgress.status === 'failed' ? (
                  <XCircle className="h-3 w-3" />
                ) : null}
                {skillProgress.status}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Feedback */}
      {evaluation.feedback && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
            Feedback
          </h4>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {evaluation.feedback}
          </p>
        </div>
      )}
    </div>
  );
};

export default EvaluationResults;
