import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== CONFIGURAÇÕES =====
ID_PLANILHA = "1XzaYeaNvzfnC5C5Hf4drW-6dpPydx2jw_cVJ7qsHnuc"
NOME_ABA = "criative"
# =========================

st.set_page_config(page_title="HZ Telecom", layout="wide")
st.title("📱 HZ Telecom - Gestão de Lançamentos (Google Docs)")


# ==================== CONEXÕES ====================

@st.cache_resource
def conectar_google():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
    ]

    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return creds


def conectar_planilha():
    creds = conectar_google()
    client = gspread.authorize(creds)
    return client.open_by_key(ID_PLANILHA).worksheet(NOME_ABA)


def criar_documento_google_docs(titulo, texto):
    try:
        creds = conectar_google()
        service = build("docs", "v1", credentials=creds)

        doc = service.documents().create(body={"title": titulo}).execute()
        doc_id = doc.get("documentId")

        service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": texto or ""
                        }
                    }
                ]
            }
        ).execute()

        return f"https://docs.google.com/document/d/{doc_id}/edit"

    except Exception as e:
        st.error(f"Erro ao criar documento: {e}")
        return None


def buscar_conteudo_documento(doc_url):
    try:
        doc_id = doc_url.split("/d/")[1].split("/")[0]
        creds = conectar_google()
        service = build("docs", "v1", credentials=creds)
        doc = service.documents().get(documentId=doc_id).execute()

        texto = ""
        for content in doc.get("body", {}).get("content", []):
            if "paragraph" in content:
                for element in content["paragraph"].get("elements", []):
                    if "textRun" in element:
                        texto += element["textRun"].get("content", "")

        return texto.strip()

    except Exception as e:
        st.error(f"Erro ao buscar conteúdo: {e}")
        return ""


# ==================== FUNÇÕES AUXILIARES ====================
def formatar_valor_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def converter_valor_para_float(val):
    if pd.isna(val):
        return 0.0

    v = str(val).replace("R$", "").replace(" ", "").strip()

    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".")

    try:
        return float(v)
    except Exception:
        return 0.0


def obter_nome_coluna(df, nome_base):
    for col in df.columns:
        if str(col).strip().lower() == nome_base.strip().lower():
            return col
    return None


# ==================== CRUD ====================
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        sheet = conectar_planilha()
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)

        if df.empty:
            return df

        col_data = obter_nome_coluna(df, "data")
        col_valor = obter_nome_coluna(df, "valor")

        if col_data:
            df[col_data] = pd.to_datetime(df[col_data], format="%d/%m/%Y", errors="coerce")
            if col_data != "data":
                df["data"] = df[col_data]

        if col_valor:
            df["valor_num"] = df[col_valor].apply(converter_valor_para_float)
            if col_valor != "valor":
                df["valor"] = df[col_valor]
        else:
            df["valor_num"] = 0.0

        return df

    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return pd.DataFrame()


def salvar_lancamento(data, revenda, cliente, valor, forma_pagamento, produto, situacao, texto_completo):
    try:
        sheet = conectar_planilha()
        df = carregar_dados()

        col_id = obter_nome_coluna(df, "id") if not df.empty else None

        if not df.empty and col_id:
            novo_id = int(df[col_id].max()) + 1
        else:
            novo_id = 1

        if forma_pagamento == "aguardando pagamento":
            situacao = "pendente"

        titulo_doc = f"{cliente} - {data.strftime('%d/%m/%Y')} - {produto}"
        link_doc = ""

        
       

        nova_linha = [
            novo_id,
            data.strftime("%d/%m/%Y"),
            revenda,
            cliente,
            formatar_valor_brl(valor),
            forma_pagamento,
            produto,
            situacao,
            link_doc,
        ]

        sheet.append_row(nova_linha)
        st.cache_data.clear()
        return novo_id

    except Exception as e:
        st.error(f"Erro ao salvar lançamento: {e}")
        return None


def atualizar_lancamento(id_lancamento, data, revenda, cliente, valor, forma_pagamento, produto, situacao, novo_texto):
    try:
        sheet = conectar_planilha()
        celula = sheet.find(str(id_lancamento))

        if not celula:
            return False

        if forma_pagamento == "aguardando pagamento":
            situacao = "pendente"

        link_antigo = sheet.cell(celula.row, 9).value

        if novo_texto is not None and str(novo_texto).strip():
            titulo_doc = f"{cliente} - {data.strftime('%d/%m/%Y')} - {produto}"
            novo_link = criar_documento_google_docs(titulo_doc, novo_texto)
            if not novo_link:
                return False
        else:
            novo_link = link_antigo

        sheet.update_cell(celula.row, 2, data.strftime("%d/%m/%Y"))
        sheet.update_cell(celula.row, 3, revenda)
        sheet.update_cell(celula.row, 4, cliente)
        sheet.update_cell(celula.row, 5, formatar_valor_brl(valor))
        sheet.update_cell(celula.row, 6, forma_pagamento)
        sheet.update_cell(celula.row, 7, produto)
        sheet.update_cell(celula.row, 8, situacao)
        sheet.update_cell(celula.row, 9, novo_link)

        st.cache_data.clear()
        return True

    except Exception as e:
        st.error(f"Erro ao atualizar lançamento: {e}")
        return False


