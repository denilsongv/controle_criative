import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# =========================
# CONFIGURAÇÕES
# =========================
ID_PLANILHA = "1XzaYeaNvzfnC5C5Hf4drW-6dpPydx2jw_cVJ7qsHnuc"
NOME_ABA = "criative"

st.set_page_config(page_title="HZ Telecom", layout="wide", page_icon="📱")
st.title("📱 Criative - Gestão de Lançamentos")


# =========================
# CONEXÃO GOOGLE SHEETS
# =========================
@st.cache_resource
def conectar_google():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    info = dict(st.secrets["gcp_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return creds


def conectar_planilha():
    creds = conectar_google()
    client = gspread.authorize(creds)
    return client.open_by_key(ID_PLANILHA).worksheet(NOME_ABA)


# =========================
# FUNÇÕES AUXILIARES
# =========================
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


def criar_pdf_servico(df_pdf, nome_servico):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    margem_esq = 40
    y = altura - 40

    pdf.setTitle(f"Relacao_{nome_servico}")

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margem_esq, y, f"Relação de Lançamentos - Serviço: {nome_servico}")
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawString(margem_esq, y, f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 25

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margem_esq, y, "Cliente")
    pdf.drawString(260, y, "Serviço")
    pdf.drawString(470, y, "Valor")
    y -= 10
    pdf.line(margem_esq, y, largura - 40, y)
    y -= 15

    total = 0.0

    pdf.setFont("Helvetica", 9)
    for _, row in df_pdf.iterrows():
        cliente = str(row["cliente"])[:38]
        servico = str(row["servico"])[:25]
        valor = float(row["valor_num"])

        total += valor

        if y < 60:
            pdf.showPage()
            y = altura - 40
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(margem_esq, y, "Cliente")
            pdf.drawString(260, y, "Serviço")
            pdf.drawString(470, y, "Valor")
            y -= 10
            pdf.line(margem_esq, y, largura - 40, y)
            y -= 15
            pdf.setFont("Helvetica", 9)

        pdf.drawString(margem_esq, y, cliente)
        pdf.drawString(260, y, servico)
        pdf.drawRightString(550, y, formatar_valor_brl(valor))
        y -= 16

    y -= 10
    pdf.line(margem_esq, y, largura - 40, y)
    y -= 18

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margem_esq, y, f"Quantidade de registros: {len(df_pdf)}")
    pdf.drawRightString(550, y, f"Total: {formatar_valor_brl(total)}")

    pdf.save()
    buffer.seek(0)
    return buffer


# =========================
# LEITURA DOS DADOS
# =========================
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        sheet = conectar_planilha()
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)

        if df.empty:
            return df

        col_id = obter_nome_coluna(df, "id")
        col_data = obter_nome_coluna(df, "data")
        col_valor = obter_nome_coluna(df, "valor")
        col_texto = obter_nome_coluna(df, "texto")
        col_produto = obter_nome_coluna(df, "produto")
        col_cliente = obter_nome_coluna(df, "cliente")

        if col_id and col_id != "id":
            df["id"] = df[col_id]

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

        if col_texto and col_texto != "texto":
            df["texto"] = df[col_texto]
        if "texto" not in df.columns:
            df["texto"] = ""

        if col_produto and col_produto != "produto":
            df["produto"] = df[col_produto]

        if col_cliente and col_cliente != "cliente":
            df["cliente"] = df[col_cliente]

        if "data" in df.columns:
            df["ano"] = df["data"].dt.year
            df["mes"] = df["data"].dt.month

        return df

    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return pd.DataFrame()


