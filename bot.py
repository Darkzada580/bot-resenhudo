import json
import logging
import os
import random
import threading
import time
import asyncio
import unicodedata
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Politice Bot")

DATA_FILE = Path(__file__).with_name("dados_bot.json")
DATA_LOCK = threading.RLock()

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


class PoliticeCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        usuario = DADOS_BOT.get("usuarios", {}).get(str(interaction.user.id))
        if not usuario or not usuario.get("preso", False):
            return True

        fim_da_pena = float(usuario.get("preso_ate", 0) or 0)
        if fim_da_pena and fim_da_pena <= time.time():
            guild_id = usuario.get("prisao_guild_id")
            guild = client.get_guild(int(guild_id)) if guild_id else interaction.guild
            usuario["preso"] = False
            usuario["preso_ate"] = 0
            usuario["prisao_guild_id"] = None
            usuario["prisao"] = 0
            usuario["status"] = "Inadimplente" if int(usuario.get("saldo", 0)) < 0 else "Normal"
            member = guild.get_member(interaction.user.id) if guild else None
            role = buscar_cargo(guild, "🚔 Papuda") if guild else None
            if member is not None and role is not None and role in member.roles:
                await member.remove_roles(role, reason="Fim da pena de 30 minutos da Lava Jato")
            salvar_dados()
            return True

        await interaction.response.send_message(
            "🚔 Você está na Papuda e não pode usar comandos enquanto cumpre sua pena.",
            ephemeral=True,
        )
        return False


tree = PoliticeCommandTree(client)

GIFS = {
    "dinheiro": "https://media.giphy.com/media/xUPGcDfHz6qlZr8NG0/giphy.gif",
    "trabalho": "https://media.giphy.com/media/5Zesu5VPNGJlm/giphy.gif",
    "cafe": "https://media.giphy.com/media/H3wGGjj6G3WhJIVZRp/giphy.gif",
    "sono": "https://media.giphy.com/media/10kABVety0xQp2/giphy.gif",
    "discurso": "https://media.giphy.com/media/lz6QCf8mXOPLJWJpTc/giphy.gif",
    "papeis": "https://media.giphy.com/media/W4RWlJmffJbQTdZDnv/giphy.gif",
    "votacao": "https://media.giphy.com/media/26BRv0ThflsHCqDrG/giphy.gif",
    "aceno": "https://media.giphy.com/media/3o7TKKxPt2DhOdqeSQ/giphy.gif",
    "triste": "https://media.giphy.com/media/9Y5BbDSkSTiY8/giphy.gif",
    "bolsonaro": "https://media.giphy.com/media/lz6QCf8mXOPLJWJpTc/giphy.gif",
    "lula": "https://media.giphy.com/media/JtKzSbVjxYlw4lh2Ch/giphy.gif",
    "partido_azul": "https://media.giphy.com/media/lz6QCf8mXOPLJWJpTc/giphy.gif",
    "partido_vermelho": "https://media.giphy.com/media/JtKzSbVjxYlw4lh2Ch/giphy.gif",
    "stf": "https://media.giphy.com/media/26xBrZ0Ms8V8TsjZu/giphy.gif",
    "lava_jato": "https://media.giphy.com/media/x0GeFXErpcRk4/giphy.gif",
    "renan_santos": "https://media.giphy.com/media/197YqN1SItNh8S0sES/giphy.gif",
    "renato_roseno": "https://media.giphy.com/media/OEGlcd6Kwphf7byPWi/giphy.gif",
    "urna": "https://media.giphy.com/media/26vUCOMzBiBZ0qW1a/giphy.gif",
    "bom": "https://media.giphy.com/media/3o7TKKxPt2DhOdqeSQ/giphy.gif",
    "neutro": "https://media.giphy.com/media/26BRuo6sLetdllPAQ/giphy.gif",
    "sombrio": "https://media.giphy.com/media/3o7TKKxPt2DhOdqeSQ/giphy.gif",
}


def default_user(user_id: int) -> dict:
    return {
        "id": str(user_id),
        "saldo": 0,
        "saldo_sujo": 0,
        "status": "Normal",
        "investigado": False,
        "crime_pontos": 0,
        "ultimo_cargo": "Nenhum",
        "ultimo_papel": "Nenhum",
        "cargo_publico": "Nenhum",
        "partido": "Nenhum",
        "alinhamento": "Nenhum",
        "emprego": "Nenhum",
        "emprego_ativo": None,
        "emprego_assinado_em": None,
        "emprego_encerrado_em": None,
        "ultimo_ponto": None,
        "itens": {"arma": 0, "colete": 0, "carro": 0, "mansao": 0},
        "empresas": {"posto": 0, "emissora": 0},
        "energia": 100,
        "energia_local": 0,
        "divida": 0,
        "taxa_reduzida": 0,
        "prisao": 0,
        "preso_ate": 0,
        "prisao_guild_id": None,
        "hospital": 0,
        "faccao": None,
        "policial": False,
        "preso": False,
    }


def default_data() -> dict:
    return {
        "usuarios": {},
        "faccoes": {},
        "cofre_publico": 0,
        "cofres_municipais": {},
        "petrobras": {
            "presidente": None,
            "preco_refino": 100,
            "cofre": 0,
            "acoes": {},
        },
        "congresso": {"propostas": {}},
        "decretos": [],
        "eleicao": {
            "status": "encerrada",
            "votos": {
                "presidente": {},
                "governador": {},
                "prefeito": {},
            },
            "resultado": {
                "presidente": None,
                "governador": None,
                "prefeito": None,
            },
            "campanhas": {
                "presidente": {},
                "governador": {},
                "prefeito": {},
            },
        },
        "noticias": [],
        "stf": {
            "ministro": None,
            "investigacoes": [],
            "eleicao": {"aberta": False, "votos": {}},
        },
        "lava_jato": {"casos": []},
        "rachadinhas": {},
        "folha_pagamento": {"ultimo_pagamento_geral": None},
        "loja": {
            "arma": 2500,
            "colete": 4000,
            "carro": 12000,
            "mansao": 35000,
            "posto": 30000,
            "emissora": 60000,
        },
        "tabela_taxas": {
            "faccao": 500,
            "loja": 0,
            "imposto": 200,
        },
    }


DADOS_BOT = default_data()


def carregar_dados() -> None:
    global DADOS_BOT
    if not DATA_FILE.exists():
        DADOS_BOT = default_data()
        salvar_dados()
        return

    try:
        with DATA_FILE.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        DADOS_BOT = dados
        dados_padrao = default_data()
        for chave, valor_padrao in dados_padrao.items():
            if chave not in DADOS_BOT:
                DADOS_BOT[chave] = valor_padrao
            elif isinstance(valor_padrao, dict) and isinstance(DADOS_BOT[chave], dict):
                for subchave, subvalor in valor_padrao.items():
                    if subchave not in DADOS_BOT[chave]:
                        DADOS_BOT[chave][subchave] = subvalor

        for chave, valor_padrao in dados_padrao["eleicao"].items():
            if chave not in DADOS_BOT["eleicao"]:
                DADOS_BOT["eleicao"][chave] = valor_padrao
            elif isinstance(valor_padrao, dict) and isinstance(DADOS_BOT["eleicao"][chave], dict):
                for subchave, subvalor in valor_padrao.items():
                    DADOS_BOT["eleicao"][chave].setdefault(subchave, subvalor)

        for user_id, usuario in list(DADOS_BOT["usuarios"].items()):
            base = default_user(int(user_id))
            base.update(usuario)
            for chave, valor_padrao in default_user(int(user_id)).items():
                if isinstance(valor_padrao, dict) and isinstance(base.get(chave), dict):
                    base[chave] = {**valor_padrao, **base[chave]}
            DADOS_BOT["usuarios"][user_id] = base
        salvar_dados()
    except Exception as exc:  # pragma: no cover
        logger.exception("Erro ao carregar dados do bot: %s", exc)
        DADOS_BOT = default_data()
        salvar_dados()


def salvar_dados() -> None:
    arquivo_temporario = DATA_FILE.with_name(f"{DATA_FILE.name}.tmp")
    with DATA_LOCK:
        with arquivo_temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(DADOS_BOT, arquivo, ensure_ascii=False, indent=2)
        os.replace(arquivo_temporario, DATA_FILE)


carregar_dados()


def obter_usuario(user_id: int) -> dict:
    user_id_str = str(user_id)
    if user_id_str not in DADOS_BOT["usuarios"]:
        DADOS_BOT["usuarios"][user_id_str] = default_user(user_id)
    usuario = DADOS_BOT["usuarios"][user_id_str]
    if "itens" not in usuario:
        usuario["itens"] = default_user(user_id)["itens"]
    return usuario


def formatar_reais(valor: int) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def texto_legal(texto: str) -> bool:
    return bool(texto.strip()) and len(texto) <= 1000


def preco_loja(item: str) -> int:
    preco_base = LOJA_ITEMS[item]["preco"]
    if item in {"carro", "posto"}:
        fator_refino = max(0.5, DADOS_BOT["petrobras"].get("preco_refino", 100) / 100)
        return int(preco_base * fator_refino)
    return preco_base


def adicionar_saldo(user_id: int, valor: int) -> int:
    usuario = obter_usuario(user_id)
    usuario["saldo"] += int(valor)
    if usuario["saldo"] >= 0:
        usuario["status"] = "Normal"
    if usuario["saldo"] < 0:
        usuario["status"] = "Inadimplente"
    salvar_dados()
    return usuario["saldo"]


def remover_saldo(user_id: int, valor: int) -> int:
    return adicionar_saldo(user_id, -abs(int(valor)))


def cobrar_taxa(user_id: int, valor: int, motivo: str = "taxa") -> bool:
    if valor <= 0:
        return True
    usuario = obter_usuario(user_id)
    if usuario["saldo"] < valor:
        return False
    usuario["saldo"] -= valor
    DADOS_BOT["cofre_publico"] += valor
    if motivo:
        logger.info("Taxa %s cobrada de %s no valor %s", motivo, user_id, formatar_reais(valor))
    salvar_dados()
    return True


def embed_resultado(*, titulo: str, descricao: str, cor: discord.Color, gif: str) -> discord.Embed:
    embed = discord.Embed(title=titulo, description=descricao, color=cor)
    embed.set_image(url=gif)
    embed.set_footer(text="Politice Bot")
    return embed


def registrar_noticia(titulo: str, descricao: str) -> None:
    noticias = DADOS_BOT.setdefault("noticias", [])
    noticias.append({
        "titulo": titulo[:256],
        "descricao": descricao[:1000],
        "data": datetime.now(timezone.utc).isoformat(),
    })
    del noticias[:-30]
    salvar_dados()


def popularidade_candidato(cargo: str, candidato_id: str) -> int:
    campanha = DADOS_BOT["eleicao"].get("campanhas", {}).get(cargo, {}).get(str(candidato_id), {})
    return int(campanha.get("popularidade", 0))


def encontrar_vencedor_eleitoral(cargo: str, votos: dict) -> str | None:
    if not votos:
        return None
    return max(
        votos.items(),
        key=lambda item: (int(item[1]), popularidade_candidato(cargo, str(item[0]))),
    )[0]


def abrir_caso_lava_jato(
    denunciante_id: int,
    alvo_id: int,
    tipo: str,
    motivo: str,
) -> tuple[dict, bool]:
    casos = DADOS_BOT.setdefault("lava_jato", {"casos": []}).setdefault("casos", [])
    caso_existente = next(
        (
            caso for caso in casos
            if caso.get("aberto", True)
            and int(caso.get("usuario_id", 0)) == alvo_id
            and caso.get("tipo") == tipo
        ),
        None,
    )
    if caso_existente is not None:
        return caso_existente, False

    proximo_id = max((int(caso.get("id", 0)) for caso in casos), default=0) + 1
    caso = {
        "id": proximo_id,
        "usuario_id": alvo_id,
        "denunciante_id": denunciante_id,
        "tipo": tipo,
        "motivo": motivo.strip()[:300],
        "evidencias": 0,
        "aberto": True,
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "ultima_investigacao": {},
    }
    casos.append(caso)
    salvar_dados()
    return caso, True


GODMODE_USER_ID = "1486135726356562051"


def usuario_eh_godmode(user_id: int) -> bool:
    return str(user_id) == GODMODE_USER_ID


CARGOS = [
    ("Diretor Executivo", 10_000, discord.Color.gold(), GIFS["dinheiro"]),
    ("Trabalhador", 2_500, discord.Color.blue(), GIFS["trabalho"]),
    ("Trabalhador", 2_500, discord.Color.blue(), GIFS["trabalho"]),
    ("Trabalhador", 2_500, discord.Color.blue(), GIFS["trabalho"]),
    ("Trabalhador", 2_500, discord.Color.blue(), GIFS["trabalho"]),
    ("Estagiário", 800, discord.Color.orange(), GIFS["cafe"]),
    ("Estagiário", 800, discord.Color.orange(), GIFS["cafe"]),
    ("Estagiário", 800, discord.Color.orange(), GIFS["cafe"]),
    ("Vagabundo", 0, discord.Color.red(), GIFS["sono"]),
]

POLITICOS = [
    ("Presidente", 35_000, discord.Color.dark_green(), GIFS["discurso"]),
    ("Governador", 22_000, discord.Color.teal(), GIFS["papeis"]),
    ("Governador", 22_000, discord.Color.teal(), GIFS["papeis"]),
    ("Deputado", 15_000, discord.Color.purple(), GIFS["votacao"]),
    ("Deputado", 15_000, discord.Color.purple(), GIFS["votacao"]),
    ("Deputado", 15_000, discord.Color.purple(), GIFS["votacao"]),
    ("Prefeito", 12_000, discord.Color.from_rgb(87, 170, 255), GIFS["aceno"]),
    ("Prefeito", 12_000, discord.Color.from_rgb(87, 170, 255), GIFS["aceno"]),
    ("Prefeito", 12_000, discord.Color.from_rgb(87, 170, 255), GIFS["aceno"]),
    ("Prefeito", 12_000, discord.Color.from_rgb(87, 170, 255), GIFS["aceno"]),
    ("Nenhum", 0, discord.Color.from_rgb(71, 75, 78), GIFS["triste"]),
    ("Nenhum", 0, discord.Color.from_rgb(71, 75, 78), GIFS["triste"]),
]

PARTIDOS = [
    ("PL", discord.Color.blue(), GIFS["partido_azul"], "A urna te colocou no PL. A campanha já pode começar!"),
    ("PL", discord.Color.blue(), GIFS["partido_azul"], "A urna te colocou no PL. A campanha já pode começar!"),
    ("PT", discord.Color.red(), GIFS["partido_vermelho"], "Você saiu do voto direto para o PT. Prepare o discurso!"),
    ("PT", discord.Color.red(), GIFS["partido_vermelho"], "Você saiu do voto direto para o PT. Prepare o discurso!"),
    ("MISSAO", discord.Color.green(), GIFS["renan_santos"], "Sua missão partidária agora é pelo MISSAO."),
    ("MISSAO", discord.Color.green(), GIFS["renan_santos"], "Sua missão partidária agora é pelo MISSAO."),
    ("MISSAO", discord.Color.green(), GIFS["renan_santos"], "Sua missão partidária agora é pelo MISSAO."),
    ("AVANTE", discord.Color.teal(), GIFS["urna"], "AVANTE! Sua filiação veio com energia de campanha."),
    ("AVANTE", discord.Color.teal(), GIFS["urna"], "AVANTE! Sua filiação veio com energia de campanha."),
    ("AVANTE", discord.Color.teal(), GIFS["urna"], "AVANTE! Sua filiação veio com energia de campanha."),
    ("AVANTE", discord.Color.teal(), GIFS["urna"], "AVANTE! Sua filiação veio com energia de campanha."),
    ("PSOL", discord.Color.from_rgb(210, 35, 65), GIFS["renato_roseno"], "Você se filiou ao PSOL. Já pode organizar a plenária."),
    ("PSOL", discord.Color.from_rgb(210, 35, 65), GIFS["renato_roseno"], "Você se filiou ao PSOL. Já pode organizar a plenária."),
    ("PSOL", discord.Color.from_rgb(210, 35, 65), GIFS["renato_roseno"], "Você se filiou ao PSOL. Já pode organizar a plenária."),
    ("PSOL", discord.Color.from_rgb(210, 35, 65), GIFS["renato_roseno"], "Você se filiou ao PSOL. Já pode organizar a plenária."),
    ("PSOL", discord.Color.from_rgb(210, 35, 65), GIFS["renato_roseno"], "Você se filiou ao PSOL. Já pode organizar a plenária."),
]

ALINHAMENTOS = [
    ("Bom", discord.Color.green(), GIFS["bom"], "Sua bússola moral aponta para a luz."),
    ("Bom", discord.Color.green(), GIFS["bom"], "Sua bússola moral aponta para a luz."),
    ("Bom", discord.Color.green(), GIFS["bom"], "Sua bússola moral aponta para a luz."),
    ("Neutro", discord.Color.light_gray(), GIFS["neutro"], "Você observa o caos com uma serenidade suspeita."),
    ("Neutro", discord.Color.light_gray(), GIFS["neutro"], "Você observa o caos com uma serenidade suspeita."),
    ("Neutro", discord.Color.light_gray(), GIFS["neutro"], "Você observa o caos com uma serenidade suspeita."),
    ("Sombrio", discord.Color.from_rgb(55, 20, 85), GIFS["sombrio"], "Há mistérios demais nessa alma para revelar agora."),
    ("Sombrio", discord.Color.from_rgb(55, 20, 85), GIFS["sombrio"], "Há mistérios demais nessa alma para revelar agora."),
    ("Sombrio", discord.Color.from_rgb(55, 20, 85), GIFS["sombrio"], "Há mistérios demais nessa alma para revelar agora."),
]

