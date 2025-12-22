# Se usa una imagen ligera de Python
FROM python:3.9-slim
# Se establece el directorio de trabajo dentro del contenedor
WORKDIR /app
# Se copia el archivo de requerimientos primero (para aprovechar la caché de Docker)
COPY requirements.txt .
# Se instalan las librerías
RUN pip install --no-cache-dir -r requirements.txt
# Se copia el resto del código (app.py)
COPY . .
# Se expone el puerto 8501 (el puerto por defecto de Streamlit)
EXPOSE 8501
# Comando para ejecutar la app
# IMPORTANTE: address=0.0.0.0 para que Docker escuche desde fuera
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]