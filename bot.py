from __future__ import annotations

import datetime
import os
import re
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks


DATABASE_NAME = "worldcup_traders.db"
TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_SINAIS = "worldcup-sinais"
CANAL_RESULTADOS = "worldcup-resultados"
CANAL_ANUNCIOS = "worldcup-anuncios"  # Canal de anúncios oficial
HASHTAG_SINAL = "#Sinal"
LIMITE_SINAIS_DIARIOS = 5
PONTOS_RESULTADOS = {
    "#TP": 5,
    "#BE": 2,
    "#SL": -1,
}
EMOJIS_RESULTADOS = {
    "#TP": "🎯",
    "#BE": "🤝",
    "#SL": "❌",
}
BONUS_HAT_TRICK = 15
BONUS_TP_SEGUIDOS = 10
BONUS_DIA_PERFEITO = 5
TIMEZONE_CAMPEONATO = ZoneInfo("Europe/Lisbon")

BANDEIRAS_SELECOES = {
    "Portugal": "🇵🇹", "Brasil": "🇧🇷", "Argentina": "🇦🇷", "França": "🇫🇷",
    "Alemanha": "🇩🇪", "Espanha": "🇪🇸", "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Senegal": "🇸🇳",
    "Holanda": "🇳🇱", "Bélgica": "🇧🇪", "Croácia": "🇭🇷", "Estados Unidos": "🇺🇸",
    "Uruguai": "🇺🇾", "Marrocos": "🇲🇦", "Japão": "🇯🇵", "México": "🇲🇽",
    "Suíça": "🇨🇭", "Cabo Verde": "🇨🇻", "Colômbia": "🇨🇴"
}

PARTICIPANTES_OFICIAIS = [
    ("id_Xitos", "Xitos", "Portugal"),
    ("id_Jack_Lourenzo", "Jack Lourenzo", "Brasil"),
    ("id_jailson", "jailson.", "Argentina"),
    ("id_Antonio_Chipinga", "Antonio Chipinga", "França"),
    ("id_Antonio_Cateia", "António Cateia", "Alemanha"),
    ("id_Cmdte_SHI_FU_Trader", "Cmdte SHI FÚ Trader", "Espanha"),
    ("id_Daniel_Marcelo", "Daniel Marcelo", "Inglaterra"),
    ("id_Fil_Leateya", "Fil Leateya", "Senegal"),
    ("id_Francisco_Caetano", "Francisco Caetano", "Holanda"),
    ("id_GOLD6018", "GOLD6018", "Bélgica"),
    ("id_Graca", "Graça", "Croácia"),
    ("id_Hosana_Manuel", "Hosana Manuel", "Estados Unidos"),
    ("id_JC_Fernandes", "JC Fernandes", "Uruguai"),
    ("id_Klaus_Willy", "Klaus Willy", "Marrocos"),
    ("id_Lukeny_Do_Rosario", "Lukeny Do Rosario", "Japão"),
    ("id_Miguel_FM", "Miguel FM", "México"),
    ("id_NR_NP", "NR-NP", "Suíça"),
    ("id_Nyna_Torres", "Nyna Torres", "Cabo Verde"),
    ("id_El_Tubarao", "El Tubarão", "Colômbia")
]

CALENDARIO_OFICIAL = {
    # --- SEMANA 1 ---
    "2026-06-08": ["Portugal", "Brasil"],
    "2026-06-09": ["Argentina", "França"],
    "2026-06-10": ["Alemanha", "Espanha"],
    "2026-06-11": ["Inglaterra", "Senegal"],
    "2026-06-12": ["Holanda", "Bélgica"],
    
    # --- SEMANA 2 ---
    "2026-06-15": ["Croácia", "Estados Unidos"],
    "2026-06-16": ["Uruguai", "Marrocos"],
    "2026-06-17": ["Japão", "México"],
    "2026-06-18": ["Suíça", "Cabo Verde"],
    "2026-06-19": ["Colômbia", "Portugal"],
    
    # --- SEMANA 3 ---
    "2026-06-22": ["Brasil", "Argentina"],
    "2026-06-23": ["França", "Alemanha"],
    "2026-06-24": ["Espanha", "Inglaterra"],
    "2026-06-25": ["Senegal", "Holanda"],
    "2026-06-26": ["Bélgica", "Croácia"],
    
    # --- SEMANA 4 ---
    "2026-06-29": ["Estados Unidos", "Uruguai"],
    "2026-06-30": ["Marrocos", "Japão"],
    "2026-07-01": ["México", "Suíça"],
    "2026-07-02": ["Cabo Verde", "Colômbia"],
    "2026-07-03": ["Portugal", "Brasil"],
}

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / DATABASE_NAME


