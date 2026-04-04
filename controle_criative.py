import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

ID_PLANILHA = "1XzaYeaNvzfnC5C5Hf4drW-6dpPydx2jw_cVJ7qsHnuc"
NOME_ABA = "criative"

# Carrega credenciais do secrets
CREDS_DICT = json.loads(st.secrets["credentials_json"])

@st.cache_resource
def conectar():
    creds = Credentials.from_service_account_info(CREDS_DICT)
    client = gspread.authorize(creds)
    return client.open_by_key(ID_PLANILHA).worksheet(NOME_ABA)

@st.cache_data(ttl=60)
def carregar_dados():
    sheet = conectar()
    dados = sheet.get_all_records()
    df = pd.DataFrame(dados)
    if df.empty:
        return df
    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
    if 'valor' in df.columns:
        def converter(val):
            if pd.isna(val):
                return 0.0
            v = str(val).replace('R$', '').replace(' ', '').strip()
            if ',' in v and '.' in v:
                v = v.replace('.', '').replace(',', '.')
            elif ',' in v:
                v = v.replace(',', '.')
            try:
                return float(v)
            except:
                return 0.0
        df['valor_num'] = df['valor'].apply(converter)
    else:
        df['valor_num'] = 0.0
    return df

def salvar_lancamento(data, revenda, cliente, valor, forma_pagamento, produto, situacao, texto):
    if not texto or not texto.strip():
        st.error("O texto é obrigatório.")
        return None
    sheet = conectar()
    df = carregar_dados()
    if df.empty or 'id' not in df.columns:
        novo_id = 1
    else:
        ids_validos = pd.to_numeric(df['id'], errors='coerce').dropna()
        novo_id = int(ids_validos.max()) + 1 if not ids_validos.empty else 1
    if forma_pagamento == 'aguardando pagamento':
        situacao = 'pendente'
    nova_linha = [
        novo_id,
        data.strftime('%d/%m/%Y'),
        revenda,
        cliente,
        f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        forma_pagamento,
        produto,
        situacao,
        texto
    ]
    sheet.append_row(nova_linha)
    st.cache_data.clear()
    return novo_id

def atualizar_lancamento(id_lancamento, data, revenda, cliente, valor, forma_pagamento, produto, situacao, texto):
    sheet = conectar()
    celula = sheet.find(str(id_lancamento))
    if not celula:
        return False
    if forma_pagamento == 'aguardando pagamento':
        situacao = 'pendente'
    sheet.update_cell(celula.row, 2, data.strftime('%d/%m/%Y'))
    sheet.update_cell(celula.row, 3, revenda)
    sheet.update_cell(celula.row, 4, cliente)
    sheet.update_cell(celula.row, 5, f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    sheet.update_cell(celula.row, 6, forma_pagamento)
    sheet.update_cell(celula.row, 7, produto)
    sheet.update_cell(celula.row, 8, situacao)
    sheet.update_cell(celula.row, 9, texto)
    st.cache_data.clear()
    return True

def excluir_lancamento(id_lancamento):
    sheet = conectar()
    celula = sheet.find(str(id_lancamento))
    if celula:
        sheet.delete_rows(celula.row)
        st.cache_data.clear()

def obter_texto_lancamento(id_lancamento):
    sheet = conectar()
    celula = sheet.find(str(id_lancamento))
    if celula:
        return sheet.cell(celula.row, 9).value or ""
    return ""

# ==================== INTERFACE ====================
st.set_page_config(page_title="Criative - Gestão", layout="wide")
st.title("📱 Criative - Gestão de Lançamentos (Google Sheets)")

menu = st.sidebar.radio("Navegação", ["📋 Dashboard", "➕ Novo Lançamento", "✏️ Editar/Excluir"])

if menu == "📋 Dashboard":
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum lançamento ainda. Use o menu para adicionar.")
    else:
        st.sidebar.header("🔍 Filtros")
        if 'situação' in df.columns:
            situacoes = df['situação'].dropna().unique().tolist()
            selecao = st.sidebar.multiselect("Situação", situacoes, default=situacoes)
            if selecao:
                df = df[df['situação'].isin(selecao)]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Valor Total", f"R$ {df['valor_num'].sum():,.2f}")
        with col2:
            st.metric("📄 Total Lançamentos", len(df))
        with col3:
            st.metric("📊 Valor Médio", f"R$ {df['valor_num'].mean():,.2f}")
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["📋 Tabela", "📈 Gráficos", "📄 Textos"])
        with tab1:
            def highlight_pendente(row):
                if row.get('forma de pagamento') == 'aguardando pagamento':
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
            styled_df = df.style.apply(highlight_pendente, axis=1)
            st.dataframe(styled_df, use_container_width=True)
        with tab2:
            if not df.empty and 'revenda' in df.columns:
                top = df.groupby('revenda')['valor_num'].sum().sort_values(ascending=False).head(10)
                fig = px.bar(x=top.values, y=top.index, orientation='h', title="Valor por Revenda")
                st.plotly_chart(fig, use_container_width=True)
        with tab3:
            for _, row in df.iterrows():
                with st.expander(f"📄 ID {row['id']} - {row['cliente']} - {row['data'].strftime('%d/%m/%Y')}"):
                    texto = obter_texto_lancamento(row['id'])
                    st.text_area("Conteúdo", texto, height=200, key=f"text_{row['id']}", disabled=True)
        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

elif menu == "➕ Novo Lançamento":
    st.header("➕ Criar novo lançamento")
    with st.form("novo_form"):
        col1, col2 = st.columns(2)
        with col1:
            data_padrao = datetime.today().strftime("%d/%m/%Y")
            data_str = st.text_input("Data (DD/MM/AAAA)", value=data_padrao)
            try:
                data = datetime.strptime(data_str, "%d/%m/%Y").date()
            except:
                st.error("Data inválida! Use DD/MM/AAAA.")
                data = datetime.today().date()
            revenda = st.text_input("Revenda")
            cliente = st.text_input("Cliente")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        with col2:
            opcoes_pagamento = ["Dinheiro", "cartão de credito", "pix", "Transferência pix", "aguardando pagamento"]
            forma_pagamento = st.selectbox("Forma de pagamento", opcoes_pagamento, index=3)
            opcoes_produto = [
                "disa e-mail", "espera e-mail", "espera modulo", "disa chip",
                "regravação espera", "natal", "itcp", "disa e-mail espera em chip",
                "disa e espera por e-mail", "visita técnica", "Outro"
            ]
            produto_selecionado = st.selectbox("Produto", opcoes_produto)
            if produto_selecionado == "Outro":
                produto = st.text_input("Especifique o produto")
            else:
                produto = produto_selecionado
            situacao = st.selectbox("Situação", ["entregue", "pendente", "cancelado", "em andamento"], index=3)
        texto = st.text_area("Observações", height=300)
        submitted = st.form_submit_button("Salvar")
        if submitted:
            if not revenda or not cliente:
                st.error("Revenda e Cliente são obrigatórios.")
            else:
                novo_id = salvar_lancamento(data, revenda, cliente, valor, forma_pagamento, produto, situacao, texto)
                if novo_id:
                    st.success(f"Lançamento ID {novo_id} salvo!")
                    st.balloons()
                    st.rerun()

elif menu == "✏️ Editar/Excluir":
    st.header("✏️ Editar ou Excluir Lançamento")
    df = carregar_dados()
    if df.empty:
        st.warning("Nenhum lançamento para editar.")
    else:
        tipo_busca = st.radio("Buscar por:", ["Cliente", "ID", "Revenda"], horizontal=True)
        if tipo_busca == "ID":
            id_busca = st.number_input("Digite o ID", min_value=1, step=1)
            if id_busca:
                df_filtrado = df[df['id'] == id_busca]
            else:
                df_filtrado = pd.DataFrame()
        elif tipo_busca == "Cliente":
            busca = st.text_input("Digite parte do nome do cliente")
            if busca:
                df_filtrado = df[df['cliente'].str.contains(busca, case=False, na=False)]
            else:
                df_filtrado = df
        else:
            busca = st.text_input("Digite parte do nome da revenda")
            if busca:
                df_filtrado = df[df['revenda'].str.contains(busca, case=False, na=False)]
            else:
                df_filtrado = df
        if df_filtrado.empty:
            st.info("Nenhum registro encontrado.")
        else:
            df_filtrado['opcao'] = df_filtrado.apply(
                lambda row: f"ID {row['id']} - {row['cliente']} - {row['data'].strftime('%d/%m/%Y')} - R$ {row['valor_num']:.2f}", axis=1)
            selecao = st.selectbox("Selecione o lançamento:", df_filtrado['opcao'])
            if selecao:
                try:
                    id_sel = int(selecao.split(" - ")[0].replace("ID ", ""))
                except (ValueError, IndexError):
                    st.error("Erro ao identificar o ID.")
                    st.stop()
                lanc = df[df['id'] == id_sel].iloc[0]
                with st.expander("Visualizar dados atuais", expanded=False):
                    st.write(f"**ID:** {lanc['id']}")
                    st.write(f"**Data:** {lanc['data'].strftime('%d/%m/%Y')}")
                    st.write(f"**Revenda:** {lanc['revenda']}")
                    st.write(f"**Cliente:** {lanc['cliente']}")
                    st.write(f"**Valor:** R$ {lanc['valor_num']:.2f}")
                    st.write(f"**Forma de pagamento:** {lanc['forma de pagamento']}")
                    st.write(f"**Produto:** {lanc['produto']}")
                    st.write(f"**Situação:** {lanc['situação']}")
                    st.text_area("Texto atual", lanc['texto'], height=100, disabled=True)
                st.subheader("Editar lançamento")
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nova_data = st.date_input("Data", lanc['data'])
                        nova_revenda = st.text_input("Revenda", lanc['revenda'])
                        novo_cliente = st.text_input("Cliente", lanc['cliente'])
                        novo_valor = st.number_input("Valor (R$)", value=float(lanc['valor_num']), step=0.01, format="%.2f")
                    with col2:
                        opcoes_pagamento = ["Dinheiro", "cartão de credito", "pix", "Transferência pix", "aguardando pagamento"]
                        valor_atual = lanc['forma de pagamento']
                        try:
                            idx_pag = opcoes_pagamento.index(valor_atual)
                        except ValueError:
                            idx_pag = 0
                        nova_forma = st.selectbox("Forma de pagamento", opcoes_pagamento, index=idx_pag)
                        opcoes_produto = [
                            "disa e-mail", "espera e-mail", "espera modulo", "disa chip",
                            "regravação espera", "natal", "itcp", "disa e-mail espera em chip",
                            "disa e espera por e-mail", "visita técnica", "Outro"
                        ]
                        if lanc['produto'] in opcoes_produto:
                            idx_prod = opcoes_produto.index(lanc['produto'])
                        else:
                            idx_prod = opcoes_produto.index("Outro")
                        prod_sel = st.selectbox("Produto", opcoes_produto, index=idx_prod)
                        if prod_sel == "Outro":
                            novo_produto = st.text_input("Especifique o produto", value=lanc['produto'] if lanc['produto'] not in opcoes_produto else "")
                        else:
                            novo_produto = prod_sel
                        nova_situacao = st.selectbox("Situação", ["entregue", "pendente", "cancelado", "em andamento"],
                                                    index=["entregue", "pendente", "cancelado", "em andamento"].index(lanc['situação']))
                    novo_texto = st.text_area("Texto", value=lanc['texto'], height=150)
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        atualizar = st.form_submit_button("💾 Atualizar Lançamento")
                    with col_btn2:
                        excluir = st.form_submit_button("🗑️ Excluir Lançamento", type="primary")
                    if atualizar:
                        ok = atualizar_lancamento(id_sel, nova_data, nova_revenda, novo_cliente, novo_valor,
                                                  nova_forma, novo_produto, nova_situacao, novo_texto)
                        if ok:
                            st.success("Lançamento atualizado!")
                            st.rerun()
                        else:
                            st.error("Erro ao atualizar.")
                    if excluir:
                        if st.checkbox("Confirmar exclusão permanente?"):
                            excluir_lancamento(id_sel)
                            st.warning("Lançamento excluído!")
                            st.rerun()