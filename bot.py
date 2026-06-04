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
    ("id_El_Tubarao", "El Tubarão", "Colômbia"),
]


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / DATABASE_NAME


def conectar_banco() -> sqlite3.Connection:
    """Cria a conexao com o banco SQLite do campeonato."""
    return sqlite3.connect(DATABASE_PATH)


def criar_tabelas() -> None:
    """Cria as tabelas principais caso ainda nao existam."""
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


def popular_dados_oficiais() -> None:
    """
    Popula traders e ranking com dados iniciais.

    Troque os valores de discord_id pelos IDs reais dos membros no Discord
    quando a lista oficial estiver pronta.
    """
    traders_oficiais = [
        ("jack_lourenzo_discord_id", "Jack Lourenzo", "Brasil"),
        ("xitos_discord_id", "Xitos", "Portugal"),
        ("jailson_discord_id", "jailson.", "Argentina"),
    ]

    selecoes = {(selecao,) for _, _, selecao in traders_oficiais}

    with conectar_banco() as conn:
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT OR IGNORE INTO traders (discord_id, nome, selecao)
            VALUES (?, ?, ?)
            """,
            traders_oficiais,
        )

        cursor.executemany(
            """
            INSERT OR IGNORE INTO ranking (selecao)
            VALUES (?)
            """,
            selecoes,
        )

        conn.commit()


def popular_campeonato_oficial() -> None:
    """Popula o banco com a lista oficial da Fabú Trader World Cup."""
    selecoes = {(selecao,) for _, _, selecao in PARTICIPANTES_OFICIAIS}

    with conectar_banco() as conn:
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT OR IGNORE INTO traders (discord_id, nome, selecao)
            VALUES (?, ?, ?)
            """,
            PARTICIPANTES_OFICIAIS,
        )

        cursor.executemany(
            """
            INSERT OR IGNORE INTO ranking (selecao)
            VALUES (?)
            """,
            selecoes,
        )

        conn.commit()


def inicializar_banco() -> None:
    """Prepara o banco local antes de iniciar o bot."""
    criar_tabelas()
    popular_dados_oficiais()


def buscar_trader(discord_id: str) -> tuple[str, str] | None:
    """Retorna nome e selecao do trader oficial, caso exista."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT nome, selecao
            FROM traders
            WHERE discord_id = ?
            """,
            (discord_id,),
        )
        return cursor.fetchone()


def contar_hashtag_hoje(discord_id: str, tipo_hashtag: str) -> int:
    """Conta quantos registros de uma hashtag o trader acumulou hoje."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM historico_sinais
            WHERE discord_id = ?
              AND tipo_hashtag = ?
              AND DATE(timestamp) = DATE('now')
            """,
            (discord_id, tipo_hashtag),
        )
        return cursor.fetchone()[0]


def contar_sinais_hoje(discord_id: str) -> int:
    """Conta quantos sinais validos o trader enviou na data atual."""
    return contar_hashtag_hoje(discord_id, HASHTAG_SINAL)


def registrar_sinal(discord_id: str, selecao: str) -> None:
    """Registra o sinal recebido e soma um ponto para a selecao."""
    with conectar_banco() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO historico_sinais (discord_id, tipo_hashtag)
            VALUES (?, ?)
            """,
            (discord_id, HASHTAG_SINAL),
        )

        cursor.execute(
            """
            UPDATE ranking
            SET pontos = pontos + 1
            WHERE selecao = ?
            """,
            (selecao,),
        )

        conn.commit()


def identificar_hashtag_resultado(conteudo: str) -> str | None:
    """Retorna a primeira hashtag de resultado encontrada na mensagem."""
    for hashtag in PONTOS_RESULTADOS:
        if hashtag in conteudo:
            return hashtag

    return None


def registrar_resultado(discord_id: str, selecao: str, tipo_hashtag: str) -> list[str]:
    """Registra um resultado, atualiza o ranking e retorna bonus aplicados."""
    bonus_aplicados = []
    pontos = PONTOS_RESULTADOS[tipo_hashtag]

    with conectar_banco() as conn:
        cursor = conn.cursor()

        if tipo_hashtag == "#TP":
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM historico_sinais
                WHERE discord_id = ?
                  AND tipo_hashtag = '#TP'
                  AND DATE(timestamp) = DATE('now')
                """,
                (discord_id,),
            )
            total_tp_hoje = cursor.fetchone()[0]

            if total_tp_hoje + 1 == 3:
                pontos += BONUS_HAT_TRICK
                bonus_aplicados.append("hat_trick")

            cursor.execute(
                """
                SELECT tipo_hashtag
                FROM historico_sinais
                WHERE discord_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 2
                """,
                (discord_id,),
            )
            ultimos_registros = [row[0] for row in cursor.fetchall()]

            if ultimos_registros == ["#TP", "#TP"]:
                pontos += BONUS_TP_SEGUIDOS
                bonus_aplicados.append("tp_seguidos")

        cursor.execute(
            """
            INSERT INTO historico_sinais (discord_id, tipo_hashtag)
            VALUES (?, ?)
            """,
            (discord_id, tipo_hashtag),
        )

        cursor.execute(
            """
            UPDATE ranking
            SET pontos = pontos + ?
            WHERE selecao = ?
            """,
            (pontos, selecao),
        )

        conn.commit()

    return bonus_aplicados


