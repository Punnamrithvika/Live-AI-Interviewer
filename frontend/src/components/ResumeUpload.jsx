import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { uploadResume } from '../services/api';

const ResumeUpload = ({ onUploadSuccess }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // 'success', 'error', null
  const [errorMessage, setErrorMessage] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt'];

  const validateFile = (selectedFile) => {
    if (!selectedFile) {
      setErrorMessage('Please select a file');
      return false;
    }

    const fileName = selectedFile.name.toLowerCase();
    const isValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));

    if (!isValidExtension) {
      setErrorMessage('Invalid file type. Please upload PDF, DOCX, or TXT');
      return false;
    }

    if (selectedFile.size > 10 * 1024 * 1024) { // 10MB limit
      setErrorMessage('File size must be less than 10MB');
      return false;
    }

    return true;
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (validateFile(selectedFile)) {
      setFile(selectedFile);
      setUploadStatus(null);
      setErrorMessage('');
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (validateFile(droppedFile)) {
        setFile(droppedFile);
        setUploadStatus(null);
        setErrorMessage('');
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setErrorMessage('Please select a file first');
      return;
    }

    setUploading(true);
    setUploadStatus(null);
    setErrorMessage('');

    try {
      const result = await uploadResume(file);
      
      if (result.success) {
        setUploadStatus('success');
        if (onUploadSuccess) {
          onUploadSuccess({
            filePath: result.file_path,
            data: result.data,
          });
        }
      } else {
        setUploadStatus('error');
        setErrorMessage(result.message || 'Upload failed');
      }
    } catch (error) {
      setUploadStatus('error');
      setErrorMessage(error.message || 'Failed to upload resume');
    } finally {
      setUploading(false);
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const clearFile = () => {
    setFile(null);
    setUploadStatus(null);
    setErrorMessage('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="card">
        <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">
          Upload Your Resume
        </h2>

        {/* Drag & Drop Area */}
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            dragActive
              ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
              : 'border-gray-300 dark:border-gray-600'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept={allowedExtensions.join(',')}
            onChange={handleFileChange}
          />

          {!file ? (
            <div className="space-y-4">
              <Upload className="mx-auto h-12 w-12 text-gray-400" />
              <div>
                <p className="text-lg text-gray-700 dark:text-gray-300">
                  Drag and drop your resume here
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  or
                </p>
              </div>
              <button
                onClick={handleButtonClick}
                className="btn-primary"
              >
                Browse Files
              </button>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Supported formats: PDF, DOCX, TXT (Max 10MB)
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <FileText className="mx-auto h-12 w-12 text-primary-600" />
              <div>
                <p className="text-lg font-medium text-gray-900 dark:text-white">
                  {file.name}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {(file.size / 1024).toFixed(2)} KB
                </p>
              </div>

              <div className="flex gap-3 justify-center">
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="animate-spin h-4 w-4" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4" />
                      Upload
                    </>
                  )}
                </button>
                <button
                  onClick={clearFile}
                  disabled={uploading}
                  className="btn-secondary disabled:opacity-50"
                >
                  Clear
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Status Messages */}
        {uploadStatus === 'success' && (
          <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
            <p className="text-black dark:text-black">
              Resume uploaded successfully!
            </p>
          </div>
        )}

        {uploadStatus === 'error' && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-3">
            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
            <p className="text-red-800 dark:text-red-200">
              {errorMessage}
            </p>
          </div>
        )}

        {errorMessage && !uploadStatus && (
          <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg flex items-center gap-3">
            <XCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
            <p className="text-yellow-800 dark:text-yellow-200">
              {errorMessage}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResumeUpload;
