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
tab_radar, tab_graficos, tab_chat, tab_historial = st.tabs(["🎯 Radar Maestro", "📈 Gráficos Visuales", "💬 Chat con JARVIS", "🗄️ Track Record"])

# --- PESTAÑA 1: RADAR DE MERCADO ---
with tab_radar:
    st.subheader("Radar Cuantitativo Maestro")
    st.markdown("Ejecuta un escaneo simultáneo con indicadores avanzados (RSI, MACD, Bandas de Bollinger).")
    
    portafolio_invex = ["VOO", "MELI", "SMH", "BTC-USD", "AAPL", "NVDA"]
    st.write(f"**Activos en vigilancia:** {', '.join(portafolio_invex)}")
    
    btn_maestro = st.button("Ejecutar Escáner Avanzado", type="primary", use_container_width=True)
    
    if btn_maestro:
        with st.spinner("JARVIS está ejecutando modelos cuantitativos en el portafolio..."):
            client = genai.Client(api_key=API_KEY_GEMINI)
            st.markdown("### 📊 Reporte Ejecutivo Avanzado de JARVIS")
            
            for ticker in portafolio_invex:
                datos, mensaje = obtener_radiografia_tecnica(ticker)
                
                if datos is not None:
                    ultimo_precio = float(datos['Close'].iloc[-1])
                    ultimo_rsi = float(datos['RSI_14'].iloc[-1])
                    
                   # Filtramos dinámicamente las columnas clave para evitar errores de versión
                    palabras_clave = ['Close', 'RSI', 'SMA', 'MACD', 'BBL', 'BBU']
                    cols_clave = [col for col in datos.columns if any(palabra in col for palabra in palabras_clave)]
                    datos_str = datos[cols_clave].to_string()
                    
                    prompt_experto = f"""
                    Eres JARVIS, el analista algorítmico principal de Invex. Analiza el último cierre de {ticker}:
                    {datos_str}
                    
                    Reglas de análisis experto:
                    1. BBL es la Banda de Bollinger Inferior y BBU la Superior. Si el Close está cerca o por debajo de BBL, es zona de rebote/compra.
                    2. Si MACD > MACDs (Señal), hay momentum alcista.
                    3. Cruza esta información con el RSI_14.
                    4. Justifica de forma ejecutiva en máximo 2 o 3 líneas.
                    5. OBLIGATORIO: Termina con una de estas frases en MAYÚSCULAS NEGRITAS:
                    - **ES BUEN MOMENTO PARA COMPRAR**
                    - **ES BUEN MOMENTO PARA VENDER**
                    - **ES MOMENTO DE MANTENER / ESPERAR**
                    """
                    
                    try:
                        respuesta = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt_experto
                        )
                        veredicto = respuesta.text
                        
                        color_icono = "🟢" if "COMPRAR" in veredicto else "🔴" if "VENDER" in veredicto else "🟡"
                        
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
            
            st.toast("✅ Escaneo avanzado completado y guardado en Invex DB.")

# --- PESTAÑA 4: TRACK RECORD (NUEVO) ---
with tab_historial:
    st.subheader("🗄️ Base de Datos Analítica (Track Record)")
    st.markdown("Revisa el registro inmutable de las operaciones y veredictos pasados de JARVIS.")
    
    if st.button("Actualizar Historial"):
        try:
            # Extraemos las últimas 20 predicciones de Supabase
            respuesta_bd = supabase.table('historial_trading').select("*").order('id', desc=True).limit(20).execute()
            
            if respuesta_bd.data:
                # Convertimos la respuesta en una tabla de Pandas
                df_historial = pd.DataFrame(respuesta_bd.data)
                
                # Ocultamos columnas técnicas y mostramos lo relevante
                st.dataframe(
                    df_historial[['created_at', 'ticker', 'precio', 'rsi', 'veredicto']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Aún no hay operaciones registradas en el servidor de Supabase.")
        except Exception as e:
            st.error(f"Error al conectar con Invex DB: {e}")

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
