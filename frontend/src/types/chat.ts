export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  content: string;
  timestamp: Date;
  visualizations?: VisualizationData[];
  insights?: string[];
  policies?: PolicyRecommendation[];
}

export interface VisualizationData {
  id: string;
  type: 'chart' | 'graph' | 'map' | 'table';
  title: string;
  config: any; // ECharts configuration
  data: any;
}

export interface PolicyRecommendation {
  id: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  category: string;
  impact: string;
  implementation: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ApiResponse {
  message: string;
  visualizations?: VisualizationData[];
  insights?: string[];
  policies?: PolicyRecommendation[];
}