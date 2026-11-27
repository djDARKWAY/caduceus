"""
Configuração

Valores globais ou de alteração frequente do Caduceus.
"""

# ==============================================================================
# 1. LANGUAGE
# ==============================================================================
DEFAULT_LANGUAGE  = "en"  # idioma de arranque (nome do ficheiro em locales/)
FALLBACK_LANGUAGE = "en"  # idioma que completa as traduções a que falte um texto

# ==============================================================================
# 2. UI
# ==============================================================================
SELECTED_STYLE = "black on white"  # opção selecionada no menu (cores explícitas, não "reverse")
DETAIL_STYLE   = "dim"      # estilo do texto de descrição, à direita do menu
MENU_WIDTH     = 32         # largura mínima da coluna das opções, em colunas (o seletor ocupa-a)
DETAIL_GAP     = 6          # colunas de espaço entre o menu e a descrição
DETAIL_WIDTH   = 62         # largura máxima da descrição, em colunas
PROGRESS_WIDTH = 40         # largura da barra de progresso, em colunas
PROGRESS_REFRESH_SECONDS = 0.05  # intervalo mínimo entre redesenhos da barra de progresso
PROGRESS_REFRESH_RATE = 8   # fotogramas por segundo da animação de progresso
CONFIRM_WIDTH  = 90         # largura do quadro de confirmação, em colunas
MAX_LISTED_PLACES = 3       # locais listados num aviso do resultado (os restantes são contados)

# ==============================================================================
# 3. WINDOW
# ==============================================================================
WINDOW_COLUMNS = 116        # largura fixa da janela da consola, em colunas
WINDOW_LINES   = 30         # altura fixa da janela da consola, em linhas

# ==============================================================================
# 4. SETTINGS
# ==============================================================================
SETTINGS_FOLDER = "Caduceus"       # pasta, dentro de %LOCALAPPDATA%, onde ficam as definições
SETTINGS_FILE   = "settings.json"  # ficheiro das definições guardadas

# ==============================================================================
# 5. CLEANUP
# ==============================================================================
CLEANUP_MIN_AGE_HOURS = 1   # idade mínima dos ficheiros removidos pelo motor de limpeza
LOG_MIN_AGE_HOURS     = 24  # registos de diagnóstico do Windows
