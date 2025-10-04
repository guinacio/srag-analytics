"""Parse SIVEP-Gripe data dictionary PDF to structured format."""
import pdfplumber
import logging
import json
from pathlib import Path
from typing import List, Dict, Any
from langchain_openai import OpenAIEmbeddings

from backend.db.connection import get_db
from backend.db.models import DataDictionary
from backend.config.settings import settings

logger = logging.getLogger(__name__)


def extract_dictionary_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extract field definitions from SIVEP-Gripe data dictionary PDF.

    This function parses the PDF and extracts structured information about
    each field in the SRAG dataset.
    """
    logger.info(f"Parsing PDF dictionary: {pdf_path}")

    fields = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            if not text:
                continue

            # Parse field definitions
            # The PDF typically has format:
            # FIELD_NAME
            # Description: ...
            # Type: ...
            # Values: ...

            lines = text.split('\n')
            current_field = None

            for line in lines:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Detect field name (usually all caps with underscores)
                if line.isupper() and '_' in line and len(line) < 50:
                    if current_field:
                        fields.append(current_field)

                    current_field = {
                        'field_name': line,
                        'display_name': line.replace('_', ' ').title(),
                        'description': '',
                        'field_type': 'text',
                        'categories': '',
                        'is_required': False,
                        'constraints': '',
                        'source_page': page_num,
                        'notes': ''
                    }

                # Extract description
                elif current_field and ('descricao' in line.lower() or 'description' in line.lower()):
                    desc_parts = line.split(':', 1)
                    if len(desc_parts) > 1:
                        current_field['description'] += desc_parts[1].strip() + ' '

                # Extract type
                elif current_field and ('tipo' in line.lower() or 'type' in line.lower()):
                    type_parts = line.split(':', 1)
                    if len(type_parts) > 1:
                        current_field['field_type'] = type_parts[1].strip()

                # Extract categories/values
                elif current_field and ('valores' in line.lower() or 'categories' in line.lower()):
                    cat_parts = line.split(':', 1)
                    if len(cat_parts) > 1:
                        current_field['categories'] += cat_parts[1].strip() + '; '

                # Check if required
                elif current_field and ('obrigatorio' in line.lower() or 'required' in line.lower()):
                    current_field['is_required'] = True

                # Additional context
                elif current_field and current_field['description']:
                    current_field['notes'] += line + ' '

            # Add last field
            if current_field:
                fields.append(current_field)

    logger.info(f"Extracted {len(fields)} field definitions from PDF")
    return fields


def create_manual_dictionary() -> List[Dict[str, Any]]:
    """
    Create manual dictionary for key fields based on SIVEP-Gripe knowledge.

    This serves as a fallback and supplements PDF parsing with known field semantics.
    """
    return [
        {
            'field_name': 'DT_SIN_PRI',
            'display_name': 'Data dos Primeiros Sintomas',
            'description': 'Data de inicio dos primeiros sintomas da sindrome respiratoria aguda grave',
            'field_type': 'date',
            'categories': '',
            'is_required': True,
            'constraints': 'Formato DD/MM/YYYY',
            'source_page': 0,
            'notes': 'Campo critico para analise temporal'
        },
        {
            'field_name': 'SG_UF_NOT',
            'display_name': 'UF de Notificacao',
            'description': 'Sigla da Unidade Federativa (Estado) onde o caso foi notificado',
            'field_type': 'text',
            'categories': 'AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE, TO',
            'is_required': True,
            'constraints': '2 caracteres',
            'source_page': 0,
            'notes': 'Permite analise geografica'
        },
        {
            'field_name': 'EVOLUCAO',
            'display_name': 'Evolucao do Caso',
            'description': 'Desfecho clinico do paciente',
            'field_type': 'integer',
            'categories': '1=Cura, 2=Obito, 3=Obito por outras causas, 9=Ignorado',
            'is_required': True,
            'constraints': '',
            'source_page': 0,
            'notes': 'Essencial para calculo de taxa de mortalidade'
        },
        {
            'field_name': 'UTI',
            'display_name': 'Internacao em UTI',
            'description': 'Indica se o paciente foi internado em Unidade de Terapia Intensiva',
            'field_type': 'integer',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': '',
            'source_page': 0,
            'notes': 'Critico para taxa de ocupacao de UTI'
        },
        {
            'field_name': 'VACINA_COV',
            'display_name': 'Vacina COVID-19',
            'description': 'Indica se o paciente recebeu vacina contra COVID-19',
            'field_type': 'integer',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': '',
            'source_page': 0,
            'notes': 'Usado para calcular taxa de vacinacao'
        },
        {
            'field_name': 'DT_ENTUTI',
            'display_name': 'Data de Entrada na UTI',
            'description': 'Data em que o paciente foi admitido na UTI',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'Formato DD/MM/YYYY',
            'source_page': 0,
            'notes': 'Permite calcular tempo de ocupacao de UTI'
        },
        {
            'field_name': 'DT_SAIDUTI',
            'display_name': 'Data de Saida da UTI',
            'description': 'Data em que o paciente saiu da UTI',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'Formato DD/MM/YYYY',
            'source_page': 0,
            'notes': 'Permite calcular tempo de ocupacao de UTI'
        },
        {
            'field_name': 'CLASSI_FIN',
            'display_name': 'Classificacao Final',
            'description': 'Classificacao final do caso',
            'field_type': 'integer',
            'categories': '1=SRAG por influenza, 2=SRAG por outro virus respiratorio, 3=SRAG por outro agente etiologico, 4=SRAG nao especificado, 5=SRAG por COVID-19',
            'is_required': True,
            'constraints': '',
            'source_page': 0,
            'notes': 'Permite filtrar casos por tipo de agente'
        },
        {
            'field_name': 'DOSE_1_COV',
            'display_name': '1a Dose COVID-19',
            'description': 'Indica se recebeu primeira dose da vacina COVID-19',
            'field_type': 'integer',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': '',
            'source_page': 0,
            'notes': 'Detalhe do status vacinal'
        },
        {
            'field_name': 'DOSE_2_COV',
            'display_name': '2a Dose COVID-19',
            'description': 'Indica se recebeu segunda dose da vacina COVID-19',
            'field_type': 'integer',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': '',
            'source_page': 0,
            'notes': 'Detalhe do status vacinal'
        },
        {
            'field_name': 'DOSE_REF',
            'display_name': 'Dose de Reforco COVID-19',
            'description': 'Indica se recebeu dose de reforco da vacina COVID-19',
            'field_type': 'integer',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': '',
            'source_page': 0,
            'notes': 'Detalhe do status vacinal'
        },
    ]


def populate_dictionary_with_embeddings() -> None:
    """Parse PDF dictionary, create embeddings, and populate database."""
    logger.info("Populating data dictionary with embeddings...")

    # Use manual dictionary as primary source (PDF parsing is unreliable)
    fields = create_manual_dictionary()
    logger.info(f"Using {len(fields)} manually curated field definitions")

    # Optionally try to parse PDF and add any additional fields
    pdf_path = Path("data/dicionario-de-dados-2019-a-2025.pdf")
    if pdf_path.exists():
        try:
            pdf_fields = extract_dictionary_from_pdf(pdf_path)
            existing_names = {f['field_name'] for f in fields}

            for pdf_field in pdf_fields:
                if pdf_field['field_name'] not in existing_names:
                    fields.append(pdf_field)
                    logger.info(f"Added field from PDF: {pdf_field['field_name']}")
        except Exception as e:
            logger.warning(f"PDF parsing encountered error (continuing with manual dictionary): {e}")
    else:
        logger.info(f"PDF not found at {pdf_path}, using manual dictionary only")

    # Initialize embeddings model
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.openai_api_key
    )

    # Create embeddings and store in database
    with get_db() as db:
        for field in fields:
            # Create text for embedding (concatenate all meaningful text)
            embed_text = f"{field['field_name']} {field['display_name']} {field['description']} {field['categories']} {field['notes']}"

            # Generate embedding
            embedding_vector = embeddings.embed_query(embed_text)

            # Create database entry
            dict_entry = DataDictionary(
                field_name=field['field_name'],
                display_name=field['display_name'],
                description=field['description'],
                field_type=field['field_type'],
                categories=field['categories'],
                is_required=field['is_required'],
                constraints=field['constraints'],
                source_page=field['source_page'],
                notes=field['notes'],
                embedding=embedding_vector
            )

            # Upsert (update if exists, insert if not)
            existing = db.query(DataDictionary).filter_by(field_name=field['field_name']).first()
            if existing:
                for key, value in field.items():
                    if key != 'field_name':
                        setattr(existing, key, value)
                existing.embedding = embedding_vector
            else:
                db.add(dict_entry)

        db.commit()

    logger.info(f"Successfully populated {len(fields)} dictionary entries with embeddings")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    populate_dictionary_with_embeddings()
