import streamlit as st
from streamlit_autorefresh import st_autorefresh
import datetime
import random
import csv
import os
import re
import time
import hashlibimport streamlit as st
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
import tempfile
import hydralit_components as hc
import base64
from io import BytesIO
import webbrowser
from PIL import Image
import io
from reportlab.lib.utils import ImageReader


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
            writer.writerow(['id', 'senha', 'tipo', 'serviço', 'cpf_cnpj', 'nome', 'data', 'hora', 'atendido'])

def validate_cpf_cnpj(cpf_cnpj):
    cpf_cnpj = re.sub(r'\D', '', cpf_cnpj)
    return len(cpf_cnpj) in [11, 14]

def generate_password(prefix):
    return f"{prefix}{random.randint(1, 999):03d}"

def add_to_queue(csv_file, senha, tipo, servico, cpf_cnpj, nome):
    now = datetime.datetime.now()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, cpf_cnpj, nome, data, hora, 0])

def get_next_id(csv_file):
    with open(csv_file, 'r') as file:
        return sum(1 for line in file)

def display_queue(csv_file, queue_type):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        rows = [row for row in reader if row[2] == queue_type and row[8] == '0']
    
    if rows:
        for row in rows:
            st.markdown(f"- Senha: {row[1]} - CPF/CNPJ: {row[4]} - Nome: {row[5]} - Serviço: {row[3]} - Emitida em: {row[6]} às {row[7]}")
    else:
        st.error("Fila vazia.")

def call_next_password(csv_file, company):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    prioritario = next((row for row in rows if row[2] == 'Prioritário' and row[8] == '0'), None)
    geral = next((row for row in rows if row[2] == 'Geral' and row[8] == '0'), None)
    
    row = prioritario or geral
    
    if row:
        row[8] = '1'  # Marcar como atendido
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        update_last_called(company, row[1], row[4], row[2])
        return row[1], row[4], row[2]
    else:
        return None, None, None