# =========================
# CRUD
# =========================
def salvar_lancamento(data, revenda, cliente, valor, forma_pagamento, produto, situacao, texto_completo):
    try:
        sheet = conectar_planilha()
        df = carregar_dados()

        if forma_pagamento == "aguardando pagamento":
            situacao = "pendente"







        novo_id = 1
        if not df.empty and "id" in df.columns:
            ids_validos = pd.to_numeric(df["id"], errors="coerce").dropna()
            if len(ids_validos) > 0:
                novo_id = int(ids_validos.max()) + 1

        nova_linha = [
            novo_id,
            data.strftime("%d/%m/%Y"),
            revenda,
            cliente,
            formatar_valor_brl(valor),
            forma_pagamento,
            produto,
            situacao,
            texto_completo if texto_completo else ""
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
        df = carregar_dados()

        if df.empty or "id" not in df.columns:
            return False

        linha_df = df[df["id"].astype(str) == str(id_lancamento)]
        if linha_df.empty:
            return False

        indice_df = linha_df.index[0]
        linha_planilha = indice_df + 2

        if forma_pagamento == "aguardando pagamento":
            situacao = "pendente"

        nova_linha = [[
            id_lancamento,
            data.strftime("%d/%m/%Y"),
            revenda,
            cliente,
            formatar_valor_brl(valor),
            forma_pagamento,
            produto,
            situacao,
            novo_texto if novo_texto else ""
        ]]

        sheet.update(f"A{linha_planilha}:I{linha_planilha}", nova_linha)
        st.cache_data.clear()
        return True

    except Exception as e:
        st.error(f"Erro ao atualizar lançamento: {e}")
        return False


def excluir_lancamento(id_lancamento):
    try:
        sheet = conectar_planilha()
        df = carregar_dados()

        if df.empty or "id" not in df.columns:
            return

        linha_df = df[df["id"].astype(str) == str(id_lancamento)]
        if linha_df.empty:
            return

        indice_df = linha_df.index[0]
        linha_planilha = indice_df + 2

        sheet.delete_rows(linha_planilha)
        st.cache_data.clear()

    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")


# =========================
# MENU
# =========================
menu = st.sidebar.radio(
    "Navegação",
    ["📋 Dashboard", "➕ Novo Lançamento", "✏️ Editar/Excluir", "📄 Gerar PDF"]
)


# =========================
# DASHBOARD
# =========================
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
        col_texto = obter_nome_coluna(df, "texto")

        st.sidebar.markdown("---")
        st.sidebar.subheader("⏳ Clientes pendentes")

        if col_cliente and (col_forma or col_situacao):
            condicoes = pd.Series(False, index=df.index)

            if col_forma:
                condicoes = condicoes | (
                    df[col_forma].astype(str).str.strip().str.lower() == "aguardando pagamento"
                )

            if col_situacao:
                condicoes = condicoes | (
                    df[col_situacao].astype(str).str.strip().str.lower() == "pendente"
                )

            pendentes = df[condicoes].copy()

            if not pendentes.empty:
                resumo_pendentes = (
                    pendentes.groupby(col_cliente, dropna=True)["valor_num"]
                    .sum()
                    .reset_index()
                    .sort_values("valor_num", ascending=False)
                )

                for _, linha in resumo_pendentes.iterrows():
                    cliente = str(linha[col_cliente]).strip()
                    valor = linha["valor_num"]
                    st.sidebar.write(f"• {cliente} — {formatar_valor_brl(valor)}")
            else:
                st.sidebar.caption("Nenhum cliente pendente.")

        st.sidebar.header("🔍 Filtros")

        if col_situacao:
            situacoes = df[col_situacao].dropna().unique().tolist()
            selecao = st.sidebar.multiselect("Situação", situacoes, default=situacoes)
            if selecao:
                df = df[df[col_situacao].isin(selecao)]









        if not df.empty and "data" in df.columns:
            df_datas_validas = df.dropna(subset=["data"]).copy()

            if not df_datas_validas.empty:
                anos_disponiveis = sorted(df_datas_validas["ano"].dropna().unique())
                meses_dict = {
                    1: "Janeiro",
                    2: "Fevereiro",
                    3: "Março",
                    4: "Abril",
                    5: "Maio",
                    6: "Junho",
                    7: "Julho",
                    8: "Agosto",
                    9: "Setembro",
                    10: "Outubro",
                    11: "Novembro",
                    12: "Dezembro"
                }

                col_filtro1, col_filtro2 = st.columns(2)

                ano_atual = datetime.today().year
                mes_atual = datetime.today().month

                if ano_atual in anos_disponiveis:
                    idx_ano = anos_disponiveis.index(ano_atual)
                else:
                    idx_ano = len(anos_disponiveis) - 1

                with col_filtro1:
                    ano_sel = st.selectbox(
                        "Selecione o ano",
                        anos_disponiveis,
                        index=idx_ano
                    )

                meses_disponiveis = sorted(
                    df_datas_validas[df_datas_validas["ano"] == ano_sel]["mes"].dropna().unique()
                )

                if mes_atual in meses_disponiveis:
                    idx_mes = meses_disponiveis.index(mes_atual)
                else:
                    idx_mes = len(meses_disponiveis) - 1 if meses_disponiveis else 0

                with col_filtro2:
                    mes_sel = st.selectbox(
                        "Selecione o mês",
                        meses_disponiveis,
                        index=idx_mes,
                        format_func=lambda x: meses_dict.get(x, str(x))
                    )

                df_mes = df_datas_validas[
                    (df_datas_validas["ano"] == ano_sel) &
                    (df_datas_validas["mes"] == mes_sel)
                ]

                faturamento_mes = df_mes["valor_num"].sum()
                ticket_medio_mes = df_mes["valor_num"].mean() if len(df_mes) > 0 else 0

                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("💰 Faturamento do mês", formatar_valor_brl(faturamento_mes))
                with m2:
                    st.metric("📄 Lançamentos no mês", len(df_mes))
                with m3:
                    st.metric("📊 Ticket médio do mês", formatar_valor_brl(ticket_medio_mes))
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    

        st.markdown("---")

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
                for i, row in df.reset_index(drop=True).iterrows():
                    data_formatada = row["data"].strftime("%d/%m/%Y") if pd.notna(row["data"]) else "Sem data"
                    with st.expander(f"📝 ID {row[col_id]} - {row[col_cliente]} - {data_formatada}"):
                        texto = row[col_texto] if col_texto and pd.notna(row[col_texto]) else ""
                        st.text_area(
                            "Conteúdo",
                            texto,
                            height=200,
                            key=f"texto_dashboard_{i}",
                            disabled=True
                        )

        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")








# =========================
# NOVO LANÇAMENTO
# =========================
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
                    data, revenda, cliente, valor,
                    forma_pagamento, produto, situacao, texto_completo
                )

                if novo_id:
                    st.success(f"Lançamento ID {novo_id} salvo com sucesso!")
                    st.rerun()


