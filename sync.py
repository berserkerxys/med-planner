import asyncio
from telethon import TelegramClient
from database import salvar_conteudo_exato
import re

# --- SEUS DADOS ---
api_id = 34900101
api_hash = 'f29c772956f0b148c4a654a66952e5ff'
session_name = 'sessao_medplanner'
chat_target = -1003727607215

# Regex
hashtag_pattern = re.compile(r"#(\w+)")
album_cache = {}

async def main():
    print("🚀 INICIANDO SYNC (Modo Estrito: Só salva o que estiver no Gabarito)")
    print("Dica: Certifique-se de ter importado os sumários na aba 'Ajustes' primeiro.\n")
    
    async with TelegramClient(session_name, api_id, api_hash) as client:
        print(f"✅ Conectado ao grupo {chat_target}...")
        
        count_ok = 0
        count_ignored = 0
        
        # Varre mensagens (reverse=True para ler do início ao fim se quiser, ou tire para ler do fim pro início)
        async for message in client.iter_messages(chat_target, limit=None, reverse=True):
            
            # 1. Recupera Texto/Legenda
            texto = message.text or ""
            if not texto and message.grouped_id: texto = album_cache.get(message.grouped_id, "")
            if texto and message.grouped_id: album_cache[message.grouped_id] = texto
            
            # 2. Busca Hashtag
            match = hashtag_pattern.search(texto)
            if not match: continue 
            
            hashtag = match.group(1)
            msg_id = message.id
            clean_id = str(chat_target).replace("-100", "")
            link = f"https://t.me/c/{clean_id}/{msg_id}"
            
            # 3. Limpa Título
            titulo_limpo = texto.replace(f"#{hashtag}", "").strip().split("\n")[0]
            if len(titulo_limpo) < 3: titulo_limpo = f"Aula {msg_id}"

            # 4. Define Tipo
            tipo = "Video" if message.video else "Material"
            subtipo = ""
            if message.video:
                dur = message.file.duration or 0
                subtipo = "Curto" if dur < 900 else "Longo"
            elif message.document:
                mime = message.file.mime_type or ""
                nome = (message.file.name or "").lower()
                if "pdf" not in mime and "pdf" not in nome: continue
                subtipo = "Ficha" if "ficha" in nome or "resumo" in nome else "Slide"

            # 5. TENTA SALVAR
            # A função salvar_conteudo_exato agora retorna erro se o assunto não existir no banco
            res = salvar_conteudo_exato(msg_id, titulo_limpo, link, hashtag, tipo, subtipo)
            
            if "⚠️" in res:
                # Assunto não existe no banco. Ignora para não sujar o Geral.
                # print(f"   [Ignorado] {res}") # Descomente se quiser ver o que está perdendo
                count_ignored += 1
            elif "⏭️" in res:
                pass # Duplicado
            else:
                print(f"[{msg_id}] {res}")
                count_ok += 1

        print(f"\n✨ FINALIZADO!")
        print(f"✅ Vinculados com Sucesso: {count_ok}")
        print(f"⚠️ Ignorados (Falta importar sumário): {count_ignored}")

if __name__ == '__main__':
    asyncio.run(main())