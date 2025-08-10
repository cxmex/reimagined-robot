#!/usr/bin/env python3
"""
FastAPI Research Endpoint
Usage: GET /research?query=your+research+topic
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import json
import feedparser
import time
from datetime import datetime, timedelta
import requests
from newspaper import Article
from openai import OpenAI
from bs4 import BeautifulSoup
from supabase import create_client, Client
import uuid
import asyncio
from typing import Optional
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Schoolab Research API",
    description="AI-powered news research endpoint that saves results to database",
    version="1.0.0"
)

class SchoolabResearchAPI:
    def __init__(self):
        # Your credentials
        self.supabase_url = "https://aggqkemnrfvogfmjcjsr.supabase.co/"
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFnZ3FrZW1ucmZ2b2dmbWpjanNyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ4MzM3NjksImV4cCI6MjA3MDQwOTc2OX0.BWwrzo5FfagEujmPowftkIZPw3zw5OjgEIBv3hya5tk"
        self.openai_key = "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"
        self.news_api_key = "ff32962b372a4d258774c9d18695aa59"
        
        # Initialize clients
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.openai_client = OpenAI(api_key=self.openai_key)
    
    def search_multiple_sources(self, query, max_articles_per_source=5):
        """Search multiple news sources"""
        all_articles = []
        
        # 1. Google News
        articles = self.search_google_news(query, max_articles_per_source)
        all_articles.extend(articles)
        
        # 2. NewsAPI
        articles = self.search_newsapi(query, max_articles_per_source)
        all_articles.extend(articles)
        
        # 3. Bing News
        articles = self.search_bing_news(query, max_articles_per_source)
        all_articles.extend(articles)
        
        # 4. Reddit
        articles = self.search_reddit(query, max_articles_per_source)
        all_articles.extend(articles)
        
        # Remove duplicates
        unique_articles = self.remove_duplicates(all_articles)
        return unique_articles
    
    def search_google_news(self, query, max_results):
        """Search Google News RSS"""
        try:
            url = f"https://news.google.com/rss/search?q={query.replace(' ', '%20')}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            
            articles = []
            for entry in feed.entries[:max_results]:
                articles.append({
                    'title': entry.get('title', ''),
                    'description': entry.get('summary', ''),
                    'url': entry.get('link', ''),
                    'published_at': entry.get('published', ''),
                    'source': 'Google News'
                })
            
            return articles
        except Exception as e:
            print(f"Google News failed: {e}")
            return []
    
    def search_newsapi(self, query, max_results):
        """Search NewsAPI"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'sortBy': 'relevancy',
                'pageSize': max_results,
                'apiKey': self.news_api_key,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = []
                
                for article in data.get('articles', []):
                    articles.append({
                        'title': article.get('title', ''),
                        'description': article.get('description', ''),
                        'url': article.get('url', ''),
                        'published_at': article.get('publishedAt', ''),
                        'source': article.get('source', {}).get('name', 'NewsAPI')
                    })
                
                return articles
            return []
        except Exception as e:
            print(f"NewsAPI failed: {e}")
            return []
    
    def search_bing_news(self, query, max_results):
        """Search Bing News RSS"""
        try:
            url = f"https://www.bing.com/news/search?q={query.replace(' ', '%20')}&format=rss"
            feed = feedparser.parse(url)
            
            articles = []
            for entry in feed.entries[:max_results]:
                articles.append({
                    'title': entry.get('title', ''),
                    'description': entry.get('summary', ''),
                    'url': entry.get('link', ''),
                    'published_at': entry.get('published', ''),
                    'source': 'Bing News'
                })
            
            return articles
        except Exception as e:
            print(f"Bing News failed: {e}")
            return []
    
    def search_reddit(self, query, max_results):
        """Search Reddit"""
        try:
            url = "https://www.reddit.com/search.json"
            params = {
                'q': query,
                'sort': 'relevance',
                'limit': max_results,
                't': 'week'
            }
            
            headers = {'User-Agent': 'SchoolabResearchAPI/1.0'}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = []
                
                for post in data.get('data', {}).get('children', []):
                    post_data = post.get('data', {})
                    
                    if post_data.get('selftext') or post_data.get('url', '').startswith('http'):
                        articles.append({
                            'title': post_data.get('title', ''),
                            'description': post_data.get('selftext', '')[:200] + "..." if post_data.get('selftext') else '',
                            'url': f"https://reddit.com{post_data.get('permalink', '')}",
                            'published_at': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                            'source': f"r/{post_data.get('subreddit', 'reddit')}"
                        })
                
                return articles
            return []
        except Exception as e:
            print(f"Reddit failed: {e}")
            return []
    
    def remove_duplicates(self, articles):
        """Remove duplicate articles based on title similarity"""
        unique_articles = []
        seen_titles = set()
        
        for article in articles:
            title_lower = article['title'].lower().strip()
            title_words = set(title_lower.split())
            
            is_duplicate = False
            for seen_title in seen_titles:
                seen_words = set(seen_title.split())
                if title_words and seen_words:
                    similarity = len(title_words & seen_words) / len(title_words | seen_words)
                    if similarity > 0.7:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(title_lower)
        
        return unique_articles
    
    def analyze_articles_batch(self, articles, query):
        """Analyze articles for relevance using AI"""
        analyzed_articles = []
        batch_size = 10
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            
            article_summaries = []
            for j, article in enumerate(batch):
                article_summaries.append(f"""
Article {i+j+1}:
Title: {article['title']}
Description: {article['description'][:200]}...
Source: {article['source']}
""")
            
            try:
                prompt = f"""
Analyze these articles for relevance to: "{query}"

{chr(10).join(article_summaries)}

For each article, provide relevance score (1-10) and brief reason.
Respond with JSON array:
[
    {{"article_number": {i+1}, "relevance_score": <1-10>, "reason": "<brief reason>"}},
    ...
]
"""
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a research analyst. Always respond with valid JSON array."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.2
                )
                
                content = response.choices[0].message.content
                scores = json.loads(content)
                
                for score_data in scores:
                    article_idx = score_data.get('article_number', i+1) - 1
                    if 0 <= article_idx < len(articles):
                        article = articles[article_idx].copy()
                        article['relevance_score'] = score_data.get('relevance_score', 0)
                        article['relevance_reason'] = score_data.get('reason', '')
                        analyzed_articles.append(article)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"Batch analysis failed: {e}")
                for article in batch:
                    article['relevance_score'] = 5
                    article['relevance_reason'] = 'Analysis failed'
                    analyzed_articles.append(article)
        
        analyzed_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return analyzed_articles
    
    def generate_report(self, query, analyzed_articles):
        """Generate comprehensive research report"""
        high_relevance = [a for a in analyzed_articles if a.get('relevance_score', 0) >= 7]
        avg_relevance = sum(a.get('relevance_score', 0) for a in analyzed_articles) / len(analyzed_articles) if analyzed_articles else 0
        
        source_count = {}
        for article in analyzed_articles:
            source = article.get('source', 'Unknown')
            source_count[source] = source_count.get(source, 0) + 1
        
        report = f"""# Research Report: {query.upper()}

## Executive Summary

**Research Query:** {query}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Articles Analyzed:** {len(analyzed_articles)}  
**High Relevance Articles (≥7/10):** {len(high_relevance)}  
**Average Relevance Score:** {avg_relevance:.1f}/10  

## Source Distribution

"""
        
        for source, count in sorted(source_count.items(), key=lambda x: x[1], reverse=True):
            report += f"- **{source}:** {count} articles\n"
        
        report += f"""
## Top Findings

"""
        
        for i, article in enumerate(analyzed_articles[:10], 1):
            score = article.get('relevance_score', 0)
            reason = article.get('relevance_reason', '')
            
            report += f"""### {i}. {article['title']}

**Relevance:** {score}/10  
**Source:** {article['source']}  
**URL:** {article['url']}

**Why Relevant:** {reason}

**Summary:** {article['description'][:300]}...

---

"""
        
        report += f"""
## Research Methodology

- **Sources:** Google News, NewsAPI, Bing News, Reddit
- **AI Analysis:** GPT-3.5-turbo relevance scoring
- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report
    
    def save_to_database(self, query, report):
        """Save to schoolab table"""
        try:
            data = {
                'query': query,
                'report': report,
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table("schoolab").insert(data).execute()
            
            if result.data:
                return result.data[0]['id']
            return None
        except Exception as e:
            print(f"Database save failed: {e}")
            return None
    
    def research(self, query):
        """Complete research workflow"""
        start_time = time.time()
        
        # Search articles
        articles = self.search_multiple_sources(query, max_articles_per_source=5)
        
        if not articles:
            return None, "No articles found"
        
        # Analyze articles
        analyzed_articles = self.analyze_articles_batch(articles, query)
        
        # Generate report
        report = self.generate_report(query, analyzed_articles)
        
        # Save to database
        record_id = self.save_to_database(query, report)
        
        duration = time.time() - start_time
        
        return {
            'record_id': record_id,
            'query': query,
            'articles_analyzed': len(analyzed_articles),
            'high_relevance_count': len([a for a in analyzed_articles if a.get('relevance_score', 0) >= 7]),
            'average_relevance': sum(a.get('relevance_score', 0) for a in analyzed_articles) / len(analyzed_articles) if analyzed_articles else 0,
            'duration_seconds': round(duration, 2),
            'report': report
        }, None

# Initialize the research API
research_api = SchoolabResearchAPI()

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Schoolab Research API",
        "version": "1.0.0",
        "endpoints": {
            "research": "/research?query=your+research+topic",
            "health": "/health",
            "recent": "/recent"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        result = research_api.supabase.table("schoolab").select("id").limit(1).execute()
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/research")
async def research_endpoint(query: str):
    """
    Main research endpoint
    
    Parameters:
    - query: Research topic/question (required)
    
    Returns:
    - JSON with research results and database record ID
    """
    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters long")
    
    try:
        result, error = research_api.research(query.strip())
        
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        return {
            "success": True,
            "message": "Research completed successfully",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")

@app.get("/recent")
async def recent_research():
    """Get recent research records"""
    try:
        result = research_api.supabase.table("schoolab").select(
            "id, query, created_at"
        ).order("created_at", desc=True).limit(10).execute()
        
        return {
            "success": True,
            "data": result.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve records: {str(e)}")

@app.get("/research/{record_id}")
async def get_research_by_id(record_id: str):
    """Get specific research record by ID"""
    try:
        result = research_api.supabase.table("schoolab").select("*").eq("id", record_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Research record not found")
        
        return {
            "success": True,
            "data": result.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve record: {str(e)}")

# Background task version for longer research
@app.post("/research/async")
async def research_async(background_tasks: BackgroundTasks, query: str):
    """
    Asynchronous research endpoint for longer queries
    Returns immediately with task ID, research runs in background
    """
    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters long")
    
    task_id = str(uuid.uuid4())
    
    # Add background task
    background_tasks.add_task(research_api.research, query.strip())
    
    return {
        "success": True,
        "message": "Research started in background",
        "task_id": task_id,
        "query": query.strip()
    }

if __name__ == "__main__":
    uvicorn.run(
        "fastapi_research_endpoint:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )