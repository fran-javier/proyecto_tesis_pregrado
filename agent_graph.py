from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.tools import BaseTool
from langgraph.graph import (
    StateGraph, 
    START, 
    END, 
    MessagesState
)
from langchain_core.messages import (
    AIMessage, 
    SystemMessage, 
    ToolMessage, 
    RemoveMessage
)
from qdrant_client import QdrantClient
from qdrant_client.http import models
from pydantic import BaseModel, Field
from typing import Literal, Any, Type, Optional
# Docker aplana la estructura app.py, por lo que no tiene sentido hacer 'from .. import prompts'
import prompts as prompt
import logging
import os

load_dotenv()

# ======================
#     CONFIGURACIÓN
# ======================
logging.basicConfig(level = logging.INFO)
log = logging.getLogger('agent_logger')

openai_api_key = os.getenv('OPENAI_API_KEY')
qdrant_api_key = os.getenv('QDRANT_API_KEY')
qdrant_url = os.getenv('QDRANT_URL')
collection_name = os.getenv('QDRANT_COLLECTION_NAME')
embedding_model_name = os.getenv('EMBEDDING_MODEL_NAME')
llm_model_name = os.getenv('LLM_MODEL_NAME')

if not openai_api_key or not qdrant_api_key:
    log.error("Error: Faltan API KEYS en el archivo .env")

# ======================
#       CLIENTES
# ======================
embedding = OpenAIEmbeddings(model = embedding_model_name)
modelo_llm = llm_model_name
llm = ChatOpenAI(
    model = modelo_llm, 
    temperature = 0
) 

qdrant_client = QdrantClient(
    url = qdrant_url,
    api_key = qdrant_api_key,
)
# ======================
#  DEFINICIÓN DE ESTADO
# ======================
class AgentState(MessagesState):
    input_type: str        
    extracted_file: str    
    summary: str           
    final_response: str    
    num_retries: int       
    raw_file_url: str

class GradeDocuments(BaseModel):
    "Binary score for relevance check."
    score: Literal['yes', 'no'] = Field(description = "Relevance score 'yes' or 'no'.")

# ======================
#         TOOLS
# ======================
# Crear índice para 'product_name' (Tipo KEYWORD para coincidencia exacta)
qdrant_client.create_payload_index(
    collection_name = collection_name,
    field_name = 'product_name',
    field_schema = models.PayloadSchemaType.KEYWORD
)

# Crear índice para 'doc_type' (Tipo KEYWORD para coincidencia exacta)
qdrant_client.create_payload_index(
    collection_name = collection_name,
    field_name = 'doc_type',
    field_schema = models.PayloadSchemaType.KEYWORD
)

class RetrieverInput(BaseModel):
    query: str = Field(
        description = "La consulta para buscar información relevante en la base de conocimiento."
    )
    product_name: Optional[str] = Field(
        description = (
            "El nombre exacto del producto a filtrar. Opciones:\n" \
            "'ROG Xbox Ally X', 'Lavadora Secadora EcoBubble', 'Refrigerador French Door', 'TV OLED S95F 4K', 'Garantía multi-producto', 'Toda la Tienda'.\n"
            "Si es duda general, usar 'General'."
        ),
        default = None 
    )
    doc_type: Optional[str] = Field(
        description = (
            "Tipo de documento. Opciones:\n" 
            "'Manual de usuario', 'Política de Garantía', 'Política de Devolución'."
        ),
        default = None
    )

class QdrantRetrieverTool(BaseTool):
    name: str = 'consultar_manuales' # Antes: search_qdrant_knowledge
    description: str = (
        "Útil para buscar información técnica, garantías, y devoluciones de productos electrónicos en la base de datos vectorial de Qdrant."
        "Usa esta herramienta cuando necesites contexto adicional para responder la pregunta del usuario."
    )
    args_schema: Type[BaseModel] = RetrieverInput
    client: Any = Field(description = "Cliente de Qdrant")
    embedding_model: Any = Field(description = "Modelo de embeddings")

    def _run(self, query: str, product_name: str = None, doc_type: str = None, **kwargs) -> str:
        """Método sincrónico que ejecuta la lógica de la herramienta."""
        try:
            log.info(">>> [TOOL] retriever_tool: Iniciando tool.")
            prod_filter = product_name or kwargs.get('product') or kwargs.get('producto')
            log.info(f"    Tool buscando: '{query}' | Filtros: product = '{prod_filter}', type = '{doc_type}'")
            
            query_vector = self.embedding_model.embed_query(query)
            conditions = []
            # Filtro de producto
            if prod_filter and prod_filter not in ['General', 'Seleccionar...', None]:
                # Se uas match exacto porque los nombres se definieron en la ingesta de datos del RAG
                conditions.append(
                    models.FieldCondition(
                        key = 'product_name', # Key en metadata de Qdrant
                        match = models.MatchValue(value = prod_filter)
                    )
                )
            # Filtro de tipo de doc
            if doc_type:
                conditions.append(
                    models.FieldCondition(
                        key = 'doc_type',
                        match = models.MatchValue(value = doc_type)
                    )
                )
            # Ejecutar búsqueda
            search_result = self.client.query_points(
                collection_name = collection_name,
                query = query_vector,
                query_filter = models.Filter(must = conditions) if conditions else None,
                limit = 5,
                score_threshold = 0.5,
                with_payload = True
            )
            if not search_result:
                return "No se encontró nunguna información relevante en los manuales con esos criterios."
            
            # Formatear respuesta 
            formatted_docs = []
            log.info(f"    Qdrant recuperó {len(search_result.points)} chunks")
            for point in search_result.points:
                payload = point.payload

                # Esto será lo que el LLM "verá"
                content = (
                    f"[Producto: {payload.get('product_name')} - Tipo documento: {payload.get('doc_type')} - Fuente: {payload.get('source')} (Página: {payload.get('page')})]\n{payload.get('text')}"
                )
                formatted_docs.append(content) 

            return "\n\n------\n\n".join(formatted_docs)
        
        except Exception as e:
            return f"Error al recuperar: {e}"

retriever_tool = QdrantRetrieverTool(
    client = qdrant_client,
    embedding_model = embedding
)
tools = [retriever_tool]
tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = llm.bind_tools(tools)

# ======================
#    NODOS DEL GRAFO
# ======================

def text_node(state: AgentState):
    log.info(">>> [NODO] text_node: Nodo usado")
    # LangGraph funciona mediante actualizaciones (updates), no mediante reemplazos
    # Si se retorna state['messages'], duplica la lista de messages
    # Acá solo se dice que no hay nada nuevo que agregar o "Pase sin cambios"
    return {'messages': []}

def process_image(state: AgentState):
    """
    Process an incoming image to generate a technical description (summary) that provides context for the agent.
    Handle the scenario where Telegram sends an image and a caption (text) together.
    """
    log.info(">>> [NODO] process_image_node: Iniciando nodo.")

    last_message = state['messages'][-1]
    image_url = None # Que extraiga la URL de la imagen del contenido del mensaje (Lista de blocks)

    if isinstance(last_message.content, list):
        for block in last_message.content:
            if isinstance(block, dict) and block.get('type') == 'image_url':
                image_url = block['image_url']['url']
                break

    if not image_url:
        log.error("    Error: Se entró al nodo de imagen pero no se encontró 'image_url' en el mensaje.")
        return {'messages': [SystemMessage(content = "Error: Image processing failed (No URL found).")]}
    
    # Formato de cómo se le envían las variables al llm
    message_content = [
        {'type': 'text', 'text': prompt.VISION_PROMPT},
        {'type': 'image_url', 'image_url': {'url': image_url}}
    ]
    try:
        log.info(f"    Enviando imagen a modelo {modelo_llm}.")
        response = llm.invoke([SystemMessage(content = message_content)])
        visual_summary = response.content
        # Se inyecta el análisis 'visual_summary' como un SystemMessage para que 'agent_node' lo lea
        context_message = SystemMessage(
            content = f"Context information: (Visual Analysis):\n{visual_summary}"
        )
        return {'messages': [context_message]}
    except Exception as e:
        log.error(f"    Error al procesar la imagen: {e}")
        error_prompt = "The image could not be read. Notify the user in Spanish."
        return {'messages': [SystemMessage(content = error_prompt)]}

