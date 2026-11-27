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
ACCENT_STYLE   = "green"    # cor do cabeçalho e dos títulos
SELECTED_STYLE = "reverse"  # estilo da opção selecionada no menu
DETAIL_STYLE   = "dim"      # estilo do texto de descrição, à direita do menu
DETAIL_GAP     = 6          # colunas de espaço entre o menu e a descrição
DETAIL_WIDTH   = 50         # largura máxima da descrição, em colunas

# ==============================================================================
# 3. WINDOW
# ==============================================================================
WINDOW_COLUMNS = 90         # largura fixa da janela da consola, em colunas
WINDOW_LINES   = 30         # altura fixa da janela da consola, em linhas
