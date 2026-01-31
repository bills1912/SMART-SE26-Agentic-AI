# SMART SE2026 Agentic AI

![Version](https://img.shields.io/badge/version-0.1.0-orange)
![React](https://img.shields.io/badge/React-19.0.0-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.4.5-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**AI-Powered Census Analysis & Policy Insight Generator for Indonesia's Economic Survey 2026**

SMART SE2026 is an intelligent agentic AI assistant designed to help analyze census data, generate insights, and create policy recommendations for Indonesia's Economic Survey 2026 (Sensus Ekonomi 2026).

---

## 🌟 Features

### Core Capabilities
- **🤖 AI-Powered Chat Interface** - Natural language interaction with Claude AI for census data analysis
- **📊 Data Visualizations** - Interactive charts and graphs powered by ECharts
- **💡 Intelligent Insights** - Automated key findings extraction from census data
- **📋 Policy Recommendations** - AI-generated policy suggestions with implementation steps
- **📄 Report Generation** - Export analysis as PDF, DOCX, or HTML reports

### User Experience
- **🎨 Modern UI/UX** - Clean, responsive interface with dark mode support
- **💬 Multi-Session Management** - Organize conversations with automatic chat history
- **🎙️ Voice Input** - Indonesian voice recognition for hands-free interaction
- **🔐 Secure Authentication** - Email/password and Google OAuth 2.0 login
- **🌐 Multi-Language Support** - Optimized for Indonesian and English

### Technical Features
- **📱 Responsive Design** - Works seamlessly on desktop, tablet, and mobile
- **⚡ Real-time Updates** - Live data synchronization across sessions
- **🔄 Session Persistence** - Automatic save and restore of conversations
- **🎯 Smart Routing** - Deep-linked chat sessions with URL-based navigation
- **♻️ Optimistic Updates** - Instant UI feedback with background synchronization

---

## 🏗️ Architecture

### Tech Stack

**Frontend:**
- React 19.0.0 with TypeScript
- React Router v6 for navigation
- Tailwind CSS + shadcn/ui components
- ECharts for data visualization
- Axios for API communication

**Backend (Expected):**
- FastAPI or similar Python framework
- AI/ML model integration (Claude API)
- PostgreSQL for data storage
- Session management with cookies

### Project Structure

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── components/        # React components
│   │   ├── ui/           # shadcn/ui components
│   │   ├── ChatInterface.tsx
│   │   ├── ChatSidebar.tsx
│   │   ├── MessageBubble.tsx
│   │   └── ...
│   ├── contexts/         # React Context providers
│   │   ├── AuthContext.tsx
│   │   ├── ChatContext.tsx
│   │   └── ThemeContext.tsx
│   ├── pages/            # Page components
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   └── AuthCallback.tsx
│   ├── services/         # API services
│   │   └── api.ts
│   ├── types/            # TypeScript types
│   │   └── chat.ts
│   └── App.tsx           # Main application
└── package.json
```

---

## 🚀 Getting Started

### Prerequisites

- Node.js 16.x or higher
- npm or yarn
- Backend server running (see backend documentation)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the frontend directory:
   ```env
   REACT_APP_BACKEND_URL=https://your-backend-url.com
   # or for local development:
   # REACT_APP_BACKEND_URL=http://localhost:8000
   ```

4. **Start development server**
   ```bash
   npm start
   ```

   The application will open at `http://localhost:3000`

### Building for Production

```bash
npm run build
```

The optimized production build will be created in the `build/` directory.

---

## 📖 Usage Guide

### Authentication

**Email/Password Registration:**
1. Navigate to `/register`
2. Fill in your name, email, and password
3. Click "Create account"

**Google OAuth:**
1. Click "Continue with Google" on login/register page
2. Authorize with your Google account
3. You'll be redirected back and logged in automatically

### Chat Interface

**Starting a New Conversation:**
1. Click "New Chat" button or navigate to `/dashboard`
2. Type your question about census data or policy analysis
3. Press Enter or click Send

**Working with Visualizations:**
- Click on "Data Visualizations" button to view charts
- Charts are interactive - hover for details, zoom, pan
- Export charts as images from the modal

**Viewing Insights & Policies:**
- Click "Key Insights" to see AI-generated findings
- Click "Policy Recommendations" for suggested actions
- Each policy includes priority level and implementation steps

**Generating Reports:**
1. Click "Download Full Report" button
2. Choose format: PDF, Word (DOCX), or HTML
3. Report includes all visualizations, insights, and policies

### Session Management

**Accessing Chat History:**
- Click the sidebar toggle (≡) to view all conversations
- Sessions are automatically titled based on first message
- Click any session to resume that conversation

**Deleting Conversations:**
- Hover over a session and click the trash icon
- Use bulk selection mode to delete multiple sessions
- "Delete All History" removes all conversations

### Voice Input

1. Click the microphone icon in the input area
2. Speak your question in Indonesian or English
3. Speech is automatically transcribed to text
4. Edit if needed, then send

---

## 🎨 Customization

### Theme

The app supports light, dark, and system-synced themes:
- Click the theme toggle button in the header
- Cycles through: Light → Dark → System
- Preference is saved to localStorage

### Styling

The project uses Tailwind CSS with a custom color scheme:
- Primary: Orange/Red gradient
- Modify colors in `tailwind.config.js`
- Custom components in `src/components/ui/`

---

## 🔧 Configuration

### API Integration

The app communicates with the backend via `src/services/api.ts`:

```typescript
// Configure timeouts
const TIMEOUTS = {
  default: 60000,    // 60s for general requests
  chat: 120000,      // 120s for AI responses
  report: 180000,    // 180s for report generation
};
```

### Environment Variables

```env
# Backend URL (required)
REACT_APP_BACKEND_URL=https://api.example.com

# Optional: Vite-style (for future migration)
VITE_BACKEND_URL=https://api.example.com
```

---

## 📊 Key Components

### ChatContext

Manages chat sessions and messages:
- `currentSession` - Active conversation
- `sessions` - All user chat sessions
- `createNewChat()` - Start new conversation
- `switchToSession(id)` - Load existing session
- `addMessageToCurrentSession(msg)` - Add message
- `deleteSession(id)` - Remove conversation

### AuthContext

Handles user authentication:
- `user` - Current user object
- `isAuthenticated` - Auth status
- `login(email, password)` - Email/password auth
- `loginWithGoogle()` - OAuth flow
- `logout()` - Sign out

### ThemeContext

Controls app appearance:
- `themeMode` - 'light' | 'dark' | 'system'
- `resolvedTheme` - Actual applied theme
- `toggleTheme()` - Cycle through modes

---

## 🔐 Security

### Authentication Flow

1. **Email/Password**: Credentials sent to `/api/auth/login`, session cookie returned
2. **Google OAuth**: 
   - Frontend redirects to `/api/auth/google/login`
   - Backend handles OAuth dance with Google
   - User redirected to `/auth/callback#session_token=...`
   - Frontend extracts token, verifies with backend
   - Session established via cookie

### Session Management

- Sessions stored in HTTP-only cookies (secure)
- User data cached in localStorage for performance
- Auto-logout on token expiration
- CSRF protection via SameSite cookies

---

## 🐛 Troubleshooting

### Common Issues

**"Backend service is currently unavailable"**
- Check backend server is running
- Verify `REACT_APP_BACKEND_URL` is correct
- Check network connectivity

**OAuth login fails**
- Ensure backend OAuth is configured correctly
- Check redirect URIs match in Google Console
- Verify backend URL is accessible

**Charts not displaying**
- Clear browser cache
- Check browser console for errors
- Ensure ECharts library loaded

**Session not persisting**
- Enable cookies in browser
- Check for CORS issues
- Verify backend session configuration

### Debug Mode

Enable verbose logging:
```javascript
// In browser console
localStorage.setItem('debug', 'true');
```

---

## 🧪 Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

---

## 📦 Deployment

### Railway (Recommended)

1. Connect GitHub repository
2. Configure build settings:
   ```
   Build Command: npm run build
   Start Command: npx serve -s build
   ```
3. Add environment variables in Railway dashboard
4. Deploy

### Vercel

```bash
npm install -g vercel
vercel --prod
```

### Docker

```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "3000"]
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Style

- Use TypeScript for type safety
- Follow React best practices
- Use functional components with hooks
- Keep components small and focused
- Write descriptive commit messages

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👥 Authors

- **Development Team** - Initial work and maintenance

---

## 🙏 Acknowledgments

- shadcn/ui for beautiful UI components
- ECharts for powerful data visualizations
- Anthropic's Claude for AI capabilities
- Indonesia's BPS for census data

---

## 📞 Support

For support, please:
- Open an issue on GitHub
- Contact the development team
- Check documentation at `/docs`

---

## 🗺️ Roadmap

- [ ] Multi-language support (full i18n)
- [ ] Advanced data filtering and queries
- [ ] Export to more formats (Excel, CSV)
- [ ] Collaborative features (share sessions)
- [ ] Mobile app version
- [ ] Offline mode support
- [ ] Custom visualization templates
- [ ] API access for developers

---

**Built with ❤️ for Indonesia's Economic Survey 2026**