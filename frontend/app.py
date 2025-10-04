"""Streamlit frontend for SRAG Analytics."""
import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any

# Page configuration
st.set_page_config(
    page_title="Análise de SRAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Configuration
API_BASE_URL = "http://localhost:8000"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin-bottom: 1rem;
    }
    .news-card {
        padding: 1rem;
        border-left: 3px solid #1f77b4;
        margin-bottom: 1rem;
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)


def api_request(endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
    """Make API request with error handling."""
    url = f"{API_BASE_URL}{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, params=data, timeout=60)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=120)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        st.error(f"Erro na API: {str(e)}")
        return {}


def render_metric_card(title: str, value: Any, delta: Any = None, help_text: str = None):
    """Render a metric card."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric(label=title, value=value, delta=delta, help=help_text)


def create_daily_chart(data: list, days: int = 30):
    """Create daily cases line chart."""
    if not data:
        st.warning("Nenhum dado disponível para o gráfico diário")
        return

    dates = [d['date'] for d in data]
    cases = [d['cases'] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=cases,
        mode='lines+markers',
        name='Casos Diários',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6),
    ))

    fig.update_layout(
        title=f"Casos Diários de SRAG (Últimos {days} Dias)",
        xaxis_title="Data",
        yaxis_title="Número de Casos",
        hovermode='x unified',
        template='plotly_white',
    )

    st.plotly_chart(fig, use_container_width=True)


def create_monthly_chart(data: list):
    """Create monthly cases bar chart."""
    if not data:
        st.warning("Nenhum dado disponível para o gráfico mensal")
        return

    labels = [d['label'] for d in data]
    cases = [d['cases'] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=cases,
        name='Casos Mensais',
        marker_color='#ff7f0e',
    ))

    fig.update_layout(
        title="Casos Mensais de SRAG (Últimos 12 Meses)",
        xaxis_title="Mês",
        yaxis_title="Número de Casos",
        template='plotly_white',
    )

    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main Streamlit application."""

    # Header
    st.markdown('<div class="main-header">Painel de Análise de SRAG</div>', unsafe_allow_html=True)
    st.markdown("**Análise com IA para Síndrome Respiratória Aguda Grave (SRAG)**")
    st.divider()

    # Sidebar
    with st.sidebar:
        st.header("Configuração")

        # Filters
        st.subheader("Filtros")
        days = st.slider("Período de Análise (dias)", 7, 90, 30)
        state_options = ["Todos os Estados", "SP", "RJ", "MG", "BA", "PR", "RS", "SC", "GO", "DF"]
        selected_state = st.selectbox("Estado (UF)", state_options)
        state_filter = None if selected_state == "Todos os Estados" else selected_state

        st.divider()

        # Actions
        st.subheader("Ações")
        generate_report = st.button("Gerar Relatório", type="primary", use_container_width=True)

        st.divider()

        # About
        st.subheader("Sobre")
        st.markdown("""
        Este painel usa agentes de IA para analisar dados de SRAG do DATASUS e fornecer:
        - **Métricas em tempo real**
        - **Contexto de notícias**
        - **Relatórios automatizados**

        Desenvolvido com LangGraph & OpenAI
        """)

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Painel",
        "Métricas",
        "Notícias",
        "Relatório",
        "Dicionário de Dados"
    ])

    # Tab 1: Dashboard Overview
    with tab1:
        st.header("Painel Geral")

        if generate_report or st.session_state.get("report_generated"):
            with st.spinner("Gerando relatório completo..."):
                report_data = api_request(
                    "/report",
                    method="POST",
                    data={"days": days, "state": state_filter}
                )

                if report_data:
                    st.session_state["report_data"] = report_data
                    st.session_state["report_generated"] = True

                    # Display key metrics
                    st.subheader("Métricas Principais")
                    metrics = report_data.get("metrics", {})

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        case_increase = metrics.get("case_increase", {})
                        rate = case_increase.get("increase_rate", 0)
                        period = case_increase.get("period_days", 30)
                        st.metric(
                            "Taxa de Aumento de Casos",
                            f"{rate:+.1f}%",
                            help=f"Comparação dos últimos {period} dias com o período anterior de {period} dias"
                        )

                    with col2:
                        mortality = metrics.get("mortality", {})
                        mort_rate = mortality.get("mortality_rate", 0)
                        st.metric(
                            "Taxa de Mortalidade",
                            f"{mort_rate:.1f}%",
                            help="Óbitos / Total de Casos"
                        )

                    with col3:
                        icu = metrics.get("icu_occupancy", {})
                        icu_rate = icu.get("icu_occupancy_rate", 0)
                        st.metric(
                            "Taxa de Ocupação de UTI",
                            f"{icu_rate:.1f}%",
                            help="Admissões em UTI / Hospitalizações"
                        )

                    with col4:
                        vaccination = metrics.get("vaccination", {})
                        vac_rate = vaccination.get("vaccination_rate", 0)
                        st.metric(
                            "Taxa de Vacinação",
                            f"{vac_rate:.1f}%",
                            help="Casos vacinados / Total de casos"
                        )

                    st.divider()

                    # Charts
                    st.subheader("Análise de Tendências")
                    col1, col2 = st.columns(2)

                    with col1:
                        chart_data = report_data.get("chart_data", {})
                        create_daily_chart(chart_data.get("daily_30d", []), days=days)

                    with col2:
                        create_monthly_chart(chart_data.get("monthly_12m", []))

                    st.divider()

                    # News context
                    st.subheader("Contexto de Notícias Recentes")
                    news_citations = report_data.get("news_citations", [])

                    if news_citations:
                        for citation in news_citations[:5]:
                            st.markdown(f"""
                            <div class="news-card">
                                <b>{citation['title']}</b><br>
                                <small>{citation.get('date', 'N/A')}</small><br>
                                <a href="{citation['url']}" target="_blank">Leia mais</a>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Nenhuma notícia recente encontrada")

                    # Audit trail download
                    st.divider()
                    st.subheader("Trilha de Auditoria")
                    audit_trail = report_data.get("audit_trail", {})

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info("Baixe a trilha de auditoria completa para transparência e governança")
                    with col2:
                        st.download_button(
                            label="Baixar JSON",
                            data=json.dumps(audit_trail, indent=2, ensure_ascii=False),
                            file_name=f"srag_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                        )

        else:
            st.info("Clique em 'Gerar Relatório' na barra lateral para iniciar a análise")

    # Tab 2: Detailed Metrics
    with tab2:
        st.header("Métricas Detalhadas")

        if st.button("Atualizar Métricas"):
            with st.spinner("Calculando métricas..."):
                metrics_data = api_request(
                    "/metrics",
                    method="POST",
                    data={"days": days, "state": state_filter}
                )

                if metrics_data:
                    st.subheader("1. Taxa de Aumento de Casos")
                    case_inc = metrics_data.get("case_increase", {})
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Período Atual", case_inc.get("current_period_cases", 0))
                    col2.metric("Período Anterior", case_inc.get("previous_period_cases", 0))
                    col3.metric("Taxa de Aumento", f"{case_inc.get('increase_rate', 0):+.1f}%")

                    st.divider()

                    st.subheader("2. Taxa de Mortalidade")
                    mortality = metrics_data.get("mortality", {})
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total de Casos", mortality.get("total_cases", 0))
                    col2.metric("Total de Óbitos", mortality.get("total_deaths", 0))
                    col3.metric("Taxa de Mortalidade", f"{mortality.get('mortality_rate', 0):.2f}%")

                    st.divider()

                    st.subheader("3. Ocupação de UTI")
                    icu = metrics_data.get("icu_occupancy", {})
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Hospitalizações", icu.get("total_hospitalizations", 0))
                    col2.metric("Admissões em UTI", icu.get("icu_admissions", 0))
                    col3.metric("Taxa de UTI", f"{icu.get('icu_occupancy_rate', 0):.2f}%")

                    st.divider()

                    st.subheader("4. Taxa de Vacinação")
                    vac = metrics_data.get("vaccination", {})
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total de Casos", vac.get("total_cases", 0))
                    col2.metric("Vacinados", vac.get("vaccinated_cases", 0))
                    col3.metric("Totalmente Vacinados", vac.get("fully_vaccinated_cases", 0))
                    col4.metric("Taxa de Vac.", f"{vac.get('vaccination_rate', 0):.2f}%")

    # Tab 3: News
    with tab3:
        st.header("Busca de Notícias de SRAG")

        search_query = st.text_input("Busca customizada (opcional)", placeholder="ex: SRAG São Paulo")
        search_days = st.slider("Buscar nos últimos (dias)", 1, 30, 7)

        if st.button("Buscar Notícias"):
            with st.spinner("Buscando notícias..."):
                news_data = api_request(
                    "/news",
                    method="POST",
                    data={
                        "query": search_query if search_query else None,
                        "days": search_days,
                        "max_results": 10,
                    }
                )

                if news_data:
                    articles = news_data.get("articles", [])
                    st.success(f"Encontrados {len(articles)} artigos")

                    for article in articles:
                        with st.expander(f"{article['title']}"):
                            st.markdown(f"**Publicado em:** {article.get('published_date', 'N/A')}")
                            st.markdown(f"**Pontuação:** {article.get('score', 0):.2f}")
                            st.markdown(f"**Resumo:** {article['content'][:300]}...")
                            st.markdown(f"[Leia o artigo completo]({article['url']})")

    # Tab 4: Full Report
    with tab4:
        st.header("Relatório Gerado por IA")

        if st.session_state.get("report_data"):
            report = st.session_state["report_data"].get("report", "")
            st.markdown(report)

            # Download report
            st.download_button(
                label="Baixar Relatório (Markdown)",
                data=report,
                file_name=f"srag_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
            )
        else:
            st.info("Gere um relatório primeiro na aba Painel")

    # Tab 5: Data Dictionary
    with tab5:
        st.header("Explorador do Dicionário de Dados")

        st.markdown("Busque por definições e explicações de campos")

        search_field = st.text_input("Buscar campos", placeholder="ex: UTI, vacina, mortalidade")

        if search_field:
            with st.spinner("Buscando no dicionário..."):
                results = api_request(f"/dictionary/search?query={search_field}")

                if results and results.get("results"):
                    for field in results["results"]:
                        with st.expander(f"{field['display_name']} ({field['field_name']})"):
                            st.markdown(f"**Descrição:** {field['description']}")
                            if field.get('categories'):
                                st.markdown(f"**Valores Válidos:** {field['categories']}")
                            if field.get('field_type'):
                                st.markdown(f"**Tipo:** {field['field_type']}")
                            if field.get('is_required'):
                                st.markdown("**Campo Obrigatório**")
                            st.markdown(f"**Similaridade:** {field.get('similarity', 0):.2f}")
                else:
                    st.warning("Nenhum campo encontrado")


if __name__ == "__main__":
    main()