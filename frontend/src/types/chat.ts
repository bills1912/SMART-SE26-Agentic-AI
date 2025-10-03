export interface ChatMessage {
  id: string;
  session_id: string;
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
  created_at: string;
}

export interface PolicyRecommendation {
  id: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  category: string;
  impact: string;
  implementation_steps: string[];
  supporting_insights: string[];
  supporting_data_ids: string[];
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  metadata?: any;
}

export interface PolicyAnalysisRequest {
  message: string;
  session_id?: string;
  include_visualizations?: boolean;
  include_insights?: boolean;
  include_policies?: boolean;
}

export interface PolicyAnalysisResponse {
  message: string;
  session_id: string;
  visualizations?: VisualizationData[];
  insights?: string[];
  policies?: PolicyRecommendation[];
  supporting_data_count: number;
}