import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, Loader2, AlertCircle } from 'lucide-react';
import { sendMessage } from '../services/api';
import useWebSocket from '../hooks/useWebSocket';

const ChatInterface = ({ sessionId, firstQuestion }) => {
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  
  const { isConnected, messages: wsMessages, sendAnswer, error: wsError } = useWebSocket(sessionId);

  // Initialize with first question if provided
  useEffect(() => {
    if (firstQuestion && !currentQuestion) {
      setCurrentQuestion(firstQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstQuestion]);

  // Scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentQuestion]);

  // Handle WebSocket messages
  useEffect(() => {
    if (wsMessages.length > 0) {
      const lastMessage = wsMessages[wsMessages.length - 1];
      
      if (lastMessage.type === 'question') {
        // Check if data exists and has a question
        const questionData = lastMessage.data;
        if (questionData && questionData.question) {
          setCurrentQuestion(questionData.question);
        } else if (questionData === null) {
          // Interview completed - no more questions
          setCurrentQuestion('Thank you! The interview has been completed. You can now view your evaluation results.');
        } else {
          console.warn('Question data missing:', lastMessage);
        }
        setIsTyping(false);
        setIsSending(false);
      } else if (lastMessage.type === 'evaluation') {
        // Evaluation received - just log it
        console.log('Evaluation received:', lastMessage.data);
        setIsSending(false);
      } else if (lastMessage.type === 'typing') {
        setIsTyping(true);
      } else if (lastMessage.type === 'error') {
        setError(lastMessage.message);
        setIsTyping(false);
        setIsSending(false);
      } else if (lastMessage.type === 'pong') {
        // Heartbeat response - ignore
      }
    }
  }, [wsMessages]);

  // Handle sending message
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isSending) return;

    const userAnswer = inputMessage.trim();
    
    // Clear input immediately
    setInputMessage('');
    setIsSending(true);
    setError(null);
    setIsTyping(true);

    try {
      if (isConnected) {
        // Use WebSocket for real-time communication
        sendAnswer(userAnswer);
      } else {
        // Fallback to HTTP API
        const response = await sendMessage(sessionId, userAnswer);
        
        if (response.success) {
          // Add evaluation if present
          if (response.evaluation) {
            console.log('Evaluation:', response.evaluation);
          }
          
          // Update to next question
          if (response.next_question) {
            setCurrentQuestion(response.next_question.question);
          }
        }
        setIsSending(false);
        setIsTyping(false);
      }
    } catch (err) {
      setError(err.message || 'Failed to send message');
      setIsSending(false);
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Interview Response
          </h2>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {isConnected ? 'Connected' : 'Offline'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {!currentQuestion && (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Waiting for the interview to begin...</p>
          </div>
        )}

        {currentQuestion && (
          <div className="flex justify-start">
            <div className="flex gap-3 max-w-full">
              {/* Avatar */}
              <div className="flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center bg-gray-200 dark:bg-gray-700">
                <Bot className="h-5 w-5 text-gray-600 dark:text-gray-300" />
              </div>

              {/* Question Display */}
              <div className="rounded-lg px-6 py-4 bg-amber-50 dark:bg-gray-700 text-gray-900 dark:text-white flex-1">
                <p className="text-lg font-medium mb-2 text-amber-900 dark:text-amber-300">Current Question:</p>
                <p className="text-base whitespace-pre-wrap">{currentQuestion}</p>
              </div>
            </div>
          </div>
        )}

        {/* Typing Indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="flex gap-3">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                <Bot className="h-5 w-5 text-gray-600 dark:text-gray-300" />
              </div>
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error Message */}
      {(error || wsError) && (
        <div className="mx-6 mb-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-800 dark:text-red-200">{error || wsError}</p>
        </div>
      )}

      {/* Input Area */}
      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-3">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your answer here..."
            className="input-field resize-none"
            rows="2"
            disabled={isSending}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isSending}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 px-6"
          >
            {isSending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
};

export default ChatInterface;
