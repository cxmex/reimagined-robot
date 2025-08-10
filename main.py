#!/usr/bin/env python3
"""
Simple News Research Agent Test
No MCP required - just tests the core functionality
"""

import json
from datetime import datetime, timedelta
import requests
from newspaper import Article
from openai import OpenAI
from bs4 import BeautifulSoup

class SimpleNewsResearcher:
    def __init__(self):
        # Replace with your actual API keys
        self.news_api_key = "ff32962b372a4d258774c9d18695aa59"
        self.openai_api_key = "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"
        self.base_url = "https://newsapi.org/v2/"
        
        # Initialize OpenAI client (new v1.0+ syntax)
        self.openai_client = OpenAI(api_key=self.openai_api_key)
    
    def search_articles(self, query, days_back=7, max_results=10):
        """Search for news articles"""
        print(f"🔍 Searching for: '{query}'...")
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)
        
        params = {
            'q': query,
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'sortBy': 'relevancy',
            'pageSize': max_results,
            'apiKey': self.news_api_key,
            'language': 'en'
        }
        
        try:
            response = requests.get(f"{self.base_url}everything", params=params)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                print(f"📰 Found {len(articles)} articles")
                return articles
            else:
                print(f"❌ NewsAPI error: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def extract_article_text(self, url):
        """Extract full text from article URL"""
        print(f"📄 Extracting text from: {url[:50]}...")
        
        try:
            # Try newspaper3k first
            article = Article(url)
            article.download()
            article.parse()
            
            if article.text and len(article.text.strip()) > 100:
                print(f"✅ Extracted {len(article.text)} characters using newspaper3k")
                return {
                    'text': article.text,
                    'title': article.title,
                    'method': 'newspaper3k'
                }
        except Exception as e:
            print(f"⚠️ newspaper3k failed: {e}")
        
        try:
            # Fallback to BeautifulSoup
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Clean up
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Extract paragraphs
            paragraphs = soup.find_all('p')
            text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            if text and len(text) > 100:
                print(f"✅ Extracted {len(text)} characters using BeautifulSoup")
                return {
                    'text': text,
                    'title': soup.find('title').get_text() if soup.find('title') else '',
                    'method': 'beautifulsoup'
                }
            
        except Exception as e:
            print(f"❌ BeautifulSoup failed: {e}")
        
        return None
    
    def analyze_relevance(self, article_text, search_query, article_title=""):
        """Analyze article relevance using OpenAI"""
        print("🤖 Analyzing relevance with OpenAI...")
        
        try:
            prompt = f"""
Analyze this article for relevance to: "{search_query}"

Title: {article_title}
Text: {article_text[:3000]}

Respond with JSON:
{{
    "relevance_score": <1-10>,
    "key_points": ["point1", "point2", "point3"],
    "summary": "<2-3 sentence summary focusing on search topic>",
    "insights": "<unique insights about the search topic>"
}}
"""
            
            # New OpenAI v1.0+ syntax
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a research analyst. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            analysis = json.loads(content)
            
            print(f"✅ Analysis complete! Relevance: {analysis.get('relevance_score', 'N/A')}/10")
            return analysis
            
        except Exception as e:
            print(f"❌ OpenAI analysis failed: {e}")
            return None
    
    def research_topic(self, topic, max_articles=3):
        """Complete research workflow"""
        print(f"🚀 Starting research on: {topic}")
        print("=" * 60)
        
        # Step 1: Search articles
        articles = self.search_articles(topic, max_results=max_articles)
        if not articles:
            return "No articles found"
        
        # Step 2: Analyze top articles
        results = []
        for i, article in enumerate(articles[:max_articles]):
            print(f"\n📋 Processing article {i+1}/{max_articles}")
            print("-" * 40)
            
            url = article.get('url', '')
            title = article.get('title', '')
            
            # Extract text
            extraction = self.extract_article_text(url)
            if not extraction:
                print("⏭️ Skipping article (extraction failed)")
                continue
            
            # Analyze relevance
            analysis = self.analyze_relevance(
                extraction['text'], 
                topic, 
                extraction['title']
            )
            
            if analysis:
                results.append({
                    'title': title,
                    'url': url,
                    'source': article.get('source', {}).get('name', ''),
                    'published': article.get('publishedAt', ''),
                    'relevance_score': analysis.get('relevance_score', 0),
                    'summary': analysis.get('summary', ''),
                    'key_points': analysis.get('key_points', []),
                    'insights': analysis.get('insights', ''),
                    'extraction_method': extraction['method']
                })
        
        # Step 3: Generate report
        return self.generate_report(topic, results)
    
    def generate_report(self, topic, results):
        """Generate final research report"""
        # Sort by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        report = f"""
🎯 RESEARCH REPORT: {topic.upper()}
{'='*60}

📊 SUMMARY:
• Articles analyzed: {len(results)}
• Research completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Average relevance: {sum(r['relevance_score'] for r in results) / len(results):.1f}/10

📰 TOP FINDINGS:
"""
        
        for i, result in enumerate(results, 1):
            report += f"""
[{i}] {result['title']}
    Relevance: {result['relevance_score']}/10 | Source: {result['source']}
    Summary: {result['summary']}
    Key Points: {', '.join(result['key_points'][:3])}
    Insights: {result['insights']}
    URL: {result['url']}
"""
        
        return report

def main():
    # Initialize researcher
    researcher = SimpleNewsResearcher()
    
    # Check API keys
    if researcher.news_api_key == "YOUR_NEWSAPI_KEY_HERE":
        print("❌ Please add your NewsAPI key!")
        print("Get it free at: https://newsapi.org/register")
        return
    
    if researcher.openai_api_key == "YOUR_OPENAI_KEY_HERE":
        print("❌ Please add your OpenAI API key!")
        print("Get it at: https://platform.openai.com/api-keys")
        return
    
    # Interactive research
    while True:
        print("\n" + "="*60)
        print("🔬 NEWS RESEARCH AGENT")
        print("="*60)
        
        topic = input("\nEnter research topic (or 'quit' to exit): ").strip()
        
        if topic.lower() in ['quit', 'exit', 'q']:
            break
        
        if topic:
            try:
                report = researcher.research_topic(topic, max_articles=3)
                print(report)
                
                # Save report
                filename = f"research_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n💾 Report saved as: {filename}")
                
            except Exception as e:
                print(f"❌ Research failed: {e}")
        
        else:
            print("Please enter a valid topic.")
    
    print("\n👋 Thanks for using the News Research Agent!")

if __name__ == "__main__":
    main()