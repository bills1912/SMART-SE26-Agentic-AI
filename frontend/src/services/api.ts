import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { ChatMessage, ChatSession, PolicyAnalysisRequest, PolicyAnalysisResponse } from '../types/chat';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

// Timeout configurations
const TIMEOUTS = {
  default: 60000,      // 60 seconds for general requests
  auth: 45000,         // 45 seconds for auth requests
  chat: 120000,        // 120 seconds for chat/AI requests (can be slow)
  health: 10000,       // 10 seconds for health check
};

class PolicyAPIService {
  private api = axios.create({
    baseURL: API_BASE,
    timeout: TIMEOUTS.default,
    withCredentials: true,  // CRITICAL: Send cookies with requests
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Retry configuration
  private maxRetries = 2;
  private retryDelay = 1000; // 1 second

  constructor() {
    // Add request interceptor for logging
    this.api.interceptors.request.use((config) => {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
      return config;
    });

    // Add response interceptor for error handling and retry
    this.api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const config = error.config as AxiosRequestConfig & { _retryCount?: number };
        
        // Don't retry if no config or already retried max times
        if (!config || (config._retryCount || 0) >= this.maxRetries) {
          console.error('API Error:', error.response?.data || error.message);
          return Promise.reject(error);
        }

        // Only retry on network errors or 5xx errors
        const shouldRetry = 
          !error.response || // Network error
          (error.response.status >= 500 && error.response.status < 600); // Server error

        if (shouldRetry) {
          config._retryCount = (config._retryCount || 0) + 1;
          console.log(`Retrying request (${config._retryCount}/${this.maxRetries})...`);
          
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, this.retryDelay * config._retryCount!));
          
          return this.api(config);
        }

        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  async sendMessage(
    message: string, 
    sessionId?: string,
    options = {
      include_visualizations: true,
      include_insights: true,
      include_policies: true
    }
  ): Promise<PolicyAnalysisResponse> {
    const request: PolicyAnalysisRequest = {
      message,
      session_id: sessionId,
      ...options
    };

    const response = await this.api.post<PolicyAnalysisResponse>('/chat', request, {
      timeout: TIMEOUTS.chat // Use longer timeout for chat
    });
    return response.data;
  }

  async getSessions(): Promise<ChatSession[]> {
    const response = await this.api.get<ChatSession[]>('/sessions');
    return response.data;
  }

  async getSession(sessionId: string): Promise<ChatSession> {
    const response = await this.api.get<ChatSession>(`/sessions/${sessionId}`);
    return response.data;
  }

  async triggerScraping(): Promise<{ message: string; status: string }> {
    const response = await this.api.post('/scrape/trigger');
    return response.data;
  }

  async getRecentData(limit = 50, category?: string) {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    if (category) {
      params.append('category', category);
    }

    const response = await this.api.get(`/data/recent?${params.toString()}`);
    return response.data;
  }

  async searchData(query: string, limit = 50) {
    const params = new URLSearchParams();
    params.append('query', query);
    params.append('limit', limit.toString());

    const response = await this.api.get(`/data/search?${params.toString()}`);
    return response.data;
  }

  async getHealth() {
    const response = await this.api.get('/health', {
      timeout: TIMEOUTS.health
    });
    return response.data;
  }

  async getStats() {
    const response = await this.api.get('/stats');
    return response.data;
  }
  
  async generateReport(sessionId: string, format: 'pdf' | 'docx') {
    const response = await this.api.get(`/report/${sessionId}/${format}`, {
      responseType: 'blob',
      timeout: TIMEOUTS.chat // Reports can take time
    });
    return response;
  }

  // Utility method to check if backend is available
  async isBackendAvailable(): Promise<boolean> {
    try {
      await this.api.get('/', {
        timeout: TIMEOUTS.health
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  // Generic HTTP methods for authentication and other uses
  async get<T = any>(url: string, config?: any): Promise<{ data: T }> {
    const timeout = url.includes('/auth/') ? TIMEOUTS.auth : TIMEOUTS.default;
    const response = await this.api.get<T>(url, { timeout, ...config });
    return response;
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    const timeout = url.includes('/auth/') ? TIMEOUTS.auth : TIMEOUTS.default;
    const response = await this.api.post<T>(url, data, { timeout, ...config });
    return response;
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    const response = await this.api.put<T>(url, data, config);
    return response;
  }

  async delete<T = any>(url: string, config?: any): Promise<{ data: T }> {
    const response = await this.api.delete<T>(url, config);
    return response;
  }
}

// Export singleton instance
export const apiService = new PolicyAPIService();
export default apiService;