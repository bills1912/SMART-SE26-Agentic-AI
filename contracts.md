# AI Policy & Insight Generator - API Contracts

## Overview
This document defines the API contracts between the React TypeScript frontend and the FastAPI backend with web scraping capabilities.

## Backend API Endpoints

### Base URL
- Development: `http://localhost:8001/api`
- Production: Uses `REACT_APP_BACKEND_URL` from frontend environment

### Authentication
- Currently no authentication required
- Future: JWT tokens for user sessions

---

## Core Endpoints

### 1. Health Check
```
GET /api/
Response: {
  "message": "AI Policy & Insight Generator API is running",
  "version": "1.0.0"
}
```

### 2. Policy Analysis (Main Chat Endpoint)
```
POST /api/chat
Content-Type: application/json

Request Body:
{
  "message": "string (user's policy question)",
  "session_id": "string (optional - for continuing conversation)",
  "include_visualizations": true,
  "include_insights": true, 
  "include_policies": true
}

Response:
{
  "message": "string (AI analysis response)",
  "session_id": "string (chat session identifier)",
  "visualizations": [
    {
      "id": "string",
      "type": "chart|graph|map|table",
      "title": "string",
      "config": {}, // ECharts configuration object
      "data": {},
      "created_at": "datetime"
    }
  ],
  "insights": [
    "string (key insight 1)",
    "string (key insight 2)"
  ],
  "policies": [
    {
      "id": "string",
      "title": "string",
      "description": "string", 
      "priority": "high|medium|low",
      "category": "economic|social|environmental|healthcare|education|security|technology",
      "impact": "string",
      "implementation_steps": ["step1", "step2"],
      "created_at": "datetime"
    }
  ],
  "supporting_data_count": 42
}
```

### 3. Chat Sessions Management
```
GET /api/sessions
Response: [
  {
    "id": "string",
    "title": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "message_count": 5
  }
]

GET /api/sessions/{session_id}
Response: {
  "id": "string", 
  "title": "string",
  "messages": [
    {
      "id": "string",
      "sender": "user|ai",
      "content": "string",
      "timestamp": "datetime",
      "visualizations": [...],
      "insights": [...],
      "policies": [...]
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. Data Scraping Endpoints
```
POST /api/scrape/trigger
Response: {
  "message": "Scraping triggered",
  "status": "started|in_progress"
}

GET /api/data/recent?limit=50&category=economic
Response: [
  {
    "id": "string",
    "source": "government|economic|news|academic",
    "url": "string",
    "title": "string", 
    "content": "string",
    "category": "economic|social|environmental|healthcare|education|security|technology",
    "scraped_at": "datetime",
    "relevance_score": 0.85
  }
]

GET /api/data/search?query=healthcare&limit=50
Response: [...] // Same as recent data
```

### 5. Statistics & Health
```
GET /api/health
Response: {
  "status": "healthy",
  "database": "connected",
  "ai_analyzer": "ready", 
  "scraping_status": "idle|in_progress",
  "last_scraping": "datetime",
  "data_stats": {
    "scraped_data_count": 1250,
    "chat_sessions_count": 45,
    "chat_messages_count": 230
  }
}

GET /api/stats  
Response: {
  "scraped_data_count": 1250,
  "chat_sessions_count": 45, 
  "chat_messages_count": 230,
  "policy_insights_count": 67,
  "policy_recommendations_count": 34,
  "scraping_status": "idle",
  "last_scraping": "datetime"
}
```

---

## Frontend Integration

### Current Mock Data Replacement

#### 1. Chat Interface (`/frontend/src/components/ChatInterface.tsx`)
**Replace:** `generateMockResponse()` function
**With:** API call to `/api/chat`

```typescript
const handleSendMessage = async () => {
  const response = await axios.post(`${BACKEND_URL}/api/chat`, {
    message: inputMessage.trim(),
    session_id: currentSessionId,
    include_visualizations: true,
    include_insights: true,
    include_policies: true
  });
  
  const aiResponse: ChatMessage = {
    id: response.data.session_id + "_" + Date.now(),
    sender: 'ai',
    content: response.data.message,
    timestamp: new Date(),
    visualizations: response.data.visualizations,
    insights: response.data.insights,
    policies: response.data.policies
  };
}
```

#### 2. Mock Data Files (`/frontend/src/data/mock.ts`)
**Replace:** Static mock data
**With:** API integration service

```typescript
// Remove: mockChatMessages, mockVisualizations, mockPolicyRecommendations
// Add: API service functions

