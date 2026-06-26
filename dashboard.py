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
API_KEY_GEMINI = os.getenv("API_KEY_GEMINI", st.secrets.get("API_KEY_GEMINI", "AQ.Ab8RN6J4U1UNseNhlgbysNcCTbErJuJHiEd1l_9MlUc2Ti0t0Q"))

# --- 2. MOTOR DE ANÁLISIS TÉCNICO (Oculto al usuario) ---
def obtener_radiografia_tecnica(ticker):
    try:
        df = yf.Ticker(ticker).history(period="6mo")
        if df.empty:
            return None, "No se encontraron datos para este símbolo."
        
        # Inyectar indicadores
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        
        df.dropna(inplace=True)
        return df.tail(3), "Éxito"
    except Exception as e:
        return None, f"Error al procesar el activo: {e}"

# --- 3. INTERFAZ PÚBLICA (PESTAÑAS) ---
tab_radar, tab_graficos, tab_chat = st.tabs(["🎯 Radar de Mercado", "📈 Gráficos Visuales", "💬 Chat con JARVIS"])

# --- PESTAÑA 1: RADAR DE MERCADO ---
with tab_radar:
    st.subheader("Escáner Cuantitativo Público")
    st.markdown("Ingresa un activo para que JARVIS evalúe sus indicadores matemáticos y emita un veredicto de operación.")
    
    col1, col2 = st.columns([1, 2]) # El chat/veredicto será más ancho que la tabla
    
    with col1:
        ticker_usuario = st.text_input("Símbolo (ej. BTC-USD, VOO, SMH, MELI):", "BTC-USD").upper()
        btn_analizar = st.button("Escanear Mercado")
        
    if btn_analizar:
        with st.spinner("Procesando matemáticas del mercado..."):
            datos, mensaje = obtener_radiografia_tecnica(ticker_usuario)
            
            if datos is not None:
                with col1:
                    st.success("Datos extraídos.")
                    # Mostramos la tabla matemática limpia
                    st.dataframe(datos[['Close', 'RSI_14', 'SMA_20', 'SMA_50']].style.format("{:.2f}"))
                
                with col2:
                    st.info("Generando veredicto de JARVIS...")
                    try:
                        client = genai.Client(api_key=API_KEY_GEMINI)
                        
                        # Convertimos la tabla a texto para que la IA la entienda
                        datos_str = datos[['Close', 'RSI_14', 'SMA_20', 'SMA_50']].to_string()
                        
                        # EL CEREBRO DEL TRADER: Las instrucciones estrictas para la IA
                        prompt_trading = f"""
                        Eres JARVIS, un analista cuantitativo experto de la plataforma Invex. Analiza los siguientes datos técnicos de los últimos 3 días para el activo {ticker_usuario}:
                        
                        {datos_str}
                        
                        Reglas de tu respuesta:
                        1. Haz un análisis directo, evaluando la tendencia del precio, el RSI (recuerda: > 70 es sobrecompra/peligro de caída, < 30 es sobreventa/oportunidad), y la relación entre la SMA_20 y SMA_50.
                        2. No seas excesivamente detallado, ve al grano.
                        3. OBLIGATORIO: Al final de tu respuesta, en un párrafo nuevo y en MAYÚSCULAS NEGRITAS, debes dar un veredicto definitivo usando solo una de estas tres frases:
                        - **ES BUEN MOMENTO PARA COMPRAR**
                        - **ES BUEN MOMENTO PARA VENDER**
                        - **ES MOMENTO DE MANTENER / ESPERAR**
                        """
                        
                        respuesta = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt_trading
                        )
                        
                        st.markdown(respuesta.text)
                        
                        # --- INICIO DEL CÓDIGO PARA GUARDAR EN SUPABASE ---
                        try:
                            # 1. Extraemos el precio y el RSI del último día de la tabla
                            ultimo_precio = float(datos['Close'].iloc[-1])
                            ultimo_rsi = float(datos['RSI_14'].iloc[-1])
                            
                            # 2. Insertamos la fila en tu tabla de la nube
                            supabase.table('historial_trading').insert({
                                "ticker": ticker_usuario,
                                "precio": ultimo_precio,
                                "rsi": ultimo_rsi,
                                "veredicto": respuesta.text
                            }).execute()
                            
                            st.toast("✅ Operación registrada en Invex DB exitosamente.")
                        except Exception as e_bd:
                            st.error(f"Error al guardar en la Base de Datos: {e_bd}")
                        # --- FIN DEL CÓDIGO PARA GUARDAR ---
                        
                        
                    except Exception as e:
                        st.error(f"Error de conexión con el cerebro de JARVIS: {e}")
            else:
                st.error(mensaje)

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