def summarization_node(state: AgentState):
    """
    """
    log.info(">>> [NODO] summarization_node: Iniciando nodo.")
    summary = state.get('summary', '')

    if summary:
        summary_prompt = prompt.SUMMARY_PROMPT.format(summary = summary)
    else:
        summary_prompt = "Crate a summary of the previous conversation."

    messages = state['messages'] + [SystemMessage(content = summary_prompt)]
    response = llm.invoke(messages)
    
    # Que se mantengan los ultimos 6 mensajes
    delete_messages = [RemoveMessage(id = m.id) for m in state['messages'][:-6]]
    return {
        'messages': delete_messages, 
        'summary': response.content
    }

def agent_node(state: AgentState):
    """
    Invokes the agent model to generate a response based on the current state.
    Given the question, it will decide to retrieve using the call tool node (tool_call_node), or simply end (END).

    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with the agent response appended to messages
    """
    log.info(">>> [NODO] agent_node: Iniciando nodo.")
    
    summary = state.get('summary', '')
    if not state.get('num_retries'): state['num_retries'] = 1

    system_prompt = [SystemMessage(content = prompt.AGENT_PROMPT)]

    if summary:
        summary_prompt = f"Summary of the previous conversation: \n{summary}"
        system_prompt.append(SystemMessage(content = summary_prompt))
    
    messages = system_prompt + state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]} # LangGraph concatena automáticamente si se usa MessagesState

def tool_call_node(state: AgentState):
    """
    """
    log.info(">>> [NODO] tool_call_node: Ejecutando herramienta.")
    last_message = state['messages'][-1]
    tool_messages = []
    
    # Qué obtenga el atributo 'tool_calls' de last_message, sino '[]'
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        log.warning("    El último mensaje no tiene tool_calls. Saltando...")
        return {'messages': []}
    
    for tool_call in getattr(last_message, 'tool_calls', []):
        log.info(f"    Procesando llamada a: {tool_call}")
        tool = tools_by_name.get(tool_call['name'])

        if tool:
            try:
                content = tool.invoke(tool_call.get('args', {}))
                log.info(f"    Ejecutando {tool_call['name']}")
            except Exception as e:
                log.error(f"    Error ejecutando la herramienta: {e}")
                content = f"Error {e}"

        else:
            log.warning(f"    Herramienta {tool_call['name']} no encontrada en 'tools_by_name'.")
            content = "Tool not found error."

        tool_messages.append(ToolMessage(
            content = content,
            tool_call_id = tool_call['id'],
            name = tool_call['name']
            )
        )
    return {'messages': tool_messages}

def rewrite_node(state: AgentState):
    """
    Transform the query to produce a better question.

    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with the rewritten question
    """
    log.info(">>> [NODO] rewrite_node: Iniciando nodo.")
    question = state['messages'][0].content

    system_prompt = prompt.REWRITE_PROMPT.format(question = question)
    response = llm.invoke([SystemMessage(content = system_prompt)])
    return {
        'messages': [response], 
        'num_retries': state.get('num_retries', 0) + 1
        }

def generate_response_node(state: AgentState):
    """
    """
    log.info(">>> [NODO] generate_response_node: Iniciando nodo.")
    question = state['messages'][0].content
    last_message = state['messages'][-1].content

    system_prompt = prompt.GENERATE_RESPONSE_PROMPT.format(context = last_message, question = question)
    response = llm.invoke([SystemMessage(content = system_prompt)])
    return {'messages': [response]} # LangGraph concatena automáticamente si se usa MessagesState

def max_retries_node(state: AgentState):
    """
    It runs when the num_retries limit is exceeded.
    It overwrites or adds a final message indicating the failure.

    Args:
        state (messages): The current state

    Returns:
        dict (messages): The updated state with the final message
    """
    log.info(">>> [NODO] max_retries_node: Iniciando nodo.")
    ai_message = (
        "No logro encontrar suficiente contexto relevante para responder con certeza tu pregunta. ¿Podrías proporcionarme más detalles o reformular tu pregunta para ayudarte mejor?"
    )
    return {'messages': [AIMessage(content = ai_message)]}

def final_node(state: AgentState):
    """
    Sink node that extracts the final response for external consumption (Telegram).

    Args:
        state (messages): The current state

    Returns:
        dict (final_response): The updated state with the final response
    """
    log.info(">>> [NODO] final_node: Iniciando nodo.")
    return {'final_response': state['messages'][-1].content}

