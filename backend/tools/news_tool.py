"""News retrieval tool using Tavily Search."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from tavily import TavilyClient

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class NewsTool:
    """
    News search tool for real-time SRAG context.

    Uses Tavily Search API to find recent news articles about:
    - SRAG (Sindrome Respiratoria Aguda Grave)
    - COVID-19
    - Respiratory outbreaks
    - Healthcare system status
    """

    def __init__(self):
        """Initialize Tavily client."""
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    def search_srag_news(
        self,
        query: Optional[str] = None,
        days: int = 7,
        max_results: int = 5,
        location: Optional[str] = "br",
    ) -> List[Dict[str, Any]]:
        """
        Search for SRAG-related news.

        Args:
            query: Custom search query (defaults to SRAG news)
            days: Number of days to look back
            max_results: Maximum number of results
            location: Geographic location filter (default: Brazil)

        Returns:
            List of news articles with title, url, content, published_date
        """
        if query is None:
            query = "SRAG síndrome respiratória aguda grave COVID-19 Brasil"

        logger.info(f"Searching news: {query} (last {days} days)")

        # Priority Brazilian news domains
        brazilian_domains = [
            "g1.globo.com",
            "oglobo.globo.com",
            "folha.uol.com.br",
            "estadao.com.br",
            "uol.com.br",
            "cnnbrasil.com.br",
            "saude.gov.br",
            "fiocruz.br",
            "butantan.gov.br",
        ]

        try:
            results = self.client.search(
                query=query,
                search_depth="advanced",  # More comprehensive results
                topic="news",  # Focus on news articles
                days=days,  # Recent news only
                max_results=max_results,
                include_domains=brazilian_domains,  # Priority for Brazilian sources
                exclude_domains=[],
            )

            articles = []
            for result in results.get("results", []):
                articles.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "published_date": result.get("published_date", ""),
                    "score": result.get("score", 0.0),
                })

            logger.info(f"Found {len(articles)} news articles")
            return articles

        except Exception as e:
            logger.error(f"News search error: {e}")
            return []

    def search_by_state(
        self,
        state: str,
        days: int = 7,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search for SRAG news specific to a Brazilian state."""
        query = f"SRAG COVID-19 síndrome respiratória {state} Brasil"
        return self.search_srag_news(
            query=query,
            days=days,
            max_results=max_results,
        )

    def get_recent_context(self) -> str:
        """
        Get formatted recent news context for report generation.

        Returns a text summary of recent SRAG news.
        """
        articles = self.search_srag_news(days=7, max_results=5)

        if not articles:
            return "Nenhuma notícia recente encontrada sobre SRAG."

        context = "## Notícias Recentes sobre SRAG\n\n"

        for i, article in enumerate(articles, 1):
            context += f"### {i}. {article['title']}\n"
            context += f"**Fonte:** {article['url']}\n"
            if article['published_date']:
                context += f"**Data:** {article['published_date']}\n"
            context += f"**Resumo:** {article['content'][:300]}...\n\n"

        return context

    def format_for_citation(self, articles: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format news articles for citation in reports."""
        citations = []

        for article in articles:
            citations.append({
                "title": article["title"],
                "url": article["url"],
                "date": article.get("published_date", "Data não disponível"),
            })

        return citations


# Global instance
news_tool = NewsTool()
