"""Metrics calculation tool for the 4 required SRAG metrics."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import text

from backend.db.connection import get_db

logger = logging.getLogger(__name__)


class MetricsTool:
    """
    Calculate the 4 required SRAG metrics:
    1. Taxa de aumento de casos (case increase rate)
    2. Taxa de mortalidade (mortality rate)
    3. Taxa de ocupação de UTI (ICU occupancy rate)
    4. Taxa de vacinação (vaccination rate)
    """

    def calculate_case_increase_rate(
        self,
        days: int = 7,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate case increase rate comparing last N days vs previous N days.

        Returns:
            {
                'current_period_cases': int,
                'previous_period_cases': int,
                'increase_rate': float (percentage),
                'period_days': int,
                'state': str or None
            }
        """
        logger.info(f"Calculating case increase rate (last {days} days)")

        with get_db() as db:
            # Use bound parameters to prevent SQL injection
            state_filter = "AND sg_uf_not = :state" if state else ""

            query = text(f"""
                WITH current_period AS (
                    SELECT COUNT(*) as cases
                    FROM srag_cases
                    WHERE dt_sin_pri >= CURRENT_DATE - :days * INTERVAL '1 day'
                      AND dt_sin_pri < CURRENT_DATE
                      {state_filter}
                ),
                previous_period AS (
                    SELECT COUNT(*) as cases
                    FROM srag_cases
                    WHERE dt_sin_pri >= CURRENT_DATE - :days_double * INTERVAL '1 day'
                      AND dt_sin_pri < CURRENT_DATE - :days * INTERVAL '1 day'
                      {state_filter}
                )
                SELECT
                    c.cases as current_cases,
                    p.cases as previous_cases,
                    CASE
                        WHEN p.cases > 0 THEN ((c.cases - p.cases)::float / p.cases * 100)
                        ELSE 0
                    END as increase_rate
                FROM current_period c, previous_period p
            """)

            params = {'days': days, 'days_double': days * 2}
            if state:
                params['state'] = state

            result = db.execute(query, params).first()

            return {
                'current_period_cases': result.current_cases,
                'previous_period_cases': result.previous_cases,
                'increase_rate': float(result.increase_rate),
                'period_days': days,
                'state': state,
            }

    def calculate_mortality_rate(
        self,
        days: Optional[int] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate mortality rate (deaths / total cases).

        Args:
            days: If specified, calculate for last N days only
            state: If specified, filter by state

        Returns:
            {
                'total_cases': int,
                'total_deaths': int,
                'mortality_rate': float (percentage),
                'period_days': int or None,
                'state': str or None
            }
        """
        logger.info(f"Calculating mortality rate")

        with get_db() as db:
            date_filter = "AND dt_sin_pri >= CURRENT_DATE - :days * INTERVAL '1 day'" if days else ""
            state_filter = "AND sg_uf_not = :state" if state else ""

            query = text(f"""
                SELECT
                    COUNT(*) as total_cases,
                    SUM(CASE WHEN evolucao = 2 THEN 1 ELSE 0 END) as total_deaths,
                    CASE
                        WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN evolucao = 2 THEN 1 ELSE 0 END)::float / COUNT(*) * 100)
                        ELSE 0
                    END as mortality_rate
                FROM srag_cases
                WHERE evolucao IS NOT NULL
                  {date_filter}
                  {state_filter}
            """)

            params = {}
            if days:
                params['days'] = days
            if state:
                params['state'] = state

            result = db.execute(query, params).first()

            return {
                'total_cases': result.total_cases,
                'total_deaths': result.total_deaths,
                'mortality_rate': float(result.mortality_rate),
                'period_days': days,
                'state': state,
            }

    def calculate_icu_occupancy_rate(
        self,
        days: Optional[int] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate ICU occupancy rate (ICU admissions / total hospitalizations).

        Note: This is a proxy metric based on available data.
        Actual ICU occupancy would require bed capacity data.

        Returns:
            {
                'total_hospitalizations': int,
                'icu_admissions': int,
                'icu_occupancy_rate': float (percentage),
                'period_days': int or None,
                'state': str or None
            }
        """
        logger.info(f"Calculating ICU occupancy rate")

        with get_db() as db:
            date_filter = "AND dt_sin_pri >= CURRENT_DATE - :days * INTERVAL '1 day'" if days else ""
            state_filter = "AND sg_uf_not = :state" if state else ""

            query = text(f"""
                SELECT
                    COUNT(*) as total_hospitalizations,
                    SUM(CASE WHEN uti = 1 THEN 1 ELSE 0 END) as icu_admissions,
                    CASE
                        WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN uti = 1 THEN 1 ELSE 0 END)::float / COUNT(*) * 100)
                        ELSE 0
                    END as icu_rate
                FROM srag_cases
                WHERE hospital = 1
                  {date_filter}
                  {state_filter}
            """)

            params = {}
            if days:
                params['days'] = days
            if state:
                params['state'] = state

            result = db.execute(query, params).first()

            return {
                'total_hospitalizations': result.total_hospitalizations,
                'icu_admissions': result.icu_admissions,
                'icu_occupancy_rate': float(result.icu_rate),
                'period_days': days,
                'state': state,
            }

    def calculate_vaccination_rate(
        self,
        days: Optional[int] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate vaccination rate among SRAG cases.

        Returns:
            {
                'total_cases': int (all cases in period),
                'vaccinated_cases': int (at least 1 dose),
                'fully_vaccinated_cases': int (2+ doses: dose_2_cov OR dose_ref OR dose_2ref),
                'vaccination_rate': float (percentage of all cases),
                'full_vaccination_rate': float (percentage of all cases),
                'period_days': int or None,
                'state': str or None
            }
        """
        logger.info(f"Calculating vaccination rate")

        with get_db() as db:
            date_filter = "AND dt_sin_pri >= CURRENT_DATE - :days * INTERVAL '1 day'" if days else ""
            state_filter = "AND sg_uf_not = :state" if state else ""

            query = text(f"""
                SELECT
                    COUNT(*) as total_cases,
                    SUM(CASE WHEN vacina_cov = 1 THEN 1 ELSE 0 END) as vaccinated,
                    SUM(CASE WHEN (dose_2_cov = 1 OR dose_ref = 1 OR dose_2ref = 1) THEN 1 ELSE 0 END) as fully_vaccinated,
                    CASE
                        WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN vacina_cov = 1 THEN 1 ELSE 0 END)::float / COUNT(*) * 100)
                        ELSE 0
                    END as vac_rate,
                    CASE
                        WHEN COUNT(*) > 0 THEN (SUM(CASE WHEN (dose_2_cov = 1 OR dose_ref = 1 OR dose_2ref = 1) THEN 1 ELSE 0 END)::float / COUNT(*) * 100)
                        ELSE 0
                    END as full_vac_rate
                FROM srag_cases
                WHERE dt_sin_pri IS NOT NULL
                  {date_filter}
                  {state_filter}
            """)

            params = {}
            if days:
                params['days'] = days
            if state:
                params['state'] = state

            result = db.execute(query, params).first()

            return {
                'total_cases': result.total_cases,
                'vaccinated_cases': result.vaccinated,
                'fully_vaccinated_cases': result.fully_vaccinated,
                'vaccination_rate': float(result.vac_rate),
                'full_vaccination_rate': float(result.full_vac_rate),
                'period_days': days,
                'state': state,
            }

    def calculate_all_metrics(
        self,
        days: Optional[int] = 30,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate all 4 required metrics at once."""
        logger.info(f"Calculating all metrics for last {days} days")

        return {
            'case_increase': self.calculate_case_increase_rate(days=days, state=state),
            'mortality': self.calculate_mortality_rate(days=days, state=state),
            'icu_occupancy': self.calculate_icu_occupancy_rate(days=days, state=state),
            'vaccination': self.calculate_vaccination_rate(days=days, state=state),
            'metadata': {
                'calculated_at': datetime.utcnow().isoformat(),
                'period_days': days,
                'state': state,
            }
        }

    def get_daily_cases_chart_data(
        self,
        days: int = 30,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get daily cases for the last N days (for chart)."""
        with get_db() as db:
            if state:
                # Query raw data with state filter
                query = text("""
                    SELECT
                        dt_sin_pri::text as date,
                        COUNT(*) as cases
                    FROM srag_cases
                    WHERE dt_sin_pri >= CURRENT_DATE - :days * INTERVAL '1 day'
                      AND dt_sin_pri < CURRENT_DATE
                      AND sg_uf_not = :state
                    GROUP BY dt_sin_pri
                    ORDER BY dt_sin_pri
                """)
                params = {'days': days, 'state': state}
            else:
                # Use materialized view for faster queries
                query = text("""
                    SELECT
                        metric_date::text as date,
                        new_cases as cases
                    FROM daily_metrics
                    WHERE metric_date >= CURRENT_DATE - :days * INTERVAL '1 day'
                      AND metric_date < CURRENT_DATE
                    ORDER BY metric_date
                """)
                params = {'days': days}

            result = db.execute(query, params)
            return [{'date': row.date, 'cases': row.cases} for row in result]

    def get_monthly_cases_chart_data(
        self,
        months: int = 12,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get monthly cases for the last N months (for chart)."""
        with get_db() as db:
            if state:
                # Query raw data with state filter
                query = text("""
                    SELECT
                        EXTRACT(YEAR FROM dt_sin_pri)::int as year,
                        EXTRACT(MONTH FROM dt_sin_pri)::int as month,
                        COUNT(*) as total_cases
                    FROM srag_cases
                    WHERE dt_sin_pri >= CURRENT_DATE - :months * INTERVAL '1 month'
                      AND sg_uf_not = :state
                    GROUP BY year, month
                    ORDER BY year, month
                """)
                params = {'months': months, 'state': state}
            else:
                # Use materialized view for faster queries
                query = text("""
                    SELECT
                        year,
                        month,
                        total_cases
                    FROM monthly_metrics
                    WHERE (year * 12 + month) >= (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - :months)
                    ORDER BY year, month
                """)
                params = {'months': months}

            result = db.execute(query, params)
            return [
                {
                    'year': row.year,
                    'month': row.month,
                    'cases': row.total_cases,
                    'label': f"{row.year}-{row.month:02d}"
                }
                for row in result
            ]


# Global instance
metrics_tool = MetricsTool()