def conectar_banco() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE_PATH)


def criar_tabelas() -> None:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS traders (
                discord_id TEXT PRIMARY KEY,
                nome TEXT,
                selecao TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historico_sinais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT,
                tipo_hashtag TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ranking (
                selecao TEXT PRIMARY KEY,
                pontos INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fechamentos_diarios (
                data TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def popular_campeonato_oficial() -> None:
    selecoes = {(selecao,) for _, _, selecao in PARTICIPANTES_OFICIAIS}
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ranking")
        cursor.executemany(
            "INSERT OR IGNORE INTO traders (discord_id, nome, selecao) VALUES (?, ?, ?)",
            PARTICIPANTES_OFICIAIS,
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO ranking (selecao, pontos) VALUES (?, 0)",
            selecoes,
        )
        conn.commit()


def inicializar_banco() -> None:
    criar_tabelas()


def buscar_trader(discord_id: str) -> tuple[str, str] | None:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome, selecao FROM traders WHERE discord_id = ?", (discord_id,))
        return cursor.fetchone()


def buscar_nome_trader_por_selecao(selecao: str) -> str:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT nome FROM traders 
            WHERE selecao = ? AND discord_id NOT LIKE 'id_%' 
            LIMIT 1
            """, 
            (selecao,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        cursor.execute("SELECT nome FROM traders WHERE selecao = ? LIMIT 1", (selecao,))
        row = cursor.fetchone()
        return row[0] if row else "Sem Trader"


def contar_hashtag_hoje(discord_id: str, tipo_hashtag: str) -> int:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM historico_sinais
            WHERE discord_id = ? AND tipo_hashtag = ? AND DATE(timestamp, 'localtime') = DATE('now', 'localtime')
            """,
            (discord_id, tipo_hashtag),
        )
        return cursor.fetchone()[0]


def contar_sinais_hoje(discord_id: str) -> int:
    return contar_hashtag_hoje(discord_id, HASHTAG_SINAL)


def registrar_sinal(discord_id: str, selecao: str) -> None:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO historico_sinais (discord_id, tipo_hashtag) VALUES (?, ?)", (discord_id, HASHTAG_SINAL))
        cursor.execute("UPDATE ranking SET pontos = pontos + 1 WHERE selecao = ?", (selecao,))
        conn.commit()


def identificar_hashtag_resultado(conteudo: str) -> str | None:
    for hashtag in PONTOS_RESULTADOS:
        if hashtag in conteudo:
            return hashtag
    return None


def registrar_resultado(discord_id: str, selecao: str, tipo_hashtag: str) -> list[str]:
    bonus_aplicados = []
    pontos = PONTOS_RESULTADOS[tipo_hashtag]

    with conectar_banco() as conn:
        cursor = conn.cursor()

        if tipo_hashtag == "#TP":
            cursor.execute(
                """
                SELECT COUNT(*) FROM historico_sinais
                WHERE discord_id = ? AND tipo_hashtag = '#TP' AND DATE(timestamp, 'localtime') = DATE('now', 'localtime')
                """,
                (discord_id,),
            )
            total_tp_hoje = cursor.fetchone()[0]
            if total_tp_hoje + 1 == 3:
                pontos += BONUS_HAT_TRICK
                bonus_aplicados.append("hat_trick")

            cursor.execute(
                "SELECT tipo_hashtag FROM historico_sinais WHERE discord_id = ? ORDER BY timestamp DESC, id DESC LIMIT 2",
                (discord_id,),
            )
            ultimos_registros = [row[0] for row in cursor.fetchall()]
            if ultimos_registros == ["#TP", "#TP"]:
                pontos += BONUS_TP_SEGUNDOS
                bonus_aplicados.append("tp_seguidos")

        cursor.execute("INSERT INTO historico_sinais (discord_id, tipo_hashtag) VALUES (?, ?)", (discord_id, tipo_hashtag))
        cursor.execute("UPDATE ranking SET pontos = pontos + ? WHERE selecao = ?", (pontos, selecao))
        conn.commit()

    return bonus_aplicados


def cadastrar_trader(discord_id: str, nome: str, selecao: str) -> None:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO traders (discord_id, nome, selecao) VALUES (?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET nome = excluded.nome, selecao = excluded.selecao
            """,
            (discord_id, nome, selecao),
        )
        cursor.execute("INSERT OR IGNORE INTO ranking (selecao, pontos) VALUES (?, 0)", (selecao,))
        conn.commit()


def buscar_selecoes_cadastradas() -> set[str]:
    selecoes = {selecao for _, _, selecao in PARTICIPANTES_OFICIAIS}
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT selecao FROM ranking")
        selecoes.update(row[0] for row in cursor.fetchall())
    return selecoes


def extrair_nome_e_selecao(texto: str) -> tuple[str, str] | None:
    texto = text.strip()
    for selecao in sorted(buscar_selecoes_cadastradas(), key=len, reverse=True):
        if texto.casefold().endswith(selecao.casefold()):
            nome = texto[: -len(selecao)].strip()
            if nome:
                return nome, selecao
    return None


def extrair_linhas_registro(ctx: commands.Context) -> list[str]:
    linhas = ctx.message.content.split("\n")
    primeira_linha = lines[0]
    comando = ctx.invoked_with or "registrar"
    prefixo = str(ctx.prefix or "")
    chamada = f"{prefixo}{comando}"
    if primeira_linha.startswith(chamada):
        primeira_linha = primeira_linha[len(chamada) :].strip()
    linhas[0] = primeira_linha
    return [linha.strip() for linha in lines if linha.strip()]


def data_hoje_campeonato() -> str:
    return datetime.datetime.now(TIMEZONE_CAMPEONATO).date().isoformat()


def fechar_dia_no_banco() -> tuple[bool, list[tuple[str, str]]]:
    data_fechamento = data_hoje_campeonato()
    traders_bonificados = []

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM fechamentos_diarios WHERE data = ?", (data_fechamento,))
        if cursor.fetchone() is not None:
            return False, traders_bonificados

        cursor.execute(
            """
            SELECT DISTINCT h.discord_id, t.nome, t.selecao FROM historico_sinais h
            JOIN traders t ON t.discord_id = h.discord_id
            WHERE h.tipo_hashtag = ? AND DATE(h.timestamp, 'localtime') = DATE('now', 'localtime')
            """,
            (HASHTAG_SINAL,),
        )
        traders_com_sinal = cursor.fetchall()

        for discord_id, nome, selecao in traders_com_sinal:
            cursor.execute(
                """
                SELECT COUNT(*) FROM historico_sinais
                WHERE discord_id = ? AND tipo_hashtag = '#SL' AND DATE(timestamp, 'localtime') = DATE('now', 'localtime')
                """,
                (discord_id,),
            )
            total_sl_hoje = cursor.fetchone()[0]
            if total_sl_hoje == 0:
                cursor.execute("UPDATE ranking SET pontos = pontos + ? WHERE selecao = ?", (BONUS_DIA_PERFEITO, selecao))
                traders_bonificados.append((nome, selecao))

        cursor.execute("INSERT INTO fechamentos_diarios (data) VALUES (?)", (data_fechamento,))
        conn.commit()

    return True, traders_bonificados


def buscar_ranking() -> list[tuple[str, int, str]]:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        for _, _, selecao in PARTICIPANTES_OFICIAIS:
            cursor.execute("INSERT OR IGNORE INTO ranking (selecao, pontos) VALUES (?, 0)", (selecao,))
        conn.commit()
        cursor.execute(
            """
            SELECT r.selecao, r.pontos,
                COALESCE(
                    (SELECT t.nome FROM traders t WHERE t.selecao = r.selecao AND t.discord_id NOT LIKE 'id_%' LIMIT 1),
                    (SELECT t.nome FROM traders t WHERE t.selecao = r.selecao LIMIT 1),
                    'Sem Trader'
                ) AS nome_trader
            FROM ranking r ORDER BY r.pontos DESC, r.selecao ASC
            """
        )
        return cursor.fetchall()


def criar_embed_ranking() -> discord.Embed:
    ranking = buscar_ranking()
    agora = datetime.datetime.now(TIMEZONE_CAMPEONATO)
    embed = discord.Embed(title="🏆 CLASSIFICAÇÃO OFICIAL - FABÚ TRADER WORLD CUP", color=discord.Color.gold(), timestamp=agora)

    if ranking:
        linhas = [
            f"**{posicao}.** 🌍 {BANDEIRAS_SELECOES.get(selecao, '🏳️')} {selecao} - Trader: **{nome_trader}** | Pontos: **{pontos}**"
            for posicao, (selecao, pontos, nome_trader) in enumerate(ranking, start=1)
        ]
        embed.description = "\n".join(linhas)
    else:
        embed.description = "Nenhuma seleção pontuou ainda."

    embed.set_footer(text="FABÚ Trader World Cup 2026")
    return embed


def encontrar_canal_por_nome(nome_canal: str) -> discord.TextChannel | None:
    for canal in bot.get_all_channels():
        if isinstance(canal, discord.TextChannel) and canal.name == nome_canal:
            return canal
    return None


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Bot conectado como {bot.user}")
    if not fechamento_diario.is_running():
        fechamento_diario.start()
    if not anuncio_escala_diaria.is_running():
        anuncio_escala_diaria.start()


@tasks.loop(time=datetime.time(hour=5, minute=0, tzinfo=TIMEZONE_CAMPEONATO))
async def anuncio_escala_diaria() -> None:
    """Anuncia de forma automatica os dois traders do dia no canal worldcup-anuncios."""
    data_hoje = data_hoje_campeonato()
    
    if data_hoje not in CALENDARIO_OFICIAL:
        return  # Nao posta nada se for fim de semana ou fora do calendario

    selecoes = CALENDARIO_OFICIAL[data_hoje]
    s1, s2 = selecoes[0], selecoes[1]
    
    t1 = buscar_nome_trader_por_selecao(s1)
    t2 = buscar_nome_trader_por_selecao(s2)
    
    b1 = BANDEIRAS_SELECOES.get(s1, "🏳️")
    b2 = BANDEIRAS_SELECOES.get(s2, "🏳️")

    canal_anuncios = encontrar_canal_por_nome(CANAL_ANUNCIOS)
    if canal_anuncios is not None:
        embed = discord.Embed(
            title="⚔️ CONFRONTOS DO DIA — FABÚ TRADER WORLD CUP",
            description=f"O mercado já está aberto e as ordens prontas! Conheça as seleções escaladas para buscar o topo do ranking hoje:\n\n"
                        f"{b1} **{s1}** — Trader Oficial: **{t1}**\n"
                        f"🤝 **VS**\n"
                        f"{b2} **{s2}** — Trader Oficial: **{t2}**\n\n"
                        f"⚠️ *Nota: Apenas os sinais enviados por estes dois traders hoje serão validados e somados ao placar geral.*",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(TIMEZONE_CAMPEONATO)
        )
        embed.set_footer(text="Foco, disciplina e boa rodada de trading!")
        await canal_anuncios.send(embed=embed)


@tasks.loop(time=datetime.time(hour=23, minute=59, tzinfo=TIMEZONE_CAMPEONATO))
async def fechamento_diario() -> None:
    aplicado, traders_bonificados = fechar_dia_no_banco()
    if aplicado:
        canal_resultados = encontrar_canal_por_nome(CANAL_RESULTADOS)
        if canal_resultados is not None:
            await canal_resultados.send("✅ Fechamento diário concluído automaticamente.")
            await canal_resultados.send(embed=criar_embed_ranking())


@bot.command(name="ranking")
async def ranking(ctx: commands.Context) -> None:
    await ctx.send(embed=criar_embed_ranking())


@bot.command(name="anunciar_hoje")
@commands.has_permissions(administrator=True)
async def anunciar_hoje(ctx: commands.Context) -> None:
    """Comando manual para forcar o anuncio do dia (util para testar ou postar fora do horario)."""
    data_hoje = data_hoje_campeonato()
    if data_hoje not in CALENDARIO_OFICIAL:
        await ctx.send("Não há rodada oficial do campeonato agendada para a data de hoje.")
        return
        
    selecoes = CALENDARIO_OFICIAL[data_hoje]
    s1, s2 = selecoes[0], selecoes[1]
    t1 = buscar_nome_trader_por_selecao(s1)
    t2 = buscar_nome_trader_por_selecao(s2)
    b1 = BANDEIRAS_SELECOES.get(s1, "🏳️")
    b2 = BANDEIRAS_SELECOES.get(s2, "🏳️")

    embed = discord.Embed(
        title="⚔️ CONFRONTOS DO DIA — FABÚ TRADER WORLD CUP",
        description=f"O mercado já está aberto e as ordens prontas! Conheça as seleções escaladas para buscar o topo do ranking hoje:\n\n"
                    f"{b1} **{s1}** — Trader Oficial: **{t1}**\n"
                    f"🤝 **VS**\n"
                    f"{b2} **{s2}** — Trader Oficial: **{t2}**\n\n"
                    f"⚠️ *Nota: Apenas os sinais enviados por estes dois traders hoje serão validados e somados ao placar geral.*",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(TIMEZONE_CAMPEONATO)
    )
    embed.set_footer(text="Foco, disciplina e boa rodada de trading!")
    
    canal_anuncios = encontrar_canal_por_nome(CANAL_ANUNCIOS)
    if canal_anuncios is not None:
        await canal_anuncios.send(embed=embed)
        await ctx.send("✅ Anúncio diário enviado com sucesso no canal `#worldcup-anuncios`!")
    else:
        await ctx.send("❌ Não encontrei o canal `#worldcup-anuncios`.")


@bot.command(name="fechar_dia")
@commands.has_permissions(administrator=True)
async def fechar_dia(ctx: commands.Context) -> None:
    aplicado, traders_bonificados = fechar_dia_no_banco()
    if not aplicado:
        await ctx.send("O fechamento de hoje já foi executado.")
        return

    if traders_bonificados:
        linhas = [f"• {nome} ({selecao}) +{BONUS_DIA_PERFEITO} pts" for nome, selecao in traders_bonificados]
        msg = "✅ Fechamento diário concluído!\n\n**Bônus Dia Perfeito:**\n" + "\n".join(linhas)
    else:
        msg = "✅ Fechamento diário concluído. Nenhum bônus aplicado."

    await ctx.send(msg)
    await ctx.send(embed=criar_embed_ranking())


@bot.command(name="registrar")
@commands.has_permissions(administrator=True)
async def registrar(ctx: commands.Context, *, dados: str = "") -> None:
    del dados
    linhas = extrair_linhas_registro(ctx)
    registrados = []

    for linha in linhas:
        match = re.match(r"^<@!?(\d+)>\s+(.+)$", linha)
        if match is None:
            continue
        discord_id, dados_trader = match.groups()
        trader = extrair_nome_e_selecao(dados_trader)
        if trader is None:
            continue
        nome, selecao = trader
        cadastrar_trader(discord_id, nome, selecao)
        registrados.append((discord_id, nome, selecao))

    if registrados:
        linhas_sucesso = [f"• <@{uid}> — **{n}** / **{s}**" for uid, n, s in registrados]
        await ctx.send("✅ Traders vinculados com sucesso:\n" + "\n".join(linhas_sucesso))


@bot.command(name="setup_campeonato")
@commands.has_permissions(administrator=True)
async def setup_campeonato(ctx: commands.Context) -> None:
    popular_campeonato_oficial()
    await ctx.send("✅ Campeonato reiniciado! Placar zerado com as 19 seleções oficiais do cartaz.")


async def processar_sinal(message: discord.Message) -> None:
    discord_id = str(message.author.id)
    trader = buscar_trader(discord_id)

    if trader is None:
        await message.reply("Você não está cadastrado como trader oficial do campeonato.")
        return

    nome_trader, selecao = trader
    data_hoje = data_hoje_campeonato()

    if data_hoje not in CALENDARIO_OFICIAL:
        await message.reply("❌ O mercado está fechado ou não há rodada oficial do campeonato hoje!")
        return

    selecoes_permitidas_hoje = CALENDARIO_OFICIAL[data_hoje]

    if selecao not in selecoes_permitidas_hoje:
        s1, s2 = selecoes_permitidas_hoje
        await message.reply(
            f"❌ **Acesso Negado!** Hoje é dia de confronto apenas para: **{s1}** e **{s2}**.\n"
            f"Sua seleção (**{selecao}**) está fora da rodada de hoje e o sinal foi descartado."
        )
        return

    if contar_sinais_hoje(discord_id) < LIMITE_SINAIS_DIARIOS:
        registrar_sinal(discord_id, selecao)
        await message.add_reaction("✅")
    else:
        await message.reply("❌ Você já atingiu o limite máximo de 5 sinais para o dia de hoje!")


async def processar_resultado(message: discord.Message, tipo_hashtag: str) -> None:
    discord_id = str(message.author.id)
    trader = buscar_trader(discord_id)
    if trader is None:
        return

    _, selecao = trader
    bonus_aplicados = registrar_resultado(discord_id, selecao, tipo_hashtag)
    await message.add_reaction(EMOJIS_RESULTADOS[tipo_hashtag])

    if "hat_trick" in bonus_aplicados:
        await message.channel.send(f"🏆 **Hat-Trick!** {message.author.mention} fez 3 TPs hoje! (+15 pts para {selecao})")
    if "tp_seguidos" in bonus_aplicados:
        await message.channel.send(f"🔥 **Sequência Imparável!** 3 TPs seguidos para {message.author.mention}! (+10 pts para {selecao})")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return
    nome_canal = getattr(message.channel, "name", None)
    contem_sinal = HASHTAG_SINAL in message.content
    hashtag_resultado = identificar_hashtag_resultado(message.content)

    if (nome_canal == CANAL_SINAIS or contem_sinal) and contem_sinal:
        await processar_sinal(message)
        return
    if (nome_canal == CANAL_RESULTADOS or hashtag_resultado) and hashtag_resultado:
        await processar_resultado(message, hashtag_resultado)
        return
    await bot.process_commands(message)

@bot.command(name="desempenho")
async def desempenho(ctx: commands.Context) -> None:
    """Exibe uma tabela detalhada com as estatísticas de trades de cada seleção/trader."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        # Consulta ultra blindada: conta o histórico de forma isolada para nunca zerar as linhas da tabela
        cursor.execute(
            """
            SELECT 
                r.selecao,
                COALESCE(
                    (SELECT t.nome FROM traders t WHERE t.selecao = r.selecao AND t.discord_id NOT LIKE 'id_%' LIMIT 1),
                    (SELECT t.nome FROM traders t WHERE t.selecao = r.selecao LIMIT 1),
                    'Sem Trader'
                ) AS nome_trader,
                (
                    SELECT COUNT(*) FROM historico_sinais h 
                    JOIN traders t2 ON t2.discord_id = h.discord_id 
                    WHERE t2.selecao = r.selecao AND h.tipo_hashtag = '#Sinal'
                ) as qtd_sinais,
                (
                    SELECT COUNT(*) FROM historico_sinais h 
                    JOIN traders t2 ON t2.discord_id = h.discord_id 
                    WHERE t2.selecao = r.selecao AND h.tipo_hashtag = '#TP'
                ) as qtd_tp,
                (
                    SELECT COUNT(*) FROM historico_sinais h 
                    JOIN traders t2 ON t2.discord_id = h.discord_id 
                    WHERE t2.selecao = r.selecao AND h.tipo_hashtag = '#BE'
                ) as qtd_be,
                (
                    SELECT COUNT(*) FROM historico_sinais h 
                    JOIN traders t2 ON t2.discord_id = h.discord_id 
                    WHERE t2.selecao = r.selecao AND h.tipo_hashtag = '#SL'
                ) as qtd_sl,
                r.pontos
            FROM ranking r
            ORDER BY r.pontos DESC, r.selecao ASC
            """
        )
        dados = cursor.fetchall()

    if not dados:
        await ctx.send("Nenhum dado de desempenho encontrado no ranking.")
        return

    # Montagem da tabela em formato de texto alinhado (Code Block do Discord)
    # Largura das colunas: Seleção (14), Trader (16), Sinais (5), TP (3), BE (3), SL (3), Pts (4)
    topo = f"{'Seleção':<14} | {'Trader':<16} | {'Sinal':<5} | {'TP':<3} | {'BE':<3} | {'SL':<3} | {'Pts':<4}"
    divisor = "-" * len(topo)
    
    linhas_tabela = [topo, divisor]
    
    for selecao, trader, sinais, tp, be, sl, pontos in dados:
        sel_trunc = selecao[:14]
        trader_trunc = trader[:16]
        
        linha = f"{sel_trunc:<14} | {trader_trunc:<16} | {sinais:<5} | {tp:<3} | {be:<3} | {sl:<3} | {pontos:<4}"
        linhas_tabela.append(linha)

    conteudo_tabela = "\n".join(linhas_tabela)
    
    await ctx.send(
        f"📊 **PAINEL DE ESTATÍSTICAS — FABÚ TRADER WORLD CUP**\n"
        f"```text\n{conteudo_tabela}\n```"
    )

if __name__ == "__main__":
    inicializar_banco()
    if not TOKEN:
        raise RuntimeError("Defina a variável DISCORD_TOKEN.")
    bot.run(TOKEN)
