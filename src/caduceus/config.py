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
SELECTED_STYLE = "reverse"  # estilo da opção selecionada no menu
DETAIL_STYLE   = "dim"      # estilo do texto de descrição, à direita do menu
DETAIL_GAP     = 6          # colunas de espaço entre o menu e a descrição
DETAIL_WIDTH   = 62         # largura máxima da descrição, em colunas
PROGRESS_WIDTH = 40         # largura da barra de progresso, em colunas
PROGRESS_REFRESH_SECONDS = 0.05  # intervalo mínimo entre redesenhos da barra de progresso
CONFIRM_WIDTH  = 90         # largura do quadro de confirmação, em colunas
MAX_LISTED_PLACES = 3       # locais listados num aviso do resultado (os restantes são contados)

# ==============================================================================
# 3. WINDOW
# ==============================================================================
WINDOW_COLUMNS = 110        # largura fixa da janela da consola, em colunas
WINDOW_LINES   = 30         # altura fixa da janela da consola, em linhas

# ==============================================================================
# 4. SETTINGS
# ==============================================================================
SETTINGS_FOLDER = "Caduceus"       # pasta, dentro de %LOCALAPPDATA%, onde ficam as definições
SETTINGS_FILE   = "settings.json"  # ficheiro das definições guardadas

# ==============================================================================
# 5. CLEANUP
# ==============================================================================
TEMP_MIN_AGE_HOURS = 1      # os temporários mais recentes do que isto não se apagam
