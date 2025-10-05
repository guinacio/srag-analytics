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


def create_manual_dictionary() -> List[Dict[str, Any]]:
    """
    Complete SIVEP-Gripe data dictionary for all SRAGCase model fields.
    Extracted from official DATASUS data dictionary (dicionario-de-dados-2019-a-2025.pdf).
    """
    return [
        # Notification fields
        {
            'field_name': 'NU_NOTIFIC',
            'display_name': 'Numero da Notificacao',
            'description': 'Numero sequencial gerado automaticamente pelo sistema para identificar o registro',
            'field_type': 'varchar',
            'categories': '',
            'is_required': True,
            'constraints': 'Varchar2(12)',
            'source_page': 1,
            'notes': 'Campo Interno - gerado automaticamente'
        },
        {
            'field_name': 'DT_NOTIFIC',
            'display_name': 'Data do Preenchimento da Ficha de Notificacao',
            'description': 'Data de preenchimento da ficha de notificacao',
            'field_type': 'date',
            'categories': '',
            'is_required': True,
            'constraints': 'DD/MM/AAAA - Data deve ser <= a data da digitacao',
            'source_page': 1,
            'notes': 'Campo Obrigatorio'
        },
        {
            'field_name': 'SEM_NOT',
            'display_name': 'Semana Epidemiologica do Preenchimento da Ficha',
            'description': 'Semana Epidemiologica do preenchimento da ficha de notificacao. Calculado a partir da data dos Primeiros Sintomas',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar2(6)',
            'source_page': 1,
            'notes': 'Campo Interno - calculado automaticamente'
        },

        # Temporal fields
        {
            'field_name': 'DT_SIN_PRI',
            'display_name': 'Data de 1os Sintomas',
            'description': 'Data de 1o sintomas do caso',
            'field_type': 'date',
            'categories': '',
            'is_required': True,
            'constraints': 'DD/MM/AAAA - Data deve ser <= a data da digitacao e data do preenchimento da ficha',
            'source_page': 2,
            'notes': 'Campo Obrigatorio - critico para analise temporal'
        },
        {
            'field_name': 'SEM_PRI',
            'display_name': 'Semana Epidemiologica dos Primeiros Sintomas',
            'description': 'Semana Epidemiologica do inicio dos sintomas. Calculado a partir da data dos Primeiros Sintomas',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar2(6)',
            'source_page': 2,
            'notes': 'Campo Interno - calculado automaticamente'
        },

        # Geographic fields
        {
            'field_name': 'SG_UF_NOT',
            'display_name': 'UF de Notificacao',
            'description': 'Unidade Federativa onde esta localizada a Unidade que realizou a notificacao',
            'field_type': 'varchar',
            'categories': 'Tabela com codigo e siglas das UF padronizados pelo IBGE',
            'is_required': True,
            'constraints': 'Varchar2(2)',
            'source_page': 2,
            'notes': 'Campo Obrigatorio - permite analise geografica'
        },
        {
            'field_name': 'CO_MUN_NOT',
            'display_name': 'Municipio de Notificacao - Codigo IBGE',
            'description': 'Municipio onde esta localizada a Unidade que realizou a notificacao',
            'field_type': 'varchar',
            'categories': 'Tabela com codigo e nomes dos Municipios padronizados pelo IBGE',
            'is_required': True,
            'constraints': 'Varchar2(6)',
            'source_page': 2,
            'notes': 'Campo Obrigatorio'
        },
        {
            'field_name': 'SG_UF',
            'display_name': 'UF de Residencia',
            'description': 'Unidade Federativa de residencia do paciente',
            'field_type': 'varchar',
            'categories': 'Tabela com codigo e siglas das UF padronizados pelo IBGE',
            'is_required': True,
            'constraints': 'Varchar2(2)',
            'source_page': 6,
            'notes': 'Campo Obrigatorio se campo Pais for Brasil'
        },
        {
            'field_name': 'CO_MUN_RES',
            'display_name': 'Municipio de Residencia - Codigo IBGE',
            'description': 'Municipio de residencia do paciente',
            'field_type': 'varchar',
            'categories': 'Tabela com codigo e nome dos Municipios padronizados pelo IBGE',
            'is_required': True,
            'constraints': 'Varchar2(6)',
            'source_page': 6,
            'notes': 'Campo Obrigatorio se campo Pais for Brasil'
        },
        {
            'field_name': 'CS_ZONA',
            'display_name': 'Zona',
            'description': 'Zona geografica do endereco de residencia do paciente',
            'field_type': 'varchar',
            'categories': '1=Urbana, 2=Rural, 3=Periurbana, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 7,
            'notes': 'Campo Essencial'
        },

        # Demographics
        {
            'field_name': 'CS_SEXO',
            'display_name': 'Sexo',
            'description': 'Sexo do paciente',
            'field_type': 'varchar',
            'categories': '1=Masculino, 2=Feminino, 9=Ignorado',
            'is_required': True,
            'constraints': 'Varchar2(1)',
            'source_page': 3,
            'notes': 'Campo Obrigatorio'
        },
        {
            'field_name': 'DT_NASC',
            'display_name': 'Data de Nascimento',
            'description': 'Data de nascimento do paciente',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser <= a data dos primeiros sintomas',
            'source_page': 4,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'NU_IDADE_N',
            'display_name': 'Idade',
            'description': 'Idade informada pelo paciente quando nao se sabe a data de nascimento. Na falta desse dado e registrada a idade aparente',
            'field_type': 'varchar',
            'categories': '',
            'is_required': True,
            'constraints': 'Varchar2(3) - Idade deve ser <= 150',
            'source_page': 4,
            'notes': 'Campo Obrigatorio - calculado automaticamente se digitado a data de nascimento'
        },
        {
            'field_name': 'TP_IDADE',
            'display_name': 'Tipo/Idade',
            'description': 'Tipo de idade (dias, meses ou anos)',
            'field_type': 'varchar',
            'categories': '1=Dia, 2=Mes, 3=Ano',
            'is_required': True,
            'constraints': 'Varchar2(1)',
            'source_page': 4,
            'notes': 'Campo Obrigatorio - calculado automaticamente se digitado a data de nascimento'
        },
        {
            'field_name': 'CS_RACA',
            'display_name': 'Raca/Cor',
            'description': 'Cor ou raca declarada pelo paciente: Branca; Preta; Amarela; Parda (pessoa que se declarou mulata, cabocla, cafuza, mameluca ou mestica de preto com pessoa de outra cor ou raca); e, Indigena',
            'field_type': 'varchar',
            'categories': '1=Branca, 2=Preta, 3=Amarela, 4=Parda, 5=Indigena, 9=Ignorado',
            'is_required': True,
            'constraints': 'Varchar2(2)',
            'source_page': 4,
            'notes': 'Campo Obrigatorio'
        },
        {
            'field_name': 'CS_ESCOL_N',
            'display_name': 'Escolaridade',
            'description': 'Nivel de escolaridade do paciente. Para os niveis fundamental e medio deve ser considerada a ultima serie ou ano concluido',
            'field_type': 'varchar',
            'categories': '0=Sem escolaridade/Analfabeto, 1=Fundamental 1o ciclo (1a a 5a serie), 2=Fundamental 2o ciclo (6a a 9a serie), 3=Medio (1o ao 3o ano), 4=Superior, 5=Nao se aplica, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 5,
            'notes': 'Campo Essencial - preenchido automaticamente com "nao se aplica" quando idade for menor que 7 anos'
        },

        # Clinical presentation - symptoms
        {
            'field_name': 'FEBRE',
            'display_name': 'Sinais e Sintomas/Febre',
            'description': 'Paciente apresentou febre?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 7,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'TOSSE',
            'display_name': 'Sinais e Sintomas/Tosse',
            'description': 'Paciente apresentou tosse?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 7,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'GARGANTA',
            'display_name': 'Sinais e Sintomas/Dor de Garganta',
            'description': 'Paciente apresentou dor de garganta?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'DISPNEIA',
            'display_name': 'Sinais e Sintomas/Dispneia',
            'description': 'Paciente apresentou dispneia?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'DESC_RESP',
            'display_name': 'Sinais e Sintomas/Desconforto Respiratorio',
            'description': 'Paciente apresentou desconforto respiratorio?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'SATURACAO',
            'display_name': 'Sinais e Sintomas/Saturacao O2< 95%',
            'description': 'Paciente apresentou saturacao O2< 95%?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'DIARREIA',
            'display_name': 'Sinais e Sintomas/Diarreia',
            'description': 'Paciente apresentou diarreia?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'VOMITO',
            'display_name': 'Sinais e Sintomas/Vomito',
            'description': 'Paciente apresentou vomito?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 8,
            'notes': 'Campo Essencial'
        },

        # Risk factors
        {
            'field_name': 'PUERPERA',
            'display_name': 'Fatores de risco/Puerpera',
            'description': 'Paciente e puerpera ou parturiente (mulher que pariu recentemente - ate 45 dias do parto)?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial - habilitado se sexo Feminino'
        },
        {
            'field_name': 'CARDIOPATI',
            'display_name': 'Fatores de risco/Doenca Cardiovascular Cronica',
            'description': 'Paciente possui Doenca Cardiovascular Cronica?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'DIABETES',
            'display_name': 'Fatores de risco/Diabetes mellitus',
            'description': 'Paciente possui Diabetes mellitus?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'OBESIDADE',
            'display_name': 'Fatores de risco/Obesidade',
            'description': 'Paciente possui obesidade?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 10,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'IMUNODEPRE',
            'display_name': 'Fatores de risco/Imunodeficiencia ou Imunodepressao',
            'description': 'Paciente possui Imunodeficiencia ou Imunodepressao (diminuicao da funcao do sistema imunologico)?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 10,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'ASMA',
            'display_name': 'Fatores de risco/Asma',
            'description': 'Paciente possui Asma?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'PNEUMOPATI',
            'display_name': 'Fatores de risco/Outra Pneumatopatia Cronica',
            'description': 'Paciente possui outra pneumopatia cronica?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'RENAL',
            'display_name': 'Fatores de risco/Doenca Renal Cronica',
            'description': 'Paciente possui Doenca Renal Cronica?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 10,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'HEPATICA',
            'display_name': 'Fatores de risco/Doenca Hepatica Cronica',
            'description': 'Paciente possui Doenca Hepatica Cronica?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 9,
            'notes': 'Campo Essencial'
        },

        # Hospitalization
        {
            'field_name': 'HOSPITAL',
            'display_name': 'Houve internacao?',
            'description': 'O paciente foi internado?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 15,
            'notes': 'Campo Essencial - sistema emite aviso se nao igual a 1-Sim'
        },
        {
            'field_name': 'DT_INTERNA',
            'display_name': 'Data da internacao por SRAG',
            'description': 'Data em que o paciente foi hospitalizado',
            'field_type': 'date',
            'categories': '',
            'is_required': True,
            'constraints': 'DD/MM/AAAA - Data deve ser >= Data de 1os sintomas e <= data da digitacao',
            'source_page': 16,
            'notes': 'Campo Obrigatorio'
        },
        {
            'field_name': 'UTI',
            'display_name': 'Internado em UTI?',
            'description': 'O paciente foi internado em UTI?',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 16,
            'notes': 'Campo Essencial - critico para taxa de ocupacao de UTI'
        },
        {
            'field_name': 'DT_ENTUTI',
            'display_name': 'Data da entrada na UTI',
            'description': 'Data de entrada do paciente na unidade de Terapia intensiva (UTI)',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser >= Data de 1os sintomas da SRAG e <= data da digitacao',
            'source_page': 16,
            'notes': 'Campo Essencial - habilitado se Internado em UTI = 1'
        },
        {
            'field_name': 'DT_SAIDUTI',
            'display_name': 'Data da saida da UTI',
            'description': 'Data em que o paciente saiu da Unidade de Terapia intensiva (UTI)',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser >= Data da entrada na UTI e <= data da digitacao',
            'source_page': 16,
            'notes': 'Campo Essencial - habilitado se Internado em UTI = 1'
        },
        {
            'field_name': 'SUPORT_VEN',
            'display_name': 'Uso de suporte ventilatorio?',
            'description': 'O paciente fez uso de suporte ventilatorio?',
            'field_type': 'varchar',
            'categories': '1=Sim, invasivo, 2=Sim, nao invasivo, 3=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 17,
            'notes': 'Campo Essencial'
        },

        # Vaccination
        {
            'field_name': 'VACINA',
            'display_name': 'Recebeu vacina contra Gripe na ultima campanha?',
            'description': 'Informar se o paciente foi vacinado contra gripe na ultima campanha, apos verificar a documentacao/caderneta',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 13,
            'notes': 'Campo Essencial'
        },
        {
            'field_name': 'DT_UT_DOSE',
            'display_name': 'Data da vacinacao',
            'description': 'Data da ultima dose de vacina contra gripe que o paciente tomou',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser <= a data da digitacao',
            'source_page': 13,
            'notes': 'Campo Essencial - habilitado se Recebeu vacina contra Gripe = 1'
        },
        {
            'field_name': 'VACINA_COV',
            'display_name': 'Recebeu vacina COVID-19?',
            'description': 'Informar se o paciente recebeu vacina COVID-19, apos verificar a documentacao/caderneta',
            'field_type': 'varchar',
            'categories': '1=Sim, 2=Nao, 9=Ignorado',
            'is_required': True,
            'constraints': 'Varchar2(1)',
            'source_page': 10,
            'notes': 'Campo Obrigatorio - integracao com a Base Nacional de Vacinacao'
        },
        {
            'field_name': 'DOSE_1_COV',
            'display_name': 'Data 1a dose da vacina COVID-19',
            'description': 'Informar a data em que o paciente recebeu a 1a dose da vacina COVID-19',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar(10) - DD/MM/AAAA',
            'source_page': 10,
            'notes': 'Campo essencial - habilitado se Recebeu vacina COVID-19 = 1'
        },
        {
            'field_name': 'DOSE_2_COV',
            'display_name': 'Data 2a dose da vacina COVID-19',
            'description': 'Informar a data em que o paciente recebeu a 2a dose da vacina COVID-19',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar(10) - DD/MM/AAAA',
            'source_page': 11,
            'notes': 'Campo essencial - habilitado se Recebeu vacina COVID-19 = 1'
        },
        {
            'field_name': 'DOSE_REF',
            'display_name': 'Data da dose reforco da vacina COVID-19',
            'description': 'Informar a data em que o paciente recebeu a dose reforco',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar(10) - DD/MM/AAAA',
            'source_page': 11,
            'notes': 'Campo essencial - habilitado se Recebeu vacina COVID-19 = 1'
        },
        {
            'field_name': 'DOSE_2REF',
            'display_name': 'Data da 2a dose reforco da vacina COVID-19',
            'description': 'Informar a data em que o paciente recebeu a 2a dose reforco',
            'field_type': 'varchar',
            'categories': '',
            'is_required': False,
            'constraints': 'Varchar(10) - DD/MM/AAAA',
            'source_page': 11,
            'notes': 'Campo essencial - habilitado se Recebeu vacina COVID-19 = 1'
        },

        # Laboratory
        {
            'field_name': 'PCR_RESUL',
            'display_name': 'Resultado da RT-PCR/outro metodo por Biologia Molecular',
            'description': 'Resultado do teste de RT-PCR/outro metodo por Biologia Molecular',
            'field_type': 'varchar',
            'categories': '1=Detectavel, 2=Nao Detectavel, 3=Inconclusivo, 4=Nao Realizado, 5=Aguardando Resultado, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 20,
            'notes': 'Campo Essencial - vira marcado com 5-Aguardando Resultado se Coletou amostra = 1'
        },
        {
            'field_name': 'DT_PCR',
            'display_name': 'Data do Resultado RT-PCR/outro metodo por Biologia Molecular',
            'description': 'Data do Resultado RT-PCR/outro metodo por Biologia Molecular',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser >= a data da coleta',
            'source_page': 20,
            'notes': 'Campo Essencial - habilitado se Resultado RT-PCR = 1, 2 ou 3'
        },
        {
            'field_name': 'RES_AN',
            'display_name': 'Resultado do Teste Antigenico',
            'description': 'Resultado do Teste Antigenico',
            'field_type': 'varchar',
            'categories': '1=positivo, 2=Negativo, 3=Inconclusivo, 4=Nao realizado, 5=Aguardando resultado, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 18,
            'notes': 'Campo Essencial - vira marcado com 5-Aguardando Resultado se Coletou amostra = 1'
        },
        {
            'field_name': 'CLASSI_FIN',
            'display_name': 'Classificacao final do caso',
            'description': 'Diagnostico final do caso. Se tiver resultados divergentes entre as metodologias laboratoriais, priorizar o resultado do RT-PCR',
            'field_type': 'varchar',
            'categories': '1=SRAG por influenza, 2=SRAG por outro virus respiratorio, 3=SRAG por outro agente etiologico, 4=SRAG nao especificado, 5=SRAG por covid-19',
            'is_required': True,
            'constraints': 'Varchar2(1)',
            'source_page': 24,
            'notes': 'Campo Obrigatorio - permite filtrar casos por tipo de agente'
        },
        {
            'field_name': 'CRITERIO',
            'display_name': 'Criterio de Encerramento',
            'description': 'Indicar qual o criterio de confirmacao',
            'field_type': 'varchar',
            'categories': '1=Laboratorial, 2=Clinico Epidemiologico, 3=Clinico, 4=Clinico Imagem',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 24,
            'notes': 'Campo Essencial - criterios 3 e 4 nao sao mais considerados para SRAG por covid-19 desde 31/10/2022'
        },

        # Outcome
        {
            'field_name': 'EVOLUCAO',
            'display_name': 'Evolucao do caso',
            'description': 'Evolucao do caso',
            'field_type': 'varchar',
            'categories': '1=Cura, 2=Obito, 3=Obito por outras causas, 9=Ignorado',
            'is_required': False,
            'constraints': 'Varchar2(1)',
            'source_page': 24,
            'notes': 'Campo Essencial - essencial para calculo de taxa de mortalidade'
        },
        {
            'field_name': 'DT_EVOLUCA',
            'display_name': 'Data da alta ou obito',
            'description': 'Data da alta ou obito',
            'field_type': 'date',
            'categories': '',
            'is_required': False,
            'constraints': 'DD/MM/AAAA - Data deve ser >= data dos primeiros sintomas e <= data da digitacao',
            'source_page': 25,
            'notes': 'Campo Essencial - habilitado se Evolucao do caso = 1 ou 2'
        },
        {
            'field_name': 'DT_ENCERRA',
            'display_name': 'Data do Encerramento',
            'description': 'Data do encerramento do caso',
            'field_type': 'date',
            'categories': '',
            'is_required': True,
            'constraints': 'DD/MM/AAAA - Data deve ser >= data do preenchimento e <= data da digitacao',
            'source_page': 25,
            'notes': 'Campo Obrigatorio - se o campo Classificacao final do caso estiver preenchido'
        },
    ]


def populate_dictionary_with_embeddings() -> None:
    """Create embeddings from manual dictionary and populate database."""
    logger.info("Populating data dictionary with embeddings...")

    # Use only manual dictionary
    fields = create_manual_dictionary()
    logger.info(f"Using {len(fields)} manually curated field definitions")

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
