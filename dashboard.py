import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from google import genai
import os
from supabase import create_client, Client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Invex - Trading", page_icon="📈", layout="wide")
st.title("Invex: Asistente Cuantitativo JARVIS")
st.markdown("---")

# Conexión segura a Gemini
API_KEY_GEMINI = os.getenv("API_KEY_GEMINI", st.secrets.get("API_KEY_GEMINI", "TU_API_KEY_GEMINI"))

# --- 2. MOTOR DE ANÁLISIS TÉCNICO (Oculto al usuario) ---
def obtener_radiografia_tecnica(ticker):
    try:
        df = yf.Ticker(ticker).history(period="6mo")
        if df.empty:
            return None, "No se encontraron datos para este símbolo."
        
        # Indicadores Base
        df.ta.rsi(length=14, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        
        # NUEVOS INDICADORES EXPERTOS: MACD y Bandas de Bollinger
        df.ta.macd(append=True) # Genera: MACD_12_26_9 y MACDs_12_26_9
        df.ta.bbands(length=20, std=2, append=True) # Genera: BBL_20_2.0 (Banda Inferior) y BBU_20_2.0 (Banda Superior)
        
        df.dropna(inplace=True)
        # Extraemos solo el último día para que JARVIS tome la decisión en tiempo real
        return df.tail(1), "Éxito"
    except Exception as e:
        return None, f"Error al procesar el activo: {e}"
        
# --- 3. INTERFAZ PÚBLICA (PESTAÑAS) ---
tab_radar, tab_graficos, tab_chat = st.tabs(["🎯 Radar de Mercado", "📈 Gráficos Visuales", "💬 Chat con JARVIS"])

# --- PESTAÑA 1: RADAR DE MERCADO ---
with tab_radar:
    st.subheader("Radar Cuantitativo Maestro")
    st.markdown("Ejecuta un escaneo simultáneo de todo el portafolio para detectar zonas de oportunidad.")
    
    # Tu portafolio predefinido de Invex
    portafolio_invex = ["VOO", "MELI", "SMH", "BTC-USD", "AAPL"]
    st.write(f"**Activos en vigilancia:** {', '.join(portafolio_invex)}")
    
    btn_maestro = st.button("Ejecutar Escáner de Portafolio", type="primary", use_container_width=True)
    
    if btn_maestro:
        with st.spinner("JARVIS está analizando la estructura matemática del portafolio..."):
            client = genai.Client(api_key=API_KEY_GEMINI)
            
            # Creamos contenedores visuales para el resumen
            st.markdown("### 📊 Reporte Ejecutivo de JARVIS")
            
            for ticker in portafolio_invex:
                datos, mensaje = obtener_radiografia_tecnica(ticker)
                
                if datos is not None:
                    # Extraer datos rápidos para visualización
                    ultimo_precio = float(datos['Close'].iloc[-1])
                    ultimo_rsi = float(datos['RSI_14'].iloc[-1])
                    datos_str = datos[['Close', 'RSI_14', 'SMA_20', 'SMA_50']].to_string()
                    
                    # Prompt ultra rápido para análisis en lote
                    prompt_lote = f"""
                    Eres JARVIS. Analiza rápidamente los últimos 3 días de {ticker}:
                    {datos_str}
                    Sé muy breve (máximo 2 líneas de justificación) y termina OBLIGATORIAMENTE con una de estas frases en MAYÚSCULAS NEGRITAS:
                    - **ES BUEN MOMENTO PARA COMPRAR**
                    - **ES BUEN MOMENTO PARA VENDER**
                    - **ES MOMENTO DE MANTENER / ESPERAR**
                    """
                    
                    try:
                        respuesta = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt_lote
                        )
                        veredicto = respuesta.text
                        
                        # Definir color del semáforo visual según la recomendación
                        color_icono = "🟢" if "COMPRAR" in veredicto else "🔴" if "VENDER" in veredicto else "🟡"
                        
                        # Mostrar el resultado en un bloque expandible elegante
                        with st.expander(f"{color_icono} {ticker} | Precio: ${ultimo_precio:.2f} | RSI: {ultimo_rsi:.2f}"):
                            st.markdown(veredicto)
                        
                        # --- GUARDAR EN SUPABASE ---
                        supabase.table('historial_trading').insert({
                            "ticker": ticker,
                            "precio": ultimo_precio,
                            "rsi": ultimo_rsi,
                            "veredicto": veredicto
                        }).execute()
                        
                    except Exception as e:
                        st.error(f"Error en el análisis de {ticker}: {e}")
                else:
                    st.warning(f"No se pudieron extraer datos de {ticker}: {mensaje}")
            
            st.toast("✅ Escaneo masivo completado y registrado en Invex DB.")

# --- PESTAÑA 2: GRÁFICOS VISUALES ---
with tab_graficos:
    st.subheader("Rendimiento Histórico")
    ticker_grafico = st.text_input("Activo a graficar:", "BTC-USD", key="grafico")
    try:
        datos_hist = yf.Ticker(ticker_grafico).history(period="6mo")
        st.line_chart(datos_hist[['Close']])
    except Exception as e:
        st.warning("No se pudo cargar el gráfico.")

# --- PESTAÑA 3: CHAT INTERACTIVO ---
with tab_chat:
    st.subheader("Chat Libre con JARVIS")
    if "mensajes_chat" not in st.session_state:
        st.session_state.mensajes_chat = []

    for mensaje in st.session_state.mensajes_chat:
        with st.chat_message(mensaje["rol"]):
            st.markdown(mensaje["contenido"])

    if peticion := st.chat_input("Escribe tu instrucción aquí..."):
        st.chat_message("user").markdown(peticion)
        st.session_state.mensajes_chat.append({"rol": "user", "contenido": peticion})
        
        with st.chat_message("assistant"):
            try:
                client = genai.Client(api_key=API_KEY_GEMINI)
                respuesta = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"Eres JARVIS. Responde de forma analítica: {peticion}"
                )
                st.markdown(respuesta.text)
                st.session_state.mensajes_chat.append({"rol": "assistant", "contenido": respuesta.text})
            except Exception as e:
                st.error(f"Error técnico: {e}")