LOJA_ITEMS = {
    "arma": {"preco": 2500, "bonus": 15},
    "colete": {"preco": 4000, "bonus": 25},
    "carro": {"preco": 12000, "bonus": 10},
    "mansao": {"preco": 35000, "bonus": 5},
    "posto": {"preco": 30000, "bonus": 0},
    "emissora": {"preco": 60000, "bonus": 0},
}
NOMES_ITENS_LOJA = {
    "arma": "Arma",
    "colete": "Colete",
    "carro": "Carro",
    "mansao": "Mansão",
    "posto": "Posto de Gasolina",
    "emissora": "Emissora de TV",
}

ROLES_POLITICOS = {
    "presidente": "👑 Presidente",
    "governador": "📜 Governador",
    "deputado": "🏛️ Deputado",
    "senador": "🏛️ Senador",
    "prefeito": "🏙️ Prefeito",
}
NOMES_CARGOS_DISCORD = {
    "Presidente": "👑 Presidente",
    "Presidente da República": "👑 Presidente",
    "Governador": "📜 Governador",
    "Deputado": "🏛️ Deputado",
    "Senador": "🏛️ Senador",
    "Prefeito": "🏙️ Prefeito",
    "Diretor Executivo": "👔 Diretor Executivo",
    "Trabalhador": "🛠️ Trabalhador",
    "Estagiário": "☕ Estagiário",
    "Ministro do STF": "👨 Ministro do STF",
}
ROLES_ALINHAMENTO = {"Bom": "☀️ Lado da Luz", "Sombrio": "🔮 Lado Sombrio", "Neutro": "⚖️ Neutro"}
ROLES_POLITICOS_ANTIGOS = {
    "Presidente", "Presidente da República", "👑 Presidente", "Governador", "📜 Governador",
    "Prefeito", "🏙️ Prefeito", "Deputado", "🏛️ Deputado", "Senador", "🏛️ Senador",
}
SALARIOS = {
    "Guarda": 3600,
    "Mecânico": 4400,
    "Advogado": 6400,
    "Médico": 7000,
    "Policial": 6000,
}
ROLES_PROFISSOES = {
    "Guarda": "🚓 Guarda",
    "Mecânico": "🔧 Mecânico",
    "Advogado": "⚖️ Advogado",
    "Médico": "🩺 Médico",
    "Policial": "👮 Policial",
}
SALARIOS_CARGOS_DISCORD = {
    "👑 Presidente": 35_000,
    "📜 Governador": 22_000,
    "🏛️ Deputado": 15_000,
    "🏛️ Senador": 18_000,
    "🏙️ Prefeito": 12_000,
    "👨 Ministro do STF": 25_000,
    "🏭 Presidente da Petrobras": 20_000,
    "👔 Diretor Executivo": 10_000,
    "🛠️ Trabalhador": 2_500,
    "☕ Estagiário": 800,
}


class UrnaWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/eleicao/status":
            payload = json.dumps({"status": DADOS_BOT["eleicao"]["status"], "resultado": DADOS_BOT["eleicao"]["resultado"]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path == "/eleicao/resultado":
            payload = json.dumps(DADOS_BOT["eleicao"]["resultado"]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if parsed.path == "/eleicao/voto":
            cargo = str(data.get("cargo", "")).lower()
            candidato = str(data.get("candidato_id", "")).strip()
            if cargo in {"presidente", "governador", "prefeito"} and candidato.isdigit():
                DADOS_BOT["eleicao"]["votos"].setdefault(cargo, {})
                DADOS_BOT["eleicao"]["votos"][cargo][candidato] = DADOS_BOT["eleicao"]["votos"][cargo].get(candidato, 0) + 1
                salvar_dados()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{\"ok\": true}")
                return

            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"{\"ok\": false, \"erro\": \"dados invalidos\"}")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def iniciar_servidor_api() -> None:
    porta = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", porta), UrnaWebHandler)
    except OSError:
        logger.exception("[WEB] Não foi possível iniciar o servidor em 0.0.0.0:%s", porta)
        print(f"[WEB] Falha ao iniciar servidor na porta {porta}; verifique se outro processo já a está usando.", flush=True)
        return

    mensagem = f"[WEB] Servidor da urna online em 0.0.0.0:{porta}"
    logger.info(mensagem)
    print(mensagem, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


async def verificar_staff(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    for role in interaction.user.roles:
        if role.name.lower() in {"staff", "admin", "moderador", "diretoria"}:
            return True
    return False


def normalizar_nome_cargo(nome: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", nome.casefold())
    return "".join(caractere for caractere in sem_acentos if caractere.isalnum())


def buscar_cargo(guild: discord.Guild, nome: str) -> discord.Role | None:
    nome_normalizado = normalizar_nome_cargo(nome)
    return next(
        (role for role in guild.roles if normalizar_nome_cargo(role.name) == nome_normalizado),
        None,
    )


async def obter_ou_criar_cargo(guild: discord.Guild, nome: str) -> discord.Role:
    role = buscar_cargo(guild, nome)
    if role is None:
        role = await guild.create_role(name=nome, reason="Cargo do RPG criado automaticamente")
    return role


async def aplicar_cargo_discord(guild: discord.Guild | None, member: discord.Member, nome: str) -> None:
    if guild is None:
        return

    cargos_emprego = {
        NOMES_CARGOS_DISCORD["Diretor Executivo"],
        NOMES_CARGOS_DISCORD["Trabalhador"],
        NOMES_CARGOS_DISCORD["Estagiário"],
        "Diretor Executivo",
        "Trabalhador",
        "Estagiário",
        "Vagabundo",
    }
    nomes_inativos = (
        ROLES_POLITICOS_ANTIGOS | {"Nenhum"}
        if nome in ROLES_POLITICOS_ANTIGOS | {"Nenhum"}
        else cargos_emprego
    )

    nomes_inativos_normalizados = {normalizar_nome_cargo(item) for item in nomes_inativos}
    for role in guild.roles:
        if normalizar_nome_cargo(role.name) in nomes_inativos_normalizados:
            if role in member.roles:
                await member.remove_roles(role, reason="Atualização de cargo do simulador")

    if nome == "Nenhum":
        return

    nome_role = NOMES_CARGOS_DISCORD.get(nome, nome)
    role = await obter_ou_criar_cargo(guild, nome_role)

    if role not in member.roles:
        await member.add_roles(role, reason="Resultado do simulador")


async def aplicar_partido_discord(guild: discord.Guild | None, member: discord.Member, nome: str) -> None:
    if guild is None:
        return

    nomes_partidos = {normalizar_nome_cargo(partido) for partido, *_ in PARTIDOS}
    nome_partido = normalizar_nome_cargo(nome)
    cargos_anteriores = [
        role for role in member.roles
        if normalizar_nome_cargo(role.name) in nomes_partidos
        and normalizar_nome_cargo(role.name) != nome_partido
    ]
    if cargos_anteriores:
        await member.remove_roles(*cargos_anteriores, reason="Atualização do partido sorteado")

    role = buscar_cargo(guild, nome)
    if role is None:
        cor = next(cor for partido, cor, _, _ in PARTIDOS if partido == nome)
        role = await guild.create_role(name=nome, colour=cor, reason="Cargo criado pelo sorteio de partido")
    if role not in member.roles:
        await member.add_roles(role, reason="Partido sorteado")


async def aplicar_alinhamento_discord(guild: discord.Guild | None, member: discord.Member, nome: str) -> None:
    if guild is None:
        return
    role_name = nome if nome in ROLES_ALINHAMENTO.values() else ROLES_ALINHAMENTO.get(nome)
    if role_name is None:
        return
    alinhamentos_anteriores = [
        role for role in member.roles
        if normalizar_nome_cargo(role.name) in {
            normalizar_nome_cargo(nome) for nome in ROLES_ALINHAMENTO.values()
        }
        and normalizar_nome_cargo(role.name) != normalizar_nome_cargo(role_name)
    ]
    if alinhamentos_anteriores:
        await member.remove_roles(*alinhamentos_anteriores, reason="Atualização do alinhamento")
    await adicionar_cargo(guild, member.id, role_name)


async def aplicar_resultado_eleitoral(guild: discord.Guild, cargo: str, usuario_id: int | None) -> None:
    if usuario_id is None:
        return

    cargo_role = ROLES_POLITICOS.get(cargo)
    if cargo_role is None:
        return

    role = await obter_ou_criar_cargo(guild, cargo_role)

    member = guild.get_member(int(usuario_id))
    if member is None:
        try:
            member = await guild.fetch_member(int(usuario_id))
        except discord.HTTPException:
            member = None
    if member is None:
        return

    nomes_politicos_anteriores = {normalizar_nome_cargo(nome) for nome in ROLES_POLITICOS_ANTIGOS}
    antigas = [
        item for item in member.roles
        if normalizar_nome_cargo(item.name) in nomes_politicos_anteriores and item != role
    ]
    if antigas:
        await member.remove_roles(*antigas, reason="Atualização de cargo eleitoral")
    await member.add_roles(role)
    usuario = obter_usuario(int(usuario_id))
    usuario["cargo_publico"] = {"presidente": "Presidente", "governador": "Governador", "prefeito": "Prefeito"}[cargo]
    usuario["ultimo_papel"] = usuario["cargo_publico"]
    salvar_dados()


def checar_investigacao(user_id: int) -> bool:
    usuario = obter_usuario(user_id)
    return bool(usuario.get("investigado", False)) or any(item.get("usuario_id") == user_id for item in DADOS_BOT["stf"]["investigacoes"])


def contrato_emprego_ativo(usuario: dict) -> bool:
    profissao = usuario.get("emprego", "Nenhum")
    if profissao not in SALARIOS:
        return False
    return usuario.get("emprego_ativo") is not False


def calcular_salarios_cargos(nomes_cargos: list[str]) -> dict[str, int]:
    salarios_normalizados = {
        normalizar_nome_cargo(nome): (nome, salario)
        for nome, salario in SALARIOS_CARGOS_DISCORD.items()
    }
    salarios: dict[str, int] = {}
    for nome in nomes_cargos:
        cargo_normalizado = normalizar_nome_cargo(nome)
        cargo = salarios_normalizados.get(cargo_normalizado)
        if cargo is not None:
            salarios[cargo[0]] = cargo[1]
    return salarios


def calcular_salario_folha(user_id: int, nomes_cargos: list[str]) -> tuple[dict[str, int], str | None]:
    salarios_cargos = calcular_salarios_cargos(nomes_cargos)
    usuario = obter_usuario(user_id)
    profissao = usuario.get("emprego") if contrato_emprego_ativo(usuario) else None
    if profissao is not None:
        salarios_cargos[f"Profissão: {profissao}"] = SALARIOS[profissao]
    return salarios_cargos, profissao


def registrar_ocorrencia_crime(user_id: int, acao: str, nome_crime: str, flagrante: bool) -> dict:
    casos = DADOS_BOT.setdefault("lava_jato", {"casos": []}).setdefault("casos", [])
    tipo_caso = f"crime_{acao}"
    caso = next(
        (
            item for item in reversed(casos)
            if item.get("aberto", True)
            and int(item.get("usuario_id", 0)) == user_id
            and item.get("tipo") == tipo_caso
        ),
        None,
    )
    if caso is None:
        caso, _ = abrir_caso_lava_jato(
            user_id,
            user_id,
            tipo_caso,
            f"Ocorrência registrada no RPG: {nome_crime}.",
        )
        caso["ocorrencias"] = 1
    else:
        caso["ocorrencias"] = int(caso.get("ocorrencias", 1)) + 1

    if flagrante:
        caso["evidencias"] = min(3, int(caso.get("evidencias", 0)) + 1)
    salvar_dados()
    return caso


def carregar_data_ultimo_pagamento(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


async def processar_folha_pagamento() -> None:
    agora = datetime.now(timezone.utc)
    folha = DADOS_BOT.setdefault("folha_pagamento", {"ultimo_pagamento_geral": None})
    ultimo_pagamento = carregar_data_ultimo_pagamento(folha.get("ultimo_pagamento_geral"))
    if ultimo_pagamento is None:
        folha["ultimo_pagamento_geral"] = agora.isoformat()
        salvar_dados()
        logger.info("Folha de pagamento iniciada; primeiro depósito ocorrerá após 48 horas.")
        return
    if agora - ultimo_pagamento < timedelta(hours=48):
        return

    membros_no_servidor: set[int] = set()
    cargos_por_usuario: dict[int, set[str]] = {}
    for guild in client.guilds:
        for member in guild.members:
            if member.bot:
                continue
            membros_no_servidor.add(member.id)
            salarios_cargos = calcular_salarios_cargos([role.name for role in member.roles])
            if salarios_cargos:
                cargos_por_usuario.setdefault(member.id, set()).update(salarios_cargos)

    contratos_por_assessor: dict[int, int] = {}
    for politico_id, contrato in DADOS_BOT["rachadinhas"].items():
        if contrato.get("ativo", True):
            assessor_id = int(contrato["assessor_id"])
            contratos_por_assessor.setdefault(assessor_id, int(politico_id))

    vazamentos: list[int] = []
    total_depositado = 0
    usuarios_pagados = 0
    for user_id in membros_no_servidor:
        salarios, _ = calcular_salario_folha(
            user_id,
            list(cargos_por_usuario.get(user_id, set())),
        )
        salario = sum(salarios.values())
        if salario <= 0:
            continue
        usuario = obter_usuario(user_id)
        retencao = 0
        politico_id = contratos_por_assessor.get(user_id)
        if politico_id is not None and politico_id != user_id:
            retencao = min(salario, int(salario * 0.30))
        valor_liquido = salario - retencao
        usuario["saldo"] = int(usuario.get("saldo", 0)) + valor_liquido
        usuario["status"] = "Normal" if usuario["saldo"] >= 0 else "Inadimplente"
        total_depositado += valor_liquido
        usuarios_pagados += 1

        if retencao:
            politico = obter_usuario(politico_id)
            politico["saldo"] = int(politico.get("saldo", 0)) + retencao
            politico["status"] = "Normal" if politico["saldo"] >= 0 else "Inadimplente"
            total_depositado += retencao
            if random.random() < 0.25:
                vazamentos.append(politico_id)

    for politico_id in set(vazamentos):
        politico = obter_usuario(politico_id)
        politico["status"] = "Impeachment"
        DADOS_BOT["rachadinhas"].pop(str(politico_id), None)
        DADOS_BOT["stf"]["investigacoes"].append({
            "usuario_id": politico_id,
            "motivo": "Vazamento de rachadinha na folha de pagamento",
            "tipo": "lava-jato",
        })

    folha["ultimo_pagamento_geral"] = (ultimo_pagamento + timedelta(hours=48)).isoformat()
    salvar_dados()

    for guild in client.guilds:
        canal = discord.utils.get(guild.text_channels, name="resenhas")
        if canal is None:
            continue
        embed = discord.Embed(
            title="💰 O SALÁRIO CAIU NA CONTA!",
            description="A Folha de Pagamento do Servidor foi depositada!",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Folha", value=f"{usuarios_pagados} usuários receberam seus salários.\nTotal depositado: **{formatar_reais(total_depositado)}**", inline=False)
        embed.set_image(url=GIFS["dinheiro"])
        embed.set_footer(text="Folha da República • ciclo de 48 horas")
        await canal.send(embed=embed)
        if vazamentos:
            await canal.send(
                "📰 **Vazamento na mídia:** rachadinha descoberta na folha. "
                + ", ".join(f"<@{politico_id}>" for politico_id in vazamentos)
                + " sofreu impeachment."
            )

    logger.info("Folha paga: %s usuários; total %s.", usuarios_pagados, formatar_reais(total_depositado))


@tasks.loop(hours=1)
async def folha_pagamento_loop() -> None:
    try:
        await processar_folha_pagamento()
    except Exception:
        logger.exception("Falha ao processar a folha de pagamento.")


@folha_pagamento_loop.before_loop
async def aguardar_bot_pronto_para_folha() -> None:
    await client.wait_until_ready()


@tree.command(name="folha", description="Consulta seus salários e a previsão do próximo pagamento")
async def folha_status(interaction: discord.Interaction) -> None:
    nomes_roles = (
        [role.name for role in interaction.user.roles]
        if isinstance(interaction.user, discord.Member)
        else []
    )
    salarios, profissao = calcular_salario_folha(interaction.user.id, nomes_roles)
    total = sum(salarios.values())
    if not salarios:
        descricao = "Você não tem cargos salariais ou contrato profissional ativo."
    else:
        itens = "\n".join(
            f"• {nome}: **{formatar_reais(valor)}**"
            for nome, valor in salarios.items()
        )
        descricao = (
            f"{itens}\n\n**Total estimado por ciclo:** {formatar_reais(total)}"
        )

    agora = datetime.now(timezone.utc)
    folha = DADOS_BOT.setdefault("folha_pagamento", {"ultimo_pagamento_geral": None})
    ultimo_pagamento = carregar_data_ultimo_pagamento(folha.get("ultimo_pagamento_geral"))
    if ultimo_pagamento is None:
        proximo_pagamento = "A folha será inicializada quando o bot iniciar; o primeiro depósito ocorre após 48 horas."
    else:
        proximo = ultimo_pagamento + timedelta(hours=48)
        restante = proximo - agora
        if restante.total_seconds() <= 0:
            proximo_pagamento = "O próximo depósito será processado na próxima verificação da folha."
        else:
            horas, segundos = divmod(int(restante.total_seconds()), 3600)
            proximo_pagamento = f"Em aproximadamente **{horas}h {segundos // 60}min**."

    embed = discord.Embed(
        title="💰 Sua folha de pagamento",
        description=descricao,
        color=discord.Color.gold(),
    )
    embed.add_field(name="Próximo depósito automático", value=proximo_pagamento, inline=False)
    if profissao is not None:
        embed.set_footer(text=f"Profissão ativa: {profissao}. O pagamento é automático a cada 48 horas.")
    else:
        embed.set_footer(text="Cargos do servidor são pagos automaticamente a cada 48 horas.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def verificar_emprego_bonus(user_id: int, valor: int) -> int:
    usuario = obter_usuario(user_id)
    emprego = usuario.get("emprego", "Nenhum")
    if not contrato_emprego_ativo(usuario):
        return 0
    bonus = 0
    if emprego == "Guarda":
        bonus = int(valor * 0.10)
    elif emprego == "Mecânico":
        bonus = int(valor * 0.12)
    elif emprego == "Advogado":
        bonus = int(valor * 0.15)
    elif emprego == "Médico":
        bonus = int(valor * 0.18)
    return bonus


def nomes_cargos(interaction: discord.Interaction) -> set[str]:
    if not isinstance(interaction.user, discord.Member):
        return set()
    return {normalizar_nome_cargo(role.name) for role in interaction.user.roles}


def tem_cargo(interaction: discord.Interaction, *nomes: str) -> bool:
    if usuario_eh_godmode(interaction.user.id):
        return True
    usuario = obter_usuario(interaction.user.id)
    cargos_discord = nomes_cargos(interaction)
    desejados = {normalizar_nome_cargo(nome) for nome in nomes}
    dados_usuario = {
        normalizar_nome_cargo(str(usuario.get("cargo_publico", ""))),
        normalizar_nome_cargo(str(usuario.get("ultimo_cargo", ""))),
        normalizar_nome_cargo(str(usuario.get("emprego", ""))),
    }
    return bool(desejados.intersection(cargos_discord | dados_usuario))


def eh_admin_ou_dono(interaction: discord.Interaction) -> bool:
    return usuario_eh_godmode(interaction.user.id) or bool(
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )


def obter_servidor(guild_id: int) -> dict:
    return DADOS_BOT["cofres_municipais"].setdefault(str(guild_id), {"cofre": 0, "energia": 0})


async def adicionar_cargo(guild: discord.Guild | None, user_id: int, nome: str) -> None:
    if guild is None:
        return
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.HTTPException:
            return
    role = await obter_ou_criar_cargo(guild, nome)
    if role not in member.roles:
        await member.add_roles(role, reason="Atualização de cargo do simulador")


async def garantir_godmode_ideal(interaction: discord.Interaction) -> None:
    if not usuario_eh_godmode(interaction.user.id):
        return
    usuario = obter_usuario(interaction.user.id)
    usuario.update({
        "ultimo_cargo": "Diretor Executivo",
        "cargo_publico": "Presidente",
        "partido": "PL",
        "alinhamento": "☀️ Lado da Luz",
    })
    salvar_dados()
    for role_name in ("👑 Presidente", "👔 Diretor Executivo", "PL", "☀️ Lado da Luz"):
        await adicionar_cargo(interaction.guild, interaction.user.id, role_name)


async def enviar_lava_jato(guild: discord.Guild | None, user_ids: set[int], motivo: str) -> None:
    envolvidos = []
    fim_da_pena = time.time() + 30 * 60
    for user_id in user_ids:
        usuario = obter_usuario(user_id)
        usuario["saldo"] = int(int(usuario.get("saldo", 0)) * 0.5)
        usuario["saldo_sujo"] = max(0, int(usuario.get("saldo_sujo", 0)) // 2)
        usuario["prisao"] = 1
        usuario["preso"] = True
        usuario["preso_ate"] = fim_da_pena
        usuario["prisao_guild_id"] = guild.id if guild else None
        usuario["status"] = "Preso"
        usuario["investigado"] = True
        usuario["cargo_publico"] = "Nenhum"
        DADOS_BOT["stf"]["investigacoes"].append({
            "usuario_id": user_id,
            "motivo": motivo,
            "tipo": "lava-jato",
            "data": date.today().isoformat(),
        })
        envolvidos.append(f"<@{user_id}>")
        if guild is not None:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    member = None
            if member is not None:
                nomes_cargos_antigos = {normalizar_nome_cargo(nome) for nome in ROLES_POLITICOS_ANTIGOS}
                cargos_antigos = [
                    role for role in member.roles
                    if normalizar_nome_cargo(role.name) in nomes_cargos_antigos
                ]
                if cargos_antigos:
                    await member.remove_roles(*cargos_antigos, reason="Operação Lava Jato")
                await adicionar_cargo(guild, user_id, "🚔 Papuda")
            asyncio.create_task(liberar_reu_depois(guild, user_id, fim_da_pena))

    salvar_dados()
    if guild is not None:
        canal = discord.utils.get(guild.text_channels, name="resenhas")
        if canal is not None:
            embed = discord.Embed(
                title="🚨 OPERAÇÃO LAVA JATO DEFLAGRADA!",
                description=f"**Motivo:** {motivo}\n**Réus:** {', '.join(envolvidos) or 'não identificados'}\n50% do dinheiro foi confiscado; os réus foram enviados à Papuda por 30 minutos.",
                color=discord.Color.dark_red(),
            )
            embed.set_image(url=GIFS["lava_jato"])
            await canal.send(embed=embed)


async def liberar_reu_depois(guild: discord.Guild, user_id: int, fim_da_pena: float) -> None:
    await asyncio.sleep(max(0, fim_da_pena - time.time()))
    usuario = obter_usuario(user_id)
    if float(usuario.get("preso_ate", 0) or 0) != fim_da_pena:
        return
    usuario["preso_ate"] = 0
    usuario["prisao_guild_id"] = None
    usuario["prisao"] = 0
    usuario["preso"] = False
    usuario["status"] = "Inadimplente" if int(usuario.get("saldo", 0)) < 0 else "Normal"
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.HTTPException:
            member = None
    role = buscar_cargo(guild, "🚔 Papuda")
    if member is not None and role is not None and role in member.roles:
        await member.remove_roles(role, reason="Fim da pena de 30 minutos da Lava Jato")
    salvar_dados()


async def tentar_lava_jato(guild: discord.Guild | None, user_ids: set[int], motivo: str) -> bool:
    if random.random() >= 0.50:
        return False
    await enviar_lava_jato(guild, user_ids, motivo)
    return True


@tree.command(name="cargo", description="Sorteia seu cargo no mundo corporativo")
async def cargo(interaction: discord.Interaction) -> None:
    if usuario_eh_godmode(interaction.user.id):
        nome, _, cor, gif = ("Diretor Executivo", 10_000, discord.Color.gold(), GIFS["dinheiro"])
    else:
        nome, _, cor, gif = random.choice(CARGOS)

    usuario = obter_usuario(interaction.user.id)
    usuario["ultimo_cargo"] = nome
    usuario["cargo_publico"] = nome if nome in {"Presidente", "Governador", "Deputado", "Prefeito"} else "Nenhum"

    if interaction.guild is not None:
        await aplicar_cargo_discord(interaction.guild, interaction.user, nome)
    await garantir_godmode_ideal(interaction)

    embed = embed_resultado(
        titulo="Resultado corporativo",
        descricao=f"{interaction.user.mention}\nSeu cargo atual é **{NOMES_CARGOS_DISCORD.get(nome, nome)}**. A remuneração será depositada pela folha automática a cada 48 horas.",
        cor=cor,
        gif=gif,
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="politica", description="Sorteia seu cargo político nas urnas")
async def politica(interaction: discord.Interaction) -> None:
    if usuario_eh_godmode(interaction.user.id):
        nome, _, cor, gif = ("Presidente", 35_000, discord.Color.dark_green(), GIFS["discurso"])
    else:
        nome, _, cor, gif = random.choice(POLITICOS)

    usuario = obter_usuario(interaction.user.id)
    usuario["cargo_publico"] = nome
    usuario["ultimo_papel"] = nome

    if interaction.guild is not None:
        await aplicar_cargo_discord(
            interaction.guild,
            interaction.user,
            ROLES_POLITICOS["presidente"] if usuario_eh_godmode(interaction.user.id) else nome,
        )
        if usuario_eh_godmode(interaction.user.id):
            await adicionar_cargo(interaction.guild, interaction.user.id, "PL")
            await adicionar_cargo(interaction.guild, interaction.user.id, "👔 Diretor Executivo")
            await adicionar_cargo(interaction.guild, interaction.user.id, "☀️ Lado da Luz")
    await garantir_godmode_ideal(interaction)

    if nome in {"Presidente", "Governador", "Deputado", "Prefeito"}:
        usuario["policial"] = True

    embed = embed_resultado(
        titulo="Apuração das urnas",
        descricao=f"{interaction.user.mention}\nSeu cargo político é **{NOMES_CARGOS_DISCORD.get(nome, nome)}**. O salário será depositado na folha automática a cada 48 horas.",
        cor=cor,
        gif=gif,
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="sincronizar_cargos", description="Aplica no servidor os cargos salvos no perfil de um membro")
async def sincronizar_cargos(interaction: discord.Interaction, membro: discord.Member) -> None:
    if interaction.guild is None or not eh_admin_ou_dono(interaction):
        await interaction.response.send_message(
            "❌ Use este comando no servidor; ele é exclusivo para administradores e para o dono do bot.",
            ephemeral=True,
        )
        return

    usuario = obter_usuario(membro.id)
    cargo_publico = str(usuario.get("cargo_publico", "Nenhum"))
    cargo_emprego = str(usuario.get("ultimo_cargo", "Nenhum"))
    partido_usuario = str(usuario.get("partido", "Nenhum"))
    cargos_aplicados: list[str] = []

    try:
        if cargo_publico != "Nenhum":
            nome_cargo_publico = NOMES_CARGOS_DISCORD.get(cargo_publico, cargo_publico)
            await aplicar_cargo_discord(interaction.guild, membro, cargo_publico)
            cargos_aplicados.append(nome_cargo_publico)

        if cargo_emprego != "Nenhum":
            nome_cargo_emprego = NOMES_CARGOS_DISCORD.get(cargo_emprego, cargo_emprego)
            await aplicar_cargo_discord(interaction.guild, membro, cargo_emprego)
            cargos_aplicados.append(nome_cargo_emprego)

        if partido_usuario != "Nenhum":
            cargo_partido = await obter_ou_criar_cargo(interaction.guild, partido_usuario)
            if cargo_partido not in membro.roles:
                await membro.add_roles(cargo_partido, reason="Sincronização de cargos do perfil do simulador")
            cargos_aplicados.append(cargo_partido.name)
    except discord.HTTPException:
        logger.exception("Falha ao sincronizar cargos de %s no servidor %s.", membro.id, interaction.guild.id)
        await interaction.response.send_message(
            "❌ O Discord recusou a atualização. Confira a permissão **Gerenciar cargos** e se o cargo do bot está acima dos cargos a atribuir.",
            ephemeral=True,
        )
        return

    resultado = (
        "✅ Cargos do perfil sincronizados: " + ", ".join(f"**{nome}**" for nome in cargos_aplicados)
        if cargos_aplicados
        else "ℹ️ O perfil não tem cargos para sincronizar."
    )
    await interaction.response.send_message(resultado, ephemeral=True)


@tree.command(name="partido", description="Sorteia sua filiação partidária")
async def partido(interaction: discord.Interaction) -> None:
    if usuario_eh_godmode(interaction.user.id):
        nome, cor, gif, mensagem = ("PL", discord.Color.blue(), GIFS["bolsonaro"], "A urna te colocou no PL. A campanha já pode começar!")
    else:
        nome, cor, gif, mensagem = random.choice(PARTIDOS)

    usuario = obter_usuario(interaction.user.id)
    usuario["partido"] = nome
    if isinstance(interaction.user, discord.Member):
        await aplicar_partido_discord(interaction.guild, interaction.user, nome)
    salvar_dados()
    await garantir_godmode_ideal(interaction)
    embed = embed_resultado(
        titulo=f"Filiação: {nome}",
        descricao=f"{interaction.user.mention}\n{mensagem}",
        cor=cor,
        gif=gif,
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="alinhamento", description="Descobre a natureza da sua alma")
async def alinhamento(interaction: discord.Interaction) -> None:
    if usuario_eh_godmode(interaction.user.id):
        nome, cor, gif, mensagem = ("☀️ Lado da Luz", discord.Color.green(), GIFS["bom"], "Sua bússola moral aponta para a luz.")
    else:
        nome, cor, gif, mensagem = random.choice(ALINHAMENTOS)
        nome = ROLES_ALINHAMENTO[nome]

    usuario = obter_usuario(interaction.user.id)
    usuario["alinhamento"] = nome
    salvar_dados()
    await aplicar_alinhamento_discord(interaction.guild, interaction.user, nome)
    await garantir_godmode_ideal(interaction)
    embed = embed_resultado(
        titulo=f"Alinhamento: {nome}",
        descricao=f"{interaction.user.mention}\n{mensagem}",
        cor=cor,
        gif=gif,
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="carteira", description="Consulta seu saldo acumulado")
async def carteira(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        embed=criar_embed_carteira(interaction.user.id, interaction.user.mention)
    )


def criar_embed_carteira(user_id: int, mention: str) -> discord.Embed:
    usuario = obter_usuario(user_id)
    saldo = usuario["saldo"]
    itens = usuario["itens"]
    ostentacao = []
    if itens["carro"]:
        ostentacao.append(f"Carro x{itens['carro']}")
    if itens["mansao"]:
        ostentacao.append(f"Mansão x{itens['mansao']}")
    for empresa, quantidade in usuario.get("empresas", {}).items():
        if quantidade:
            ostentacao.append(f"{NOMES_ITENS_LOJA[empresa]} x{quantidade}")
    if not ostentacao:
        ostentacao.append("Nenhum patrimônio ostentado")
    descricao = (
        f"{mention}\n"
        f"Saldo acumulado: **{formatar_reais(saldo)}**\n"
        f"Dinheiro sujo: **{formatar_reais(usuario.get('saldo_sujo', 0))}**\n"
        f"Status: **{usuario['status']}**\n"
        f"Patrimônio: **{', '.join(ostentacao)}**"
    )
    return embed_resultado(
        titulo="Sua carteira",
        descricao=descricao,
        cor=discord.Color.gold(),
        gif=GIFS["dinheiro"],
    )


@tree.command(name="saldo", description="Mostra rapidamente seu saldo disponível")
async def saldo(interaction: discord.Interaction) -> None:
    usuario = obter_usuario(interaction.user.id)
    embed = discord.Embed(
        title="💵 Saldo disponível",
        description=f"{interaction.user.mention}\nSaldo limpo: **{formatar_reais(usuario['saldo'])}**\nSaldo sujo: **{formatar_reais(usuario.get('saldo_sujo', 0))}**",
        color=discord.Color.gold(),
    )
    embed.set_image(url=GIFS["dinheiro"])
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="extrato", description="Mostra saldo, status e patrimônio completo")
async def extrato(interaction: discord.Interaction) -> None:
    usuario = obter_usuario(interaction.user.id)
    itens = [f"{NOMES_ITENS_LOJA.get(nome, nome)} x{quantidade}" for nome, quantidade in usuario.get("itens", {}).items() if quantidade]
    empresas = [f"{NOMES_ITENS_LOJA.get(nome, nome)} x{quantidade}" for nome, quantidade in usuario.get("empresas", {}).items() if quantidade]
    patrimonio = itens + empresas or ["Nenhum bem registrado"]
    embed = discord.Embed(title="📑 Extrato patrimonial", color=discord.Color.gold())
    embed.add_field(name="Saldos", value=f"Limpo: **{formatar_reais(usuario['saldo'])}**\nSujo: **{formatar_reais(usuario.get('saldo_sujo', 0))}**", inline=True)
    embed.add_field(name="Situação", value=f"Status: **{usuario['status']}**\nEnergia: **{usuario.get('energia', 100)}**\nEmprego: **{usuario.get('emprego', 'Nenhum')}**", inline=True)
    embed.add_field(name="Bens e empresas", value="\n".join(patrimonio), inline=False)
    embed.set_image(url=GIFS["dinheiro"])
    await interaction.response.send_message(embed=embed, ephemeral=True)


banco_group = app_commands.Group(name="banco", description="Serviços bancários e defesa jurídica")


@banco_group.command(name="pix", description="Transfere saldo limpo para outro usuário")
async def banco_pix(interaction: discord.Interaction, usuario: discord.Member, quantidade: app_commands.Range[int, 1]) -> None:
    resultado = transferir_saldo(interaction.user.id, usuario.id, quantidade)
    if not resultado.startswith("✅"):
        await interaction.response.send_message(resultado, ephemeral=True)
        return
    embed = discord.Embed(
        title="💸 PIX enviado",
        description=f"{interaction.user.mention} enviou **{formatar_reais(quantidade)}** para {usuario.mention}.",
        color=discord.Color.gold(),
    )
    embed.set_image(url=GIFS["dinheiro"])
    await interaction.response.send_message(embed=embed)


def transferir_saldo(remetente_id: int, destinatario_id: int, quantidade: int) -> str:
    if quantidade <= 0:
        return "⚠️ O valor da transferência deve ser maior que zero."
    if remetente_id == destinatario_id:
        return "⚠️ Você não pode transferir saldo para si mesmo."
    remetente = obter_usuario(remetente_id)
    if remetente["saldo"] < quantidade:
        return "❌ Você não tem saldo suficiente para enviar esse valor."
    remover_saldo(remetente_id, quantidade)
    adicionar_saldo(destinatario_id, quantidade)
    salvar_dados()
    return "✅ Transferência realizada."


@banco_group.command(name="defender", description="Advogado tenta libertar uma pessoa presa")
async def banco_defender(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not tem_cargo(interaction, "Advogado"):
        await interaction.response.send_message("❌ Esta ação é exclusiva para quem trabalha como advogado.", ephemeral=True)
        return
    alvo = obter_usuario(usuario.id)
    if alvo["prisao"] <= 0:
        await interaction.response.send_message("ℹ️ Essa pessoa não está na Papuda.", ephemeral=True)
        return
    if random.random() < 0.50:
        alvo["prisao"] = 0
        alvo["preso"] = False
        alvo["preso_ate"] = 0
        alvo["prisao_guild_id"] = None
        alvo["status"] = "Inadimplente" if int(alvo.get("saldo", 0)) < 0 else "Livre"
        if interaction.guild is not None:
            role = buscar_cargo(interaction.guild, "🚔 Papuda")
            if role is not None and role in usuario.roles:
                await usuario.remove_roles(role, reason="Defesa aceita")
        resultado = f"⚖️ Defesa aceita: {usuario.mention} foi libertado(a) da Papuda."
    else:
        resultado = f"⚖️ Pedido negado. {usuario.mention} continua na Papuda."
    salvar_dados()
    embed = discord.Embed(title="⚖️ Banco de defesa", description=resultado, color=discord.Color.dark_purple())
    embed.set_image(url=GIFS["dinheiro"])
    await interaction.response.send_message(embed=embed)


@tree.command(name="eleicao", description="Gerencia a urna eletrônica e a apuração eleitoral")
async def eleicao(interaction: discord.Interaction, acao: str) -> None:
    if not await verificar_staff(interaction):
        await interaction.response.send_message("❌ Você não tem permissão para gerir a eleição.", ephemeral=True)
        return

    if acao == "iniciar":
        DADOS_BOT["eleicao"]["status"] = "aberta"
        DADOS_BOT["eleicao"]["votos"] = {"presidente": {}, "governador": {}, "prefeito": {}}
        DADOS_BOT["eleicao"]["resultado"] = {"presidente": None, "governador": None, "prefeito": None}
        DADOS_BOT["eleicao"]["campanhas"] = {"presidente": {}, "governador": {}, "prefeito": {}}
        salvar_dados()
        registrar_noticia("Eleições abertas", "As candidaturas e campanhas estão abertas.")
        await interaction.response.send_message("✅ Eleição iniciada. A urna eletrônica web está aberta para apuração.")
        return

    if acao == "encerrar":
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando precisa ser usado em um servidor.")
            return

        for cargo, candidatos in DADOS_BOT["eleicao"]["votos"].items():
            vencedor = encontrar_vencedor_eleitoral(cargo, candidatos)
            DADOS_BOT["eleicao"]["resultado"][cargo] = vencedor
            if vencedor is not None:
                await aplicar_resultado_eleitoral(interaction.guild, cargo, vencedor)

        DADOS_BOT["eleicao"]["status"] = "encerrada"
        salvar_dados()
        registrar_noticia("Apuração concluída", "A eleição foi encerrada e os vencedores foram definidos.")
        await interaction.response.send_message(
            "✅ Eleição encerrada. Os cargos reais foram distribuídos automaticamente no servidor."
        )
        return

    await interaction.response.send_message("⚠️ Ações válidas: `iniciar` ou `encerrar`.")


@tree.command(name="eleicao_resultado", description="Publica o resultado oficial da eleição no canal de resenhas")
async def eleicao_resultado(interaction: discord.Interaction, cargo: str = "") -> None:
    if interaction.guild is None:
        await interaction.response.send_message("❌ Este comando precisa ser usado em um servidor.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator and not usuario_eh_godmode(interaction.user.id):
        await interaction.response.send_message(
            "❌ Este comando é exclusivo para administradores do servidor ou para o dono do bot.",
            ephemeral=True,
        )
        return

    canal = discord.utils.get(interaction.guild.text_channels, name="resenhas")
    if canal is None:
        await interaction.response.send_message("❌ Canal 'resenhas' não encontrado no servidor!")
        return

    cargos_validos = {"presidente": "Presidente", "governador": "Governador", "prefeito": "Prefeito"}
    cargo_normalizado = cargo.strip().lower()
    if cargo_normalizado and cargo_normalizado not in cargos_validos:
        await interaction.response.send_message(
            "⚠️ Cargo inválido. Use `presidente`, `governador` ou `prefeito`.",
            ephemeral=True,
        )
        return

    if not cargo_normalizado:
        for cargo_nome, votos in DADOS_BOT["eleicao"]["votos"].items():
            DADOS_BOT["eleicao"]["resultado"][cargo_nome] = encontrar_vencedor_eleitoral(cargo_nome, votos)

    elif cargo_normalizado in cargos_validos:
        votos = DADOS_BOT["eleicao"]["votos"].get(cargo_normalizado, {})
        DADOS_BOT["eleicao"]["resultado"][cargo_normalizado] = encontrar_vencedor_eleitoral(cargo_normalizado, votos)

    DADOS_BOT["eleicao"]["status"] = "encerrada"
    salvar_dados()

    if cargo_normalizado:
        vencedor_id = DADOS_BOT["eleicao"]["resultado"].get(cargo_normalizado)
        if vencedor_id is None:
            await interaction.response.send_message(
                f"⚠️ Ainda não há resultado oficial para **{cargos_validos[cargo_normalizado]}**.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(int(vencedor_id))
        nome_vencedor = member.mention if member else f"<@{vencedor_id}>"
        await aplicar_resultado_eleitoral(interaction.guild, cargo_normalizado, vencedor_id)

        embed = discord.Embed(
            title=f"🏛️ Resultado oficial: {ROLES_POLITICOS[cargo_normalizado]}",
            description=f"{nome_vencedor} foi eleito(a) para **{ROLES_POLITICOS[cargo_normalizado]}**.",
            color=discord.Color.gold(),
        )
        embed.set_image(url=GIFS["discurso"])
        embed.set_footer(text="Politice Bot • Eleição oficial")

        await canal.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Resultado oficial do cargo **{cargos_validos[cargo_normalizado]}** foi anunciado em #{canal.name}."
        )
        return

    campos = []
    for cargo_nome, nome_cargo in cargos_validos.items():
        vencedor_id = DADOS_BOT["eleicao"]["resultado"].get(cargo_nome)
        if vencedor_id is None:
            campos.append(f"**{nome_cargo}:** Sem vencedor")
            continue
        member = interaction.guild.get_member(int(vencedor_id))
        nome_vencedor = member.mention if member else f"<@{vencedor_id}>"
        await aplicar_resultado_eleitoral(interaction.guild, cargo_nome, vencedor_id)
        campos.append(f"**{ROLES_POLITICOS[cargo_nome]}:** {nome_vencedor}")

    embed = discord.Embed(
        title="🏛️ Resultado oficial da eleição",
        description="A apuração foi concluída e os cargos foram definidos oficialmente.",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Mandato nacional", value="\n".join(campos), inline=False)
    embed.set_image(url=GIFS["discurso"])
    embed.set_footer(text="Politice Bot • Eleição oficial")

    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ Resultado oficial da eleição foi anunciado em #{canal.name}.")


@tree.command(name="campanha", description="Registre uma candidatura, publique propostas e faça campanha")
@app_commands.choices(
    acao=[
        app_commands.Choice(name="Registrar candidatura", value="registrar"),
        app_commands.Choice(name="Publicar proposta", value="proposta"),
        app_commands.Choice(name="Fazer evento", value="evento"),
        app_commands.Choice(name="Ver painel eleitoral", value="painel"),
    ],
    cargo=[
        app_commands.Choice(name="Presidente", value="presidente"),
        app_commands.Choice(name="Governador", value="governador"),
        app_commands.Choice(name="Prefeito", value="prefeito"),
    ],
    tipo=[
        app_commands.Choice(name="Comício (R$ 1.000)", value="comicio"),
        app_commands.Choice(name="Voluntariado (R$ 250)", value="voluntariado"),
        app_commands.Choice(name="Debate (gratuito)", value="debate"),
    ],
)
async def campanha(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    cargo: app_commands.Choice[str] | None = None,
    texto: str | None = None,
    tipo: app_commands.Choice[str] | None = None,
) -> None:
    eleicao = DADOS_BOT["eleicao"]
    campanhas = eleicao.setdefault(
        "campanhas",
        {"presidente": {}, "governador": {}, "prefeito": {}},
    )

    if acao.value == "painel":
        linhas = []
        nomes_cargos = {"presidente": "Presidência", "governador": "Governo estadual", "prefeito": "Prefeitura"}
        for cargo_atual, candidaturas in campanhas.items():
            for candidato_id, candidatura in sorted(
                candidaturas.items(),
                key=lambda item: int(item[1].get("popularidade", 0)),
                reverse=True,
            )[:5]:
                linhas.append(
                    f"**{nomes_cargos.get(cargo_atual, cargo_atual.title())}** — <@{candidato_id}> "
                    f"({candidatura.get('partido', 'Independente')}): "
                    f"⭐ {int(candidatura.get('popularidade', 0))} popularidade · "
                    f"📜 {len(candidatura.get('propostas', []))} propostas"
                )
        descricao = "\n".join(linhas) if linhas else "Ainda não há candidaturas registradas."
        embed = discord.Embed(title="🗳️ Painel eleitoral", description=descricao, color=discord.Color.dark_green())
        embed.set_footer(text=f"Eleição {eleicao.get('status', 'encerrada')} • popularidade desempata votos iguais")
        await interaction.response.send_message(embed=embed)
        return

    if eleicao.get("status") != "aberta":
        await interaction.response.send_message("❌ Não há eleição aberta. A administração pode iniciar uma com `/eleicao`.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando dentro do servidor.", ephemeral=True)
        return

    usuario = obter_usuario(interaction.user.id)
    candidato_id = str(interaction.user.id)
    candidatura_cargo = next(
        (
            (cargo_atual, candidaturas[candidato_id])
            for cargo_atual, candidaturas in campanhas.items()
            if candidato_id in candidaturas
        ),
        None,
    )

    if acao.value == "registrar":
        if cargo is None:
            await interaction.response.send_message("⚠️ Escolha o cargo que deseja disputar.", ephemeral=True)
            return
        if usuario.get("partido", "Nenhum") == "Nenhum":
            await interaction.response.send_message("❌ Para se candidatar, primeiro escolha um partido com `/partido`.", ephemeral=True)
            return
        if candidatura_cargo is not None:
            await interaction.response.send_message("❌ Você já tem uma candidatura nesta eleição.", ephemeral=True)
            return
        candidaturas = campanhas.setdefault(cargo.value, {})
        if candidato_id in candidaturas:
            await interaction.response.send_message("❌ Você já está inscrito para este cargo.", ephemeral=True)
            return
        candidaturas[candidato_id] = {
            "partido": usuario.get("partido", "Independente"),
            "popularidade": 0,
            "propostas": [],
            "ultima_acao": 0,
        }
        salvar_dados()
        registrar_noticia(
            "Nova candidatura",
            f"{interaction.user.display_name} registrou candidatura a {cargo.name} pelo partido {usuario['partido']}.",
        )
        await interaction.response.send_message(
            f"✅ Candidatura registrada para **{cargo.name}** pelo **{usuario['partido']}**. Publique até 3 propostas e organize eventos.",
        )
        return

    if candidatura_cargo is None:
        await interaction.response.send_message("❌ Registre uma candidatura antes de publicar propostas ou fazer eventos.", ephemeral=True)
        return

    cargo_candidato, candidatura = candidatura_cargo
    if acao.value == "proposta":
        if texto is None or not texto.strip() or len(texto) > 300:
            await interaction.response.send_message("⚠️ A proposta deve ter entre 1 e 300 caracteres.", ephemeral=True)
            return
        propostas = candidatura.setdefault("propostas", [])
        if len(propostas) >= 3:
            await interaction.response.send_message("❌ Cada candidatura pode publicar no máximo 3 propostas.", ephemeral=True)
            return
        proposta = texto.strip()
        propostas.append(proposta)
        salvar_dados()
        registrar_noticia(
            "Proposta publicada",
            f"{interaction.user.display_name} ({candidatura['partido']}) propôs: {proposta}",
        )
        await interaction.response.send_message(f"📜 Proposta **{len(propostas)}/3** publicada: {proposta}")
        return

    if acao.value == "evento":
        if tipo is None:
            await interaction.response.send_message("⚠️ Escolha comício, voluntariado ou debate.", ephemeral=True)
            return
        agora = time.time()
        restante = 12 * 60 * 60 - (agora - float(candidatura.get("ultima_acao", 0)))
        if restante > 0:
            horas, segundos = divmod(int(restante), 3600)
            minutos = segundos // 60
            await interaction.response.send_message(
                f"⏳ Sua campanha pode realizar outro evento em **{horas}h {minutos}min**.",
                ephemeral=True,
            )
            return

        eventos = {
            "comicio": (1000, 3, "comício"),
            "voluntariado": (250, 1, "ação de voluntariado"),
            "debate": (0, 2, "debate público"),
        }
        custo, ganho, nome_evento = eventos[tipo.value]
        if custo and not cobrar_taxa(interaction.user.id, custo, f"campanha: {nome_evento}"):
            await interaction.response.send_message(
                f"❌ Você precisa de **{formatar_reais(custo)}** para realizar esse evento.",
                ephemeral=True,
            )
            return
        candidatura["popularidade"] = min(100, int(candidatura.get("popularidade", 0)) + ganho)
        candidatura["ultima_acao"] = agora
        salvar_dados()
        registrar_noticia(
            "Evento de campanha",
            f"{interaction.user.display_name} ({candidatura['partido']}) realizou {nome_evento} para {cargo_candidato}.",
        )
        await interaction.response.send_message(
            f"📣 Você realizou um(a) **{nome_evento}**. Popularidade: "
            f"**{candidatura['popularidade']}** (+{ganho}, máximo 100). Próximo evento em 12 horas."
        )
        return

    await interaction.response.send_message("⚠️ Ação de campanha inválida.", ephemeral=True)


@tree.command(name="noticias", description="Leia as notícias recentes do RPG")
async def noticias(interaction: discord.Interaction) -> None:
    recentes = list(reversed(DADOS_BOT.get("noticias", [])[-10:]))
    if not recentes:
        await interaction.response.send_message("📰 Ainda não há notícias. Inicie uma eleição ou comece uma campanha!", ephemeral=True)
        return

    embed = discord.Embed(title="📰 Notícias do RPG", color=discord.Color.blue())
    for noticia in recentes:
        try:
            momento = int(datetime.fromisoformat(noticia["data"]).timestamp())
            data = f"<t:{momento}:R>"
        except (KeyError, TypeError, ValueError):
            data = "data indisponível"
        embed.add_field(
            name=f"{noticia.get('titulo', 'Notícia')} · {data}"[:256],
            value=str(noticia.get("descricao", ""))[:1024] or "Sem detalhes.",
            inline=False,
        )
    embed.set_footer(text="Últimos 10 acontecimentos • Politice Bot")
    await interaction.response.send_message(embed=embed)


governo_group = app_commands.Group(name="governo", description="Decretos e ações do Poder Executivo")


@governo_group.command(name="decreto", description="Publica um decreto presidencial")
async def governo_decreto(interaction: discord.Interaction, texto: str) -> None:
    if not tem_cargo(interaction, "Presidente", "👑 Presidente", "Presidente da República"):
        await interaction.response.send_message("❌ A publicação de decretos é exclusiva da Presidência.", ephemeral=True)
        return
    if not texto_legal(texto):
        await interaction.response.send_message("⚠️ O texto do decreto deve ter entre 1 e 1000 caracteres.", ephemeral=True)
        return
    registro = {"autor_id": interaction.user.id, "texto": texto, "data": date.today().isoformat()}
    DADOS_BOT["decretos"].append(registro)
    salvar_dados()
    embed = discord.Embed(title="📜 Decreto Presidencial", description=texto, color=discord.Color.dark_green())
    embed.set_footer(text=f"Publicado por {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


@governo_group.command(name="desviar", description="Tenta desviar verba pública, com risco de investigação")
async def governo_desviar(interaction: discord.Interaction, valor: app_commands.Range[int, 1]) -> None:
    usuario = obter_usuario(interaction.user.id)
    cargos_eleitos = {"Presidente", "Governador", "Prefeito", "Deputado", "Senador"}
    if usuario["cargo_publico"] not in cargos_eleitos and not tem_cargo(
        interaction, "Presidente", "Governador", "Prefeito", "Deputado", "Senador",
        "👑 Presidente", "📜 Governador", "🏙️ Prefeito", "🏛️ Deputado", "🏛️ Senador",
    ):
        await interaction.response.send_message("❌ Só políticos eleitos podem desviar verba pública.", ephemeral=True)
        return
    if usuario["saldo"] < valor:
        await interaction.response.send_message("❌ Saldo insuficiente para esse desvio.", ephemeral=True)
        return
    remover_saldo(interaction.user.id, valor)
    adicionar_saldo(interaction.user.id, valor // 2)
    DADOS_BOT["cofre_publico"] += valor
    if await tentar_lava_jato(interaction.guild, {interaction.user.id}, "Desvio de verba pública"):
        await interaction.response.send_message("🚨 OPERAÇÃO LAVA JATO DEFLAGRADA! O desvio foi descoberto; bens confiscados e réu enviado à Papuda.")
    else:
        await interaction.response.send_message(f"✅ Desvio de **{formatar_reais(valor)}** concluído sem operação nesta ocasião.")
    salvar_dados()


stf_group = app_commands.Group(name="stf", description="Supremo Tribunal Federal e Lava Jato")
stf_eleicao_group = app_commands.Group(name="eleicao", description="Eleição do Ministro do STF")
stf_group.add_command(stf_eleicao_group)


def stf_autorizado(interaction: discord.Interaction) -> bool:
    return (
        eh_admin_ou_dono(interaction)
        or DADOS_BOT["stf"].get("ministro") == interaction.user.id
        or tem_cargo(interaction, "👨 Ministro do STF", "Ministro do STF", "Ministro STF")
    )


def policial_autorizado(interaction: discord.Interaction) -> bool:
    usuario = obter_usuario(interaction.user.id)
    cargos_policiais = {
        normalizar_nome_cargo(nome)
        for nome in ("👮 Policial", "Policial", "🚓 Polícia", "Polícia")
    }
    return (
        contrato_emprego_ativo(usuario) and usuario.get("emprego") == "Policial"
    ) or bool(cargos_policiais.intersection(nomes_cargos(interaction)))


def investigador_autorizado(interaction: discord.Interaction) -> bool:
    return stf_autorizado(interaction) or policial_autorizado(interaction)


lavajato_group = app_commands.Group(name="lavajato", description="Denúncias, investigações e operações do RPG")
petrolao_group = app_commands.Group(name="petrolao", description="Escândalos da estatal e investigações do RPG")


@lavajato_group.command(name="denunciar", description="Abre um caso para apuração judicial no RPG")
@app_commands.choices(
    tipo=[
        app_commands.Choice(name="Rachadinha", value="rachadinha"),
        app_commands.Choice(name="Petrolão", value="petrolao"),
        app_commands.Choice(name="Desvio de verba", value="desvio"),
        app_commands.Choice(name="Abuso de poder", value="abuso"),
    ]
)
async def lavajato_denunciar(
    interaction: discord.Interaction,
    usuario: discord.Member,
    tipo: app_commands.Choice[str],
    motivo: str,
) -> None:
    if usuario.id == interaction.user.id or usuario.bot:
        await interaction.response.send_message("⚠️ Selecione outro membro do servidor.", ephemeral=True)
        return
    if not 5 <= len(motivo.strip()) <= 300:
        await interaction.response.send_message("⚠️ Descreva a denúncia em 5 a 300 caracteres.", ephemeral=True)
        return
    caso, criado = abrir_caso_lava_jato(
        interaction.user.id,
        usuario.id,
        tipo.value,
        motivo,
    )
    if not criado:
        await interaction.response.send_message(
            f"ℹ️ Já existe um caso aberto desse tipo contra esse membro: **#{caso['id']}**.",
            ephemeral=True,
        )
        return
    registrar_noticia("Denúncia recebida", f"Um caso de {tipo.name} contra {usuario.display_name} aguarda investigação.")
    await interaction.response.send_message(
        f"📨 Denúncia registrada como caso **#{caso['id']}**. Ela não aplica punição automaticamente; "
        "Polícia, Ministro do STF ou administração pode investigar e reunir provas."
    )


@lavajato_group.command(name="investigar", description="Polícia, Justiça ou administração reúne provas de um caso")
async def lavajato_investigar(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not investigador_autorizado(interaction):
        await interaction.response.send_message("❌ Apenas a Polícia, o Ministro do STF, administradores ou o dono do bot podem investigar.", ephemeral=True)
        return
    casos = DADOS_BOT.setdefault("lava_jato", {"casos": []}).setdefault("casos", [])
    caso = next(
        (item for item in reversed(casos) if item.get("aberto", True) and int(item.get("usuario_id", 0)) == usuario.id),
        None,
    )
    if caso is None:
        await interaction.response.send_message("ℹ️ Não há caso aberto contra esse membro.", ephemeral=True)
        return

    agora = time.time()
    ultima = float(caso.setdefault("ultima_investigacao", {}).get(str(interaction.user.id), 0))
    intervalo = 6 * 60 * 60
    restante = intervalo - (agora - ultima)
    if restante > 0:
        horas, segundos = divmod(int(restante), 3600)
        await interaction.response.send_message(
            f"⏳ Aguarde **{horas}h {segundos // 60}min** antes de investigar esse caso novamente.",
            ephemeral=True,
        )
        return

    caso["ultima_investigacao"][str(interaction.user.id)] = agora
    caso["evidencias"] = min(3, int(caso.get("evidencias", 0)) + 1)
    salvar_dados()
    registrar_noticia("Investigação avançou", f"O caso #{caso['id']} contra {usuario.display_name} ganhou uma nova prova.")
    await interaction.response.send_message(
        f"🔎 Investigação do caso **#{caso['id']}** avançou: **{caso['evidencias']}/3 provas**. "
        "São necessárias 2 provas para autorizar uma operação."
    )


@lavajato_group.command(name="operacao", description="Executa uma operação após reunir provas suficientes")
async def lavajato_operacao(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not stf_autorizado(interaction):
        await interaction.response.send_message("❌ Apenas a Justiça, administradores ou o dono do bot podem autorizar operações.", ephemeral=True)
        return
    casos = DADOS_BOT.setdefault("lava_jato", {"casos": []}).setdefault("casos", [])
    caso = next(
        (item for item in reversed(casos) if item.get("aberto", True) and int(item.get("usuario_id", 0)) == usuario.id),
        None,
    )
    if caso is None:
        await interaction.response.send_message("ℹ️ Não há caso aberto contra esse membro.", ephemeral=True)
        return
    if int(caso.get("evidencias", 0)) < 2:
        await interaction.response.send_message(
            f"⚠️ O caso **#{caso['id']}** só tem **{caso.get('evidencias', 0)}/2 provas**. "
            "Use `/lavajato investigar` antes de autorizar a operação.",
            ephemeral=True,
        )
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando dentro do servidor.", ephemeral=True)
        return

    await enviar_lava_jato(
        interaction.guild,
        {usuario.id},
        f"Operação do RPG — caso #{caso['id']} ({caso['tipo']}): {caso['motivo']}",
    )
    caso["aberto"] = False
    caso["encerrado_em"] = datetime.now(timezone.utc).isoformat()
    caso["resultado"] = "operacao"
    salvar_dados()
    registrar_noticia("Operação autorizada", f"A Justiça autorizou uma operação no caso #{caso['id']} contra {usuario.display_name}.")
    await interaction.response.send_message(
        f"🚨 Operação do RPG autorizada no caso **#{caso['id']}** contra {usuario.mention}. "
        "O caso foi encaminhado ao STF para julgamento."
    )


@lavajato_group.command(name="painel", description="Lista casos abertos e o andamento das investigações")
async def lavajato_painel(interaction: discord.Interaction) -> None:
    casos = [
        caso for caso in DADOS_BOT.get("lava_jato", {}).get("casos", [])
        if caso.get("aberto", True)
    ][-10:]
    if not casos:
        await interaction.response.send_message("✅ Não há casos abertos no momento.")
        return
    linhas = [
        f"**#{caso.get('id')} · {str(caso.get('tipo', 'caso')).title()}** — "
        f"<@{caso.get('usuario_id')}> · 🔎 {int(caso.get('evidencias', 0))}/3 provas\n"
        f"_{str(caso.get('motivo', 'Sem descrição'))[:180]}_"
        for caso in reversed(casos)
    ]
    embed = discord.Embed(title="⚖️ Casos abertos da Lava Jato", description="\n\n".join(linhas), color=discord.Color.dark_red())
    await interaction.response.send_message(embed=embed)


@petrolao_group.command(name="denunciar", description="Registra uma denúncia sobre a estatal no RPG")
async def petrolao_denunciar(
    interaction: discord.Interaction,
    usuario: discord.Member,
    motivo: str,
) -> None:
    if usuario.id == interaction.user.id or usuario.bot:
        await interaction.response.send_message("⚠️ Selecione outro membro do servidor.", ephemeral=True)
        return
    if not 5 <= len(motivo.strip()) <= 300:
        await interaction.response.send_message("⚠️ Descreva a denúncia em 5 a 300 caracteres.", ephemeral=True)
        return
    caso, criado = abrir_caso_lava_jato(
        interaction.user.id,
        usuario.id,
        "petrolao",
        motivo,
    )
    if not criado:
        await interaction.response.send_message(
            f"ℹ️ Já existe um caso de Petrolão aberto contra esse membro: **#{caso['id']}**.",
            ephemeral=True,
        )
        return
    registrar_noticia("Denúncia do Petrolão", f"Uma denúncia sobre a estatal contra {usuario.display_name} aguarda apuração.")
    await interaction.response.send_message(
        f"🛢️ Denúncia registrada como caso **#{caso['id']}**. Para apurar, a Justiça pode usar `/lavajato investigar`."
    )


@petrolao_group.command(name="balanco", description="Consulta o caixa público da estatal e casos do Petrolão")
async def petrolao_balanco(interaction: discord.Interaction) -> None:
    petrobras = DADOS_BOT["petrobras"]
    acoes = petrobras.get("acoes", {})
    casos_abertos = [
        caso for caso in DADOS_BOT.get("lava_jato", {}).get("casos", [])
        if caso.get("aberto", True) and caso.get("tipo") == "petrolao"
    ]
    embed = discord.Embed(title="🛢️ Balanço público da Petrobras (RPG)", color=discord.Color.dark_teal())
    embed.add_field(name="Caixa da estatal", value=formatar_reais(int(petrobras.get("cofre", 0))))
    embed.add_field(name="Preço de referência", value=formatar_reais(int(petrobras.get("preco_refino", 0))))
    embed.add_field(name="Acionistas", value=str(len(acoes)))
    embed.add_field(name="Denúncias do Petrolão abertas", value=str(len(casos_abertos)))
    await interaction.response.send_message(embed=embed)


async def definir_ministro_stf(guild: discord.Guild, ministro: discord.Member) -> None:
    cargo_nome = "👨 Ministro do STF"
    cargo = await obter_ou_criar_cargo(guild, cargo_nome)

    ministro_atual = DADOS_BOT["stf"].get("ministro")
    if ministro_atual is not None and int(ministro_atual) != ministro.id:
        membro_atual = guild.get_member(int(ministro_atual))
        if membro_atual is None:
            try:
                membro_atual = await guild.fetch_member(int(ministro_atual))
            except discord.NotFound:
                membro_atual = None
        if membro_atual is not None and cargo in membro_atual.roles:
            await membro_atual.remove_roles(cargo, reason="Substituição do Ministro do STF")

    if cargo not in ministro.roles:
        await ministro.add_roles(cargo, reason="Nomeação para Ministro do STF")
    DADOS_BOT["stf"]["ministro"] = ministro.id
    salvar_dados()


@stf_group.command(name="mandado", description="Emite mandado e envia o alvo para a Papuda")
async def stf_mandado(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not stf_autorizado(interaction):
        await interaction.response.send_message("❌ Ação exclusiva do Ministro do STF, administração ou dono do bot.", ephemeral=True)
        return
    alvo = obter_usuario(usuario.id)
    alvo["prisao"] = max(3, int(alvo["prisao"]))
    alvo["status"] = "Preso"
    alvo["preso"] = True
    alvo["preso_ate"] = 0
    alvo["prisao_guild_id"] = None
    await adicionar_cargo(interaction.guild, usuario.id, "🚔 Papuda")
    salvar_dados()
    embed = discord.Embed(
        title="⚖️ Mandado judicial cumprido",
        description=f"{usuario.mention} foi enviado(a) à Papuda.",
        color=discord.Color.dark_red(),
    )
    embed.set_image(url=GIFS["stf"])
    await interaction.response.send_message(embed=embed)


@stf_group.command(name="julgar", description="Julga um investigado da Lava Jato")
async def stf_julgar(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not stf_autorizado(interaction):
        await interaction.response.send_message("❌ Ação exclusiva do Ministro do STF, administração ou dono do bot.", ephemeral=True)
        return
    if not checar_investigacao(usuario.id):
        await interaction.response.send_message("ℹ️ Essa pessoa não consta como investigada pela Lava Jato.", ephemeral=True)
        return
    alvo = obter_usuario(usuario.id)
    if random.random() < 0.50:
        alvo["prisao"] = max(1, int(alvo["prisao"]))
        alvo["status"] = "Preso"
        resultado = f"⚖️ {usuario.mention} foi condenado e permanece na Papuda."
    else:
        alvo["prisao"] = 0
        alvo["preso"] = False
        alvo["preso_ate"] = 0
        alvo["prisao_guild_id"] = None
        alvo["status"] = "Inadimplente" if int(alvo.get("saldo", 0)) < 0 else "Livre"
        alvo["investigado"] = False
        DADOS_BOT["stf"]["investigacoes"] = [
            caso for caso in DADOS_BOT["stf"]["investigacoes"]
            if caso.get("usuario_id") != usuario.id
        ]
        role = buscar_cargo(interaction.guild, "🚔 Papuda") if interaction.guild else None
        if role and isinstance(usuario, discord.Member) and role in usuario.roles:
            await usuario.remove_roles(role, reason="Absolvição pelo STF")
        resultado = f"⚖️ {usuario.mention} foi absolvido(a) e liberado(a)."
    salvar_dados()
    embed = discord.Embed(title="⚖️ Decisão do Supremo Tribunal Federal", description=resultado, color=discord.Color.dark_purple())
    embed.set_image(url=GIFS["stf"])
    await interaction.response.send_message(embed=embed)


@stf_group.command(name="sortear", description="Sorteia um Ministro do STF entre os membros do servidor")
async def stf_sortear(interaction: discord.Interaction) -> None:
    if not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas administradores ou o dono podem sortear o Ministro.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    membros = [member for member in interaction.guild.members if not member.bot]
    if not membros:
        await interaction.response.send_message("❌ Não há membros elegíveis para o sorteio.", ephemeral=True)
        return
    ministro = random.choice(membros)
    await definir_ministro_stf(interaction.guild, ministro)
    await interaction.response.send_message(f"🎲 {ministro.mention} foi sorteado(a) Ministro(a) do STF.")


@stf_group.command(name="nomear", description="Nomeia o Ministro do STF")
async def stf_nomear(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas administradores ou o dono podem nomear o Ministro.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    await definir_ministro_stf(interaction.guild, usuario)
    await interaction.response.send_message(f"✅ {usuario.mention} foi nomeado(a) Ministro(a) do STF.")


@stf_eleicao_group.command(name="iniciar", description="Abre a votação para Ministro do STF")
async def stf_eleicao_iniciar(interaction: discord.Interaction) -> None:
    if not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas administradores ou o dono podem iniciar a eleição.", ephemeral=True)
        return
    eleicao = DADOS_BOT["stf"].setdefault("eleicao", {"aberta": False, "votos": {}})
    if eleicao.get("aberta"):
        await interaction.response.send_message("ℹ️ Já existe uma eleição do STF em andamento.", ephemeral=True)
        return
    eleicao["aberta"] = True
    eleicao["votos"] = {}
    salvar_dados()
    await interaction.response.send_message("🗳️ Eleição do Ministro do STF aberta! Use `/stf eleicao votar` para votar em um membro.")


@stf_eleicao_group.command(name="votar", description="Vota em um membro para Ministro do STF")
async def stf_eleicao_votar(interaction: discord.Interaction, candidato: discord.Member) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    eleicao = DADOS_BOT["stf"].setdefault("eleicao", {"aberta": False, "votos": {}})
    if not eleicao.get("aberta"):
        await interaction.response.send_message("ℹ️ Não há eleição do STF aberta no momento.", ephemeral=True)
        return
    if candidato.bot:
        await interaction.response.send_message("⚠️ Bots não podem ser candidatos a Ministro do STF.", ephemeral=True)
        return
    votos = eleicao.setdefault("votos", {})
    eleitor_id = str(interaction.user.id)
    if eleitor_id in votos:
        await interaction.response.send_message("ℹ️ Você já votou nesta eleição.", ephemeral=True)
        return
    votos[eleitor_id] = candidato.id
    salvar_dados()
    await interaction.response.send_message(f"✅ Seu voto em {candidato.mention} foi registrado.", ephemeral=True)


@stf_eleicao_group.command(name="encerrar", description="Encerra a votação e nomeia o vencedor")
async def stf_eleicao_encerrar(interaction: discord.Interaction) -> None:
    if not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas administradores ou o dono podem encerrar a eleição.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    eleicao = DADOS_BOT["stf"].setdefault("eleicao", {"aberta": False, "votos": {}})
    if not eleicao.get("aberta"):
        await interaction.response.send_message("ℹ️ Não há eleição do STF aberta no momento.", ephemeral=True)
        return
    votos_por_candidato: dict[int, int] = {}
    for candidato_id in eleicao.get("votos", {}).values():
        candidato_id = int(candidato_id)
        votos_por_candidato[candidato_id] = votos_por_candidato.get(candidato_id, 0) + 1
    if not votos_por_candidato:
        await interaction.response.send_message("⚠️ Ainda não há votos. A eleição continua aberta.", ephemeral=True)
        return
    maior_votacao = max(votos_por_candidato.values())
    vencedores = [candidato_id for candidato_id, total in votos_por_candidato.items() if total == maior_votacao]
    if len(vencedores) > 1:
        mencoes = ", ".join(f"<@{candidato_id}>" for candidato_id in vencedores)
        await interaction.response.send_message(
            f"⚖️ Há empate entre {mencoes}. A votação continua aberta para desempate."
        )
        return
    candidato = interaction.guild.get_member(vencedores[0])
    if candidato is None:
        try:
            candidato = await interaction.guild.fetch_member(vencedores[0])
        except discord.NotFound:
            candidato = None
    if candidato is None:
        await interaction.response.send_message(
            "❌ O candidato vencedor não está mais no servidor. A votação continua aberta.",
            ephemeral=True,
        )
        return
    await definir_ministro_stf(interaction.guild, candidato)
    eleicao["aberta"] = False
    salvar_dados()
    await interaction.response.send_message(
        f"⚖️ {candidato.mention} foi eleito(a) Ministro(a) do STF com **{maior_votacao}** voto(s)!"
    )


@stf_group.command(name="derrubar", description="Congela uma facção")
async def stf_derrubar(interaction: discord.Interaction, faccao: str) -> None:
    if not stf_autorizado(interaction):
        await interaction.response.send_message("❌ Ação exclusiva do Ministro do STF, administração ou dono do bot.", ephemeral=True)
        return
    dados_faccao = DADOS_BOT["faccoes"].get(faccao.casefold())
    if not dados_faccao:
        await interaction.response.send_message("❌ Facção não encontrada.", ephemeral=True)
        return
    dados_faccao["congelada"] = True
    dados_faccao["saldos"] = 0
    salvar_dados()
    await interaction.response.send_message(f"🧊 A facção **{faccao}** foi congelada e seus saldos foram bloqueados.")


@tree.command(name="bet", description="Aposte seu saldo em um jogo de sorte")
async def bet(interaction: discord.Interaction, valor: int) -> None:
    usuario = obter_usuario(interaction.user.id)
    if valor <= 0:
        await interaction.response.send_message("⚠️ O valor da aposta deve ser positivo.")
        return
    if usuario["saldo"] < valor:
        await interaction.response.send_message("❌ Saldo insuficiente para essa aposta.")
        return

    chance = random.random()
    if chance < 0.50:
        ganho = valor * random.randint(2, 5)
        adicionar_saldo(interaction.user.id, ganho)
        await interaction.response.send_message(f"🎉 {interaction.user.mention} ganhou a aposta e recebeu **{formatar_reais(ganho)}**.")
    else:
        remover_saldo(interaction.user.id, valor)
        if usuario["saldo"] < 0:
            usuario["status"] = "Inadimplente"
            juros = abs(usuario["saldo"]) * 0.20
            adicionar_saldo(interaction.user.id, int(juros))
            await interaction.response.send_message(
                f"💸 {interaction.user.mention} perdeu a aposta, ficou negativado e agora está **Inadimplente**. Juros aplicados: **{formatar_reais(int(juros))}**."
            )
        else:
            await interaction.response.send_message(f"💥 {interaction.user.mention} perdeu a aposta e foi descontado **{formatar_reais(valor)}**.")
    salvar_dados()


rachadinha_group = app_commands.Group(name="rachadinha", description="Assessores fantasmas e rachadinhas")


def eh_politico(interaction: discord.Interaction) -> bool:
    return tem_cargo(
        interaction,
        "👑 Presidente", "📜 Governador", "🏛️ Deputado", "🏛️ Senador", "🏙️ Prefeito",
        "Presidente", "Governador", "Deputado", "Senador", "Prefeito",
    )


@rachadinha_group.command(name="contratar", description="Contrata um assessor fantasma")
async def rachadinha_contratar(interaction: discord.Interaction, usuario: discord.Member) -> None:
    user = obter_usuario(interaction.user.id)
    if not eh_politico(interaction):
        await interaction.response.send_message("❌ Só políticos eleitos podem contratar assessores fantasmas.")
        return
    if usuario.id == interaction.user.id or usuario.bot:
        await interaction.response.send_message("⚠️ Escolha outra pessoa que não seja um bot.", ephemeral=True)
        return
    DADOS_BOT["rachadinhas"][str(interaction.user.id)] = {"assessor_id": usuario.id, "ativo": True}
    salvar_dados()
    await interaction.response.send_message(f"✅ {interaction.user.mention} contratou {usuario.mention} como assessor fantasma.")


@rachadinha_group.command(name="status", description="Consulta seu assessor fantasma")
async def rachadinha_status(interaction: discord.Interaction) -> None:
    info = DADOS_BOT["rachadinhas"].get(str(interaction.user.id))
    if not info or not info.get("ativo", True):
        await interaction.response.send_message("❌ Você não possui assessor fantasma ativo.", ephemeral=True)
        return
    membro = interaction.guild.get_member(info["assessor_id"]) if interaction.guild else None
    mencao = membro.mention if membro else f"<@{info['assessor_id']}>"
    await interaction.response.send_message(f"📌 Seu assessor ativo é: {mencao}")


@rachadinha_group.command(name="cancelar", description="Encerra seu contrato de assessor fantasma")
async def rachadinha_cancelar(interaction: discord.Interaction) -> None:
    contrato = DADOS_BOT["rachadinhas"].get(str(interaction.user.id))
    if not contrato or not contrato.get("ativo", True):
        await interaction.response.send_message("ℹ️ Você não tem uma rachadinha ativa para encerrar.", ephemeral=True)
        return
    contrato["ativo"] = False
    contrato["encerrado_em"] = datetime.now(timezone.utc).isoformat()
    salvar_dados()
    registrar_noticia("Contrato encerrado", f"{interaction.user.display_name} encerrou seu esquema de assessor fantasma.")
    await interaction.response.send_message("🧾 Contrato encerrado. Não haverá novos repasses nas próximas folhas.")


@rachadinha_group.command(name="denunciar", description="Denuncia uma rachadinha ativa para investigação no RPG")
async def rachadinha_denunciar(interaction: discord.Interaction, politico: discord.Member) -> None:
    if politico.id == interaction.user.id:
        await interaction.response.send_message("⚠️ Você não pode denunciar a si mesmo.", ephemeral=True)
        return
    contrato = DADOS_BOT["rachadinhas"].get(str(politico.id))
    if not contrato or not contrato.get("ativo", True):
        await interaction.response.send_message("ℹ️ Esse político não tem um contrato de assessor ativo.", ephemeral=True)
        return
    caso, criado = abrir_caso_lava_jato(
        interaction.user.id,
        politico.id,
        "rachadinha",
        "Denúncia de assessor fantasma e repasse irregular.",
    )
    if not criado:
        await interaction.response.send_message(
            f"ℹ️ Já existe um caso aberto para essa denúncia (caso **#{caso['id']}**).",
            ephemeral=True,
        )
        return
    registrar_noticia(
        "Denúncia de rachadinha",
        f"Uma denúncia contra {politico.display_name} foi encaminhada para apuração.",
    )
    await interaction.response.send_message(
        f"🕵️ Denúncia registrada como caso **#{caso['id']}**. A Justiça pode apurar com `/lavajato investigar`."
    )


@tree.command(name="crime", description="Cometa crimes com diferentes chances de prisão")
@app_commands.choices(
    acao=[
        app_commands.Choice(name="Roubar (15% de prisão)", value="roubar"),
        app_commands.Choice(name="Ameaçar (20% de prisão)", value="ameacar"),
        app_commands.Choice(name="Homicídio (50% de prisão)", value="matar"),
        app_commands.Choice(name="Fraude (10% de prisão)", value="fraudar"),
        app_commands.Choice(name="Contrabando (25% de prisão)", value="contrabandear"),
        app_commands.Choice(name="Vandalismo (10% de prisão)", value="vandalizar"),
    ]
)
async def crime(interaction: discord.Interaction, acao: str, alvo: discord.Member | None = None) -> None:
    usuario = obter_usuario(interaction.user.id)
    if usuario["prisao"] > 0:
        await interaction.response.send_message("🚫 Você está preso e não pode agir.")
        return

    chances_sucesso = {
        "roubar": 0.85,
        "ameacar": 0.80,
        "matar": 0.50,
        "fraudar": 0.90,
        "contrabandear": 0.75,
        "vandalizar": 0.90,
    }
    if acao not in chances_sucesso:
        await interaction.response.send_message("⚠️ Selecione uma das ações disponíveis no comando.")
        return

    nomes_crimes = {
        "roubar": "roubo",
        "ameacar": "ameaça",
        "matar": "tentativa de homicídio",
        "fraudar": "fraude",
        "contrabandear": "contrabando",
        "vandalizar": "vandalismo",
    }
    if random.random() >= chances_sucesso[acao]:
        usuario["prisao"] += 3 if acao == "matar" else 1
        usuario["status"] = "Preso"
        await adicionar_cargo(interaction.guild, interaction.user.id, "🚔 Papuda")
        registrar_ocorrencia_crime(interaction.user.id, acao, nomes_crimes[acao], flagrante=True)
        await interaction.response.send_message(
            f"🚨 {interaction.user.mention} foi pego(a) ao tentar cometer {nomes_crimes[acao]} e foi preso(a) na Papuda."
        )
        salvar_dados()
        return

    recompensas = {
        "roubar": (1500, 12000),
        "ameacar": (1000, 8000),
        "matar": (20000, 95000),
        "fraudar": (4000, 20000),
        "contrabandear": (8000, 30000),
    }
    if acao == "vandalizar":
        resultado = f"🎨 {interaction.user.mention} vandalizou um local e escapou sem ser pego(a)."
    else:
        valor = random.randint(*recompensas[acao])
        usuario["saldo_sujo"] += valor
        descricoes = {
            "roubar": "roubou",
            "ameacar": "ameaçou e extorquiu",
            "matar": "concluiu o serviço",
            "fraudar": "aplicou uma fraude e embolsou",
            "contrabandear": "vendeu contrabando e embolsou",
        }
        resultado = (
            f"💰 {interaction.user.mention} {descricoes[acao]} "
            f"**{formatar_reais(valor)}** com sucesso."
        )
    registrar_ocorrencia_crime(interaction.user.id, acao, nomes_crimes[acao], flagrante=False)
    await interaction.response.send_message(resultado)
    salvar_dados()


@tree.command(name="loja", description="Compra itens, veículos e empresas")
async def loja(interaction: discord.Interaction, acao: str, item: str = "") -> None:
    usuario = obter_usuario(interaction.user.id)
    if usuario["status"] == "Inadimplente":
        await interaction.response.send_message("❌ Você está inadimplente e não pode comprar itens na loja.")
        return

    if acao == "listar":
        itens = "\n".join(
            f"- {NOMES_ITENS_LOJA[nome]}: {formatar_reais(preco_loja(nome))}"
            for nome in LOJA_ITEMS
        )
        await interaction.response.send_message(f"🛒 Loja do servidor:\n{itens}")
        return

    if acao == "comprar":
        item = item.lower().strip()
        resultado = comprar_item(interaction.user.id, item)
        await interaction.response.send_message(f"{interaction.user.mention}\n{resultado}")
        return

    await interaction.response.send_message("⚠️ Use `listar` ou `comprar [item]`.")


def comprar_item(usuario_id: int, item: str) -> str:
    usuario = obter_usuario(usuario_id)
    if usuario["status"] == "Inadimplente":
        return "❌ Você está inadimplente e não pode comprar itens na loja."
    if item not in LOJA_ITEMS:
        return "⚠️ Selecione um item válido da loja."

    preco = preco_loja(item)
    if usuario["saldo"] < preco:
        return f"❌ Saldo insuficiente para comprar **{NOMES_ITENS_LOJA[item]}**."
    usuario["saldo"] -= preco
    if item in {"posto", "emissora"}:
        usuario["empresas"][item] += 1
    else:
        usuario["itens"][item] += 1
    DADOS_BOT["cofre_publico"] += int(preco * 0.15)
    salvar_dados()
    return f"✅ Compra concluída: **{NOMES_ITENS_LOJA[item]}** por **{formatar_reais(preco)}**."


@tree.command(name="inventario", description="Mostra os itens que você possui")
async def inventario(interaction: discord.Interaction) -> None:
    usuario = obter_usuario(interaction.user.id)
    itens = usuario["itens"]
    texto = "\n".join(f"- {nome}: {quantidade}" for nome, quantidade in itens.items())
    empresas = usuario.get("empresas", {})
    texto += "\n" + "\n".join(f"- Empresa {nome}: {quantidade}" for nome, quantidade in empresas.items())
    embed = embed_resultado(
        titulo="Inventário",
        descricao=f"{interaction.user.mention}\n{texto}",
        cor=discord.Color.magenta(),
        gif=GIFS["dinheiro"],
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="faccao", description="Cria, entra ou convida para facções")
async def faccao(interaction: discord.Interaction, acao: str, nome: str = "", usuario: discord.Member | None = None) -> None:
    if acao == "criar":
        if not nome:
            await interaction.response.send_message("⚠️ Informe um nome para a facção.")
            return
        if nome.lower() in DADOS_BOT["faccoes"]:
            await interaction.response.send_message("❌ Essa facção já existe.")
            return
        valor = 5000
        usuario_local = obter_usuario(interaction.user.id)
        if usuario_local["saldo"] < valor:
            await interaction.response.send_message("❌ Você não tem saldo suficiente para criar uma facção.")
            return
        remover_saldo(interaction.user.id, valor)
        DADOS_BOT["cofre_publico"] += valor
        DADOS_BOT["faccoes"][nome.lower()] = {
            "lider": interaction.user.id,
            "membros": [interaction.user.id],
            "saldos": 0,
            "dinheiro_sujo": 0,
            "congelada": False,
        }
        salvar_dados()
        await interaction.response.send_message(f"✅ A facção **{nome}** foi criada por {interaction.user.mention}.")
        return

    if acao == "convidar":
        if not nome:
            await interaction.response.send_message("⚠️ Informe o nome da facção.")
            return
        if usuario is None:
            await interaction.response.send_message("⚠️ Indique o usuário a ser convidado.")
            return
        fac = DADOS_BOT["faccoes"].get(nome.lower())
        if not fac or fac["lider"] != interaction.user.id:
            await interaction.response.send_message("❌ Você não é o líder dessa facção.")
            return
        fac["membros"].append(usuario.id)
        salvar_dados()
        await interaction.response.send_message(f"✅ {usuario.mention} foi convidado para **{nome}**.")
        return

    if acao == "entrar":
        if not nome:
            await interaction.response.send_message("⚠️ Informe o nome da facção.")
            return
        fac = DADOS_BOT["faccoes"].get(nome.lower())
        if not fac:
            await interaction.response.send_message("❌ Facção não encontrada.")
            return
        if interaction.user.id not in fac["membros"]:
            fac["membros"].append(interaction.user.id)
            obter_usuario(interaction.user.id)["faccao"] = nome.lower()
            salvar_dados()
            await interaction.response.send_message(f"✅ {interaction.user.mention} entrou na facção **{nome}**.")
            return
        await interaction.response.send_message("⚠️ Você já faz parte dessa facção.")
        return

    await interaction.response.send_message("⚠️ Ações válidas: `criar`, `convidar`, `entrar`.")


emprego_group = app_commands.Group(name="emprego", description="Profissões e rotina de trabalho")


def escolher_profissao(interaction: discord.Interaction, profissao: str) -> str:
    usuario = obter_usuario(interaction.user.id)
    if usuario["ultimo_cargo"] != "Trabalhador" and not tem_cargo(interaction, "🛠️ Trabalhador", "Trabalhador"):
        return "❌ Só quem tirou o cargo de Trabalhador pode assinar contratos de emprego."
    if profissao not in SALARIOS:
        return "⚠️ Selecione uma profissão válida."
    if contrato_emprego_ativo(usuario):
        return (
            f"ℹ️ Você já tem contrato ativo como **{usuario['emprego']}**. "
            "Peça demissão ou quebre o contrato antes de assinar outro."
        )
    usuario["emprego"] = profissao
    usuario["emprego_ativo"] = True
    usuario["emprego_assinado_em"] = datetime.now(timezone.utc).isoformat()
    usuario["emprego_encerrado_em"] = None
    salvar_dados()
    return f"✅ {interaction.user.mention} assinou contrato como **{profissao}**."


def encerrar_contrato_emprego(user_id: int, quebrar: bool) -> str:
    usuario = obter_usuario(user_id)
    if not contrato_emprego_ativo(usuario):
        return "ℹ️ Você não tem um contrato de trabalho ativo."
    multa = max(0, int(usuario.get("saldo", 0))) // 10 if quebrar else 0
    if multa:
        remover_saldo(user_id, multa)
    usuario["emprego_ativo"] = False
    usuario["emprego_encerrado_em"] = datetime.now(timezone.utc).isoformat()
    salvar_dados()
    if quebrar:
        return f"📄 Contrato quebrado. Multa de 10% do seu saldo positivo: **{formatar_reais(multa)}**."
    return f"✅ Demissão registrada. Contrato encerrado sem multa; sua profissão anterior era **{usuario['emprego']}**."


@emprego_group.command(name="profissao", description="Assina contrato de trabalho após conseguir Trabalhador")
@app_commands.choices(
    profissao=[
        app_commands.Choice(name=f"{nome} — {formatar_reais(salario)}/48h", value=nome)
        for nome, salario in SALARIOS.items()
    ]
)
async def emprego_profissao(interaction: discord.Interaction, profissao: str) -> None:
    resultado = escolher_profissao(interaction, profissao)
    await interaction.response.send_message(resultado)


@emprego_group.command(name="pedir_demissao", description="Encerra seu contrato de trabalho sem multa")
async def emprego_pedir_demissao(interaction: discord.Interaction) -> None:
    resultado = encerrar_contrato_emprego(interaction.user.id, quebrar=False)
    await interaction.response.send_message(resultado)


@emprego_group.command(name="quebrar_contrato", description="Encerra seu contrato pagando multa de 10% do saldo")
async def emprego_quebrar_contrato(interaction: discord.Interaction) -> None:
    resultado = encerrar_contrato_emprego(interaction.user.id, quebrar=True)
    await interaction.response.send_message(resultado)


petrobras_group = app_commands.Group(name="petrobras", description="Estatal, refino, ações e dividendos")


def eh_presidente_petrobras(interaction: discord.Interaction) -> bool:
    return (
        usuario_eh_godmode(interaction.user.id)
        or DADOS_BOT["petrobras"].get("presidente") == interaction.user.id
        or tem_cargo(interaction, "Presidente da Petrobras", "🏭 Presidente da Petrobras")
    )


@petrobras_group.command(name="indicar", description="Indica o Presidente da Petrobras")
async def petrobras_indicar(interaction: discord.Interaction, usuario: discord.Member) -> None:
    if not tem_cargo(interaction, "Presidente", "👑 Presidente", "Presidente da República"):
        await interaction.response.send_message("❌ Apenas o Presidente da República pode indicar o comando da Petrobras.", ephemeral=True)
        return
    DADOS_BOT["petrobras"]["presidente"] = usuario.id
    await adicionar_cargo(interaction.guild, usuario.id, "🏭 Presidente da Petrobras")
    salvar_dados()
    await interaction.response.send_message(f"✅ {usuario.mention} foi indicado(a) Presidente da Petrobras.")


@petrobras_group.command(name="reajustar", description="Altera o preço de refino e o rendimento das ações")
async def petrobras_reajustar(interaction: discord.Interaction, preco: app_commands.Range[int, 10, 10000]) -> None:
    if not eh_presidente_petrobras(interaction):
        await interaction.response.send_message("❌ Ação exclusiva da Presidência da Petrobras.", ephemeral=True)
        return
    anterior = DADOS_BOT["petrobras"].get("preco_refino", 100)
    DADOS_BOT["petrobras"]["preco_refino"] = preco
    salvar_dados()
    await interaction.response.send_message(
        f"⛽ Refino reajustado de **{formatar_reais(anterior)}** para **{formatar_reais(preco)}**. "
        f"O dividendo por ação agora rende **{formatar_reais(max(1, preco // 10))}**; preços de transporte foram atualizados."
    )


@petrobras_group.command(name="comprar_acoes", description="Compra ações e participa dos dividendos")
async def petrobras_comprar_acoes(interaction: discord.Interaction, quantidade: app_commands.Range[int, 1, 10000]) -> None:
    preco_unitario = max(100, int(DADOS_BOT["petrobras"].get("preco_refino", 100)) * 10)
    custo = quantidade * preco_unitario
    usuario = obter_usuario(interaction.user.id)
    if usuario["saldo"] < custo:
        await interaction.response.send_message(f"❌ Saldo insuficiente. Custo: **{formatar_reais(custo)}**.", ephemeral=True)
        return
    usuario["saldo"] -= custo
    DADOS_BOT["petrobras"]["cofre"] += custo
    acoes = DADOS_BOT["petrobras"].setdefault("acoes", {})
    acoes[str(interaction.user.id)] = int(acoes.get(str(interaction.user.id), 0)) + quantidade
    salvar_dados()
    await interaction.response.send_message(f"📈 Você comprou **{quantidade} ações** por **{formatar_reais(custo)}**.")


@petrobras_group.command(name="dividendos", description="Resgata os dividendos disponíveis das suas ações")
async def petrobras_dividendos(interaction: discord.Interaction) -> None:
    acoes = int(DADOS_BOT["petrobras"].get("acoes", {}).get(str(interaction.user.id), 0))
    dividendo = acoes * max(1, int(DADOS_BOT["petrobras"].get("preco_refino", 100)) // 10)
    if not acoes or DADOS_BOT["petrobras"]["cofre"] < dividendo:
        await interaction.response.send_message("ℹ️ Você não tem dividendos disponíveis ou o cofre da estatal está sem fundos.", ephemeral=True)
        return
    DADOS_BOT["petrobras"]["cofre"] -= dividendo
    adicionar_saldo(interaction.user.id, dividendo)
    salvar_dados()
    await interaction.response.send_message(f"💹 Dividendos pagos: **{formatar_reais(dividendo)}** por suas {acoes} ações.")


@petrobras_group.command(name="desviar", description="Tenta desviar dinheiro do cofre da estatal")
async def petrobras_desviar(interaction: discord.Interaction, valor: app_commands.Range[int, 1]) -> None:
    autorizado = eh_presidente_petrobras(interaction) or tem_cargo(interaction, "👑 Presidente", "Presidente")
    if not autorizado:
        await interaction.response.send_message("❌ Ação exclusiva do Presidente da República ou da Presidência da Petrobras.", ephemeral=True)
        return
    if DADOS_BOT["petrobras"]["cofre"] < valor:
        await interaction.response.send_message("❌ O cofre da estatal não tem esse valor.", ephemeral=True)
        return
    DADOS_BOT["petrobras"]["cofre"] -= valor
    obter_usuario(interaction.user.id)["saldo_sujo"] += valor
    operacao = await tentar_lava_jato(interaction.guild, {interaction.user.id}, "Desvio do cofre da Petrobras")
    salvar_dados()
    mensagem = "🚨 OPERAÇÃO LAVA JATO DEFLAGRADA! Valores confiscados e réu enviado à Papuda." if operacao else f"✅ **{formatar_reais(valor)}** desviados e registrados como dinheiro sujo."
    await interaction.response.send_message(mensagem)


estado_group = app_commands.Group(name="estado", description="Decretos e operações estaduais")


def eh_governador(interaction: discord.Interaction) -> bool:
    return tem_cargo(interaction, "Governador", "📜 Governador")


@estado_group.command(name="decreto", description="Publica um decreto estadual")
async def estado_decreto(interaction: discord.Interaction, texto: str) -> None:
    if not eh_governador(interaction):
        await interaction.response.send_message("❌ Apenas o Governador pode publicar decretos estaduais.", ephemeral=True)
        return
    if not texto_legal(texto):
        await interaction.response.send_message("⚠️ O texto do decreto deve ter entre 1 e 1000 caracteres.", ephemeral=True)
        return
    DADOS_BOT["decretos"].append({"autor_id": interaction.user.id, "texto": texto, "tipo": "estadual", "data": date.today().isoformat()})
    salvar_dados()
    await interaction.response.send_message(embed=discord.Embed(title="📜 Decreto Estadual", description=texto, color=discord.Color.teal()))


@estado_group.command(name="pm_operacao", description="Polícia Militar tenta apreender recursos de uma facção")
async def estado_pm_operacao(interaction: discord.Interaction, faccao: str) -> None:
    if not eh_governador(interaction):
        await interaction.response.send_message("❌ Apenas o Governador pode autorizar a operação.", ephemeral=True)
        return
    dados_faccao = DADOS_BOT["faccoes"].get(faccao.casefold())
    if not dados_faccao:
        await interaction.response.send_message("❌ Facção não encontrada.", ephemeral=True)
        return
    if random.random() < 0.50:
        apreendido = int(dados_faccao.get("dinheiro_sujo", dados_faccao.get("saldos", 0)))
        dados_faccao["dinheiro_sujo"] = 0
        dados_faccao["saldos"] = max(0, int(dados_faccao.get("saldos", 0)) - apreendido)
        DADOS_BOT["cofre_publico"] += apreendido
        mensagem = f"🚔 Operação concluída. Apreendidos **{formatar_reais(apreendido)}** da facção **{faccao}**."
    else:
        mensagem = f"🚨 A operação contra **{faccao}** não encontrou provas suficientes desta vez."
    salvar_dados()
    await interaction.response.send_message(mensagem)


cidade_group = app_commands.Group(name="cidade", description="Gestão do município e infraestrutura")


@cidade_group.command(name="repassar", description="Transfere verba pública geral para o cofre municipal")
async def cidade_repassar(interaction: discord.Interaction, valor: app_commands.Range[int, 1]) -> None:
    if not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas administradores podem fazer repasses ao município.", ephemeral=True)
        return
    if DADOS_BOT["cofre_publico"] < valor or interaction.guild is None:
        await interaction.response.send_message("❌ Cofre geral insuficiente ou comando fora de um servidor.", ephemeral=True)
        return
    DADOS_BOT["cofre_publico"] -= valor
    obter_servidor(interaction.guild.id)["cofre"] += valor
    salvar_dados()
    await interaction.response.send_message(f"🏦 **{formatar_reais(valor)}** repassados ao cofre municipal.")


@cidade_group.command(name="asfalto", description="Investe no asfalto e gera energia local")
async def cidade_asfalto(interaction: discord.Interaction) -> None:
    if not tem_cargo(interaction, "Prefeito", "🏙️ Prefeito"):
        await interaction.response.send_message("❌ Apenas o Prefeito pode autorizar obras municipais.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    cidade = obter_servidor(interaction.guild.id)
    custo = 5000
    if cidade["cofre"] < custo:
        await interaction.response.send_message("❌ Cofre municipal insuficiente. Um administrador pode usar `/cidade repassar`.", ephemeral=True)
        return
    cidade["cofre"] -= custo
    cidade["energia"] += 25
    usuario = obter_usuario(interaction.user.id)
    usuario["energia"] = min(100, int(usuario.get("energia", 100)) + 25)
    usuario["energia_local"] = int(usuario.get("energia_local", 0)) + 25
    salvar_dados()
    await interaction.response.send_message("🛣️ Asfalto concluído! A energia local recebeu bônus de 25 pontos.")


congresso_group = app_commands.Group(name="congresso", description="Propostas de emenda e votação legislativa")


def eh_legislador(interaction: discord.Interaction) -> bool:
    return tem_cargo(interaction, "Deputado", "Senador", "🏛️ Deputado", "🏛️ Senador")


@congresso_group.command(name="propor_pec", description="Apresenta uma PEC para votação do Legislativo")
async def congresso_propor_pec(interaction: discord.Interaction, texto: str) -> None:
    if not eh_legislador(interaction):
        await interaction.response.send_message("❌ Apenas Deputados e Senadores podem propor PECs.", ephemeral=True)
        return
    if not texto_legal(texto):
        await interaction.response.send_message("⚠️ O texto da PEC deve ter entre 1 e 1000 caracteres.", ephemeral=True)
        return
    propostas = DADOS_BOT["congresso"].setdefault("propostas", {})
    proposta_id = str(max([int(chave) for chave in propostas if str(chave).isdigit()] or [0]) + 1)
    propostas[proposta_id] = {"autor_id": interaction.user.id, "texto": texto, "sim": [], "nao": [], "aberta": True}
    salvar_dados()
    embed = discord.Embed(title=f"🏛️ PEC {proposta_id} em votação", description=texto, color=discord.Color.blue())
    embed.add_field(name="Como votar", value=f"Legisladores: `/congresso votar proposta:{proposta_id} voto:sim` ou `nao`.")
    await interaction.response.send_message(embed=embed)


@congresso_group.command(name="votar", description="Registra o voto de um Deputado ou Senador em uma PEC")
async def congresso_votar(interaction: discord.Interaction, proposta: str, voto: str) -> None:
    if not eh_legislador(interaction):
        await interaction.response.send_message("❌ A votação é exclusiva para Deputados e Senadores.", ephemeral=True)
        return
    voto = voto.casefold()
    if voto not in {"sim", "nao", "não"}:
        await interaction.response.send_message("⚠️ O voto deve ser `sim` ou `nao`.", ephemeral=True)
        return
    dados_proposta = DADOS_BOT["congresso"].get("propostas", {}).get(proposta)
    if not dados_proposta or not dados_proposta.get("aberta"):
        await interaction.response.send_message("❌ PEC inexistente ou votação encerrada.", ephemeral=True)
        return
    lista_votos = dados_proposta["sim"] if voto == "sim" else dados_proposta["nao"]
    outra_lista = dados_proposta["nao"] if voto == "sim" else dados_proposta["sim"]
    if interaction.user.id in lista_votos or interaction.user.id in outra_lista:
        await interaction.response.send_message("⚠️ Seu voto nesta PEC já foi registrado.", ephemeral=True)
        return
    lista_votos.append(interaction.user.id)
    salvar_dados()
    await interaction.response.send_message(f"🗳️ Voto **{voto}** registrado para a PEC {proposta}.", ephemeral=True)


@congresso_group.command(name="encerrar", description="Encerra a votação e aprova ou rejeita a PEC")
async def congresso_encerrar(interaction: discord.Interaction, proposta: str) -> None:
    if not eh_legislador(interaction):
        await interaction.response.send_message("❌ Ação exclusiva do Legislativo.", ephemeral=True)
        return
    dados_proposta = DADOS_BOT["congresso"].get("propostas", {}).get(proposta)
    if not dados_proposta or not dados_proposta.get("aberta"):
        await interaction.response.send_message("❌ PEC inexistente ou votação encerrada.", ephemeral=True)
        return
    if dados_proposta["autor_id"] != interaction.user.id and not eh_admin_ou_dono(interaction):
        await interaction.response.send_message("❌ Apenas o autor da PEC ou a administração pode encerrar a votação.", ephemeral=True)
        return
    dados_proposta["aberta"] = False
    aprovada = len(dados_proposta["sim"]) > len(dados_proposta["nao"])
    if aprovada:
        DADOS_BOT["decretos"].append({"autor_id": interaction.user.id, "texto": dados_proposta["texto"], "tipo": "PEC", "data": date.today().isoformat()})
    salvar_dados()
    resultado = "✅ aprovada" if aprovada else "❌ rejeitada"
    await interaction.response.send_message(f"🏛️ PEC {proposta} {resultado}: {len(dados_proposta['sim'])} votos sim, {len(dados_proposta['nao'])} votos não.")


empresa_group = app_commands.Group(name="empresa", description="Gestão de empresas e caixa empresarial")


@empresa_group.command(name="limpar_caixa", description="Lava dinheiro sujo em notas frias através de uma empresa")
async def empresa_limpar_caixa(interaction: discord.Interaction, valor: app_commands.Range[int, 1]) -> None:
    usuario = obter_usuario(interaction.user.id)
    empresas = usuario.get("empresas", {})
    if sum(int(qtd) for qtd in empresas.values()) <= 0:
        await interaction.response.send_message("❌ Você precisa possuir um Posto ou Emissora comprado na loja.", ephemeral=True)
        return
    if usuario.get("saldo_sujo", 0) < valor:
        await interaction.response.send_message("❌ Você não tem dinheiro sujo suficiente para essa operação.", ephemeral=True)
        return
    taxa = max(1, valor // 4)
    usuario["saldo_sujo"] -= valor
    adicionar_saldo(interaction.user.id, valor - taxa)
    salvar_dados()
    await interaction.response.send_message(
        f"🧾 Notas frias emitidas pela empresa. **{formatar_reais(valor - taxa)}** foram lavados; "
        f"{formatar_reais(taxa)} retidos como custo operacional."
    )


hospital_group = app_commands.Group(name="hospital", description="Serviços médicos do simulador")


@hospital_group.command(name="curar", description="Médico dá alta imediata a uma pessoa hospitalizada")
async def hospital_curar(interaction: discord.Interaction, usuario: discord.Member) -> None:
    resultado = await conceder_alta(interaction, usuario)
    await interaction.response.send_message(resultado, ephemeral=resultado.startswith(("❌", "ℹ️")))


async def conceder_alta(interaction: discord.Interaction, usuario: discord.Member) -> str:
    if not tem_cargo(interaction, "Médico"):
        return "❌ Apenas quem trabalha como Médico pode dar alta."
    alvo = obter_usuario(usuario.id)
    if alvo.get("hospital", 0) <= 0:
        return "ℹ️ Essa pessoa não está hospitalizada."
    alvo["hospital"] = 0
    if alvo["prisao"] <= 0:
        alvo["status"] = "Normal"
    if interaction.guild is not None:
        role = buscar_cargo(interaction.guild, "🏥 Hospitalizado")
        if role is not None and role in usuario.roles:
            await usuario.remove_roles(role, reason="Alta médica")
    salvar_dados()
    return f"🏥 {usuario.mention} recebeu alta médica."


cafe_group = app_commands.Group(name="cafe", description="Apoio aos trabalhadores")


@cafe_group.command(name="trazer", description="Estagiário recupera a energia dos Diretores Executivos")
async def cafe_trazer(interaction: discord.Interaction) -> None:
    if not tem_cargo(interaction, "☕ Estagiário", "Estagiário"):
        await interaction.response.send_message("❌ Apenas Estagiários podem trazer o café.", ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        return
    recuperados = []
    for member in interaction.guild.members:
        if member.bot or not any(
            normalizar_nome_cargo(role.name) == normalizar_nome_cargo("👔 Diretor Executivo")
            for role in member.roles
        ):
            continue
        obter_usuario(member.id)["energia"] = 100
        recuperados.append(member.mention)
    salvar_dados()
    await interaction.response.send_message("☕ Café servido. Energia recuperada: " + (", ".join(recuperados) or "nenhum Diretor estava no servidor."))


@tree.command(name="vadiar", description="Procura moedas, com risco de ser preso")
async def vadiar(interaction: discord.Interaction) -> None:
    usuario = obter_usuario(interaction.user.id)
    if usuario.get("ultimo_cargo") not in {"Vagabundo", "Nenhum"} or usuario.get("cargo_publico") != "Nenhum":
        await interaction.response.send_message("❌ `/vadiar` é exclusivo para Vagabundos ou pessoas sem ficha.", ephemeral=True)
        return
    if random.random() < 0.25:
        usuario["prisao"] = max(1, int(usuario.get("prisao", 0)))
        usuario["status"] = "Preso"
        await adicionar_cargo(interaction.guild, interaction.user.id, "🚔 Papuda")
        resultado = "🚔 Você foi pego procurando moedas e acabou na Papuda."
    else:
        moedas = random.randint(50, 800)
        adicionar_saldo(interaction.user.id, moedas)
        resultado = f"🪙 Você encontrou **{formatar_reais(moedas)}** pelo caminho."
    usuario["energia"] = max(0, int(usuario.get("energia", 100)) - 10)
    salvar_dados()
    await interaction.response.send_message(resultado)


PAGINAS_AJUDA = {
    "geral": (
        "Como usar",
        "Abra uma aba para ver comandos, parâmetros e permissões. No Discord, digite `/` e selecione o comando; "
        "nos comandos de grupo, escolha primeiro o subcomando e depois preencha os campos exibidos.\n\n"
        "`/cargo` e `/politica` definem seu cargo; os salários dos cargos e de profissões com contrato ativo são "
        "depositados automaticamente a cada 48 horas. Use `/folha` para consultar os valores e a previsão; não há saque manual.",
    ),
    "economia": (
        "Economia e vida",
        "`/menu` abre a central interativa: consulte a carteira, compre na loja, assine contrato de trabalho e faça PIX por botões.\n"
        "`/saldo`: consulta rápida dos saldos limpo e sujo. `/extrato`: status, energia, emprego, itens e empresas.\n"
        "`/cargo` e `/politica`: sorteiam seu cargo. A cada 48 horas são somados todos os cargos salariais que você possui — Presidente, Governador, Deputado, Senador, Prefeito, Ministro do STF, Presidente da Petrobras, Diretor Executivo, Trabalhador e Estagiário — mais uma profissão com contrato ativo. `/folha` consulta o valor e o próximo depósito; não existe saque manual. `/partido` e `/alinhamento`: sorteiam sua filiação e seu lado.\n"
        "`/sincronizar_cargos membro:<membro>` aplica os cargos salvos no perfil ao servidor; exclusivo para administradores.\n"
        "`/banco pix usuario:<membro> quantidade:<valor>` transfere saldo limpo. `/bet valor:<valor>` aposta saldo.\n"
        "`/loja acao:listar` mostra preços; use `/loja acao:comprar item:<nome>` para comprar arma, colete, carro, mansao, posto ou emissora.\n"
        "`/inventario` lista bens. `/faccao acao:criar|entrar|convidar nome:<nome>` gerencia facções. `/vadiar` procura moedas se você não tiver cargo político.",
    ),
    "governo": (
        "Governo e eleições",
        "Presidente: `/governo decreto texto:<texto>` publica decreto; `/governo desviar valor:<quantia>` tenta desviar verba; `/petrobras indicar usuario:<membro>` nomeia o chefe.\n"
        "Governador: `/estado decreto texto:<texto>` ou `/estado pm_operacao faccao:<nome>`. Prefeito: `/cidade asfalto`; administração abastece o cofre em `/cidade repassar valor:<quantia>`.\n"
        "Deputado/Senador: `/congresso propor_pec texto:<texto>`, depois vote com `/congresso votar proposta:<id> voto:sim` ou `nao`; encerre com `/congresso encerrar proposta:<id>`.\n"
        "Administração inicia/encerra em `/eleicao acao:iniciar|encerrar`. Com eleição aberta, use `/campanha` para registrar candidatura (é preciso ter partido), publicar até 3 propostas e fazer um evento a cada 12 horas. Comícios e voluntariado custam saldo; debates são gratuitos. A popularidade desempata candidaturas com o mesmo número de votos.\n"
        "`/campanha acao:painel` mostra candidaturas e `/noticias` traz os acontecimentos recentes. `/eleicao_resultado` publica em `#resenhas`; exige administrador ou dono do bot.",
    ),
    "justica": (
        "Justiça e segurança",
        "`/stf mandado usuario:<membro>` e `/stf julgar usuario:<membro>` são do Ministro do STF, administradores ou dono do bot. `/stf nomear|sortear|derrubar` exige autorização administrativa ou judicial. Admins iniciam e encerram a eleição em `/stf eleicao`; todos votam com `/stf eleicao votar candidato:<membro>`.\n"
        "`/crime` oferece roubo (15%), ameaça (20%), homicídio (50%), fraude (10%), contrabando (25%) e vandalismo (10%) de chance de prisão. `/banco defender usuario:<membro>` é ação de Advogado.\n"
        "Crimes tentados ou concluídos geram ocorrências investigáveis. Policiais com contrato ativo ou cargo Policial no servidor, STF e administração podem apurar com `/lavajato investigar`; só STF/administração autoriza operações e julgamentos.\n"
        "Médicos podem dar alta na aba Hospital de `/menu` ou usar `/hospital curar usuario:<membro>`. Políticos podem usar `/rachadinha contratar|status|cancelar`; qualquer membro pode denunciar um contrato ativo.\n"
        "`/lavajato denunciar` abre um caso; Polícia, STF e administração investigam a cada 6h por investigador, e `/lavajato operacao` requer ao menos 2 provas e fica restrita ao STF/administração. `/lavajato painel` lista os casos. `/petrolao denunciar` abre denúncia sobre a estatal e `/petrolao balanco` mostra seu balanço público.\n"
        "Operações do RPG confiscam metade dos saldos e enviam o alvo à Papuda por 30 minutos; em seguida, o STF pode julgá-lo. Rachadinhas também podem vazar na folha.",
    ),
    "empresas": (
        "Empresas e trabalho",
        "`/petrobras comprar_acoes quantidade:<n>` compra ações; `/petrobras dividendos` resgata dividendos. Presidente indica com `/petrobras indicar usuario:<membro>`; o chefe reajusta com `/petrobras reajustar preco:<valor>`. Presidente ou chefe pode `/petrobras desviar valor:<quantia>`.\n"
        "Compre Posto de Gasolina ou Emissora de TV em `/loja`. Donos usam `/empresa limpar_caixa valor:<quantia>` para lavar dinheiro sujo, com taxa.\n"
        "Trabalhador assina contrato para Guarda, Mecânico, Advogado, Médico ou Policial com `/emprego profissao`; o salário entra automaticamente na folha a cada 48 horas. `/emprego pedir_demissao` encerra sem multa; `/emprego quebrar_contrato` cobra 10% do saldo positivo. `/folha` mostra os salários previstos. É preciso encerrar o contrato ativo antes de assinar outro.\n"
        "Estagiário usa `/cafe trazer` para recuperar a energia de Diretores Executivos.",
    ),
}


def criar_embed_ajuda(pagina: str) -> discord.Embed:
    titulo, descricao = PAGINAS_AJUDA[pagina]
    embed = discord.Embed(title=f"📚 Politice Bot | {titulo}", description=descricao, color=discord.Color.dark_green())
    embed.set_footer(text="Use /ajuda novamente para abrir as abas. Opções e campos também aparecem ao selecionar cada comando.")
    return embed


class AjudaView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=180)

    async def abrir_pagina(self, interaction: discord.Interaction, pagina: str) -> None:
        await interaction.response.edit_message(embed=criar_embed_ajuda(pagina), view=self)

    @discord.ui.button(label="Início", style=discord.ButtonStyle.secondary)
    async def aba_inicio(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.abrir_pagina(interaction, "geral")

    @discord.ui.button(label="Economia", style=discord.ButtonStyle.primary)
    async def aba_economia(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.abrir_pagina(interaction, "economia")

    @discord.ui.button(label="Governo", style=discord.ButtonStyle.primary)
    async def aba_governo(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.abrir_pagina(interaction, "governo")

    @discord.ui.button(label="Justiça", style=discord.ButtonStyle.primary)
    async def aba_justica(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.abrir_pagina(interaction, "justica")

    @discord.ui.button(label="Empresas", style=discord.ButtonStyle.primary)
    async def aba_empresas(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.abrir_pagina(interaction, "empresas")


class MenuPrincipalView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Carteira", emoji="💰", style=discord.ButtonStyle.success)
    async def abrir_carteira(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=criar_embed_carteira(interaction.user.id, interaction.user.mention),
            view=self,
        )

    @discord.ui.button(label="Loja", emoji="🛒", style=discord.ButtonStyle.primary)
    async def abrir_loja(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        view = LojaView(interaction.user.id)
        await interaction.response.edit_message(
            embed=criar_embed_loja(interaction.user.id),
            view=view,
        )

    @discord.ui.button(label="Profissões", emoji="🧰", style=discord.ButtonStyle.primary)
    async def abrir_profissoes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        view = ProfissoesView(interaction.user.id)
        await interaction.response.edit_message(
            embed=criar_embed_profissoes(interaction.user.id),
            view=view,
        )

    @discord.ui.button(label="PIX", emoji="💸", style=discord.ButtonStyle.success)
    async def abrir_pix(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="💸 Transferência PIX",
                description="Selecione o membro que vai receber o saldo e depois informe o valor.",
                color=discord.Color.gold(),
            ),
            view=PixDestinatarioView(interaction.user.id),
        )

    @discord.ui.button(label="Hospital", emoji="🏥", style=discord.ButtonStyle.primary)
    async def abrir_hospital(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🏥 Serviço hospitalar",
                description="Médicos podem selecionar uma pessoa hospitalizada e confirmar a alta.",
                color=discord.Color.teal(),
            ),
            view=AltaHospitalView(interaction.user.id),
        )

    @discord.ui.button(label="Ajuda", emoji="📚", style=discord.ButtonStyle.secondary)
    async def abrir_ajuda(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=criar_embed_ajuda("geral"), view=AjudaView())


def criar_embed_loja(user_id: int, item_selecionado: str | None = None, aviso: str | None = None) -> discord.Embed:
    usuario = obter_usuario(user_id)
    embed = discord.Embed(
        title="🛒 Loja do servidor",
        description=(
            f"Saldo disponível: **{formatar_reais(usuario['saldo'])}**\n"
            "Escolha um produto no menu e confira o preço antes de confirmar."
        ),
        color=discord.Color.blue(),
    )
    if item_selecionado in LOJA_ITEMS:
        preco = preco_loja(item_selecionado)
        embed.add_field(
            name=NOMES_ITENS_LOJA[item_selecionado],
            value=f"Preço: **{formatar_reais(preco)}**",
            inline=False,
        )
    if aviso:
        embed.add_field(name="Resultado", value=aviso, inline=False)
    embed.set_footer(text="As compras continuam disponíveis pelo comando /loja.")
    return embed


class LojaItemSelect(discord.ui.Select):
    def __init__(self) -> None:
        opcoes = [
            discord.SelectOption(
                label=NOMES_ITENS_LOJA[item],
                value=item,
                description=f"{formatar_reais(preco_loja(item))} | {'Empresa' if item in {'posto', 'emissora'} else 'Item'}",
            )
            for item in LOJA_ITEMS
        ]
        super().__init__(placeholder="Escolha um produto", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, LojaView):
            self.view.item_selecionado = self.values[0]
            self.view.botao_comprar.disabled = False
            await interaction.response.edit_message(
                embed=criar_embed_loja(interaction.user.id, self.view.item_selecionado),
                view=self.view,
            )


class LojaView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.item_selecionado: str | None = None
        self.add_item(LojaItemSelect())
        self.botao_comprar.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Esta loja pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar compra", emoji="✅", style=discord.ButtonStyle.success)
    async def botao_comprar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.item_selecionado is None:
            await interaction.response.send_message("Escolha um produto antes de confirmar.", ephemeral=True)
            return
        resultado = comprar_item(interaction.user.id, self.item_selecionado)
        if resultado.startswith("✅"):
            self.item_selecionado = None
            button.disabled = True
        await interaction.response.edit_message(
            embed=criar_embed_loja(interaction.user.id, self.item_selecionado, resultado),
            view=self,
        )

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, row=1)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=criar_embed_menu(interaction.user),
            view=MenuPrincipalView(interaction.user.id),
        )


def criar_embed_profissoes(user_id: int, profissao_selecionada: str | None = None, aviso: str | None = None) -> discord.Embed:
    usuario = obter_usuario(user_id)
    detalhes = "\n".join(
        f"**{nome}** — {formatar_reais(salario)} por ciclo de 48 horas"
        for nome, salario in SALARIOS.items()
    )
    embed = discord.Embed(
        title="🧰 Central de profissões",
        description=(
            f"Cargo atual: **{usuario.get('ultimo_cargo', 'Nenhum')}**\n"
            f"Profissão: **{usuario.get('emprego', 'Nenhum')}** "
            f"({'contrato ativo' if contrato_emprego_ativo(usuario) else 'sem contrato ativo'})\n\n"
            f"{detalhes}\n\n"
            "A assinatura exige o cargo Trabalhador. O salário é depositado automaticamente a cada 48 horas."
        ),
        color=discord.Color.teal(),
    )
    if profissao_selecionada in SALARIOS:
        embed.add_field(
            name="Profissão selecionada",
            value=f"{profissao_selecionada} — **{formatar_reais(SALARIOS[profissao_selecionada])} por 48 horas**",
            inline=False,
        )
    if aviso:
        embed.add_field(name="Resultado", value=aviso, inline=False)
    embed.set_footer(text="Comandos: /emprego profissao, pedir_demissao, quebrar_contrato e /folha.")
    return embed


class ProfissaoSelect(discord.ui.Select):
    def __init__(self) -> None:
        opcoes = [
            discord.SelectOption(label=nome, value=nome, description=f"Salário por 48h: {formatar_reais(salario)}")
            for nome, salario in SALARIOS.items()
        ]
        super().__init__(placeholder="Escolha uma profissão", min_values=1, max_values=1, options=opcoes)

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, ProfissoesView):
            self.view.profissao_selecionada = self.values[0]
            self.view.botao_escolher.disabled = False
            await interaction.response.edit_message(
                embed=criar_embed_profissoes(interaction.user.id, self.view.profissao_selecionada),
                view=self.view,
            )


class ProfissoesView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.profissao_selecionada: str | None = None
        self.add_item(ProfissaoSelect())
        self.botao_escolher.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Assinar contrato", emoji="✅", style=discord.ButtonStyle.success)
    async def botao_escolher(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.profissao_selecionada is None:
            await interaction.response.send_message("Escolha uma profissão antes de confirmar.", ephemeral=True)
            return
        resultado = escolher_profissao(interaction, self.profissao_selecionada)
        await interaction.response.edit_message(
            embed=criar_embed_profissoes(interaction.user.id, self.profissao_selecionada, resultado),
            view=self,
        )

    @discord.ui.button(label="Pedir demissão", style=discord.ButtonStyle.secondary, row=1)
    async def botao_pedir_demissao(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        resultado = encerrar_contrato_emprego(interaction.user.id, quebrar=False)
        await interaction.response.edit_message(
            embed=criar_embed_profissoes(interaction.user.id, self.profissao_selecionada, resultado),
            view=self,
        )

    @discord.ui.button(label="Quebrar contrato (10%)", style=discord.ButtonStyle.danger, row=1)
    async def botao_quebrar_contrato(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        resultado = encerrar_contrato_emprego(interaction.user.id, quebrar=True)
        await interaction.response.edit_message(
            embed=criar_embed_profissoes(interaction.user.id, self.profissao_selecionada, resultado),
            view=self,
        )

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, row=1)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=criar_embed_menu(interaction.user),
            view=MenuPrincipalView(interaction.user.id),
        )


class PixDestinatarioSelect(discord.ui.UserSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Selecione quem receberá o PIX", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, PixDestinatarioView):
            destinatario = self.values[0]
            if destinatario.bot:
                await interaction.response.send_message("⚠️ Não é possível enviar PIX para um bot.", ephemeral=True)
                return
            self.view.destinatario_id = destinatario.id
            self.view.botao_continuar.disabled = False
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="💸 Transferência PIX",
                    description=f"Destinatário: {destinatario.mention}\nAgora informe o valor para confirmar.",
                    color=discord.Color.gold(),
                ),
                view=self.view,
            )


class PixValorModal(discord.ui.Modal, title="Confirmar transferência PIX"):
    quantidade = discord.ui.Label(
        text="Valor em reais",
        component=discord.ui.TextInput(
            placeholder="Exemplo: 500",
            min_length=1,
            max_length=12,
        ),
    )

    def __init__(self, remetente_id: int, destinatario_id: int) -> None:
        super().__init__()
        self.remetente_id = remetente_id
        self.destinatario_id = destinatario_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        texto_quantidade = str(self.quantidade.component.value).strip()
        if not texto_quantidade.isdecimal():
            await interaction.response.send_message("⚠️ Informe um valor inteiro positivo.", ephemeral=True)
            return
        resultado = transferir_saldo(self.remetente_id, self.destinatario_id, int(texto_quantidade))
        await interaction.response.send_message(resultado, ephemeral=True)


class PixDestinatarioView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.destinatario_id: int | None = None
        self.add_item(PixDestinatarioSelect())
        self.botao_continuar.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Esta transferência pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Informar valor", emoji="➡️", style=discord.ButtonStyle.primary)
    async def botao_continuar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.destinatario_id is None:
            await interaction.response.send_message("Selecione quem receberá o PIX primeiro.", ephemeral=True)
            return
        await interaction.response.send_modal(PixValorModal(interaction.user.id, self.destinatario_id))

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=criar_embed_menu(interaction.user),
            view=MenuPrincipalView(interaction.user.id),
        )


class PacienteSelect(discord.ui.UserSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Selecione uma pessoa para dar alta", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, AltaHospitalView):
            paciente = self.values[0]
            if not isinstance(paciente, discord.Member):
                await interaction.response.send_message("⚠️ Selecione alguém deste servidor.", ephemeral=True)
                return
            self.view.paciente = paciente
            self.view.botao_alta.disabled = False
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🏥 Confirmar alta médica",
                    description=f"Paciente selecionado: {paciente.mention}\nConfirme para tentar conceder alta.",
                    color=discord.Color.teal(),
                ),
                view=self.view,
            )


class AltaHospitalView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=180)
        self.user_id = user_id
        self.paciente: discord.Member | None = None
        self.add_item(PacienteSelect())
        self.botao_alta.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este menu pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar alta", emoji="✅", style=discord.ButtonStyle.success)
    async def botao_alta(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.paciente is None:
            await interaction.response.send_message("Selecione o paciente primeiro.", ephemeral=True)
            return
        resultado = await conceder_alta(interaction, self.paciente)
        await interaction.response.edit_message(
            embed=discord.Embed(title="🏥 Serviço hospitalar", description=resultado, color=discord.Color.teal()),
            view=self,
        )

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=criar_embed_menu(interaction.user),
            view=MenuPrincipalView(interaction.user.id),
        )


def criar_embed_menu(user: discord.User | discord.Member) -> discord.Embed:
    usuario = obter_usuario(user.id)
    return discord.Embed(
        title="🏛️ Politice Bot | Central do cidadão",
        description=(
            f"Olá, {user.mention}! Escolha uma área abaixo para consultar seu perfil, "
            "visitar a loja, transferir saldo, gerenciar sua profissão ou acessar o hospital.\n\n"
            f"Saldo: **{formatar_reais(usuario['saldo'])}** · "
            f"Cargo: **{usuario.get('ultimo_cargo', 'Nenhum')}** · "
            f"Profissão: **{usuario.get('emprego', 'Nenhum')}**\n\n"
            "Os sorteios de cargos políticos continuam nos comandos `/cargo` e `/politica`; campanhas e propostas ficam em `/campanha`."
        ),
        color=discord.Color.dark_green(),
    )


@tree.command(name="ajuda", description="Abre as abas de ajuda do simulador")
async def ajuda(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(embed=criar_embed_ajuda("geral"), view=AjudaView(), ephemeral=True)


@tree.command(name="menu", description="Abre a central interativa do bot")
async def menu(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        embed=criar_embed_menu(interaction.user),
        view=MenuPrincipalView(interaction.user.id),
        ephemeral=True,
    )


for grupo in (
    banco_group,
    governo_group,
    stf_group,
    emprego_group,
    petrobras_group,
    estado_group,
    cidade_group,
    congresso_group,
    empresa_group,
    rachadinha_group,
    lavajato_group,
    petrolao_group,
    hospital_group,
    cafe_group,
):
    tree.add_command(grupo)


@client.event
async def on_ready() -> None:
    if not folha_pagamento_loop.is_running():
        folha_pagamento_loop.start()

    comandos = []
    try:
        comandos = await tree.sync()
        logger.info("Conectado como %s; %s comandos sincronizados.", client.user, len(comandos))
    except discord.DiscordException:
        logger.exception("Não foi possível sincronizar os comandos de barra.")

    for user_id, usuario in DADOS_BOT["usuarios"].items():
        fim_da_pena = float(usuario.get("preso_ate", 0) or 0)
        guild_id = usuario.get("prisao_guild_id")
        guild = client.get_guild(int(guild_id)) if guild_id else None
        if fim_da_pena and guild is not None:
            asyncio.create_task(liberar_reu_depois(guild, int(user_id), fim_da_pena))

    mensagem = f"[BOT] Online como {client.user}; {len(comandos)} comandos de barra sincronizados."
    logger.info(mensagem)
    print(mensagem, flush=True)


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN")
    if not token:
        raise RuntimeError("Defina DISCORD_TOKEN ou TOKEN no arquivo .env ou nas variáveis de ambiente.")
    threading.Thread(
        target=iniciar_servidor_api,
        name="urna-web-server",
        daemon=True,
    ).start()
    client.run(token)
