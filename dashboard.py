import streamlit as st
import pandas as pd
import yfinance as yf
# Usamos la nueva librería oficial de Google
from google import genai
import os
from trading_ai import obtener_portafolio_de_sheets, descargar_precios_y_analisis_tecnico
import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from google import genai
import os

# --- MOTOR DE ANÁLISIS TÉCNICO ---
def obtener_radiografia_tecnica(ticker):
    """
    Descarga el historial del activo y calcula indicadores matemáticos clave.
    Diseñado para resistir entradas erróneas del usuario público.
    """
    try:
        # 1. Descargar historial de 6 meses
        df = yf.Ticker(ticker).history(period="6mo")
        
        if df.empty:
            return None, "No se encontraron datos para este símbolo."
            
        # 2. Inyectar indicadores usando pandas_ta
        # RSI (Fuerza de la tendencia)
        df.ta.rsi(length=14, append=True)
        # MACD (Cruces de tendencia)
        df.ta.macd(append=True)
        # Medias Móviles (Soportes/Resistencias)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        
        # 3. Limpiar datos vacíos generados por los cálculos
        df.dropna(inplace=True)
        
        # 4. Retornar solo los últimos 3 días para el análisis de la IA
        ultimos_dias = df.tail(3)
        return ultimos_dias, "Éxito"
        
    except Exception as e:
        return None, f"Error al procesar el activo: {e}"

# Reconstruir credenciales de Google Sheets de forma segura en la nube
if not os.path.exists("credenciales.json"):
    try:
        with open("credenciales.json", "w") as f:
            f.write(st.secrets["GCP_CREDENCIALES"])
    except:
        pass

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Invex - Terminal", page_icon="📈", layout="wide")
st.title("Invex: Centro de Operaciones JARVIS")
st.markdown("---")

# Intenta leer la llave local, si no, usa la de la nube
API_KEY_GEMINI = os.getenv("API_KEY_GEMINI", st.secrets.get("API_KEY_GEMINI", "AQ.Ab8RN6J4U1UNseNhlgbysNcCTbErJuJHiEd1l_9MlUc2Ti0t0Q"))


# --- 2. CREACIÓN DE PESTAÑAS (TABS) ---
tab_resumen, tab_graficos, tab_chat = st.tabs(["📊 Resumen de Portafolio", "📈 Gráficos Visuales", "💬 Chat con JARVIS"])

# --- PESTAÑA 1: RESUMEN ---
with tab_resumen:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Estado Actual")
        try:
            portafolio = obtener_portafolio_de_sheets()
            resumen, valor_total = descargar_precios_y_analisis_tecnico(portafolio)
            st.metric(label="Capital Total Invex", value=f"${valor_total:.2f} USD")
            for linea in resumen:
                if "Alcista" in linea:
                    st.success(linea)
                elif "Bajista" in linea:
                    st.error(linea)
                else:
                    st.info(linea)
        except Exception as e:
            st.error(f"Esperando conexión con la matriz de datos... Error: {e}")

    with col2:
        st.subheader("Monitor Rápido")
        ticker_prueba = st.text_input("Ingresa un Ticker para analizar:", value="VOO")
        if ticker_prueba:
            try:
                datos = yf.Ticker(ticker_prueba)
                precio = datos.history(period="1d")['Close'].iloc[-1]
                st.metric(label=f"Precio Actual de {ticker_prueba.upper()}", value=f"${precio:.2f} USD")
            except:
                st.error("Error al buscar el Ticker.")

# --- PESTAÑA 2: GRÁFICOS VISUALES ---
with tab_graficos:
    st.subheader("Rendimiento Histórico (Últimos 6 meses)")
    opciones_tickers = ["VOO", "SMH", "MELI", "AAPL", "MSFT"]
    ticker_seleccionado = st.selectbox("Selecciona el activo a visualizar:", opciones_tickers)
    
    try:
        datos_hist = yf.Ticker(ticker_seleccionado).history(period="6mo")
        precios_cierre = datos_hist[['Close']]
        precios_cierre.columns = [f'Precio de {ticker_seleccionado}']
        st.line_chart(precios_cierre)
    except Exception as e:
        st.warning(f"No se pudo cargar el gráfico de {ticker_seleccionado}.")

# --- PESTAÑA 3: CHAT INTERACTIVO (CORREGIDO) ---
with tab_chat:
    st.subheader("Interfaz de Comunicación Segura")
    
    if API_KEY_GEMINI == "TU_API_KEY_AQUI":
        st.warning("⚠️ ALERTA: Debes pegar tu API Key real en la línea 14 del archivo dashboard.py.")
    else:
        # Inicializamos el cliente con la nueva arquitectura
        try:
            client = genai.Client(api_key=API_KEY_GEMINI)
        except Exception as e:
            st.error(f"Error al inicializar cliente de IA: {e}")

        if "mensajes_chat" not in st.session_state:
            st.session_state.mensajes_chat = []

        for mensaje in st.session_state.mensajes_chat:
            with st.chat_message(mensaje["rol"]):
                st.markdown(mensaje["contenido"])

        if peticion := st.chat_input("Escribe tu instrucción para JARVIS aquí..."):
            st.chat_message("user").markdown(peticion)
            st.session_state.mensajes_chat.append({"rol": "user", "contenido": peticion})
            
            with st.chat_message("assistant"):
                with st.spinner("Procesando consulta..."):
                    try:
                        # Usamos gemini-2.5-flash igual que en el backend
                        respuesta = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=f"Eres JARVIS, el asistente de la empresa Invex. Responde de forma concisa: {peticion}"
                        )
                        st.markdown(respuesta.text)
                        st.session_state.mensajes_chat.append({"rol": "assistant", "contenido": respuesta.text})
                    except Exception as e:
                        st.error(f"Error técnico al generar respuesta: {e}")
