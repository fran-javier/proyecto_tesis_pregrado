# Asistente Técnico Post-Venta con Arquitectura RAG Multimodal

**Autor:** Francisco Reveco  
**Carrera:** Ingeniería Civil Industrial  
**Universidad:** Universidad Mayor  
**Año:** 2026  

Repositorio asociado a la tesis de pregrado orientada al diseño e implementación de un agente conversacional multimodal basado en Retrieval-Augmented Generation (RAG) para automatización de soporte técnico postventa en e-commerce de productos electrónicos.

---

## 1. Resumen del Proyecto

Este sistema implementa un agente conversacional que integra:

- Recuperación semántica desde una base vectorial (Qdrant)
- Razonamiento mediante Large Language Models (LLMs)
- Procesamiento multimodal (texto + imagen)
- Orquestación basada en grafo de estados (LangGraph)

El objetivo es responder consultas técnicas, de garantía y devolución basándose exclusivamente en documentación oficial estructurada (manuales y políticas).

El agente restringe su generación al contexto recuperado, incorporando citación obligatoria de fuentes.

---

## 2. Contribución Técnica

Desde una perspectiva de ingeniería, el sistema implementa:

1. Pipeline RAG con filtros estructurados por metadata.
2. Indexación vectorial con embeddings OpenAI (`text-embedding-3-small`).
3. Orquestación determinística mediante grafo de estados.
4. Control de ciclos y retries para evitar loops infinitos.
5. Evaluación automática de relevancia documental mediante LLM estructurado.
6. Integración multimodal para análisis de evidencia visual.

---

## 3. Arquitectura del Sistema

### 3.1 Componentes principales

- `app.py`: Interfaz de usuario en Streamlit.
- `agent_graph.py`: Definición del grafo de estados del agente.
- `prompts.py`: Especificación formal de prompts.
- Qdrant: Base de datos vectorial externa.
- OpenAI API: Modelos LLM y embeddings.

### 3.2 Flujo del Agente

El flujo operacional se modela como un `StateGraph`:

START
→ Router de tipo de input (texto / imagen)
→ Nodo de procesamiento visual (si aplica)
→ Nodo agente principal
→ Llamada a herramienta (si requerida)
→ Evaluación de relevancia
→ Generación final o reescritura
→ END

El sistema incorpora:

- Límite máximo de 3 retries.
- Resumen automático si el historial supera 6 mensajes.
- Persistencia de estado vía `MemorySaver`.

---

## 4. Modelos Utilizados

- **LLM principal:** `gpt-5-nano`  
- **Embeddings:** `text-embedding-3-small`  
- **Temperatura:** 0 (configuración determinística)

**Observación:** Aunque se fija `temperature = 0`, el sistema depende de modelos externos, por lo que la reproducibilidad exacta puede variar según actualizaciones del proveedor.

---

## 5. Requisitos del Sistema

### 5.1 Software

- Python 3.9
- Docker (opcional pero recomendado)
- Cuenta OpenAI activa
- Instancia activa de Qdrant (cloud)

### 5.2 Dependencias Python

Se encuentran en `requirements.txt`.

---

## 6. Variables de Entorno

Debe crearse un archivo `.env` en la raíz del proyecto:

```env
OPENAI_API_KEY=
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=manuales_tecnicos
EMBEDDING_MODEL_NAME=text-embedding-3-small
LLM_MODEL_NAME=gpt-5-nano
```

El sistema no inicia correctamente si faltan las credenciales. Se pueden modificar los modelos escogidos.

---

## 7. Preparación de la Base Vectorial

Este repositorio asume que:

1. Existe una colección en Qdrant.
2. Los documentos fueron previamente:
* Parseados
* Fragmentados
* Embebidos
* Cargados con metadata:
    * `product_name`
    * `doc_type`
    * `source`
    * `page`
    * `text`

El proceso de ingesta no está incluido en este repositorio.

---

## 8. Obtención del Código Fuente

Para reproducir el sistema, primero debe descargarse el código fuente desde el repositorio oficial.

### 8.1 Clonar el repositorio

```bash
git clone https://github.com/fran-javier/proyecto_tesis_pregrado.git
cd proyecto_tesis_pregrado
```

---

## 9. Ejecución en local (Sin Docker)

### 9.1 Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 9.2 Instalar dependencias

```bash
pip install -r requirements.txt
```

### 9.3 Ejecutar aplicación

Acceder en el navegador:

```
http://localhost:8501
```

---

## 10. Ejecución con Docker

### 10.1 Build

```bash
docker build -t agente-postventa .
```

### 10.2 Run

```bash
docker run -p 8501:8501 --env-file .env agente-postventa
```

### 10.3 Alternativa con docker-compose

```bash
docker-compose up --build
```

---

## 11. Reproducibilidad experimental

Para replicar el comportamiento:

1. Usar misma versión de Python (3.9).
2. Fijar versiones exactas de librerías.
3. Utilizar mismo modelo OpenAI.
4. Usar misma colección Qdrant.
5. Mantener temperatura en 0.

**Limitaciones**

* Dependencia de APIs externas.
* Cambios en modelos pueden alterar outputs.
* Base documental no incluida en repositorio.

---

## 12. Limitaciones Técnicas

* Dependencia de servicios cloud externos.
* No incluye pipeline de ingesta documental.
* No incluye dataset público por restricciones de copyright.
* No incluye evaluación cuantitativa formal de desempeño.