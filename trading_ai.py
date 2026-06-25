import yfinance as yf
import pandas as pd
from google import genai
from google.genai import types
import gspread
import os
from datetime import datetime
import requests
import sys

# --- 1. CONFIGURACIÓN DEL SISTEMA ---
# Usamos os.getenv para leer llaves ocultas (o valores por defecto para pruebas locales)
API_KEY_GEMINI = os.getenv("API_KEY_GEMINI", "AQ.Ab8RN6J4U1UNseNhlgbysNcCTbErJuJHiEd1l_9MlUc2Ti0t0Q")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8877606673:AAHsLzX2RPYNMdPZ20W0UHSqDD74DmvW2qI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6585335847")

ARCHIVO_CREDENCIALES = "credenciales.json"
ARCHIVO_MEMORIA = "memoria_jarvis.txt"
NOMBRE_SHEET = "Mi Portafolio"

client = genai.Client(api_key=API_KEY_GEMINI)

# --- 2. MÓDULOS DE EXTRACCIÓN DE DATOS ---
def obtener_portafolio_de_sheets():
    gc = gspread.service_account(filename=ARCHIVO_CREDENCIALES)
    hoja = gc.open(NOMBRE_SHEET).sheet1
    registros = hoja.get_all_records(value_render_option='UNFORMATTED_VALUE')
    
    mi_portafolio = {}
    for fila in registros:
        ticker = fila['Ticker']
        cantidad = float(str(fila['Cantidad']).replace(',', '.'))
        if cantidad > 0:
            mi_portafolio[ticker] = cantidad
    return mi_portafolio

def descargar_precios_y_analisis_tecnico(portafolio):
    tickers = list(portafolio.keys())
    resumen = []
    valor_total = 0.0

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            if df.empty: continue
                
            precio_actual = float(df['Close'].iloc[-1])
            sma50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            diferencia_pct = ((precio_actual - sma50) / sma50) * 100
            
            estado_tecnico = f"Alcista (+{diferencia_pct:.1f}% sobre SMA50)" if diferencia_pct > 0 else f"Bajista ({diferencia_pct:.1f}% bajo SMA50)"
            
            acciones = portafolio[ticker]
            valor_posicion = precio_actual * acciones
            valor_total += valor_posicion
            
            resumen.append(f"- {ticker}: {acciones} acciones a {precio_actual:.2f} USD (Total: {valor_posicion:.2f} USD) | {estado_tecnico}")
        except Exception as e:
            print(f"Error técnico en {ticker}: {e}")
            continue
    return resumen, valor_total

def obtener_noticias_recientes(portafolio):
    noticias_texto = []
    tickers = list(portafolio.keys())
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            noticias = stock.news
            if noticias:
                noticias_texto.append(f"\n[Titulares para {ticker}]:")
                for n in noticias[:2]:
                    # Búsqueda profunda del título para evitar el "Sin título"
                    titulo = n.get('title', n.get('content', {}).get('title', 'Noticia encriptada'))
                    noticias_texto.append(f"  > {titulo}")
        except Exception:
            continue
    return "\n".join(noticias_texto) if noticias_texto else "No hay noticias relevantes hoy."

# --- 3. MÓDULOS DE MEMORIA Y ALERTA ---
def leer_memoria_historica():
    if os.path.exists(ARCHIVO_MEMORIA):
        with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
            contenido = f.read()
            return contenido[-2000:] if len(contenido) > 2000 else contenido
    return "No hay recuerdos previos."

def guardar_recuerdo(mensaje, respuesta):
    with open(ARCHIVO_MEMORIA, "a", encoding="utf-8") as f:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        f.write(f"\n[{fecha}] Usuario: {mensaje}\n[{fecha}] JARVIS: {respuesta}\n")

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

# --- 4. LOS DOS CEREBROS (CENTINELA Y CHAT) CON REDUNDANCIA ---

