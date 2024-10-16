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
            writer.writerow(['id', 'senha', 'tipo', 'serviço', 'nome', 'data', 'hora', 'atendido'])

def generate_password(prefix):
    return f"{prefix}{random.randint(1, 999):03d}"

def add_to_queue(csv_file, senha, tipo, servico, nome):
    now = datetime.datetime.now()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, nome, data, hora, 0])

def get_next_id(csv_file):
    with open(csv_file, 'r') as file:
        return sum(1 for line in file)

def display_queue(csv_file, queue_type):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        rows = [row for row in reader if row[2] == queue_type and row[7] == '0']
    
    if rows:
        for row in rows:
            st.markdown(f"- Senha: {row[1]} - Nome: {row[4]} - Serviço: {row[3]} - Emitida em: {row[5]} às {row[6]}")
    else:
        st.error("Fila vazia.")

# Atualize também a função call_next_password
def call_next_password(csv_file, company):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    prioritario = next((row for row in rows if row[2] == 'Prioritário' and row[7] == '0'), None)
    geral = next((row for row in rows if row[2] == 'Geral' and row[7] == '0'), None)
    
    row = prioritario or geral
    
    if row:
        row[7] = '1'  # Marcar como atendido
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        update_last_called(company, row[1], row[4], row[2])  # row[4] agora é 'nome' em vez de 'cpf_cnpj'
        return row[1], row[4], row[2]
    else:
        return None, None, None

def update_last_called(company, senha, nome, tipo):
    data = {
        'senha': senha,
        'nome': nome,  # Alterado de 'cpf_cnpj' para 'nome'
        'tipo': tipo,
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
        return data.get('senha'), data.get('nome'), data.get('tipo'), data.get('timestamp', 0)
    return None, None, None, 0


def get_last_called_password(csv_file):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    for row in reversed(rows[1:]):  # Ignorar o cabeçalho e começar do final
        if row[7] == '1':  # Se foi atendido
            return row[1], row[4], row[2]  # Retorna a senha, o nome e o tipo
    
    return None, None, None

def generate_password_pdf_in_memory(senha, tipo, nome, servico, company):
    # Criar um buffer de bytes para gerar o PDF em memória
    pdf_buffer = BytesIO()
    
    # Inicializar o canvas com o buffer
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    
    # Definir a fonte (use fontes padrão, como Helvetica)
    c.setFont("Helvetica-Bold", 16)
    
    # Obter a data e hora atual
    now = datetime.datetime.now()
    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

    # Adicionar conteúdo ao PDF na ordem especificada
    y_position = 750  # Posição inicial do topo
    line_height = 25  # Altura entre as linhas

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

    # Finalizar o PDF
    c.showPage()
    c.save()

    # Mover o ponteiro de leitura para o início do buffer
    pdf_buffer.seek(0)

    # Retornar o PDF como bytes
    return pdf_buffer.getvalue()

def get_pdf_download_link(pdf_data):
    # Use the bytes buffer directly
    b64 = base64.b64encode(pdf_data).decode()  # Encode in base64
    href = f'<a href="data:application/pdf;base64,{b64}" download="senha.pdf">Baixar Senha PDF</a>'
    return href

def add_to_queue_and_generate_pdf(csv_file, senha, tipo, servico, nome, company):
    # Adicionar à fila
    now = datetime.datetime.now()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, nome, data, hora, 0])
    
    # Gerar PDF
    pdf_buffer = generate_password_pdf_in_memory(senha, tipo, nome, servico, company)
    return pdf_buffer

