from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class DataSource(str, Enum):
    GOVERNMENT = "government"
    ECONOMIC = "economic"
    NEWS = "news"
    ACADEMIC = "academic"
    SOCIAL_MEDIA = "social_media"


class PolicyCategory(str, Enum):
    ECONOMIC = "economic"
    SOCIAL = "social"
    ENVIRONMENTAL = "environmental"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    SECURITY = "security"
    TECHNOLOGY = "technology"


class ScrapedData(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    source: DataSource
    url: str
    title: str
    content: str
    metadata: Dict[str, Any] = {}
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = False
    category: Optional[PolicyCategory] = None
    tags: List[str] = []
    relevance_score: Optional[float] = None


class VisualizationConfig(BaseModel):
    id: str
    type: str  # 'chart', 'graph', 'map', 'table'
    title: str
    config: Dict[str, Any]  # ECharts/D3 configuration
    data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyInsight(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    text: str
    confidence_score: float = 0.0
    supporting_data_ids: List[str] = []
    category: PolicyCategory
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    title: str
    description: str
    priority: str  # 'high', 'medium', 'low'
    category: PolicyCategory
    impact: str
    implementation_steps: List[str]
    supporting_insights: List[str] = []
    supporting_data_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    session_id: str
    sender: str  # 'user' or 'ai'
    content: str
    visualizations: Optional[List[VisualizationConfig]] = []
    insights: Optional[List[str]] = []
    policies: Optional[List[PolicyRecommendation]] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    user_id: Optional[str] = None  # NEW: Link session to user (None for legacy/anonymous)
    title: str = "Policy Analysis Session"
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class PolicyAnalysisRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    include_visualizations: bool = True
    include_insights: bool = True
    include_policies: bool = True


class PolicyAnalysisResponse(BaseModel):
    message: str
    session_id: str
    visualizations: Optional[List[VisualizationConfig]] = []
    insights: Optional[List[str]] = []
    policies: Optional[List[PolicyRecommendation]] = []
    supporting_data_count: int = 0
    
class SensusData(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    provinsi: str
    kode_provinsi: str
    tahun: int
    data_kbli: Dict[str, int]  # {'B': 1234, 'C': 5678, ...}
    total_usaha: int
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueryIntent(BaseModel):
    intent_type: str  # 'comparison', 'ranking', 'trend', 'distribution'
    provinces: List[str] = []
    sectors: List[str] = []  # Kode KBLI
    aggregation: str = 'sum'  # 'sum', 'average', 'count'