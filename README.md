# Asistente Técnico Post-Venta con RAG Multimodal

Este repositorio contiene el código fuente y la documentación técnica del proyecto de tesis enfocado en la automatización del soporte técnico post-venta para un e-commerce de productos electrónicos.

El sistema es un agente conversacional que implementa la arquitectura RAG (Retrieval-Augmented Generation) para consultar bases de conocimiento técnicas (manuales, garantías, devoluciones) y posee capacidades multimodales para el análisis de imágenes proporcionadas por el usuario.

## Descripción del Proyecto

El objetivo principal de esta herramienta es asistir a los usuarios en la resolución de fallas técnicas y dudas sobre garantías de productos electrónicos específicos. El sistema combina la recuperación de información semántica mediante bases de datos vectoriales con la capacidad de razonamiento de Modelos de Lenguaje Grande (LLM).

Funcionalidades principales:
- **Búsqueda Vectorial Filtrada:** Recuperación de fragmentos relevantes de manuales basada en similitud semántica, con filtros por producto y tipo de documento.
- **Análisis Multimodal:** Capacidad para procesar imágenes adjuntas por el usuario (fotos de averías o errores) y correlacionarlas con la información técnica.
- **Gestión de Estado:** Mantenimiento del contexto de la conversación para un flujo de soporte continuo.

## Arquitectura Tecnológica

El proyecto está construido utilizando las siguientes tecnologías:

- **Lenguaje:** Python 3.9+
- **Interfaz de Usuario:** Streamlit
- **Orquestación de Agentes:** LangChain y LangGraph
- **Base de Datos Vectorial:** Qdrant
- **Modelos (LLM/Embeddings):** OpenAI API

## Instalación y Configuración

Siga estos pasos para ejecutar el proyecto en un entorno local.

### 1. Clonar el repositorio
```bash
git clone [https://github.com/TU_USUARIO/NOMBRE_DEL_REPO.git](https://github.com/TU_USUARIO/NOMBRE_DEL_REPO.git)
cd NOMBRE_DEL_REPO