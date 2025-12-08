import axios from 'axios';
import { ChatMessage, ChatSession, PolicyAnalysisRequest, PolicyAnalysisResponse } from '../types/chat';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

class PolicyAPIService {
  private api = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
    withCredentials: true,  // CRITICAL: Send cookies with requests
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    // Add request interceptor for logging
    this.api.interceptors.request.use((config) => {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
      return config;
    });

    // Add response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
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

    const response = await this.api.post<PolicyAnalysisResponse>('/chat', request);
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
    const response = await this.api.get('/health');
    return response.data;
  }

  async getStats() {
    const response = await this.api.get('/stats');
    return response.data;
  }

  // Utility method to check if backend is available
  async isBackendAvailable(): Promise<boolean> {
    try {
      await this.api.get('/');
      return true;
    } catch (error) {
      return false;
    }
  }

  // Generic HTTP methods for authentication and other uses
  async get<T = any>(url: string, config?: any): Promise<{ data: T }> {
    const response = await this.api.get<T>(url, config);
    return response;
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    const response = await this.api.post<T>(url, data, config);
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