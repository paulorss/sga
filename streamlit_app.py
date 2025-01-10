import streamlit as st
from streamlit_autorefresh import st_autorefresh
import datetime
import random
import csv
import os
import re
import time
import hashlib
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A7
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import base64
from io import BytesIO
import hydralit_components as hc
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import pytz

st.set_page_config(
    page_title="SGA - Senhas",
    layout="wide",
    initial_sidebar_state="auto",
)

st.header('SGA - Senhas')

TEMP_FILE = 'last_called.json'
USERS_FILE = 'users.json'
COMPANIES_DIR = 'companies'

# Criar diretório de empresas se não existir
if not os.path.exists(COMPANIES_DIR):
    os.makedirs(COMPANIES_DIR)

# Criar arquivo de usuários se não existir
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as file:
        json.dump({}, file)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, company):
    with open(USERS_FILE, 'r+') as file:
        users = json.load(file)
        if username not in users:
            users[username] = {
                'password': hash_password(password),
                'company': company
            }
            file.seek(0)
            json.dump(users, file)
            file.truncate()
            return True
    return False

def authenticate(username, password):
    with open(USERS_FILE, 'r') as file:
        users = json.load(file)
        if username in users and users[username]['password'] == hash_password(password):
            return users[username]['company']
    return None

def get_csv_file(company):
    return os.path.join(COMPANIES_DIR, f'{company}_senhas.csv')

def create_csv_if_not_exists(csv_file):
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'senha', 'tipo', 'serviço', 'nome', 'data', 'hora', 'atendido', 'guiche'])

def generate_password(prefix):
    return f"{prefix}{random.randint(1, 999):03d}"

# Função auxiliar para obter o horário atual de Brasília
def get_brasilia_time():
    fuso_horario = pytz.timezone('America/Sao_Paulo')
    return datetime.datetime.now(fuso_horario)

def add_to_queue(csv_file, senha, tipo, servico, nome):
    now = get_brasilia_time()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, nome, data, hora, 0, ''])


def get_next_id(csv_file):
    with open(csv_file, 'r') as file:
        return sum(1 for line in file)

def display_queue(csv_file, queue_type):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        rows = []
        for row in reader:
            if len(row) < 9:  # Se não tiver o campo guiche
                row.append('')  # Adiciona campo vazio para guiche
            if row[2] == queue_type and row[7] == '0':
                rows.append(row)
    
    if rows:
        for row in rows:
            st.markdown(f"- Senha: {row[1]} - Nome: {row[4]} - Serviço: {row[3]} - Emitida em: {row[5]} às {row[6]}")
    else:
        st.error("Fila vazia.")

def call_next_password(csv_file, company, selected_service, counter_number):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
        header = rows[0]
        
        # Garantir que todas as linhas tenham o campo guiche
        normalized_rows = [header]  # Manter o cabeçalho
        for row in rows[1:]:  # Para todas as outras linhas
            if len(row) < 9:  # Se não tiver o campo guiche
                row.append('')  # Adiciona campo vazio para guiche
            normalized_rows.append(row)
        
        # First try to find a priority ticket for the selected service
        prioritario = next((row for row in normalized_rows[1:] if row[2] == 'Prioritário' and 
                          row[3] == selected_service and row[7] == '0'), None)
        
        # If no priority ticket, look for a general ticket
        geral = next((row for row in normalized_rows[1:] if row[2] == 'Geral' and 
                     row[3] == selected_service and row[7] == '0'), None)
        
        row = prioritario or geral
        
        if row:
            row[7] = '1'  # Mark as attended
            row[8] = str(counter_number)  # Add counter number
            with open(csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(normalized_rows)
            update_last_called(company, row[1], row[4], row[2], counter_number, selected_service)
            return row[1], row[4], row[2], counter_number, selected_service
        else:
            return None, None, None, None, None

def update_last_called(company, senha, nome, tipo, counter, service):
    data = {
        'senha': senha,
        'nome': nome,
        'tipo': tipo,
        'guiche': counter,
        'servico': service,
        'timestamp': time.time()
    }
    file_path = os.path.join(COMPANIES_DIR, f'{company}_last_called.json')
    with open(file_path, 'w') as f:
        json.dump(data, f)

def get_last_called_from_file(company):
    file_path = os.path.join(COMPANIES_DIR, f'{company}_last_called.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return (
            data.get('senha'),
            data.get('nome'),
            data.get('tipo'),
            data.get('timestamp', 0),
            data.get('guiche', ''),
            data.get('servico', '')
        )
    return None, None, None, 0, '', ''

# Atualizar a função generate_password_pdf_in_memory
def generate_password_pdf_in_memory(senha, tipo, nome, servico, company):
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    
    now = get_brasilia_time()
    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

    y_position = 750
    line_height = 25

    c.drawString(100, y_position, f"Empresa: {company}")
    y_position -= line_height

    c.drawString(100, y_position, f"Senha: {senha}")
    y_position -= line_height

    c.drawString(100, y_position, f"Tipo: {tipo}")
    y_position -= line_height

    c.drawString(100, y_position, f"Nome: {nome}")
    y_position -= line_height

    c.drawString(100, y_position, f"Serviço: {servico}")
    y_position -= line_height

    c.drawString(100, y_position, f"Data e hora de Geração da senha: {date_time}")

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

def get_pdf_download_link(pdf_data):
    b64 = base64.b64encode(pdf_data).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="senha.pdf">Baixar Senha PDF</a>'
    return href

def add_to_queue_and_generate_pdf(csv_file, senha, tipo, servico, nome, company):
    # Primeiro adicionar à fila
    now = get_brasilia_time()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, nome, data, hora, 0, ''])
    
    # Depois gerar o PDF
    try:
        pdf_buffer = generate_password_pdf_in_memory(senha, tipo, nome, servico, company)
        return pdf_buffer
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        return None

