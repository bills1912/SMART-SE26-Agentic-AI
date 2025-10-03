import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re
from datetime import datetime
from models import ScrapedData, DataSource, PolicyCategory
import logging

logger = logging.getLogger(__name__)


class PolicyDataScraper:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def scrape_government_data(self) -> List[ScrapedData]:
        """Scrape government policy websites"""
        government_sources = [
            {
                'url': 'https://www.whitehouse.gov/briefing-room/statements-and-releases/',
                'selector': '.briefing-item',
                'title_selector': 'h3 a',
                'content_selector': '.excerpt'
            },
            {
                'url': 'https://www.congress.gov/browse',
                'selector': '.result-item',
                'title_selector': '.result-heading a',
                'content_selector': '.result-summary'
            }
        ]
        
        results = []
        for source in government_sources:
            try:
                data = await self._scrape_site(
                    source['url'], 
                    source['selector'],
                    source['title_selector'],
                    source['content_selector'],
                    DataSource.GOVERNMENT
                )
                results.extend(data)
            except Exception as e:
                logger.error(f"Error scraping {source['url']}: {e}")
                
        return results

    async def scrape_economic_data(self) -> List[ScrapedData]:
        """Scrape economic indicators and data"""
        economic_sources = [
            {
                'url': 'https://data.worldbank.org/indicator',
                'selector': '.indicator-item',
                'title_selector': '.indicator-name',
                'content_selector': '.indicator-description'
            },
            {
                'url': 'https://fred.stlouisfed.org/releases',
                'selector': '.release-item',
                'title_selector': '.release-title a',
                'content_selector': '.release-summary'
            }
        ]
        
        results = []
        for source in economic_sources:
            try:
                data = await self._scrape_site(
                    source['url'], 
                    source['selector'],
                    source['title_selector'],
                    source['content_selector'],
                    DataSource.ECONOMIC
                )
                results.extend(data)
            except Exception as e:
                logger.error(f"Error scraping {source['url']}: {e}")
                
        return results

    async def scrape_news_data(self) -> List[ScrapedData]:
        """Scrape policy-related news"""
        news_sources = [
            {
                'url': 'https://www.politico.com/policy',
                'selector': '.story-frag',
                'title_selector': '.headline a',
                'content_selector': '.dek'
            },
            {
                'url': 'https://www.reuters.com/politics',
                'selector': '.story-card',
                'title_selector': '[data-testid="Heading"]',
                'content_selector': '[data-testid="Body"]'
            }
        ]
        
        results = []
        for source in news_sources:
            try:
                data = await self._scrape_site(
                    source['url'], 
                    source['selector'],
                    source['title_selector'],
                    source['content_selector'],
                    DataSource.NEWS
                )
                results.extend(data)
            except Exception as e:
                logger.error(f"Error scraping {source['url']}: {e}")
                
        return results

    async def scrape_academic_data(self) -> List[ScrapedData]:
        """Scrape academic research and think tank publications"""
        academic_sources = [
            {
                'url': 'https://www.brookings.edu/research',
                'selector': '.research-item',
                'title_selector': '.research-title a',
                'content_selector': '.research-excerpt'
            },
            {
                'url': 'https://www.cato.org/publications',
                'selector': '.publication-item',
                'title_selector': '.publication-title a',
                'content_selector': '.publication-summary'
            }
        ]
        
        results = []
        for source in academic_sources:
            try:
                data = await self._scrape_site(
                    source['url'], 
                    source['selector'],
                    source['title_selector'],
                    source['content_selector'],
                    DataSource.ACADEMIC
                )
                results.extend(data)
            except Exception as e:
                logger.error(f"Error scraping {source['url']}: {e}")
                
        return results

    async def _scrape_site(
        self, 
        url: str, 
        item_selector: str, 
        title_selector: str, 
        content_selector: str,
        source_type: DataSource
    ) -> List[ScrapedData]:
        """Generic site scraper"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch {url}: {response.status}")
                    return []
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                items = soup.select(item_selector)
                results = []
                
                for item in items[:10]:  # Limit to 10 items per source
                    try:
                        title_elem = item.select_one(title_selector)
                        content_elem = item.select_one(content_selector)
                        
                        if title_elem and content_elem:
                            title = title_elem.get_text(strip=True)
                            content = content_elem.get_text(strip=True)
                            
                            # Clean and validate content
                            if len(title) > 10 and len(content) > 20:
                                scraped_data = ScrapedData(
                                    source=source_type,
                                    url=url,
                                    title=title,
                                    content=content,
                                    metadata={'scraped_from': item_selector},
                                    category=self._categorize_content(title + " " + content)
                                )
                                results.append(scraped_data)
                                
                    except Exception as e:
                        logger.error(f"Error processing item: {e}")
                        continue
                        
                return results
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []

    def _categorize_content(self, text: str) -> PolicyCategory:
        """Categorize content based on keywords"""
        text_lower = text.lower()
        
        economic_keywords = ['economy', 'gdp', 'inflation', 'employment', 'trade', 'budget', 'tax', 'finance']
        social_keywords = ['social', 'welfare', 'community', 'society', 'demographic', 'inequality']
        environmental_keywords = ['environment', 'climate', 'green', 'sustainable', 'carbon', 'pollution']
        healthcare_keywords = ['health', 'medical', 'healthcare', 'pandemic', 'disease', 'hospital']
        education_keywords = ['education', 'school', 'university', 'student', 'learning', 'academic']
        security_keywords = ['security', 'defense', 'military', 'terrorism', 'cyber', 'national security']
        technology_keywords = ['technology', 'digital', 'ai', 'artificial intelligence', 'innovation', 'tech']
        
        keyword_categories = {
            PolicyCategory.ECONOMIC: economic_keywords,
            PolicyCategory.SOCIAL: social_keywords,
            PolicyCategory.ENVIRONMENTAL: environmental_keywords,
            PolicyCategory.HEALTHCARE: healthcare_keywords,
            PolicyCategory.EDUCATION: education_keywords,
            PolicyCategory.SECURITY: security_keywords,
            PolicyCategory.TECHNOLOGY: technology_keywords
        }
        
        category_scores = {}
        for category, keywords in keyword_categories.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return PolicyCategory.ECONOMIC  # Default category

    async def scrape_all_sources(self) -> List[ScrapedData]:
        """Scrape data from all sources"""
        all_data = []
        
        try:
            # Run all scrapers concurrently
            government_task = self.scrape_government_data()
            economic_task = self.scrape_economic_data()
            news_task = self.scrape_news_data()
            academic_task = self.scrape_academic_data()
            
            results = await asyncio.gather(
                government_task, 
                economic_task, 
                news_task, 
                academic_task,
                return_exceptions=True
            )
            
            for result in results:
                if isinstance(result, list):
                    all_data.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Scraping error: {result}")
            
            logger.info(f"Total scraped items: {len(all_data)}")
            return all_data
            
        except Exception as e:
            logger.error(f"Error in scrape_all_sources: {e}")
            return all_data