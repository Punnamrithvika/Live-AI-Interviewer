# AI Interviewer - React Frontend

Modern React frontend for the AI Interviewer application with Tailwind CSS styling and real-time WebSocket communication.

## Features

- 📤 **Resume Upload**: Drag-and-drop file upload with validation (PDF, DOCX, TXT)
- 💬 **Real-time Chat**: WebSocket-powered instant messaging with typing indicators
- 📊 **Live Dashboard**: Real-time interview progress and skill evaluation tracking
- 🎯 **Evaluation Display**: Visual score representation with detailed feedback
- 🌓 **Dark Mode**: Full dark mode support with system preference detection
- 📱 **Responsive**: Mobile-first design that works on all screen sizes

## Tech Stack

- **React 18**: Modern React with hooks
- **React Router 6**: Client-side routing
- **Tailwind CSS**: Utility-first CSS framework
- **Axios**: HTTP client for API calls
- **WebSocket**: Real-time bidirectional communication
- **Lucide React**: Beautiful icon library

## Prerequisites

- Node.js 16+ and npm
- Backend API server running on `http://localhost:8000`

## Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

## Configuration

Create a `.env` file in the `frontend` directory:

```env
REACT_APP_API_URL=http://localhost:8000
```

## Running the Application

### Development Mode

```bash
npm start
```

The app will open at [http://localhost:3000](http://localhost:3000)

### Production Build

```bash
npm run build
```

Builds the app for production to the `build` folder.

## Project Structure

```
frontend/
├── public/
│   └── index.html          # HTML template
├── src/
│   ├── components/
│   │   ├── ResumeUpload.jsx       # File upload component
│   │   ├── ChatInterface.jsx      # Real-time chat UI
│   │   ├── Dashboard.jsx          # Interview dashboard
│   │   └── EvaluationResults.jsx  # Score visualization
│   ├── services/
│   │   └── api.js                 # API service layer
│   ├── hooks/
│   │   └── useWebSocket.js        # WebSocket custom hook
│   ├── App.jsx                    # Main app component
│   ├── index.js                   # Entry point
│   └── index.css                  # Tailwind styles
├── .env                    # Environment variables
├── package.json           # Dependencies
├── tailwind.config.js     # Tailwind configuration
└── postcss.config.js      # PostCSS configuration
```

## API Integration

The frontend communicates with the backend through:

### HTTP Endpoints
- `POST /api/upload-resume` - Upload resume file
- `POST /api/start-interview` - Start new session
- `POST /api/send-message` - Send candidate answer
- `GET /api/interview-status/:id` - Get session status
- `DELETE /api/end-interview/:id` - End session

### WebSocket
- `WS /ws/chat/:sessionId` - Real-time chat communication

## Usage Flow

1. **Upload Resume** (Optional)
   - Drag and drop or browse for resume file
   - Supports PDF, DOCX, TXT formats
   - Max file size: 10MB

2. **Setup Interview**
   - Enter candidate name and job title
   - Add skills with difficulty levels
   - Click "Start Interview"

3. **Conduct Interview**
   - Real-time Q&A through chat interface
   - View live evaluation scores
   - Monitor skill progress on dashboard

4. **End Interview**
   - Click "End Interview" button
   - Review final summary

## Component Details

### ResumeUpload
- Drag-and-drop file upload
- File type validation
- Upload progress indication
- Success/error feedback

### ChatInterface
- Message history display
- Real-time message sending
- Typing indicators
- WebSocket fallback to HTTP
- Auto-scroll to latest message

### Dashboard
- Candidate information
- Interview statistics
- Skill-by-skill progress bars
- Real-time status updates

### EvaluationResults
- Circular progress indicator
- Score level badges (Excellent/Good/Fair/Poor)
- Skill progress tracking
- Detailed feedback display

## Customization

### Colors
Edit `tailwind.config.js` to customize the color scheme:

```js
theme: {
  extend: {
    colors: {
      primary: { /* your colors */ },
    },
  },
}
```

### Dark Mode
Dark mode is enabled by default. Toggle button in top-right corner.

## Troubleshooting

### Backend Connection Issues
- Ensure backend API is running on port 8000
- Check CORS configuration in `api.py`
- Verify `.env` file has correct API URL

### WebSocket Connection Failed
- WebSocket URL is auto-generated from HTTP URL
- Falls back to HTTP polling if WebSocket fails
- Check browser console for connection errors

### Build Errors
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

## Development Tips

### Hot Reload
Changes to React components auto-reload in development mode.

### API Proxy
The `package.json` includes a proxy configuration for local development.

### Console Logging
API requests and WebSocket messages are logged to console in development.

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Performance

- Lazy loading for components
- Optimized re-renders with React.memo
- Debounced API calls
- Efficient WebSocket message handling

## License

Same as parent project
