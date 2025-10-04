"""News retrieval tool using Tavily Search."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
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
        """Initialize Tavily and OpenAI clients."""
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    def search_srag_news(
        self,
        query: Optional[str] = None,
        days: int = 7,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for SRAG-related news.

        Args:
            query: Custom search query (defaults to SRAG news)
            days: Number of days to look back
            max_results: Maximum number of results

        Returns:
            List of news articles with title, url, content, published_date
        """
        if query is None:
            # Query in Portuguese to prioritize Portuguese-language results
            query = "SRAG síndrome respiratória aguda grave COVID-19 Brasil notícias saúde"

        safe_days = max(1, days or 1)
        start_date, end_date = self._compute_date_window(safe_days)

        logger.info(
            "Searching news: %s (window %s to %s)",
            query,
            start_date,
            end_date,
        )

        # Priority Brazilian Portuguese news domains
        brazilian_domains = [
            "g1.globo.com",
            "oglobo.globo.com",
            "folha.uol.com.br",
            "estadao.com.br",
            "uol.com.br",
            "cnnbrasil.com.br",
            "agencia.fiocruz.br",
            "butantan.gov.br",
            "msn.com.br",
            "terra.com.br",
            "noticias.uol.com.br",
            "saude.abril.com.br"
        ]
        
        # Explicitly exclude English-language domains and English sections
        english_domains = [
            "biospace.com",
            "bionews.com",
            "medicalxpress.com",
            "sciencedaily.com",
            "reuters.com",
            "bloomberg.com",
            "forbes.com",
            "folha.uol.com.br/internacional/en",  # Folha English edition
            "www1.folha.uol.com.br/internacional/en"  # Folha English edition
        ]

        try:
            search_params: Dict[str, Any] = {
                "query": query,
                "search_depth": "advanced",
                "topic": "news",
                "max_results": max_results,
                "include_domains": brazilian_domains,
                "exclude_domains": english_domains,
                "days": safe_days,
            }

            results = self.client.search(**search_params)

            articles: List[Dict[str, Any]] = []
            for result in results.get("results", []):
                # Stop if we have enough articles
                if len(articles) >= max_results:
                    break
                
                # Filter out English-language URLs
                url = result.get("url", "")
                if "/en/" in url or "/english/" in url or "/internacional/en" in url:
                    logger.debug(f"Skipping English article: {url}")
                    continue
                
                # Filter out non-SRAG related content
                title = result.get("title", "")
                content = result.get("content", "")
                combined = (title + " " + content).lower()
                
                # Must contain SRAG-related keywords
                srag_keywords = ["srag", "síndrome respiratória", "respiratória aguda", "covid", "gripe", "influenza", "saúde"]
                if not any(keyword in combined for keyword in srag_keywords):
                    logger.debug(f"Skipping non-SRAG article: {title[:50]}")
                    continue
                
                # Extract date (may be empty for some sources)
                published_date = self._extract_published_date(result)
                if not published_date:
                    # Fallback: try to extract from content using LLM
                    published_date = self._extract_date_with_llm(title, content)

                # Skip articles without dates - we can't verify their recency
                if not published_date:
                    logger.debug(f"Skipping article without date: {title[:50]}")
                    continue

                # Validate date is within the requested time window
                if not self._is_date_within_range(published_date, safe_days):
                    logger.debug(f"Skipping old article from {published_date}: {title[:50]}")
                    continue

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "content": content,
                        "published_date": published_date,
                        "score": result.get("score", 0.0),
                    }
                )

            logger.info("Found %s relevant Portuguese news articles (filtered from %s results)", 
                       len(articles), len(results.get("results", [])))
            return articles

        except Exception as exc:  # pragma: no cover - defensive log
            logger.error("News search error: %s", exc)
            return []

    def search_by_state(
        self,
        state: str,
        days: int = 7,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for SRAG news specific to a Brazilian state."""
        query = f"SRAG COVID-19 sindrome respiratoria {state} Brasil"
        return self.search_srag_news(
            query=query,
            days=days,
            max_results=max_results,
        )

    def get_recent_context(self, days: int = 30) -> str:
        """
        Get formatted recent news context for report generation.

        Args:
            days: Number of days to look back (default: 30)

        Returns a text summary of recent SRAG news.
        """
        articles = self.search_srag_news(days=days, max_results=10)

        if not articles:
            return "Nenhuma noticia recente encontrada sobre SRAG."

        context = "## Noticias Recentes sobre SRAG\n\n"

        for i, article in enumerate(articles, 1):
            context += f"### {i}. {article['title']}\n"
            context += f"**Fonte:** {article['url']}\n"
            if article["published_date"]:
                context += f"**Data:** {article['published_date']}\n"
            context += f"**Resumo:** {article['content'][:300]}...\n\n"

        return context

    def format_for_citation(self, articles: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format news articles for citation in reports."""
        citations: List[Dict[str, str]] = []

        for article in articles:
            citations.append(
                {
                    "title": article["title"],
                    "url": article["url"],
                    "date": article.get("published_date", "Data nao disponivel"),
                    "content": article.get("content", ""),
                }
            )

        return citations

    @staticmethod
    def _compute_date_window(days: int) -> Tuple[str, str]:
        """Return ISO date strings (YYYY-MM-DD) representing the search window."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days - 1)
        return start.date().isoformat(), end.date().isoformat()

    def _extract_published_date(self, result: Dict[str, Any]) -> str:
        """Try to normalize a published date from Tavily's response."""
        candidate_keys = [
            "published_date",
            "published_at",
            "date",
            "date_published",
            "news_date",
            "timestamp",
        ]

        for key in candidate_keys:
            normalized = self._normalize_date(result.get(key))
            if normalized:
                return normalized

        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            for key in candidate_keys + ["published_time", "modified_date", "created_at"]:
                normalized = self._normalize_date(metadata.get(key))
                if normalized:
                    return normalized

        return ""

    @staticmethod
    def _normalize_date(value: Any) -> str:
        """Convert different date formats into an ISO date string."""
        if value is None or value == "":
            return ""

        if isinstance(value, datetime):
            ts = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc).date().isoformat()

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1e12:  # likely milliseconds
                timestamp /= 1000.0
            try:
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return ""
            return dt.date().isoformat()

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ""

            # Try RFC 2822 format first (e.g., "Tue, 30 Sep 2025 05:10:32 GMT")
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                pass

            # Try ISO format and common patterns
            iso_candidate = raw.replace("Z", "+00:00")
            parse_fmts = [None, "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]

            for fmt in parse_fmts:
                try:
                    if fmt is None:
                        dt = datetime.fromisoformat(iso_candidate)
                    else:
                        dt = datetime.strptime(raw, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc).date().isoformat()
                except ValueError:
                    continue

            # Last resort: try to extract YYYY-MM-DD from beginning
            if len(raw) >= 10:
                potential = raw[:10]
                try:
                    dt = datetime.strptime(potential, "%Y-%m-%d")
                    return dt.date().isoformat()
                except ValueError:
                    pass

        return ""

    @staticmethod
    def _is_date_within_range(date_str: str, days: int) -> bool:
        """
        Check if a date string is within the specified number of days from today.

        Args:
            date_str: ISO date string (YYYY-MM-DD)
            days: Number of days back from today

        Returns:
            True if date is within range, False otherwise
        """
        try:
            article_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
            return article_date >= cutoff_date
        except (ValueError, TypeError):
            # If we can't parse the date, assume it's not valid
            return False

    def _extract_date_with_llm(self, title: str, content: str) -> str:
        """
        Use OpenAI to extract publication date from article content.

        Args:
            title: Article title
            content: Article content

        Returns:
            ISO date string (YYYY-MM-DD) or empty string if not found
        """
        try:
            # Limit content size to avoid token limits
            truncated_content = content[:1000] if len(content) > 1000 else content

            prompt = f"""Extraia a data de publicação deste artigo de notícia em português.
Procure por padrões como "quinta-feira (28)", "divulgado nesta quinta", "publicado em", datas no formato DD/MM/AAAA, etc.
Retorne APENAS a data no formato YYYY-MM-DD, sem texto adicional.
Se não encontrar uma data específica, retorne apenas "NONE".

IMPORTANTE: Hoje é {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. Use isso para interpretar datas relativas.

Título: {title}

Conteúdo: {truncated_content}

Data de publicação (YYYY-MM-DD):"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap model
                messages=[
                    {"role": "system", "content": "Você é um assistente que extrai datas de artigos de notícias. Retorne apenas datas no formato YYYY-MM-DD ou NONE."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=20,
            )

            extracted_date = response.choices[0].message.content.strip()

            # Validate format
            if extracted_date and extracted_date != "NONE":
                try:
                    datetime.strptime(extracted_date, "%Y-%m-%d")
                    logger.debug(f"LLM extracted date: {extracted_date}")
                    return extracted_date
                except ValueError:
                    logger.debug(f"Invalid date format from LLM: {extracted_date}")
                    return ""

            return ""

        except Exception as exc:
            logger.warning(f"LLM date extraction failed: {exc}")
            return ""


# Global instance
news_tool = NewsTool()