def excluir_lancamento(id_lancamento):
    try:
        sheet = conectar_planilha()
        celula = sheet.find(str(id_lancamento))

        if celula:
            sheet.delete_rows(celula.row)
            st.cache_data.clear()

    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")


def obter_texto_lancamento(id_lancamento):
    try:
        sheet = conectar_planilha()
        celula = sheet.find(str(id_lancamento))

        if celula:
            link = sheet.cell(celula.row, 9).value
            if link and link.startswith("http"):
                return buscar_conteudo_documento(link)

        return ""

    except Exception as e:
        st.error(f"Erro ao obter texto do lançamento: {e}")
        return ""


# ==================== INTERFACE ====================
menu = st.sidebar.radio("Navegação", ["📋 Dashboard", "➕ Novo Lançamento", "✏️ Editar/Excluir"])


if menu == "📋 Dashboard":
    df = carregar_dados()

    if df.empty:
        st.info("Nenhum lançamento ainda. Use o menu para adicionar.")
    else:
        col_situacao = obter_nome_coluna(df, "situação") or obter_nome_coluna(df, "situacao")
        col_forma = obter_nome_coluna(df, "forma de pagamento")
        col_revenda = obter_nome_coluna(df, "revenda")
        col_cliente = obter_nome_coluna(df, "cliente")
        col_id = obter_nome_coluna(df, "id")

        st.sidebar.header("🔍 Filtros")

        if col_situacao:
            situacoes = df[col_situacao].dropna().unique().tolist()
            selecao = st.sidebar.multiselect("Situação", situacoes, default=situacoes)
            if selecao:
                df = df[df[col_situacao].isin(selecao)]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("💰 Valor Total", formatar_valor_brl(df["valor_num"].sum()))

        with col2:
            st.metric("📄 Total Lançamentos", len(df))

        with col3:
            media = df["valor_num"].mean() if len(df) > 0 else 0
            st.metric("📊 Valor Médio", formatar_valor_brl(media))

        st.markdown("---")

        tab1, tab2, tab3 = st.tabs(["📋 Tabela", "📈 Gráficos", "📄 Textos"])

        with tab1:
            def highlight_pendente(row):
                if col_forma and row.get(col_forma) == "aguardando pagamento":
                    return ["background-color: #ffcccc"] * len(row)
                return [""] * len(row)

            styled_df = df.style.apply(highlight_pendente, axis=1)
            st.dataframe(styled_df, use_container_width=True)

        with tab2:
            if col_revenda:
                top = df.groupby(col_revenda)["valor_num"].sum().sort_values(ascending=False).head(10)
                fig = px.bar(
                    x=top.values,
                    y=top.index,
                    orientation="h",
                    title="Valor por Revenda"
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab3:
            if col_id and col_cliente:
                for _, row in df.iterrows():
                    data_formatada = row["data"].strftime("%d/%m/%Y") if pd.notna(row["data"]) else "Sem data"
                    with st.expander(f"📝 ID {row[col_id]} - {row[col_cliente]} - {data_formatada}"):
                        texto = obter_texto_lancamento(row[col_id])
                        st.text_area(
                            "Conteúdo",
                            texto,
                            height=200,
                            key=f"text_{row[col_id]}",
                            disabled=True
                        )

        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")


elif menu == "➕ Novo Lançamento":
    st.header("➕ Criar novo lançamento")

    with st.form("novo_form"):
        col1, col2 = st.columns(2)

        with col1:
            data_padrao = datetime.today().strftime("%d/%m/%Y")
            data_str = st.text_input("Data (DD/MM/AAAA)", value=data_padrao)

            try:
                data = datetime.strptime(data_str, "%d/%m/%Y")
            except Exception:
                st.error("Data inválida! Use o formato DD/MM/AAAA.")
                data = datetime.today()

            revenda = st.text_input("Revenda")
            cliente = st.text_input("Cliente")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")

        with col2:
            forma_pagamento = st.selectbox(
                "Forma de pagamento",
                ["Dinheiro", "cartão de credito", "pix", "aguardando pagamento"],
                index=3
            )

            opcoes_produto = [
                "disa e-mail",
                "espera e-mail",
                "espera modulo",
                "disa chip",
                "regravação espera",
                "natal",
                "itcp",
                "disa e-mail espera em chip",
                "disa e espera por e-mail",
                "visita técnica",
                "Outro",
            ]

            produto_selecionado = st.selectbox("Produto", opcoes_produto)

            if produto_selecionado == "Outro":
                produto = st.text_input("Especifique o produto")
            else:
                produto = produto_selecionado

            situacao = st.selectbox(
                "Situação",
                ["entregue", "pendente", "cancelado", "em andamento"],
                index=3
            )

        texto_completo = st.text_area("Texto completo (observações)", height=300)
        submitted = st.form_submit_button("Salvar")

        if submitted:
            if not revenda or not cliente:
                st.error("Revenda e Cliente são obrigatórios.")
            else:
                novo_id = salvar_lancamento(
                    data,
                    revenda,
                    cliente,
                    valor,
                    forma_pagamento,
                    produto,
                    situacao,
                    texto_completo
                )

                if novo_id:
                    st.success(f"Lançamento ID {novo_id} salvo! Texto no Google Docs.")
                    st.balloons()
                    st.rerun()


elif menu == "✏️ Editar/Excluir":
    st.header("✏️ Editar ou Excluir Lançamento")
    df = carregar_dados()

    if df.empty:
        st.warning("Nenhum lançamento para editar.")
    else:
        col_id = obter_nome_coluna(df, "id")
        col_cliente = obter_nome_coluna(df, "cliente")
        col_revenda = obter_nome_coluna(df, "revenda")
        col_produto = obter_nome_coluna(df, "produto")
        col_forma = obter_nome_coluna(df, "forma de pagamento")
        col_situacao = obter_nome_coluna(df, "situação") or obter_nome_coluna(df, "situacao")

        tipo_busca = st.radio("Buscar por:", ["Cliente", "ID", "Revenda"], horizontal=True)

        if tipo_busca == "ID":
            id_busca = st.number_input("Digite o ID", min_value=1, step=1)

            if id_busca and col_id:
                df_filtrado = df[df[col_id] == id_busca]
            else:
                df_filtrado = pd.DataFrame()

        elif tipo_busca == "Cliente":
            busca = st.text_input("Digite parte do nome do cliente")

            if busca and col_cliente:
                df_filtrado = df[df[col_cliente].astype(str).str.contains(busca, case=False, na=False)]
            else:
                df_filtrado = df

        else:
            busca = st.text_input("Digite parte do nome da revenda")

            if busca and col_revenda:
                df_filtrado = df[df[col_revenda].astype(str).str.contains(busca, case=False, na=False)]
            else:
                df_filtrado = df

        if df_filtrado.empty:
            st.info("Nenhum registro encontrado.")
        else:
            df_filtrado = df_filtrado.copy()
            df_filtrado["opcao"] = df_filtrado.apply(
                lambda row: (
                    f"ID {row[col_id]} - "
                    f"{row[col_cliente]} - "
                    f"{row['data'].strftime('%d/%m/%Y') if pd.notna(row['data']) else 'Sem data'} - "
                    f"R$ {row['valor_num']:.2f}"
                ),
                axis=1
            )

            selecao = st.selectbox("Selecione o lançamento:", df_filtrado["opcao"])
            id_sel = int(selecao.split(" - ")[0].replace("ID ", ""))
            lanc = df[df[col_id] == id_sel].iloc[0]

            with st.expander("Visualizar dados atuais", expanded=False):
                st.write(f"**ID:** {lanc[col_id]}")
                st.write(f"**Data:** {lanc['data'].strftime('%d/%m/%Y') if pd.notna(lanc['data']) else 'Sem data'}")
                st.write(f"**Revenda:** {lanc[col_revenda]}")
                st.write(f"**Cliente:** {lanc[col_cliente]}")
                st.write(f"**Valor:** {formatar_valor_brl(lanc['valor_num'])}")
                st.write(f"**Forma de pagamento:** {lanc[col_forma]}")
                st.write(f"**Produto:** {lanc[col_produto]}")
                st.write(f"**Situação:** {lanc[col_situacao]}")

                link_doc = lanc.iloc[8] if len(lanc) > 8 else "Link não disponível"
                st.write(f"**Link do documento:** [Abrir]({link_doc})")

                texto_curto = obter_texto_lancamento(id_sel)
                previa = texto_curto[:500] + ("..." if len(texto_curto) > 500 else "")
                st.text_area("Prévia do texto", previa, height=150, disabled=True)

            st.subheader("Editar lançamento")

            with st.form("edit_form"):
                col1, col2 = st.columns(2)

                with col1:
                    nova_data = st.date_input(
                        "Data",
                        value=lanc["data"].date() if pd.notna(lanc["data"]) else datetime.today().date()
                    )
                    nova_revenda = st.text_input("Revenda", value=lanc[col_revenda])
                    novo_cliente = st.text_input("Cliente", value=lanc[col_cliente])
                    novo_valor = st.number_input(
                        "Valor (R$)",
                        value=float(lanc["valor_num"]),
                        step=0.01,
                        format="%.2f"
                    )

                with col2:
                    opcoes_pagamento = ["Dinheiro", "cartão de credito", "pix", "aguardando pagamento"]
                    forma_atual = lanc[col_forma]
                    idx_forma = opcoes_pagamento.index(forma_atual) if forma_atual in opcoes_pagamento else 0

                    nova_forma = st.selectbox(
                        "Forma de pagamento",
                        opcoes_pagamento,
                        index=idx_forma
                    )

                    opcoes_produto = [
                        "disa e-mail",
                        "espera e-mail",
                        "espera modulo",
                        "disa chip",
                        "regravação espera",
                        "natal",
                        "itcp",
                        "disa e-mail espera em chip",
                        "disa e espera por e-mail",
                        "visita técnica",
                        "Outro",
                    ]

                    produto_atual = lanc[col_produto]
                    idx_prod = opcoes_produto.index(produto_atual) if produto_atual in opcoes_produto else opcoes_produto.index("Outro")

                    prod_sel = st.selectbox("Produto", opcoes_produto, index=idx_prod)

                    if prod_sel == "Outro":
                        novo_produto = st.text_input(
                            "Especifique o produto",
                            value=produto_atual if produto_atual not in opcoes_produto else ""
                        )
                    else:
                        novo_produto = prod_sel

                    opcoes_situacao = ["entregue", "pendente", "cancelado", "em andamento"]
                    situacao_atual = lanc[col_situacao]
                    idx_situacao = opcoes_situacao.index(situacao_atual) if situacao_atual in opcoes_situacao else 0

                    nova_situacao = st.selectbox(
                        "Situação",
                        opcoes_situacao,
                        index=idx_situacao
                    )

                texto_atual = obter_texto_lancamento(id_sel)
                novo_texto = st.text_area(
                    "Texto completo (deixe em branco para manter o atual)",
                    value=texto_atual,
                    height=200,
                    help="Se você alterar este texto, um novo documento será criado no Google Docs."
                )

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    atualizar = st.form_submit_button("💾 Atualizar Lançamento")

                with col_btn2:
                    excluir = st.form_submit_button("🗑️ Excluir Lançamento", type="primary")

                if atualizar:
                    texto_para_envio = novo_texto if novo_texto != texto_atual else None

                    ok = atualizar_lancamento(
                        id_sel,
                        datetime.combine(nova_data, datetime.min.time()),
                        nova_revenda,
                        novo_cliente,
                        novo_valor,
                        nova_forma,
                        novo_produto,
                        nova_situacao,
                        texto_para_envio
                    )

                    if ok:
                        st.success("Lançamento atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao atualizar. Verifique os dados.")

                if excluir:
                    confirmar = st.checkbox("Confirmar exclusão permanente?")
                    if confirmar:
                        excluir_lancamento(id_sel)
                        st.warning("Lançamento excluído!")
                        st.rerun()


# ==================== TESTES OPCIONAIS ====================
st.sidebar.markdown("---")

if st.sidebar.button("Testar conexão com Sheets"):
    try:
        aba = conectar_planilha()
        dados = aba.get_all_records()
        st.sidebar.success(f"Sheets OK: {len(dados)} linhas")
    except Exception as e:
        st.sidebar.error(f"Erro Sheets: {e}")

if st.sidebar.button("Testar criação de Docs"):
    try:
        link = criar_documento_google_docs("Teste Streamlit", "Documento criado com sucesso.")
        if link:
            st.sidebar.success("Docs OK")
            
            st.sidebar.write(link)
    except Exception as e:
        st.sidebar.error(f"Erro Docs: {e}")

st.write(st.secrets)


if st.button("TESTAR CONEXÃO"):
    try:
        aba = conectar_planilha()
        dados = aba.get_all_records()
        st.success(f"Funcionou! {len(dados)} linhas encontradas.")
    except Exception as e:
        st.error(f"Erro: {e}")