# Atualizar a função generate_password_html
def generate_password_html(senha, tipo, nome, servico, company):
    now = get_brasilia_time()
    date_time = now.strftime("%d/%m/%Y %H:%M:%S")
    
    html_content = f"""
    <html>
    <head>
        <title>Senha - {company}</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; }}
            .container {{ border: 2px solid #000; padding: 20px; width: 300px; margin: 0 auto; }}
            .senha {{ font-size: 24px; font-weight: bold; margin: 20px 0; }}
            .info {{ font-size: 14px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Senhas - {company}</h2>
            <div class="senha">{senha}</div>
            <div class="info">Tipo: {tipo}</div>
            <div class="info">Serviço: {servico}</div>
            <div class="info">Nome: {nome}</div>
            <div class="info">Emitido em: {date_time}</div>
        </div>
        <script>
            window.print();
            window.onafterprint = function() {{ window.close(); }};
        </script>
    </body>
    </html>
    """
    return html_content

def main_app():
    csv_file = get_csv_file(st.session_state.company)
    create_csv_if_not_exists(csv_file)

    st.title(f"Painel de Senhas - {st.session_state.company}")
    
    if 'update_counter' not in st.session_state:
        st.session_state.update_counter = 0

    st_autorefresh(interval=500, key=f"autorefresh_{st.session_state.update_counter}")
    
    # Update this section to handle all returned values
    senha, nome, tipo, timestamp, guiche, servico = get_last_called_from_file(st.session_state.company)
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = 0
    
    if timestamp > st.session_state.last_update:
        st.session_state.last_called = (senha, nome, tipo, guiche, servico)
        st.session_state.last_update = timestamp
        st.rerun()

    servicos_disponiveis = ["Registro de Imóveis", "Registro Civil Pessoas Naturais", 
                           "Tabelionato de Notas", "Protesto", 
                           "Registro de Títulos e Documentos", 
                           "Registro Civil Pessoas Jurídicas"]

    tab1, tab2, tab3 = st.tabs(["Cadastramento e Acionamento", "Painel de Chamada", "Auto Atendimento"])

    st.markdown("""
    <script>
    function openPrintWindow(htmlContent) {
        var printWindow = window.open('', '_blank');
        printWindow.document.write(htmlContent);
        printWindow.document.close();
    }
    </script>
    """, unsafe_allow_html=True)

    with tab1:
        col1, col2 = st.columns(2)

        # Atualizar a parte do código que lida com a geração e download do PDF em tab1
        with col1:
            st.subheader("Emitir Nova Senha")
            nome = st.text_input("Nome do Cliente", key="nome_cliente_tab1")
            queue_type = st.radio("Tipo de Atendimento", ["Geral", "Prioritário"], key="queue_type_tab1")
            servico = st.selectbox("Escolha o Serviço", servicos_disponiveis, key="servico_tab1")
        
            if 'pdf_data' not in st.session_state:
                st.session_state.pdf_data = None
        
            if st.button("Gerar Senha", key="gerar_senha_tab1"):
                if nome:
                    senha = generate_password("G" if queue_type == "Geral" else "P")
                    pdf_data = add_to_queue_and_generate_pdf(
                        csv_file, senha, queue_type, servico, nome, st.session_state.company
                    )
                    st.session_state.pdf_data = pdf_data
                    st.session_state.last_senha = senha
                    st.success(f"Senha gerada: {senha}")
                    
                    # Gerar o link de download logo após gerar o PDF
                    if pdf_data:
                        pdf_download_link = get_pdf_download_link(pdf_data)
                        st.markdown(pdf_download_link, unsafe_allow_html=True)
                else:
                    st.error("Por favor, insira o nome do cliente.")
        
            # Manter o link de download visível mesmo após rerun
            if st.session_state.pdf_data is not None:
                pdf_download_link = get_pdf_download_link(st.session_state.pdf_data)
                st.markdown(pdf_download_link, unsafe_allow_html=True)

        with col2:
            st.subheader("Chamar Próxima Senha")
            
            selected_service = st.selectbox(
                "Selecione o Serviço para Chamar",
                servicos_disponiveis,
                key="service_selection"
            )
            
            counter_number = st.number_input(
                "Número do Guichê",
                min_value=1,
                max_value=99,
                value=1,
                step=1,
                key="counter_number"
            )
            
            st.divider()
            
            st.success("Fila Geral:")
            display_queue(csv_file, "Geral")
            st.divider()
            
            st.warning("Fila Prioritária:")
            display_queue(csv_file, "Prioritário")
            
            if st.button("Chamar Próxima Senha"):
                senha, nome, tipo, guiche, servico = call_next_password(
                    csv_file, 
                    st.session_state.company,
                    selected_service,
                    counter_number
                )
                if senha and nome:
                    st.session_state.last_called = (senha, nome, tipo, guiche, servico)
                    st.success(f"Senha chamada: {senha} - Usuário: {nome} - Tipo: {tipo}")
                    st.success(f"Dirija-se ao Guichê {guiche} - Serviço: {servico}")
                    st.session_state.update_counter += 1
                    st.rerun()
                else:
                    st.info(f"Não há senhas na fila para o serviço: {selected_service}")

    with tab2:
        st.subheader("Senha Chamada")
        last_called_placeholder = st.empty()
        last_five_placeholder = st.empty()

        with last_called_placeholder.container():
            if senha and nome:
                theme_good = {'bgcolor': '#EFF8F7','title_color': 'green',
                             'content_color': 'green','icon_color': 'green', 
                             'icon': 'fa fa-check-circle'}
                
                hc.info_card(
                    title=f"Senha: {senha} ({tipo})",  
                    content=f"Usuário: {nome}\nGuichê: {guiche}\nServiço: {servico}", 
                    sentiment='good',
                    bar_value=100,
                    theme_override=theme_good,
                    key=f"last_called_{senha}_{st.session_state.update_counter}"
                )
            else:
                st.info("Nenhuma senha chamada ainda.")
        
        with last_five_placeholder.container():
            st.subheader("Últimas Senhas Chamadas")
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)
                rows = list(reader)[1:]  # Ignorar o cabeçalho
                
                # Garantir que todas as linhas tenham o campo guiche
                normalized_rows = []
                for row in rows:
                    if len(row) < 9:  # Se não tiver o campo guiche
                        row.append('')  # Adiciona campo vazio para guiche
                    normalized_rows.append(row)
            
            called_passwords = [row for row in reversed(normalized_rows) if row[7] == '1'][:5]
            
            theme_neutral = {'bgcolor': '#f9f9f9','title_color': 'orange',
                            'content_color': 'orange','progress_color': 'orange',
                            'icon_color': 'orange', 'icon': 'fa fa-question-circle'}
            
            for i, row in enumerate(called_passwords):
                guiche_info = f"\nGuichê: {row[8]}" if row[8] else ""
                hc.info_card(
                    title=f"Senha: {row[1]} ({row[2]})",
                    content=f"Usuário: {row[4]}{guiche_info}\nServiço: {row[3]}", 
                    sentiment='neutral',
                    theme_override=theme_neutral,
                    bar_value=100,
                    key=f"last_five_{i}_{row[1]}_{st.session_state.update_counter}"
                )


    with tab3:
        st.subheader("Auto Atendimento")
        nome = st.text_input("Seu Nome", key="nome_cliente_tab3")
        queue_type = st.radio("Tipo de Atendimento", ["Geral", "Prioritário"], key="queue_type_tab3")
        servico = st.selectbox("Escolha o Serviço", servicos_disponiveis, key="servico_tab3")

        if st.button("Gerar Minha Senha", key="gerar_senha_tab3"):
            if nome:
                password = generate_password("G" if queue_type == "Geral" else "P")
                add_to_queue(csv_file, password, queue_type, servico, nome)
                html_content = generate_password_html(password, queue_type, nome, servico, st.session_state.company)
                st.success(f"Sua senha foi gerada: {password}")
                
                encoded_html = base64.b64encode(html_content.encode()).decode()
                st.markdown(f"""
                <button onclick="openPrintWindow(atob('{encoded_html}'))">
                    Imprimir Minha Senha
                </button>
                """, unsafe_allow_html=True)
            else:
                st.error("Por favor, insira seu nome.")

def login_page():
    st.title("Login")
    username = st.text_input("Usuário", key="login_username")
    password = st.text_input("Senha", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        company = authenticate(username, password)
        if company:
            st.session_state.logged_in = True
            st.session_state.company = company
            st.success("Login bem-sucedido!")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

def register_page():
    st.title("Registro de Novo Usuário")
    access_code = st.text_input("Código de Acesso", type="password")
    if access_code == "cartoriogo":
        username = st.text_input("Usuário", key="register_username")
        password = st.text_input("Senha", type="password", key="register_password")
        company = st.text_input("Nome da Empresa", key="register_company")
        if st.button("Registrar", key="register_button"):
            if create_user(username, password, company):
                st.success("Usuário registrado com sucesso!")
            else:
                st.error("Usuário já existe")
    else:
        st.error("Código de acesso inválido. Registro não permitido.")

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Registro"])
        with tab1:
            login_page()
        with tab2:
            register_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