# =========================
# EDITAR / EXCLUIR
# =========================
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
        col_texto = obter_nome_coluna(df, "texto")

        tipo_busca = st.radio("Buscar por:", ["Cliente", "ID", "Revenda"], horizontal=True)

        if tipo_busca == "ID":
            id_busca = st.number_input("Digite o ID", min_value=1, step=1)

            if id_busca and col_id:
                df_filtrado = df[df[col_id].astype(str) == str(id_busca)]
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
            lanc = df[df[col_id].astype(str) == str(id_sel)].iloc[0]

            with st.expander("Visualizar dados atuais", expanded=False):
                st.write(f"**ID:** {lanc[col_id]}")
                st.write(f"**Data:** {lanc['data'].strftime('%d/%m/%Y') if pd.notna(lanc['data']) else 'Sem data'}")
                st.write(f"**Revenda:** {lanc[col_revenda]}")
                st.write(f"**Cliente:** {lanc[col_cliente]}")
                st.write(f"**Valor:** {formatar_valor_brl(lanc['valor_num'])}")
                st.write(f"**Forma de pagamento:** {lanc[col_forma]}")
                st.write(f"**Produto:** {lanc[col_produto]}")
                st.write(f"**Situação:** {lanc[col_situacao]}")

                texto_curto = lanc[col_texto] if col_texto and pd.notna(lanc[col_texto]) else ""
                previa = texto_curto[:500] + ("..." if len(texto_curto) > 500 else "")
                st.text_area("Prévia do texto", previa, height=150, disabled=True)

            st.subheader("Editar lançamento")

            with st.form("edit_form"):
                c1, c2 = st.columns(2)

                with c1:
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

                with c2:
                    opcoes_pagamento = ["Dinheiro", "cartão de credito", "pix", "aguardando pagamento"]
                    forma_atual = lanc[col_forma]
                    idx_forma = opcoes_pagamento.index(forma_atual) if forma_atual in opcoes_pagamento else 0

                    nova_forma = st.selectbox("Forma de pagamento", opcoes_pagamento, index=idx_forma)

                    opcoes_produto = [
                        "disa e-mail", "espera e-mail", "espera modulo", "disa chip",
                        "regravação espera", "natal", "itcp", "disa e-mail espera em chip",
                        "disa e espera por e-mail", "visita técnica", "Outro",
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

                    nova_situacao = st.selectbox("Situação", opcoes_situacao, index=idx_situacao)

                texto_atual = lanc[col_texto] if col_texto and pd.notna(lanc[col_texto]) else ""
                novo_texto = st.text_area("Texto completo", value=texto_atual, height=250)

                b1, b2 = st.columns(2)

                with b1:
                    atualizar = st.form_submit_button("💾 Atualizar Lançamento")

                with b2:
                    excluir = st.form_submit_button("🗑️ Excluir Lançamento", type="primary")

                if atualizar:
                    ok = atualizar_lancamento(
                        id_sel,
                        datetime.combine(nova_data, datetime.min.time()),
                        nova_revenda,
                        novo_cliente,
                        novo_valor,
                        nova_forma,
                        novo_produto,
                        nova_situacao,
                        novo_texto
                    )

                    if ok:
                        st.success("Lançamento atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao atualizar. Verifique os dados.")

                if excluir:
                    excluir_lancamento(id_sel)
                    st.warning("Lançamento excluído!")
                    st.rerun()



# =========================
# GERAR PDF
# =========================







elif menu == "📄 Gerar PDF":
    st.header("📄 Gerar PDF por serviço")

    df = carregar_dados()

    if df.empty:
        st.info("Não há lançamentos para gerar PDF.")
    else:
        col_cliente = obter_nome_coluna(df, "cliente")
        col_produto = obter_nome_coluna(df, "produto")

        if not col_cliente or not col_produto:
            st.error("As colunas 'cliente' e 'produto' precisam existir na planilha.")
        else:
            servicos = (
                df[col_produto]
                .dropna()
                .astype(str)
                .str.strip()
                .sort_values()
                .unique()
                .tolist()
            )

            if not servicos:
                st.warning("Não há serviços cadastrados.")
            else:
                servicos_sel = st.multiselect(
                    "Selecione um ou mais serviços",
                    servicos
                )

                if servicos_sel:
                    servicos_sel_normalizados = [s.strip().lower() for s in servicos_sel]

                    df_pdf = df[
                        df[col_produto].astype(str).str.strip().str.lower().isin(servicos_sel_normalizados)
                    ].copy()

                    if df_pdf.empty:
                        st.warning("Nenhum registro encontrado para os serviços selecionados.")
                    else:
                        df_pdf["cliente"] = df_pdf[col_cliente].astype(str)
                        df_pdf["servico"] = df_pdf[col_produto].astype(str)

                        st.subheader("Prévia")
                        st.dataframe(
                            df_pdf[["cliente", "servico", "valor"]]
                            if "valor" in df_pdf.columns else
                            df_pdf[["cliente", "servico"]],
                            use_container_width=True
                        )

                        total_pdf = df_pdf["valor_num"].sum()
                        st.metric("Total dos serviços selecionados", formatar_valor_brl(total_pdf))

                        nome_servicos = "_".join(
                            [s.lower().replace(" ", "_") for s in servicos_sel[:3]]
                        )
                        if len(servicos_sel) > 3:
                            nome_servicos += "_e_outros"

                        pdf_buffer = criar_pdf_servico(
                            df_pdf[["cliente", "servico", "valor_num"]],
                            ", ".join(servicos_sel)
                        )

                        nome_arquivo = f"relacao_{nome_servicos}.pdf"
                        st.download_button(
                            label="📥 Baixar PDF",
                            data=pdf_buffer,
                            file_name=nome_arquivo,
                            mime="application/pdf"
                        )
                else:
                    st.info("Selecione pelo menos um serviço para gerar o PDF.")
