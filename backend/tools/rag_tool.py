"""RAG tool for data dictionary semantic search."""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings

from backend.db.connection import get_db
from backend.db.models import DataDictionary
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class DictionaryRAGTool:
    """
    RAG (Retrieval-Augmented Generation) tool for data dictionary.

    Uses pgvector semantic search to find field explanations,
    valid values, and constraints.
    """

    def __init__(self):
        """Initialize embeddings model."""
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key,
        )

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on data dictionary.

        Args:
            query: Natural language query about fields
            top_k: Number of results to return
            threshold: Similarity threshold (0-1)

        Returns:
            List of relevant field definitions
        """
        logger.info(f"Dictionary semantic search: {query}")

        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)

        # Perform vector similarity search using pgvector
        with get_db() as db:
            # Use cosine similarity (1 - cosine distance)
            # Format embedding as PostgreSQL array
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

            # Use f-string to avoid parameter issues with ::vector cast
            sql = text(f"""
                SELECT
                    field_name,
                    display_name,
                    description,
                    field_type,
                    categories,
                    is_required,
                    constraints,
                    notes,
                    1 - (embedding <=> '{embedding_str}'::vector) as similarity
                FROM data_dictionary
                WHERE 1 - (embedding <=> '{embedding_str}'::vector) > {threshold}
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT {top_k}
            """)

            result = db.execute(sql)

            fields = []
            for row in result:
                fields.append({
                    "field_name": row.field_name,
                    "display_name": row.display_name,
                    "description": row.description,
                    "field_type": row.field_type,
                    "categories": row.categories,
                    "is_required": row.is_required,
                    "constraints": row.constraints,
                    "notes": row.notes,
                    "similarity": float(row.similarity),
                })

        logger.info(f"Found {len(fields)} relevant fields via semantic search")

        # If no results from semantic search, try text-based search
        if not fields:
            logger.info("Trying text-based search fallback...")
            with get_db() as db:
                from sqlalchemy import or_
                query_upper = query.upper()
                text_results = db.query(DataDictionary).filter(
                    or_(
                        DataDictionary.field_name.like(f'%{query_upper}%'),
                        DataDictionary.display_name.ilike(f'%{query}%'),
                        DataDictionary.description.ilike(f'%{query}%')
                    )
                ).limit(top_k).all()

                for row in text_results:
                    fields.append({
                        "field_name": row.field_name,
                        "display_name": row.display_name,
                        "description": row.description,
                        "field_type": row.field_type,
                        "categories": row.categories,
                        "is_required": row.is_required,
                        "constraints": row.constraints,
                        "notes": row.notes,
                        "similarity": 0.0,  # No similarity score for text search
                    })
                logger.info(f"Found {len(fields)} fields via text search")

        return fields

    def get_field_by_name(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get exact field definition by name (deterministic lookup)."""
        with get_db() as db:
            field = db.query(DataDictionary).filter_by(
                field_name=field_name.upper()
            ).first()

            if not field:
                return None

            return {
                "field_name": field.field_name,
                "display_name": field.display_name,
                "description": field.description,
                "field_type": field.field_type,
                "categories": field.categories,
                "is_required": field.is_required,
                "constraints": field.constraints,
                "notes": field.notes,
            }

    def explain_field(self, field_name: str) -> str:
        """Get human-readable explanation of a field."""
        field = self.get_field_by_name(field_name)

        if not field:
            return f"Campo '{field_name}' não encontrado no dicionário de dados."

        explanation = f"**{field['display_name']}** (`{field['field_name']}`)\n\n"
        explanation += f"{field['description']}\n\n"

        if field['categories']:
            explanation += f"**Valores possíveis:** {field['categories']}\n\n"

        if field['field_type']:
            explanation += f"**Tipo:** {field['field_type']}\n\n"

        if field['is_required']:
            explanation += "**Campo obrigatório**\n\n"

        if field['constraints']:
            explanation += f"**Restrições:** {field['constraints']}\n\n"

        if field['notes']:
            explanation += f"**Observações:** {field['notes']}\n\n"

        return explanation

    def get_context_for_query(self, query_intent: str) -> str:
        """
        Get dictionary context relevant to a query intent.

        Used to provide field semantics to SQL agent.
        """
        results = self.semantic_search(query_intent, top_k=5)

        if not results:
            return "Nenhum campo relevante encontrado."

        context = "## Campos relevantes do dicionário de dados:\n\n"

        for field in results:
            context += f"- **{field['field_name']}**: {field['description']}"
            if field['categories']:
                context += f" (Valores: {field['categories'][:100]}...)"
            context += f" [similaridade: {field['similarity']:.2f}]\n"

        return context

    def list_all_fields(self) -> List[str]:
        """List all available field names."""
        with get_db() as db:
            fields = db.query(DataDictionary.field_name).all()
            return [f.field_name for f in fields]


# Global instance
rag_tool = DictionaryRAGTool()
