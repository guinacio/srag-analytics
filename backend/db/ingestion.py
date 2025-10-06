"""Data ingestion from DATASUS CSV files to PostgreSQL."""
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import text

from backend.db.connection import engine, get_db, init_db
from backend.db.models import SRAGCase, DailyMetrics, MonthlyMetrics, Base

logger = logging.getLogger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date from YYYY-MM-DD or DD/MM/YYYY format."""
    if not date_str or date_str.strip() == "":
        return None

    date_str = date_str.strip().strip('"')  # Remove quotes and whitespace

    # Try YYYY-MM-DD format first (common in CSV exports)
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        pass

    # Try DD/MM/YYYY format
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """Safely parse integer."""
    if not value or value.strip() == "":
        return None
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def clean_row(row: Dict[str, str]) -> Dict[str, Any]:
    """Clean and transform a CSV row to database model fields."""
    return {
        "nu_notific": row.get("NU_NOTIFIC", "").strip(),
        "dt_notific": parse_date(row.get("DT_NOTIFIC")),
        "dt_sin_pri": parse_date(row.get("DT_SIN_PRI")),
        "sem_not": parse_int(row.get("SEM_NOT")),
        "sem_pri": parse_int(row.get("SEM_PRI")),

        # Geographic
        "sg_uf_not": row.get("SG_UF_NOT", "").strip()[:2],
        "co_mun_not": row.get("CO_MUN_NOT", "").strip(),
        "sg_uf": row.get("SG_UF", "").strip()[:2],
        "co_mun_res": row.get("CO_MUN_RES", "").strip(),
        "cs_zona": parse_int(row.get("CS_ZONA")),

        # Demographics
        "cs_sexo": parse_int(row.get("CS_SEXO")),
        "dt_nasc": parse_date(row.get("DT_NASC")),
        "nu_idade_n": parse_int(row.get("NU_IDADE_N")),
        "tp_idade": parse_int(row.get("TP_IDADE")),
        "cs_raca": parse_int(row.get("CS_RACA")),
        "cs_escol_n": parse_int(row.get("CS_ESCOL_N")),

        # Clinical
        "febre": parse_int(row.get("FEBRE")),
        "tosse": parse_int(row.get("TOSSE")),
        "garganta": parse_int(row.get("GARGANTA")),
        "dispneia": parse_int(row.get("DISPNEIA")),
        "desc_resp": parse_int(row.get("DESC_RESP")),
        "saturacao": parse_int(row.get("SATURACAO")),
        "diarreia": parse_int(row.get("DIARREIA")),
        "vomito": parse_int(row.get("VOMITO")),

        # Risk factors
        "puerpera": parse_int(row.get("PUERPERA")),
        "cardiopati": parse_int(row.get("CARDIOPATI")),
        "diabetes": parse_int(row.get("DIABETES")),
        "obesidade": parse_int(row.get("OBESIDADE")),
        "imunodepre": parse_int(row.get("IMUNODEPRE")),
        "asma": parse_int(row.get("ASMA")),
        "pneumopati": parse_int(row.get("PNEUMOPATI")),
        "renal": parse_int(row.get("RENAL")),
        "hepatica": parse_int(row.get("HEPATICA")),

        # Hospitalization
        "hospital": parse_int(row.get("HOSPITAL")),
        "dt_interna": parse_date(row.get("DT_INTERNA")),
        "uti": parse_int(row.get("UTI")),
        "dt_entuti": parse_date(row.get("DT_ENTUTI")),
        "dt_saiduti": parse_date(row.get("DT_SAIDUTI")),
        "suport_ven": parse_int(row.get("SUPORT_VEN")),

        # Vaccination
        "vacina": parse_int(row.get("VACINA")),
        "dt_ut_dose": parse_date(row.get("DT_UT_DOSE")),
        "vacina_cov": parse_int(row.get("VACINA_COV")),
        "dose_1_cov": parse_date(row.get("DOSE_1_COV")),
        "dose_2_cov": parse_date(row.get("DOSE_2_COV")),
        "dose_ref": parse_date(row.get("DOSE_REF")),
        "dose_2ref": parse_date(row.get("DOSE_2REF")),

        # Laboratory
        "pcr_resul": parse_int(row.get("PCR_RESUL")),
        "dt_pcr": parse_date(row.get("DT_PCR")),
        "res_an": parse_int(row.get("RES_AN")),
        "classi_fin": parse_int(row.get("CLASSI_FIN")),
        "criterio": parse_int(row.get("CRITERIO")),

        # Outcome
        "evolucao": parse_int(row.get("EVOLUCAO")),
        "dt_evoluca": parse_date(row.get("DT_EVOLUCA")),
        "dt_encerra": parse_date(row.get("DT_ENCERRA")),
    }


def ingest_csv(csv_path: Path, batch_size: int = 1000) -> int:
    """Ingest SRAG data from CSV file."""
    logger.info(f"Starting ingestion of {csv_path}")

    total_rows = 0
    batch = []

    with get_db() as db:
        with open(csv_path, 'r', encoding='latin-1') as f:
            # DATASUS uses semicolon as delimiter
            reader = csv.DictReader(f, delimiter=';')

            for row in reader:
                try:
                    cleaned = clean_row(row)
                    batch.append(SRAGCase(**cleaned))
                    total_rows += 1

                    # Bulk insert in batches
                    if len(batch) >= batch_size:
                        db.bulk_save_objects(batch)
                        db.commit()
                        logger.info(f"Ingested {total_rows} rows...")
                        batch = []

                except Exception as e:
                    logger.warning(f"Error processing row {total_rows}: {e}")
                    continue

            # Insert remaining rows
            if batch:
                db.bulk_save_objects(batch)
                db.commit()

    logger.info(f"Successfully ingested {total_rows} rows from {csv_path}")
    return total_rows


def compute_daily_metrics() -> None:
    """
    Compute and materialize daily metrics for fast chart rendering.
    
    Creates both national (state=NULL) and per-state metrics with:
    - total_cases: cumulative cases up to that date
    - new_cases: new cases on that specific date
    - Same pattern for deaths, ICU admissions, and vaccinated cases
    """
    logger.info("Computing daily metrics (national + per-state)...")

    with engine.connect() as conn:
        # Clear existing metrics
        conn.execute(text("TRUNCATE TABLE daily_metrics"))

        # 1. Compute NATIONAL metrics (state = NULL)
        logger.info("Computing national daily metrics...")
        query_national = text("""
            WITH daily_base AS (
                SELECT
                    dt_sin_pri::date AS metric_date,
                    COUNT(*) AS daily_cases,
                    SUM(CASE WHEN evolucao = 2 THEN 1 ELSE 0 END) AS daily_deaths,
                    SUM(CASE WHEN evolucao IN (1, 2) THEN 1 ELSE 0 END) AS daily_cases_with_outcome,
                    SUM(CASE WHEN uti = 1 THEN 1 ELSE 0 END) AS daily_icu_adm,
                    SUM(CASE WHEN vacina_cov = 1 THEN 1 ELSE 0 END) AS daily_vaccinated
                FROM srag_cases
                WHERE dt_sin_pri IS NOT NULL
                GROUP BY dt_sin_pri::date
            ),
            cumulative AS (
                SELECT
                    metric_date,
                    NULL as state,
                    SUM(daily_cases) OVER (ORDER BY metric_date ROWS UNBOUNDED PRECEDING) AS total_cases,
                    daily_cases AS new_cases,
                    SUM(daily_deaths) OVER (ORDER BY metric_date ROWS UNBOUNDED PRECEDING) AS total_deaths,
                    daily_deaths AS new_deaths,
                    daily_cases_with_outcome AS cases_with_outcome,
                    daily_icu_adm AS icu_admissions,
                    daily_vaccinated AS vaccinated_cases
                FROM daily_base
            )
            INSERT INTO daily_metrics 
                (metric_date, state, total_cases, new_cases, total_deaths, new_deaths, cases_with_outcome, icu_admissions, vaccinated_cases)
            SELECT
                metric_date,
                state,
                total_cases,
                new_cases,
                total_deaths,
                new_deaths,
                cases_with_outcome,
                icu_admissions,
                vaccinated_cases
            FROM cumulative
        """)
        conn.execute(query_national)
        conn.commit()

        # 2. Compute PER-STATE metrics
        logger.info("Computing per-state daily metrics...")
        query_states = text("""
            WITH daily_base AS (
                SELECT
                    dt_sin_pri::date AS metric_date,
                    sg_uf_not AS state,
                    COUNT(*) AS daily_cases,
                    SUM(CASE WHEN evolucao = 2 THEN 1 ELSE 0 END) AS daily_deaths,
                    SUM(CASE WHEN evolucao IN (1, 2) THEN 1 ELSE 0 END) AS daily_cases_with_outcome,
                    SUM(CASE WHEN uti = 1 THEN 1 ELSE 0 END) AS daily_icu_adm,
                    SUM(CASE WHEN vacina_cov = 1 THEN 1 ELSE 0 END) AS daily_vaccinated
                FROM srag_cases
                WHERE dt_sin_pri IS NOT NULL
                  AND sg_uf_not IS NOT NULL
                  AND sg_uf_not != ''
                GROUP BY dt_sin_pri::date, sg_uf_not
            ),
            cumulative AS (
                SELECT
                    metric_date,
                    state,
                    SUM(daily_cases) OVER (PARTITION BY state ORDER BY metric_date ROWS UNBOUNDED PRECEDING) AS total_cases,
                    daily_cases AS new_cases,
                    SUM(daily_deaths) OVER (PARTITION BY state ORDER BY metric_date ROWS UNBOUNDED PRECEDING) AS total_deaths,
                    daily_deaths AS new_deaths,
                    daily_cases_with_outcome AS cases_with_outcome,
                    daily_icu_adm AS icu_admissions,
                    daily_vaccinated AS vaccinated_cases
                FROM daily_base
            )
            INSERT INTO daily_metrics 
                (metric_date, state, total_cases, new_cases, total_deaths, new_deaths, cases_with_outcome, icu_admissions, vaccinated_cases)
            SELECT
                metric_date,
                state,
                total_cases,
                new_cases,
                total_deaths,
                new_deaths,
                cases_with_outcome,
                icu_admissions,
                vaccinated_cases
            FROM cumulative
        """)
        conn.execute(query_states)
        conn.commit()

    logger.info("Daily metrics computed successfully (national + per-state)")


def compute_monthly_metrics() -> None:
    """Compute and materialize monthly metrics."""
    logger.info("Computing monthly metrics...")

    with engine.connect() as conn:
        # Clear existing metrics
        conn.execute(text("TRUNCATE TABLE monthly_metrics"))

        # Compute monthly aggregates
        query = text("""
            INSERT INTO monthly_metrics (year, month, total_cases, total_deaths, vaccination_rate)
            SELECT
                EXTRACT(YEAR FROM dt_sin_pri) as year,
                EXTRACT(MONTH FROM dt_sin_pri) as month,
                COUNT(*) as total_cases,
                SUM(CASE WHEN evolucao = 2 THEN 1 ELSE 0 END) as total_deaths,
                AVG(CASE WHEN vacina_cov = 1 THEN 100.0 ELSE 0.0 END) as vaccination_rate
            FROM srag_cases
            WHERE dt_sin_pri IS NOT NULL
            GROUP BY EXTRACT(YEAR FROM dt_sin_pri), EXTRACT(MONTH FROM dt_sin_pri)
            ORDER BY year, month
        """)
        conn.execute(query)
        conn.commit()

    logger.info("Monthly metrics computed successfully")


def grant_readonly_permissions() -> None:
    """Grant read-only permissions to SQL agent user."""
    logger.info("Granting read-only permissions...")

    with engine.connect() as conn:
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO srag_readonly"))
        conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO srag_readonly"))
        conn.commit()

    logger.info("Permissions granted successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize database (create tables)
    logger.info("Initializing database tables...")
    init_db()

    # Ingest all CSV files in data directory
    data_dir = Path("data")
    csv_files = list(data_dir.glob("INFLUD*.csv"))

    if not csv_files:
        logger.warning(f"No CSV files found in {data_dir}")
    else:
        for csv_file in csv_files:
            ingest_csv(csv_file)

    # Compute materialized metrics
    compute_daily_metrics()
    compute_monthly_metrics()

    # Grant permissions
    grant_readonly_permissions()

    logger.info("Data ingestion complete!")