def update_last_called(company, senha, cpf_cnpj, tipo):
    data = {
        'senha': senha,
        'cpf_cnpj': cpf_cnpj,
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
        return data['senha'], data['cpf_cnpj'], data['tipo'], data['timestamp']
    return None, None, None, 0

def get_last_called_password(csv_file):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    for row in reversed(rows[1:]):  # Ignorar o cabeçalho e começar do final
        if row[8] == '1':  # Se foi atendido
            return row[1], row[4], row[2]  # Retorna a senha, o CPF/CNPJ e o tipo
    
    return None, None, None

def generate_password_pdf(senha, tipo, nome, servico, company):
    pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        c = canvas.Canvas(temp_file.name, pagesize=A7)
        
        # Ajustando tamanhos de fonte
        c.setFont('Arial', 10)  # Reduzido de 12 para 10
        c.drawString(10*mm, 60*mm, f"Senhas - {company}")
        
        c.setFont('Arial', 10)  # Reduzido de 24 para 20
        c.drawString(10*mm, 40*mm, senha)
        
        c.setFont('Arial', 8)  # Reduzido de 14 para 12
        c.drawString(10*mm, 30*mm, f"Tipo: {tipo}")
        c.drawString(10*mm, 25*mm, f"Serviço: {servico}")
        c.drawString(10*mm, 20*mm, f"Nome: {nome}")
        
        now = datetime.datetime.now()
        date_time = now.strftime("%d/%m/%Y %H:%M:%S")
        c.setFont('Arial', 8)  # Reduzido de 10 para 8
        c.drawString(10*mm, 10*mm, f"Emitido em: {date_time}")
        
        c.save()
    return temp_file.name

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
    
    senha, cpf_cnpj, tipo, timestamp = get_last_called_from_file(st.session_state.company)
    if timestamp > st.session_state.last_update:
        st.session_state.last_called = (senha, cpf_cnpj, tipo)
        st.session_state.last_update = timestamp
        st.rerun()

    tab1, tab2 = st.tabs(["Cadastramento e Acionamento", "Painel de Chamada"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Emitir Nova Senha")
            nome = st.text_input("Nome do Cliente")
            queue_type = st.radio("Tipo de Atendimento", ["Geral", "Prioritário"])
            cpf_cnpj = st.text_input("CPF/CNPJ")
            
            servicos_disponiveis = ["Registro de Imóveis", "Registro Civil Pessoas Naturais", "Tabelionato de Notas", "Protesto", "Registro de Títulos e Documentos", "Registro Civil Pessoas Jurídicas"]
            servico = st.selectbox("Escolha o Serviço", servicos_disponiveis)

            if st.button("Gerar Senha"):
                if validate_cpf_cnpj(cpf_cnpj) and nome:
                    password = generate_password("G" if queue_type == "Geral" else "P")
                    add_to_queue(csv_file, password, queue_type, servico, cpf_cnpj, nome)
                    st.success(f"Senha gerada: {password}")

                    # Generate PDF
                    pdf_file = generate_password_pdf(password, queue_type, nome, servico, st.session_state.company)

                    # Open PDF in a new browser tab (which should trigger download)
                    webbrowser.open('file://' + os.path.realpath(pdf_file), new=2)

                    st.info("O PDF da senha foi aberto em uma nova aba do navegador. Por favor, verifique se o download iniciou automaticamente.")

                    # Remove the temporary file after a short delay
                    st.empty().success("Aguarde, o arquivo temporário será removido em breve...")
                    time.sleep(5)  # Give some time for the browser to access the file
                    os.remove(pdf_file)
                    st.success("Arquivo temporário removido com sucesso.")

                else:
                    st.error("Por favor, insira um CPF/CNPJ válido e o nome do cliente.")
        
        with col2:
            st.subheader("Filas de Atendimento")
            st.success("Fila Geral:")
            display_queue(csv_file, "Geral")
            st.divider()
            
            st.warning("Fila Prioritária:")
            display_queue(csv_file, "Prioritário")
            
            if st.button("Chamar Próxima Senha"):
                senha, cpf_cnpj, tipo = call_next_password(csv_file, st.session_state.company)
                if senha and cpf_cnpj:
                    st.session_state.last_called = (senha, cpf_cnpj, tipo)
                    st.success(f"Senha chamada: {senha} - CPF/CNPJ: {cpf_cnpj} - Tipo: {tipo}")
                    st.info(senha)
                    st.session_state.update_counter += 1
                    st.rerun()
                else:
                    st.info("Não há senhas na fila.")

    with tab2:
        st.subheader("Senha Chamada")
        last_called_placeholder = st.empty()
        last_five_placeholder = st.empty()

        senha, cpf_cnpj, tipo = st.session_state.last_called

        with last_called_placeholder.container():
            if senha and cpf_cnpj:
                theme_good = {'bgcolor': '#EFF8F7','title_color': 'green','content_color': 'green','icon_color': 'green', 'icon': 'fa fa-check-circle'}
                
                hc.info_card(title=f"Senha: {senha} ({tipo})",  
                             content=f"CPF/CNPJ: {cpf_cnpj[:3]}...{cpf_cnpj[-3:]}", 
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
            
            called_passwords = [row for row in reversed(rows) if row[8] == '1'][:5]  # Pegando as últimas 5 senhas chamadas
            
            theme_neutral = {'bgcolor': '#f9f9f9','title_color': 'orange','content_color': 'orange','progress_color': 'orange','icon_color': 'orange', 'icon': 'fa fa-question-circle'}
            
            for i, row in enumerate(called_passwords):
                hc.info_card(title=f"Senha: {row[1]} ({row[2]})",
                            content=f"CPF/CNPJ: {row[4][:3]}...{row[4][-3:]}", 
                            sentiment='neutral',
                            theme_override=theme_neutral,
                            bar_value=100,
                            key=f"last_five_{i}_{row[1]}_{st.session_state.update_counter}")

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
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A7
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import tempfile
import hydralit_components as hc

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
            writer.writerow(['id', 'senha', 'tipo', 'serviço', 'cpf_cnpj', 'nome', 'data', 'hora', 'atendido'])

def validate_cpf_cnpj(cpf_cnpj):
    cpf_cnpj = re.sub(r'\D', '', cpf_cnpj)
    return len(cpf_cnpj) in [11, 14]

def generate_password(prefix):
    return f"{prefix}{random.randint(1, 999):03d}"

def add_to_queue(csv_file, senha, tipo, servico, cpf_cnpj, nome):
    now = datetime.datetime.now()
    data = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    with open(csv_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([get_next_id(csv_file), senha, tipo, servico, cpf_cnpj, nome, data, hora, 0])

def get_next_id(csv_file):
    with open(csv_file, 'r') as file:
        return sum(1 for line in file)

def display_queue(csv_file, queue_type):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        rows = [row for row in reader if row[2] == queue_type and row[8] == '0']
    
    if rows:
        for row in rows:
            st.markdown(f"- Senha: {row[1]} - CPF/CNPJ: {row[4]} - Nome: {row[5]} - Serviço: {row[3]} - Emitida em: {row[6]} às {row[7]}")
    else:
        st.error("Fila vazia.")

def call_next_password(csv_file, company):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    prioritario = next((row for row in rows if row[2] == 'Prioritário' and row[8] == '0'), None)
    geral = next((row for row in rows if row[2] == 'Geral' and row[8] == '0'), None)
    
    row = prioritario or geral
    
    if row:
        row[8] = '1'  # Marcar como atendido
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
        update_last_called(company, row[1], row[4], row[2])
        return row[1], row[4], row[2]
    else:
        return None, None, None

def update_last_called(company, senha, cpf_cnpj, tipo):
    data = {
        'senha': senha,
        'cpf_cnpj': cpf_cnpj,
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
        return data['senha'], data['cpf_cnpj'], data['tipo'], data['timestamp']
    return None, None, None, 0

def get_last_called_password(csv_file):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    for row in reversed(rows[1:]):  # Ignorar o cabeçalho e começar do final
        if row[8] == '1':  # Se foi atendido
            return row[1], row[4], row[2]  # Retorna a senha, o CPF/CNPJ e o tipo
    
    return None, None, None

def generate_password_pdf(senha, tipo, nome, servico, company):
    pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        c = canvas.Canvas(temp_file.name, pagesize=A7)
        c.setFont('Arial', 12)
        c.drawString(10*mm, 60*mm, company)
        c.setFont('Arial', 24)
        c.drawString(10*mm, 40*mm, senha)
        c.setFont('Arial', 14)
        c.drawString(10*mm, 30*mm, f"Tipo: {tipo}")
        c.drawString(10*mm, 25*mm, f"Serviço: {servico}")
        c.drawString(10*mm, 20*mm, f"Nome: {nome}")
        now = datetime.datetime.now()
        date_time = now.strftime("%d/%m/%Y %H:%M:%S")
        c.setFont('Arial', 10)
        c.drawString(10*mm, 10*mm, f"Emitido em: {date_time}")
        c.save()
    return temp_file.name

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
    if access_code == "SGA_cart2024":
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
    
    senha, cpf_cnpj, tipo, timestamp = get_last_called_from_file(st.session_state.company)
    if timestamp > st.session_state.last_update:
        st.session_state.last_called = (senha, cpf_cnpj, tipo)
        st.session_state.last_update = timestamp
        st.rerun()

    tab1, tab2 = st.tabs(["Cadastramento e Acionamento", "Painel de Chamada"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Emitir Nova Senha")
            nome = st.text_input("Nome do Cliente")
            queue_type = st.radio("Tipo de Atendimento", ["Geral", "Prioritário"])
            cpf_cnpj = st.text_input("CPF/CNPJ")
            
            servicos_disponiveis = ["Registro de Imóveis", "Tabelionato de Notas", "Protesto", "RTDPJ", "Registro Civil"]
            servico = st.selectbox("Escolha o Serviço", servicos_disponiveis)

            if st.button("Gerar Senha"):
                if validate_cpf_cnpj(cpf_cnpj) and nome:
                    password = generate_password("G" if queue_type == "Geral" else "P")
                    add_to_queue(csv_file, password, queue_type, servico, cpf_cnpj, nome)
                    st.success(f"Senha gerada: {password}")

                    pdf_file = generate_password_pdf(password, queue_type, nome, servico, st.session_state.company)

                    with open(pdf_file, "rb") as file:
                        st.download_button(
                            label="Baixar senha em PDF",
                            data=file,
                            file_name=f"senha_{password}.pdf",
                            mime="application/pdf"
                        )
                    
                    os.remove(pdf_file)
                else:
                    st.error("Por favor, insira um CPF/CNPJ válido e o nome do cliente.")
        
        with col2:
            st.subheader("Filas de Atendimento")
            st.success("Fila Geral:")
            display_queue(csv_file, "Geral")
            st.divider()
            
            st.warning("Fila Prioritária:")
            display_queue(csv_file, "Prioritário")
            
            if st.button("Chamar Próxima Senha"):
                senha, cpf_cnpj, tipo = call_next_password(csv_file, st.session_state.company)
                if senha and cpf_cnpj:
                    st.session_state.last_called = (senha, cpf_cnpj, tipo)
                    st.success(f"Senha chamada: {senha} - CPF/CNPJ: {cpf_cnpj} - Tipo: {tipo}")
                    st.info(senha)
                    st.session_state.update_counter += 1
                    st.rerun()
                else:
                    st.info("Não há senhas na fila.")

    with tab2:
        st.subheader("Senha Chamada")
        last_called_placeholder = st.empty()
        last_five_placeholder = st.empty()

        senha, cpf_cnpj, tipo = st.session_state.last_called

        with last_called_placeholder.container():
            if senha and cpf_cnpj:
                theme_good = {'bgcolor': '#EFF8F7','title_color': 'green','content_color': 'green','icon_color': 'green', 'icon': 'fa fa-check-circle'}
                
                hc.info_card(title=f"Senha: {senha} ({tipo})",  
                             content=f"CPF/CNPJ: {cpf_cnpj[:3]}...{cpf_cnpj[-3:]}", 
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
            
            called_passwords = [row for row in reversed(rows) if row[8] == '1'][:5]  # Pegando as últimas 5 senhas chamadas
            
            theme_neutral = {'bgcolor': '#f9f9f9','title_color': 'orange','content_color': 'orange','progress_color': 'orange','icon_color': 'orange', 'icon': 'fa fa-question-circle'}
            
            for i, row in enumerate(called_passwords):
                hc.info_card(title=f"Senha: {row[1]} ({row[2]})",
                            content=f"CPF/CNPJ: {row[4][:3]}...{row[4][-3:]}", 
                            sentiment='neutral',
                            theme_override=theme_neutral,
                            bar_value=100,
                            key=f"last_five_{i}_{row[1]}_{st.session_state.update_counter}")

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