export class PolicyAPIService {
  private baseURL = process.env.REACT_APP_BACKEND_URL + '/api';
  
  async sendMessage(message: string, sessionId?: string): Promise<PolicyAnalysisResponse> {
    // Implementation
  }
  
  async getSessions(): Promise<ChatSession[]> {
    // Implementation  
  }
  
  async getSession(sessionId: string): Promise<ChatSession> {
    // Implementation
  }
}
```

### Error Handling

```typescript
try {
  const response = await apiService.sendMessage(message);
  // Handle success
} catch (error) {
  if (error.response?.status === 500) {
    // Show fallback message with limited functionality
    showToast("AI service temporarily unavailable. Using cached insights.");
  } else {
    showToast("Connection error. Please try again.");
  }
}
```

### Loading States

```typescript
const [isLoading, setIsLoading] = useState(false);
const [scrapingStatus, setScrapingStatus] = useState<'idle' | 'in_progress'>('idle');

// Show different loading messages based on state
{isLoading && (
  <div className="flex items-center gap-2">
    <Loader2 className="h-4 w-4 animate-spin" />
    <span>
      {scrapingStatus === 'in_progress' 
        ? 'Gathering latest policy data...' 
        : 'Analyzing policy scenario...'}
    </span>
  </div>
)}
```

---

## Database Schema

### MongoDB Collections

#### 1. `scraped_data`
```javascript
{
  _id: ObjectId,
  id: String,
  source: String, // government|economic|news|academic
  url: String,
  title: String,
  content: String,
  metadata: Object,
  scraped_at: Date,
  processed: Boolean,
  category: String,
  tags: Array,
  relevance_score: Number
}
```

#### 2. `chat_sessions`
```javascript
{
  _id: ObjectId,
  id: String,
  title: String,
  created_at: Date,
  updated_at: Date,
  metadata: Object
}
```

#### 3. `chat_messages`
```javascript
{
  _id: ObjectId,
  id: String,
  session_id: String,
  sender: String, // user|ai
  content: String,
  visualizations: Array,
  insights: Array,
  policies: Array,
  timestamp: Date
}
```

#### 4. `policy_recommendations`
```javascript
{
  _id: ObjectId,
  id: String,
  title: String,
  description: String,
  priority: String,
  category: String,
  impact: String,
  implementation_steps: Array,
  supporting_insights: Array,
  supporting_data_ids: Array,
  created_at: Date
}
```

---

## Implementation Steps

### Phase 1: Backend Integration ✅
- [x] Set up FastAPI server with comprehensive endpoints
- [x] Implement MongoDB integration with proper models
- [x] Add web scraping capabilities for multiple sources
- [x] Integrate Emergent LLM key for AI analysis
- [x] Create visualization generation system

### Phase 2: Frontend Integration
- [ ] Replace mock data with API service calls
- [ ] Update chat interface to use real endpoints
- [ ] Add session management functionality
- [ ] Implement error handling and loading states
- [ ] Add real-time data scraping status

### Phase 3: Testing & Optimization
- [ ] Test end-to-end policy analysis workflow
- [ ] Verify visualization rendering with real data
- [ ] Test web scraping and data storage
- [ ] Performance optimization
- [ ] Error handling edge cases

---

## Data Sources Being Scraped

1. **Government Sources:**
   - White House press releases and statements
   - Congressional records and legislation
   - Federal agency publications

2. **Economic Sources:**
   - World Bank economic indicators
   - Federal Reserve economic data
   - National statistics databases

3. **News Sources:**
   - Policy-focused news articles
   - Political analysis and commentary
   - Breaking policy developments

4. **Academic Sources:**
   - Think tank research and reports
   - Policy research publications
   - Academic policy analysis

## Security & Performance Considerations

- Rate limiting for scraping operations
- Database connection pooling
- Async processing for heavy operations
- Error recovery and retry mechanisms
- Data validation and sanitization
- CORS configuration for frontend integration