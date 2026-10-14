#!/bin/bash
# Cambiar al directorio donde está el script
cd "$(dirname "$0")"

echo "========================================="
echo "🚀 Iniciando Sistema TuWebFacil..."
echo "========================================="

# Limpiar puertos por si quedaron abiertos de antes
echo "🧹 Limpiando procesos antiguos..."
lsof -ti:5000 | xargs kill -9 2>/dev/null
lsof -ti:5002 | xargs kill -9 2>/dev/null
killall -9 ngrok 2>/dev/null

# Activar entorno virtual
source venv/bin/activate

# Iniciar app.py en segundo plano
echo "🌐 Levantando Web Server (Puerto 5000)..."
python app.py &
PID_APP=$!

# Iniciar receiver.py en segundo plano
echo "🤖 Levantando Cerebro de WhatsApp (Puerto 5002)..."
python receiver.py &
PID_REC=$!

# Pausa breve para asegurar que arrancaron
sleep 2

# Iniciar ngrok en primer plano para ver la URL
echo "🌍 Conectando con Meta (ngrok)..."
echo "========================================="
echo "❌ PARA CERRAR TODO: Apretá 'Ctrl + C' en esta ventana."
echo "========================================="
ngrok http 5002

# Cuando el usuario apriete Ctrl+C en ngrok, el script continúa acá y mata a los de Python
echo "Apagando servidores..."
kill -9 $PID_APP 2>/dev/null
kill -9 $PID_REC 2>/dev/null
echo "¡Sistema apagado correctamente!"
