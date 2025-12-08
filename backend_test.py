#!/usr/bin/env python3
"""
Comprehensive Backend Testing for AI Policy & Insight Generator
Tests all API endpoints, AI integration, database operations, and web scraping functionality
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolicyBackendTester:
    def __init__(self):
        # Get backend URL from frontend .env file
        self.base_url = self._get_backend_url()
        self.session = None
        self.test_results = []
        
    def _get_backend_url(self) -> str:
        """Get backend URL from frontend .env file"""
        try:
            with open('/app/frontend/.env', 'r') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        url = line.split('=', 1)[1].strip()
                        return f"{url}/api"
            return "http://localhost:8001/api"  # fallback
        except Exception as e:
            logger.error(f"Error reading frontend .env: {e}")
            return "http://localhost:8001/api"
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'Content-Type': 'application/json'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def log_test_result(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}: {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'response_data': response_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def test_health_endpoint(self) -> bool:
        """Test GET /api/health endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check required fields
                    required_fields = ['status', 'database', 'ai_analyzer', 'scraping_status', 'data_stats']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        self.log_test_result("Health Check", False, f"Missing fields: {missing_fields}", data)
                        return False
                    
                    # Check if database is connected
                    if data.get('database') != 'connected':
                        self.log_test_result("Health Check", False, f"Database not connected: {data.get('database')}", data)
                        return False
                    
                    self.log_test_result("Health Check", True, f"All systems healthy. Database stats: {data.get('data_stats', {})}", data)
                    return True
                else:
                    self.log_test_result("Health Check", False, f"HTTP {response.status}", await response.text())
                    return False
                    
        except Exception as e:
            self.log_test_result("Health Check", False, f"Exception: {str(e)}")
            return False
    
    async def test_root_endpoint(self) -> bool:
        """Test GET /api/ endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    if 'message' in data and 'version' in data:
                        self.log_test_result("Root Endpoint", True, f"API running: {data['message']}", data)
                        return True
                    else:
                        self.log_test_result("Root Endpoint", False, "Missing required fields", data)
                        return False
                else:
                    self.log_test_result("Root Endpoint", False, f"HTTP {response.status}", await response.text())
                    return False
                    
        except Exception as e:
            self.log_test_result("Root Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_chat_endpoint_basic(self) -> Dict[str, Any]:
        """Test POST /api/chat endpoint with basic policy analysis"""
        try:
            test_request = {
                "message": "What are the economic impacts of renewable energy policies on job creation and GDP growth?",
                "include_visualizations": True,
                "include_insights": True,
                "include_policies": True
            }
            
            async with self.session.post(f"{self.base_url}/chat", json=test_request) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check required response fields
                    required_fields = ['message', 'session_id', 'visualizations', 'insights', 'policies']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        self.log_test_result("Chat Endpoint - Basic", False, f"Missing fields: {missing_fields}", data)
                        return {'success': False, 'session_id': None}
                    
                    # Validate response content
                    if not data.get('message') or len(data['message']) < 50:
                        self.log_test_result("Chat Endpoint - Basic", False, "AI response too short or empty", data)
                        return {'success': False, 'session_id': data.get('session_id')}
                    
                    # Check if AI generated real analysis (not just mock data)
                    message_content = data['message'].lower()
                    if 'mock' in message_content or 'placeholder' in message_content:
                        self.log_test_result("Chat Endpoint - Basic", False, "Response appears to be mock data", data)
                        return {'success': False, 'session_id': data.get('session_id')}
                    
                    # Check insights
                    insights = data.get('insights', [])
                    if not insights or len(insights) == 0:
                        self.log_test_result("Chat Endpoint - Basic", False, "No insights generated", data)
                        return {'success': False, 'session_id': data.get('session_id')}
                    
                    self.log_test_result("Chat Endpoint - Basic", True, 
                                       f"AI analysis successful. Message length: {len(data['message'])}, "
                                       f"Insights: {len(insights)}, Policies: {len(data.get('policies', []))}, "
                                       f"Visualizations: {len(data.get('visualizations', []))}", data)
                    
                    return {'success': True, 'session_id': data.get('session_id'), 'data': data}
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Chat Endpoint - Basic", False, f"HTTP {response.status}: {error_text}")
                    return {'success': False, 'session_id': None}
                    
        except Exception as e:
            self.log_test_result("Chat Endpoint - Basic", False, f"Exception: {str(e)}")
            return {'success': False, 'session_id': None}
    
    async def test_chat_endpoint_with_session(self, session_id: str) -> bool:
        """Test POST /api/chat endpoint with existing session"""
        try:
            test_request = {
                "message": "Can you provide more details about the implementation steps for the renewable energy policies you mentioned?",
                "session_id": session_id,
                "include_visualizations": True,
                "include_insights": True,
                "include_policies": True
            }
            
            async with self.session.post(f"{self.base_url}/chat", json=test_request) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if session ID matches
                    if data.get('session_id') != session_id:
                        self.log_test_result("Chat Endpoint - Session Continuity", False, 
                                           f"Session ID mismatch. Expected: {session_id}, Got: {data.get('session_id')}", data)
                        return False
                    
                    # Check if response is contextual
                    message_content = data.get('message', '').lower()
                    if not message_content or len(message_content) < 30:
                        self.log_test_result("Chat Endpoint - Session Continuity", False, "Response too short", data)
                        return False
                    
                    self.log_test_result("Chat Endpoint - Session Continuity", True, 
                                       f"Session continuity maintained. Response length: {len(data.get('message', ''))}", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Chat Endpoint - Session Continuity", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Chat Endpoint - Session Continuity", False, f"Exception: {str(e)}")
            return False
    
    async def test_sessions_endpoint(self) -> bool:
        """Test GET /api/sessions endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/sessions") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if not isinstance(data, list):
                        self.log_test_result("Sessions Endpoint", False, "Response is not a list", data)
                        return False
                    
                    # Check if we have sessions (should have at least one from previous tests)
                    if len(data) == 0:
                        self.log_test_result("Sessions Endpoint", True, "No sessions found (empty database)", data)
                        return True
                    
                    # Validate session structure
                    first_session = data[0]
                    required_fields = ['id', 'title', 'created_at', 'updated_at']
                    missing_fields = [field for field in required_fields if field not in first_session]
                    
                    if missing_fields:
                        self.log_test_result("Sessions Endpoint", False, f"Missing fields in session: {missing_fields}", data)
                        return False
                    
                    self.log_test_result("Sessions Endpoint", True, f"Retrieved {len(data)} sessions", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Sessions Endpoint", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Sessions Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_specific_session_endpoint(self, session_id: str) -> bool:
        """Test GET /api/sessions/{session_id} endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/sessions/{session_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check required fields
                    required_fields = ['id', 'title', 'messages', 'created_at', 'updated_at']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        self.log_test_result("Specific Session Endpoint", False, f"Missing fields: {missing_fields}", data)
                        return False
                    
                    # Check if session ID matches
                    if data.get('id') != session_id:
                        self.log_test_result("Specific Session Endpoint", False, 
                                           f"Session ID mismatch. Expected: {session_id}, Got: {data.get('id')}", data)
                        return False
                    
                    # Check messages
                    messages = data.get('messages', [])
                    if not isinstance(messages, list):
                        self.log_test_result("Specific Session Endpoint", False, "Messages is not a list", data)
                        return False
                    
                    self.log_test_result("Specific Session Endpoint", True, 
                                       f"Session retrieved with {len(messages)} messages", data)
                    return True
                    
                elif response.status == 404:
                    self.log_test_result("Specific Session Endpoint", False, f"Session {session_id} not found")
                    return False
                else:
                    error_text = await response.text()
                    self.log_test_result("Specific Session Endpoint", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Specific Session Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_scrape_trigger_endpoint(self) -> bool:
        """Test POST /api/scrape/trigger endpoint"""
        try:
            async with self.session.post(f"{self.base_url}/scrape/trigger") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check required fields
                    if 'message' not in data or 'status' not in data:
                        self.log_test_result("Scrape Trigger", False, "Missing required fields", data)
                        return False
                    
                    # Check if scraping was triggered or already in progress
                    status = data.get('status')
                    if status not in ['started', 'in_progress']:
                        self.log_test_result("Scrape Trigger", False, f"Unexpected status: {status}", data)
                        return False
                    
                    self.log_test_result("Scrape Trigger", True, f"Scraping {status}: {data.get('message')}", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Scrape Trigger", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Scrape Trigger", False, f"Exception: {str(e)}")
            return False
    
    async def test_recent_data_endpoint(self) -> bool:
        """Test GET /api/data/recent endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/data/recent?limit=10") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if not isinstance(data, list):
                        self.log_test_result("Recent Data Endpoint", False, "Response is not a list", data)
                        return False
                    
                    # If no data, that's okay for a fresh system
                    if len(data) == 0:
                        self.log_test_result("Recent Data Endpoint", True, "No scraped data found (empty database)", data)
                        return True
                    
                    # Validate data structure
                    first_item = data[0]
                    required_fields = ['id', 'source', 'url', 'title', 'content', 'scraped_at']
                    missing_fields = [field for field in required_fields if field not in first_item]
                    
                    if missing_fields:
                        self.log_test_result("Recent Data Endpoint", False, f"Missing fields in data item: {missing_fields}", data)
                        return False
                    
                    self.log_test_result("Recent Data Endpoint", True, f"Retrieved {len(data)} scraped data items", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Recent Data Endpoint", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Recent Data Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_search_data_endpoint(self) -> bool:
        """Test GET /api/data/search endpoint"""
        try:
            search_query = "economic policy"
            async with self.session.get(f"{self.base_url}/data/search?query={search_query}&limit=5") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if not isinstance(data, list):
                        self.log_test_result("Search Data Endpoint", False, "Response is not a list", data)
                        return False
                    
                    # Empty results are acceptable for search
                    self.log_test_result("Search Data Endpoint", True, 
                                       f"Search for '{search_query}' returned {len(data)} results", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Search Data Endpoint", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Search Data Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_stats_endpoint(self) -> bool:
        """Test GET /api/stats endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for expected statistical fields
                    expected_fields = ['scraped_data_count', 'chat_sessions_count', 'chat_messages_count', 'scraping_status']
                    missing_fields = [field for field in expected_fields if field not in data]
                    
                    if missing_fields:
                        self.log_test_result("Stats Endpoint", False, f"Missing statistical fields: {missing_fields}", data)
                        return False
                    
                    # Validate data types
                    numeric_fields = ['scraped_data_count', 'chat_sessions_count', 'chat_messages_count']
                    for field in numeric_fields:
                        if not isinstance(data.get(field), int):
                            self.log_test_result("Stats Endpoint", False, f"Field {field} is not numeric", data)
                            return False
                    
                    self.log_test_result("Stats Endpoint", True, 
                                       f"Stats retrieved: Sessions={data.get('chat_sessions_count')}, "
                                       f"Messages={data.get('chat_messages_count')}, "
                                       f"Scraped={data.get('scraped_data_count')}", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("Stats Endpoint", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Stats Endpoint", False, f"Exception: {str(e)}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling with invalid requests"""
        try:
            # Test invalid chat request
            invalid_request = {"invalid_field": "test"}
            
            async with self.session.post(f"{self.base_url}/chat", json=invalid_request) as response:
                if response.status in [400, 422]:  # Expected validation error
                    self.log_test_result("Error Handling - Invalid Chat Request", True, 
                                       f"Properly handled invalid request with HTTP {response.status}")
                    return True
                else:
                    self.log_test_result("Error Handling - Invalid Chat Request", False, 
                                       f"Unexpected response to invalid request: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            self.log_test_result("Error Handling - Invalid Chat Request", False, f"Exception: {str(e)}")
            return False
    
    async def test_ai_integration(self) -> bool:
        """Test AI integration specifically"""
        try:
            # Test with a complex policy question that requires real AI analysis
            complex_request = {
                "message": "Analyze the potential economic and social impacts of implementing a universal basic income policy in the United States, considering inflation risks, labor market effects, and fiscal sustainability. Provide specific policy recommendations with implementation timelines.",
                "include_visualizations": True,
                "include_insights": True,
                "include_policies": True
            }
            
            async with self.session.post(f"{self.base_url}/chat", json=complex_request) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    message = data.get('message', '')
                    insights = data.get('insights', [])
                    policies = data.get('policies', [])
                    
                    # Check for substantive AI analysis
                    if len(message) < 200:
                        self.log_test_result("AI Integration", False, "AI response too brief for complex query", data)
                        return False
                    
                    # Check for policy-specific content
                    policy_keywords = ['universal basic income', 'ubi', 'economic', 'social', 'implementation']
                    message_lower = message.lower()
                    keyword_matches = sum(1 for keyword in policy_keywords if keyword in message_lower)
                    
                    if keyword_matches < 2:
                        self.log_test_result("AI Integration", False, "AI response lacks policy-specific content", data)
                        return False
                    
                    # Check for insights
                    if len(insights) < 2:
                        self.log_test_result("AI Integration", False, "Insufficient insights generated", data)
                        return False
                    
                    self.log_test_result("AI Integration", True, 
                                       f"AI generated comprehensive analysis: {len(message)} chars, "
                                       f"{len(insights)} insights, {len(policies)} policies, "
                                       f"{keyword_matches} policy keywords matched", data)
                    return True
                    
                else:
                    error_text = await response.text()
                    self.log_test_result("AI Integration", False, f"HTTP {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_test_result("AI Integration", False, f"Exception: {str(e)}")
            return False

    async def test_multilingual_language_detection(self) -> Dict[str, bool]:
        """Test multilingual language detection and response system"""
        test_cases = [
            {
                "language": "French",
                "input": "Analysez l'impact des politiques de tarification du carbone sur les industries manufacturières",
                "expected_keywords": ["carbone", "industries", "manufacturières", "impact", "politiques"]
            },
            {
                "language": "Spanish", 
                "input": "Analiza el impacto económico de las políticas de carbono en las industrias",
                "expected_keywords": ["impacto", "económico", "políticas", "carbono", "industrias"]
            },
            {
                "language": "German",
                "input": "Analysieren Sie die wirtschaftlichen Auswirkungen der Klimapolitik",
                "expected_keywords": ["wirtschaftlichen", "auswirkungen", "klimapolitik"]
            },
            {
                "language": "Indonesian",
                "input": "Analisis dampak ekonomi dari kebijakan perubahan iklim terhadap industri manufaktur",
                "expected_keywords": ["dampak", "ekonomi", "kebijakan", "perubahan", "iklim", "industri", "manufaktur"]
            },
            {
                "language": "Portuguese",
                "input": "Analise o impacto econômico das políticas de carbono nas indústrias",
                "expected_keywords": ["impacto", "econômico", "políticas", "carbono", "indústrias"]
            },
            {
                "language": "Italian",
                "input": "Analizza l'impatto economico delle politiche sul carbonio nelle industrie",
                "expected_keywords": ["impatto", "economico", "politiche", "carbonio", "industrie"]
            },
            {
                "language": "Chinese",
                "input": "分析碳定价政策对制造业的经济影响",
                "expected_keywords": ["碳", "政策", "制造业", "经济", "影响"]
            }
        ]
        
        results = {}
        
        for test_case in test_cases:
            try:
                language = test_case["language"]
                input_text = test_case["input"]
                expected_keywords = test_case["expected_keywords"]
                
                logger.info(f"Testing {language} language detection and response...")
                
                request_data = {
                    "message": input_text,
                    "include_visualizations": True,
                    "include_insights": True,
                    "include_policies": True
                }
                
                async with self.session.post(f"{self.base_url}/chat", json=request_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        main_response = data.get('message', '')
                        insights = data.get('insights', [])
                        policies = data.get('policies', [])
                        
                        # Check if response is not empty
                        if not main_response or len(main_response) < 50:
                            self.log_test_result(f"Multilingual Test - {language}", False, 
                                               f"Response too short or empty: {len(main_response)} chars", data)
                            results[language] = False
                            continue
                        
                        # Check if response contains expected language keywords
                        response_lower = main_response.lower()
                        keyword_matches = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
                        
                        # For non-Latin scripts, check if response contains characters from that script
                        if language == "Chinese":
                            chinese_chars = sum(1 for char in main_response if '\u4e00' <= char <= '\u9fff')
                            if chinese_chars < 10:  # Should have at least 10 Chinese characters
                                self.log_test_result(f"Multilingual Test - {language}", False, 
                                                   f"Response not in Chinese. Chinese chars: {chinese_chars}", data)
                                results[language] = False
                                continue
                        else:
                            # For Latin-based languages, check keyword presence
                            if keyword_matches < 2:
                                self.log_test_result(f"Multilingual Test - {language}", False, 
                                                   f"Response may not be in {language}. Keyword matches: {keyword_matches}/{len(expected_keywords)}", data)
                                results[language] = False
                                continue
                        
                        # Check insights are in correct language
                        insights_text = ' '.join(insights) if insights else ''
                        if insights_text:
                            if language == "Chinese":
                                insights_chinese_chars = sum(1 for char in insights_text if '\u4e00' <= char <= '\u9fff')
                                if insights_chinese_chars < 5:
                                    self.log_test_result(f"Multilingual Test - {language} Insights", False, 
                                                       f"Insights not in Chinese. Chinese chars: {insights_chinese_chars}", data)
                                    results[language] = False
                                    continue
                            else:
                                insights_keyword_matches = sum(1 for keyword in expected_keywords if keyword.lower() in insights_text.lower())
                                if insights_keyword_matches < 1:
                                    self.log_test_result(f"Multilingual Test - {language} Insights", False, 
                                                       f"Insights may not be in {language}. Keyword matches: {insights_keyword_matches}", data)
                                    results[language] = False
                                    continue
                        
                        # Success case
                        self.log_test_result(f"Multilingual Test - {language}", True, 
                                           f"✅ Language detection and response working. Response: {len(main_response)} chars, "
                                           f"Keywords matched: {keyword_matches}/{len(expected_keywords)}, "
                                           f"Insights: {len(insights)}, Policies: {len(policies)}", data)
                        results[language] = True
                        
                    else:
                        error_text = await response.text()
                        self.log_test_result(f"Multilingual Test - {language}", False, 
                                           f"HTTP {response.status}: {error_text}")
                        results[language] = False
                        
            except Exception as e:
                self.log_test_result(f"Multilingual Test - {language}", False, f"Exception: {str(e)}")
                results[language] = False
        
        return results

    async def test_multilingual_edge_cases(self) -> Dict[str, bool]:
        """Test edge cases for multilingual detection"""
        edge_cases = [
            {
                "name": "Short French Text",
                "input": "Politique économique française",
                "expected_language": "French"
            },
            {
                "name": "Short Spanish Text", 
                "input": "Política económica española",
                "expected_language": "Spanish"
            },
            {
                "name": "Mixed Language (English-Spanish)",
                "input": "What is the impacto económico of carbon policies?",
                "expected_language": "Mixed"
            },
            {
                "name": "English Baseline",
                "input": "Analyze the economic impact of carbon pricing policies on manufacturing industries",
                "expected_language": "English"
            }
        ]
        
        results = {}
        
        for case in edge_cases:
            try:
                case_name = case["name"]
                input_text = case["input"]
                
                logger.info(f"Testing edge case: {case_name}")
                
                request_data = {
                    "message": input_text,
                    "include_visualizations": True,
                    "include_insights": True,
                    "include_policies": True
                }
                
                async with self.session.post(f"{self.base_url}/chat", json=request_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        main_response = data.get('message', '')
                        
                        # Check if response is not empty
                        if not main_response or len(main_response) < 30:
                            self.log_test_result(f"Edge Case - {case_name}", False, 
                                               f"Response too short: {len(main_response)} chars", data)
                            results[case_name] = False
                            continue
                        
                        # For baseline English, ensure it still works
                        if case_name == "English Baseline":
                            if 'economic' not in main_response.lower() or 'carbon' not in main_response.lower():
                                self.log_test_result(f"Edge Case - {case_name}", False, 
                                                   "English baseline test failed - missing expected content", data)
                                results[case_name] = False
                                continue
                        
                        self.log_test_result(f"Edge Case - {case_name}", True, 
                                           f"✅ Edge case handled correctly. Response: {len(main_response)} chars", data)
                        results[case_name] = True
                        
                    else:
                        error_text = await response.text()
                        self.log_test_result(f"Edge Case - {case_name}", False, 
                                           f"HTTP {response.status}: {error_text}")
                        results[case_name] = False
                        
            except Exception as e:
                self.log_test_result(f"Edge Case - {case_name}", False, f"Exception: {str(e)}")
                results[case_name] = False
        
        return results
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*80)
        print("BACKEND TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print("="*80)
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            print("-" * 40)
            for result in self.test_results:
                if not result['success']:
                    print(f"❌ {result['test']}: {result['details']}")
        
        print("\nPASSED TESTS:")
        print("-" * 40)
        for result in self.test_results:
            if result['success']:
                print(f"✅ {result['test']}: {result['details']}")
        
        return passed_tests, failed_tests

async def main():
    """Main test execution"""
    print("Starting Comprehensive Backend Testing for AI Policy & Insight Generator")
    print("="*80)
    
    async with PolicyBackendTester() as tester:
        print(f"Testing backend at: {tester.base_url}")
        print("-" * 80)
        
        # Core API endpoint tests
        await tester.test_root_endpoint()
        await tester.test_health_endpoint()
        
        # Chat functionality tests
        chat_result = await tester.test_chat_endpoint_basic()
        session_id = chat_result.get('session_id')
        
        if session_id:
            await tester.test_chat_endpoint_with_session(session_id)
            await tester.test_specific_session_endpoint(session_id)
        
        # Session management tests
        await tester.test_sessions_endpoint()
        
        # Data scraping tests
        await tester.test_scrape_trigger_endpoint()
        await tester.test_recent_data_endpoint()
        await tester.test_search_data_endpoint()
        
        # Statistics tests
        await tester.test_stats_endpoint()
        
        # Error handling tests
        await tester.test_error_handling()
        
        # AI integration tests
        await tester.test_ai_integration()
        
        # Multilingual language detection tests
        print("\n" + "="*80)
        print("MULTILINGUAL LANGUAGE DETECTION TESTING")
        print("="*80)
        
        multilingual_results = await tester.test_multilingual_language_detection()
        edge_case_results = await tester.test_multilingual_edge_cases()
        
        # Print multilingual test summary
        print("\nMULTILINGUAL TEST RESULTS:")
        print("-" * 40)
        for language, success in multilingual_results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} - {language} Language Detection & Response")
        
        print("\nEDGE CASE TEST RESULTS:")
        print("-" * 40)
        for case, success in edge_case_results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} - {case}")
        
        # Print summary
        passed, failed = tester.print_summary()
        
        # Add multilingual test results to summary
        multilingual_passed = sum(1 for success in multilingual_results.values() if success)
        multilingual_failed = len(multilingual_results) - multilingual_passed
        edge_passed = sum(1 for success in edge_case_results.values() if success)
        edge_failed = len(edge_case_results) - edge_passed
        
        total_multilingual_tests = len(multilingual_results) + len(edge_case_results)
        total_multilingual_passed = multilingual_passed + edge_passed
        total_multilingual_failed = multilingual_failed + edge_failed
        
        print(f"\nMULTILINGUAL TESTING SUMMARY:")
        print(f"Total Multilingual Tests: {total_multilingual_tests}")
        print(f"Passed: {total_multilingual_passed} ✅")
        print(f"Failed: {total_multilingual_failed} ❌")
        if total_multilingual_tests > 0:
            print(f"Multilingual Success Rate: {(total_multilingual_passed/total_multilingual_tests)*100:.1f}%")
        
        # Return appropriate exit code
        total_failed = failed + total_multilingual_failed
        return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during testing: {e}")
        sys.exit(1)