def cadastrar_trader(discord_id: str, nome: str, selecao: str) -> None:
    """Cadastra ou atualiza um trader oficial e garante a selecao no ranking."""
    with conectar_banco() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO traders (discord_id, nome, selecao)
            VALUES (?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                nome = excluded.nome,
                selecao = excluded.selecao
            """,
            (discord_id, nome, selecao),
        )

        cursor.execute(
            """
            INSERT OR IGNORE INTO ranking (selecao)
            VALUES (?)
            """,
            (selecao,),
        )

        conn.commit()


def buscar_selecoes_cadastradas() -> set[str]:
    """Retorna selecoes ja conhecidas pelo ranking e pela lista oficial."""
    selecoes = {selecao for _, _, selecao in PARTICIPANTES_OFICIAIS}

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT selecao FROM ranking")
        selecoes.update(row[0] for row in cursor.fetchall())

    return selecoes


def extrair_nome_e_selecao(texto: str) -> tuple[str, str] | None:
    """Separa nome e selecao, priorizando selecoes conhecidas com nomes compostos."""
    texto = texto.strip()

    for selecao in sorted(buscar_selecoes_cadastradas(), key=len, reverse=True):
        if texto.casefold().endswith(selecao.casefold()):
            nome = texto[: -len(selecao)].strip()
            if nome:
                return nome, selecao

    partes = texto.rsplit(" ", 1)
    if len(partes) != 2:
        return None

    nome, selecao = (parte.strip() for parte in partes)
    if not nome or not selecao:
        return None

    return nome, selecao


def extrair_linhas_registro(ctx: commands.Context) -> list[str]:
    """Extrai as linhas de cadastro removendo o comando da primeira linha."""
    linhas = ctx.message.content.split("\n")
    primeira_linha = linhas[0]
    comando = ctx.invoked_with or "registrar"
    prefixo = str(ctx.prefix or "")
    chamada = f"{prefixo}{comando}"

    if primeira_linha.startswith(chamada):
        primeira_linha = primeira_linha[len(chamada) :].strip()

    linhas[0] = primeira_linha
    return [linha.strip() for linha in linhas if linha.strip()]


def data_hoje_campeonato() -> str:
    """Retorna a data atual no fuso horario oficial do campeonato."""
    return datetime.datetime.now(TIMEZONE_CAMPEONATO).date().isoformat()


def fechar_dia_no_banco() -> tuple[bool, list[tuple[str, str]]]:
    """Aplica o bonus Dia Perfeito uma unica vez por dia."""
    data_fechamento = data_hoje_campeonato()
    traders_bonificados = []

    with conectar_banco() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM fechamentos_diarios
            WHERE data = ?
            """,
            (data_fechamento,),
        )
        if cursor.fetchone() is not None:
            return False, traders_bonificados

        cursor.execute(
            """
            SELECT DISTINCT h.discord_id, t.nome, t.selecao
            FROM historico_sinais h
            JOIN traders t ON t.discord_id = h.discord_id
            WHERE h.tipo_hashtag = ?
              AND DATE(h.timestamp) = DATE('now')
            """,
            (HASHTAG_SINAL,),
        )
        traders_com_sinal = cursor.fetchall()

        for discord_id, nome, selecao in traders_com_sinal:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM historico_sinais
                WHERE discord_id = ?
                  AND tipo_hashtag = '#SL'
                  AND DATE(timestamp) = DATE('now')
                """,
                (discord_id,),
            )
            total_sl_hoje = cursor.fetchone()[0]

            if total_sl_hoje == 0:
                cursor.execute(
                    """
                    UPDATE ranking
                    SET pontos = pontos + ?
                    WHERE selecao = ?
                    """,
                    (BONUS_DIA_PERFEITO, selecao),
                )
                traders_bonificados.append((nome, selecao))

        cursor.execute(
            """
            INSERT INTO fechamentos_diarios (data)
            VALUES (?)
            """,
            (data_fechamento,),
        )

        conn.commit()

    return True, traders_bonificados


def buscar_ranking() -> list[tuple[str, int]]:
    """Busca a classificacao atual ordenada por pontuacao."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT selecao, pontos
            FROM ranking
            ORDER BY pontos DESC, selecao ASC
            """
        )
        return cursor.fetchall()


def criar_embed_ranking() -> discord.Embed:
    """Monta o embed oficial da classificacao."""
    ranking = buscar_ranking()
    agora = datetime.datetime.now(TIMEZONE_CAMPEONATO)

    embed = discord.Embed(
        title="🏆 CLASSIFICAÇÃO ATUALIZADA - FABÚ TRADER WORLD CUP",
        color=discord.Color.gold(),
        timestamp=agora,
    )

    if ranking:
        linhas = [
            f"**{posicao}. {selecao}** — `{pontos}` pontos"
            for posicao, (selecao, pontos) in enumerate(ranking, start=1)
        ]
        embed.description = "\n".join(linhas)
    else:
        embed.description = "Nenhuma seleção pontuou ainda."

    if agora.weekday() == 4:
        embed.add_field(
            name="⭐ Melhor Trader da Semana",
            value="Sexta-feira é dia de anúncio oficial do Melhor Trader da Semana!",
            inline=False,
        )

    embed.set_footer(text="FABÚ Trader World Cup • Início oficial: 08/06/2026")
    return embed


def encontrar_canal_por_nome(nome_canal: str) -> discord.TextChannel | None:
    """Busca o primeiro canal de texto com o nome informado."""
    for canal in bot.get_all_channels():
        if isinstance(canal, discord.TextChannel) and canal.name == nome_canal:
            return canal

    return None


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Bot conectado como {bot.user} (ID: {bot.user.id})")
    if not fechamento_diario.is_running():
        fechamento_diario.start()


@tasks.loop(
    time=datetime.time(hour=23, minute=59, tzinfo=TIMEZONE_CAMPEONATO),
)
async def fechamento_diario() -> None:
    """Executa o fechamento diario automatico as 23:59."""
    aplicado, traders_bonificados = fechar_dia_no_banco()

    if aplicado:
        print(
            "Fechamento diario executado. "
            f"Traders com Dia Perfeito: {len(traders_bonificados)}."
        )
        canal_resultados = encontrar_canal_por_nome(CANAL_RESULTADOS)

        if canal_resultados is not None:
            await canal_resultados.send("✅ Fechamento diario concluido automaticamente.")
            await canal_resultados.send(embed=criar_embed_ranking())


@fechamento_diario.before_loop
async def aguardar_bot_pronto() -> None:
    await bot.wait_until_ready()


@bot.command(name="ranking")
async def ranking(ctx: commands.Context) -> None:
    """Mostra a classificacao atual do campeonato."""
    await ctx.send(embed=criar_embed_ranking())


@bot.command(name="fechar_dia")
@commands.has_permissions(administrator=True)
async def fechar_dia(ctx: commands.Context) -> None:
    """Executa o fechamento diario manualmente para testes ou operacao."""
    aplicado, traders_bonificados = fechar_dia_no_banco()

    if not aplicado:
        await ctx.send("O fechamento de hoje ja foi executado.")
        await ctx.send(embed=criar_embed_ranking())
        return

    if traders_bonificados:
        linhas = [
            f"• {nome} ({selecao}) recebeu +{BONUS_DIA_PERFEITO} pontos"
            for nome, selecao in traders_bonificados
        ]
        mensagem = "✅ Fechamento diario concluido!\n\n**Bonus Dia Perfeito:**\n" + "\n".join(linhas)
    else:
        mensagem = "✅ Fechamento diario concluido. Nenhum bonus Dia Perfeito aplicado hoje."

    await ctx.send(mensagem)
    await ctx.send(embed=criar_embed_ranking())


@bot.command(name="registrar")
@commands.has_permissions(administrator=True)
async def registrar(ctx: commands.Context, *, dados: str = "") -> None:
    """
    Cadastra um ou varios traders oficiais.

    Uso:
    !registrar @usuario Nome Selecao

    Ou:
    !registrar
    @usuario Nome Selecao
    @usuario2 Outro Nome Outra Selecao
    """
    del dados

    linhas = extrair_linhas_registro(ctx)
    registrados = []
    falhas = []

    if not linhas:
        await ctx.send("Use: `!registrar @usuario Nome Selecao` ou envie uma lista com uma linha por trader.")
        return

    for linha in linhas:
        match = re.match(r"^<@!?(\d+)>\s+(.+)$", linha)

        if match is None:
            falhas.append(f"`{linha}`")
            continue

        discord_id, dados_trader = match.groups()
        trader = extrair_nome_e_selecao(dados_trader)

        if trader is None:
            falhas.append(f"`{linha}`")
            continue

        nome, selecao = trader
        cadastrar_trader(discord_id, nome, selecao)
        registrados.append((discord_id, nome, selecao))

    if not registrados:
        await ctx.send(
            "Nenhum trader foi registrado. Use o formato: `@Membro Nome Do Trader País`."
        )
        return

    linhas_sucesso = [
        f"• <@{discord_id}> — **{nome}** / **{selecao}**"
        for discord_id, nome, selecao in registrados
    ]
    resposta = "✅ Traders registrados com sucesso:\n" + "\n".join(linhas_sucesso)

    if falhas:
        resposta += "\n\n⚠️ Linhas ignoradas por formato inválido:\n" + "\n".join(falhas)

    await ctx.send(resposta)


@bot.command(name="setup_campeonato")
@commands.has_permissions(administrator=True)
async def setup_campeonato(ctx: commands.Context) -> None:
    """Popula o banco com os traders e selecoes oficiais do campeonato."""
    popular_campeonato_oficial()
    await ctx.send("✅ Banco de dados oficial populado com as seleções do campeonato!")


@fechar_dia.error
@registrar.error
@setup_campeonato.error
async def comando_admin_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Mensagem amigavel para erros comuns dos comandos administrativos."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Apenas administradores podem usar este comando.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("Nao consegui identificar o usuario. Use uma mencao valida, por exemplo: `@usuario`.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Formato invalido. Use: `!registrar @usuario Nome Selecao`")
        return

    raise error


async def processar_sinal(message: discord.Message) -> None:
    """Valida e registra um sinal enviado por trader oficial."""
    discord_id = str(message.author.id)
    trader = buscar_trader(discord_id)

    if trader is None:
        await message.reply("Voce nao esta cadastrado como trader oficial do campeonato.")
        return

    _, selecao = trader
    total_sinais_hoje = contar_sinais_hoje(discord_id)

    if total_sinais_hoje < LIMITE_SINAIS_DIARIOS:
        registrar_sinal(discord_id, selecao)
        await message.add_reaction("✅")
    else:
        await message.reply("❌ Você já atingiu o limite máximo de 5 sinais para o dia de hoje!")


async def processar_resultado(message: discord.Message, tipo_hashtag: str) -> None:
    """Valida e registra resultados de TP, BE ou SL."""
    discord_id = str(message.author.id)
    trader = buscar_trader(discord_id)

    if trader is None:
        return

    _, selecao = trader
    bonus_aplicados = registrar_resultado(discord_id, selecao, tipo_hashtag)

    await message.add_reaction(EMOJIS_RESULTADOS[tipo_hashtag])

    if "hat_trick" in bonus_aplicados:
        await message.channel.send(
            f"🏆 Hat-Trick! {message.author.mention} conquistou 3 TPs hoje e garantiu "
            f"+{BONUS_HAT_TRICK} pontos extras para {selecao}!"
        )

    if "tp_seguidos" in bonus_aplicados:
        await message.channel.send(
            f"🔥 3 TP Seguidos! {message.author.mention} emplacou uma sequência perfeita e "
            f"somou +{BONUS_TP_SEGUIDOS} pontos extras para {selecao}!"
        )


@bot.event
async def on_message(message: discord.Message) -> None:
    """Monitora sinais e resultados oficiais enviados no campeonato."""
    if message.author == bot.user:
        return

    nome_canal = getattr(message.channel, "name", None)
    contem_sinal = HASHTAG_SINAL in message.content
    hashtag_resultado = identificar_hashtag_resultado(message.content)

    if (nome_canal == CANAL_SINAIS or contem_sinal) and contem_sinal:
        await processar_sinal(message)
        await bot.process_commands(message)
        return

    if (nome_canal == CANAL_RESULTADOS or hashtag_resultado) and hashtag_resultado:
        await processar_resultado(message, hashtag_resultado)
        await bot.process_commands(message)
        return

    await bot.process_commands(message)


if __name__ == "__main__":
    inicializar_banco()

    if not TOKEN:
        raise RuntimeError("Defina a variavel de ambiente DISCORD_TOKEN antes de iniciar o bot.")

    bot.run(TOKEN)