def ejecutar_modo_centinela():
    print("Iniciando revisión silenciosa del portafolio...")
    portafolio_actual = obtener_portafolio_de_sheets()
    resumen, valor_total = descargar_precios_y_analisis_tecnico(portafolio_actual)
    texto_resumen = "\n".join(resumen)
    noticias = obtener_noticias_recientes(portafolio_actual)

    prompt = f"""
    Eres JARVIS, operando en 'Modo Centinela'. Redacta un reporte corto (máximo 3 párrafos) para Telegram.
    Valor Total: {valor_total:.2f} USD.
    Detalles: {texto_resumen}
    Noticias: {noticias}
    Usa formato Markdown. Menciona lo crítico y despídete formalmente.
    """
    
    # PROTOCOLO DE RESPALDO (REDUNDANCIA)
    modelos = ['gemini-2.5-flash', 'gemini-1.5-flash']
    for modelo in modelos:
        try:
            print(f"Intentando generar reporte con: {modelo}...")
            respuesta = client.models.generate_content(model=modelo, contents=prompt)
            enviar_alerta_telegram(respuesta.text)
            print("✅ Reporte centinela enviado con éxito.")
            return # Si funcionó, terminamos la función aquí
        except Exception as e:
            print(f"⚠️ {modelo} no disponible. Intentando red de respaldo...")
            
    # Si el bucle termina y no funcionó ningún modelo
    enviar_alerta_telegram("⚠️ *Alerta*: Los servidores principales de la IA están caídos.")
    print("🚨 [ERROR]: Ningún modelo disponible.")

def iniciar_chat_interactivo():
    print("Cargando datos del mercado y memoria...")
    portafolio_actual = obtener_portafolio_de_sheets()
    resumen, valor_total = descargar_precios_y_analisis_tecnico(portafolio_actual)
    texto_resumen = "\n".join(resumen)
    noticias = obtener_noticias_recientes(portafolio_actual)
    recuerdos = leer_memoria_historica()
    
    contexto = f"""
    Eres JARVIS, el asistente de trading de Invex. 
    [ESTADO TÉCNICO]: {texto_resumen} | TOTAL: {valor_total:.2f} USD.
    [NOTICIAS]: {noticias}
    [MEMORIA]: {recuerdos}
    Cruza análisis técnico con noticias. Mantén tono analítico y profesional.
    """

    print("\nIniciando sistemas de comunicación JARVIS...")
    
    # PROTOCOLO DE RESPALDO PARA EL CHAT
    modelos = ['gemini-2.5-flash', 'gemini-1.5-flash']
    chat = None
    
    for modelo in modelos:
        try:
            print(f"Conectando matriz de lenguaje con {modelo}...")
            chat = client.chats.create(
                model=modelo,
                config=types.GenerateContentConfig(system_instruction=contexto)
            )
            break # Si conecta, salimos del bucle
        except Exception as e:
            print(f"⚠️ {modelo} saturado. Desviando tráfico...")

    if not chat:
        print("\n🚨 [ERROR CRÍTICO]: Imposible iniciar el chat. Todos los servidores de IA están fuera de línea.")
        return

    print("\n" + "="*60)
    print("¡JARVIS EN LÍNEA!")
    print(f"Portafolio sincronizado: {valor_total:.2f} USD.")
    print("Escribe 'salir' para desconectar.")
    print("="*60 + "\n")
    
    while True:
        mensaje_usuario = input("\nTú: ")
        if mensaje_usuario.lower() in ['salir', 'exit', 'quit']:
            print("JARVIS: Guardando protocolos. ¡Hasta pronto!")
            break
        if not mensaje_usuario.strip(): continue
            
        try:
            print("JARVIS procesando matrices...")
            respuesta = chat.send_message(mensaje_usuario)
            print(f"\nJARVIS: {respuesta.text}")
            guardar_recuerdo(mensaje_usuario, respuesta.text)
        except Exception as e:
            print(f"Error de comunicación temporal (intenta de nuevo): {e}")

# --- 5. INTERRUPTOR PRINCIPAL ---
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--alerta":
        ejecutar_modo_centinela()
    else:
        try:
            iniciar_chat_interactivo()
        except KeyboardInterrupt:
            print("\nApagado manual de emergencia. Sistemas desconectados.")
        except Exception as e:
            print(f"\n[ERROR FATAL]: {e}")