# ======================
#   FUNCIONES DE RUTEO
# ======================
def grade_documents(state: AgentState) -> Literal['generate_response_node', 'rewrite_node']:
    """
    Determines whether the retrieved documents are relevant to the question.
    """
    log.info(">>> [ROUTER] grade_documents: Evaluando...")

    question = state['messages'][0].content
    last_message = state['messages'][-1] 
    
    if isinstance(last_message, ToolMessage):
        docs_content = last_message.content
    else:
        # Si por alguna razón, el último mensaje no es una tool, se asume vacío
        log.warning(f"    El último mensaje ({type(last_message)}), no es ToolMessage.")
        return 'rewrite_node'
    
    if not docs_content:
        log.info("    Documentos insuficientes -> REWRITE")
        return 'rewrite_node'
    
    try:
        log.info(f"    Se recuperaron documentos")
    except Exception as e:
        log.info(f"    No se recuperaron documentos: {e}")

    # Tras una tool_call, last_message debería ser una tool_call
    answer_prompt = prompt.GRADE_DOCUMENTS_PROMPT.format(context = docs_content, question = question)
    score_result = llm \
        .with_structured_output(GradeDocuments) \
        .invoke([SystemMessage(content = answer_prompt)])
    
    score = score_result.score
    log.info(f"    Evaluación LLM: {score}")
    
    if score == 'yes':
        return 'generate_response_node'
    elif score == 'no':
        return 'rewrite_node'

def input_router(state: AgentState):
    """
    Decide la ruta basada en el tipo de input detectado en app.py
    """
    input_type = state.get('input_type')
    log.info(f">>> [ROUTER] Input detectado: {input_type}")

    if input_type == 'image':
        return 'process_image_node'
    else:
        return 'text_node'

def should_continue(state: AgentState):
    """
    """
    if len(state['messages']) > 6:
        return 'summarization_node'
    else:
        return 'agent_node'

def custom_agent_router(state: AgentState) -> Literal['max_retries_node', 'tool_call_node', 'final_node']:
    """
    1. Checks if the retries were exceeded.
    2. Checks if there are any tool_calls.
    3. If there are none, it goes to the END.
    """
    retries = state.get('num_retries', 0)
    last_message = state['messages'][-1]

    # Para evitar un bucle indefinido
    if retries > 3: 
        return 'max_retries_node'
    
    # Chequeo de tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return 'tool_call_node'
    
    # Si no hay tools y no hay exceso de retries, se termina la generación
    return 'final_node'

# ======================
# CONSTRUCCIÓN DEL GRAFO
# ======================
workflow = StateGraph(AgentState)
workflow.add_node('text_node', text_node)
workflow.add_node('process_image_node', process_image)
workflow.add_node('summarization_node', summarization_node)
workflow.add_node('agent_node', agent_node)
workflow.add_node('tool_call_node', tool_call_node)
workflow.add_node('rewrite_node', rewrite_node)
workflow.add_node('generate_response_node', generate_response_node)
workflow.add_node('max_retries_node', max_retries_node)
workflow.add_node('final_node', final_node)

workflow.add_conditional_edges(
    START, 
    input_router, 
    {
        'process_image_node': 'process_image_node', 
        'text_node': 'text_node'
    }
)
workflow.add_conditional_edges(
    'text_node', 
    should_continue, 
    ['summarization_node', 'agent_node']
)
workflow.add_conditional_edges(
    'process_image_node', 
    should_continue, 
    ['summarization_node', 'agent_node']
)
workflow.add_edge('summarization_node', 'agent_node')
workflow.add_conditional_edges(
    'agent_node', 
    custom_agent_router, 
    {
        'tool_call_node': 'tool_call_node',     # Caso: Usa herramienta
        'max_retries_node': 'max_retries_node', # Caso: Loop indefinido detectado
        'final_node': 'final_node'              # Caso: Respondió directamente
    }
)
workflow.add_conditional_edges(
    'tool_call_node', 
    grade_documents, 
    {
        'rewrite_node': 'rewrite_node', 
        'generate_response_node': 'generate_response_node'
    }
)
workflow.add_edge('rewrite_node', 'agent_node')
workflow.add_edge('generate_response_node', 'final_node')
workflow.add_edge('max_retries_node', 'final_node')
workflow.add_edge('final_node', END)

memory = MemorySaver()
graph = workflow.compile(checkpointer = memory)