def generate_password_html(senha, tipo, nome, servico, company):
    now = datetime.datetime.now()
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
    if 'last_called' not in st.session_state:
        st.session_state.last_called = get_last_called_password(csv_file)

    if 'last_update' not in st.session_state:
        st.session_state.last_update = 0
    
    senha, nome, tipo, timestamp = get_last_called_from_file(st.session_state.company)
    if timestamp > st.session_state.last_update:
        st.session_state.last_called = (senha, nome, tipo)
        st.session_state.last_update = timestamp
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["Cadastramento e Acionamento", "Painel de Chamada", "Auto Atendimento"])

    # Add this JavaScript function to your Streamlit app
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

        with col1:
            st.subheader("Emitir Nova Senha")
            nome = st.text_input("Nome do Cliente", key="nome_cliente_tab1")
            queue_type = st.radio("Tipo de Atendimento", ["Geral", "Prioritário"], key="queue_type_tab1")
            
            servicos_disponiveis = ["Registro de Imóveis", "Registro Civil Pessoas Naturais", "Tabelionato de Notas", "Protesto", "Registro de Títulos e Documentos", "Registro Civil Pessoas Jurídicas"]
            servico = st.selectbox("Escolha o Serviço", servicos_disponiveis, key="servico_tab1")

            if 'pdf_data' not in st.session_state:
                st.session_state.pdf_data = None

            if st.button("Gerar Senha", key="gerar_senha_tab1"):
                if nome:
                    senha = generate_password("G" if queue_type == "Geral" else "P")
                    st.session_state.pdf_data = add_to_queue_and_generate_pdf(csv_file, senha, queue_type, servico, nome, st.session_state.company)
                    st.success(f"Senha gerada: {senha}")
                else:
                    st.error("Por favor, insira o nome do cliente.")

            # Display PDF download link if pdf_data exists
            if st.session_state.pdf_data is not None:
                pdf_download_link = get_pdf_download_link(st.session_state.pdf_data)
                st.markdown(pdf_download_link, unsafe_allow_html=True)

        with col2:
            st.subheader("Filas de Atendimento")
            st.success("Fila Geral:")
            display_queue(csv_file, "Geral")
            st.divider()
            
            st.warning("Fila Prioritária:")
            display_queue(csv_file, "Prioritário")
            
            if st.button("Chamar Próxima Senha"):
                senha, nome, tipo = call_next_password(csv_file, st.session_state.company)
                if senha and nome:
                    st.session_state.last_called = (senha, nome, tipo)
                    st.success(f"Senha chamada: {senha} - Usuário: {nome} - Tipo: {tipo}")
                    st.session_state.update_counter += 1
                    st.rerun()
                else:
                    st.info("Não há senhas na fila.")

    with tab2:
        st.subheader("Senha Chamada")
        last_called_placeholder = st.empty()
        last_five_placeholder = st.empty()

        senha, nome, tipo = st.session_state.last_called

        with last_called_placeholder.container():
            if senha and nome:
                theme_good = {'bgcolor': '#EFF8F7','title_color': 'green','content_color': 'green','icon_color': 'green', 'icon': 'fa fa-check-circle'}
                
                hc.info_card(title=f"Senha: {senha} ({tipo})",  
                             content=f"Usuário: {nome}", 
                             sentiment='good',
                             bar_value=100,
                             theme_override=theme_good,
                             key=f"last_called_{senha}_{st.session_state.update_counter}")
            else:
                st.info("Nenhuma senha chamada ainda.")
        
        with last_five_placeholder.container():
            st.subheader("Últimas Senhas Chamadas")
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)
                rows = list(reader)[1:]  # Ignorar o cabeçalho
            
            called_passwords = [row for row in reversed(rows) if row[7] == '1'][:5]  # Pegando as últimas 5 senhas chamadas
            
            theme_neutral = {'bgcolor': '#f9f9f9','title_color': 'orange','content_color': 'orange','progress_color': 'orange','icon_color': 'orange', 'icon': 'fa fa-question-circle'}
            
            for i, row in enumerate(called_passwords):
                hc.info_card(title=f"Senha: {row[1]} ({row[2]})",
                            content=f"Usuário: {row[4]}", 
                            sentiment='neutral',
                            theme_override=theme_neutral,
                            bar_value=100,
                            key=f"last_five_{i}_{row[1]}_{st.session_state.update_counter}")

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
