import logging
from openai import AzureOpenAI
from sqlalchemy.orm import Session
from app.core.config import settings
from app.repositories.research_likes_repository import ResearchLikesRepository
from app.repositories.research_visits_repository import ResearchVisitsRepository
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un asistente académico de la plataforma Red de Mujeres Investigadoras de la UNA. "
    "Responde en español de forma natural y cercana.\n\n"
    "Reglas estrictas:\n"
    "- Usa SOLO la información de los fragmentos proporcionados. No inventes ni supongas.\n"
    "- Cita las investigaciones de forma conversacional: 'Según \"Título\"...', 'En \"Título\" se aborda...'.\n"
    "- NUNCA menciones 'fragmentos', 'fuentes adjuntas', ni términos técnicos internos. "
    "Las fuentes se muestran automáticamente debajo de tu respuesta por el sistema.\n"
    "- NUNCA ofrezcas hacer cosas que no puedes (filtrar, buscar más, hacer nuevas búsquedas). "
    "Solo puedes responder con la información que se te proporciona en este mensaje.\n"
    "- Si no hay información relevante sobre lo que pregunta el usuario, dilo brevemente "
    "y sugiere 2-3 temas de la lista de investigaciones disponibles que se incluye al final del contexto. "
    "Preséntalo natural: 'No tengo investigaciones sobre ese tema, pero tengo sobre X, Y y Z. ¿Te interesa alguno?' "
    "No repitas información de mensajes anteriores.\n"
    "- Sé conciso. Máximo 2-3 párrafos cortos. No repitas lo que ya dijiste en la conversación.\n"
    "- No respondas preguntas que no tengan relación con investigaciones o la plataforma. "
    "Si preguntan algo fuera de contexto (ej: cálculos, trivia, clima), redirige brevemente: "
    "'Estoy aquí para ayudarte con investigaciones. ¿Hay algún tema académico que te interese?'\n"
    "- Varía tu estilo — no uses siempre la misma estructura ni las mismas frases de cierre."
)

MAX_HISTORY = 10
MIN_SCORE = 0.35
QDRANT_FETCH_LIMIT = 20
MAX_SOURCES = 5


def _get_chat_client():
    endpoint = settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY

    if not endpoint or not api_key:
        raise ValueError("Azure OpenAI chat configuration is missing")

    return AzureOpenAI(
        api_key=api_key,
        api_version="2025-04-01-preview",
        azure_endpoint=endpoint.replace("/openai/v1", ""),
    )


def _get_embedding_client():
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        raise ValueError("Azure OpenAI embedding configuration is missing")
    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )


def _embed_query(text: str) -> list[float]:
    client = _get_embedding_client()
    response = client.embeddings.create(
        input=[text],
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )
    return response.data[0].embedding


def _get_available_titles() -> list[str]:
    if not qdrant_service.is_enabled or not qdrant_service.client:
        return []
    try:
        results, _ = qdrant_service.client.scroll(
            collection_name=qdrant_service.collection_name,
            limit=100,
            with_payload=["title"],
            with_vectors=False,
        )
        titles = set()
        for point in results:
            title = (point.payload or {}).get("title", "")
            if title:
                titles.add(title)
        return sorted(titles)
    except Exception:
        return []


def _deduplicate_and_filter(results) -> tuple[list[str], dict]:
    best_per_research = {}
    for point in results:
        if point.score < MIN_SCORE:
            continue
        payload = point.payload or {}
        research_id = payload.get("research_id")
        if not research_id:
            continue

        if research_id not in best_per_research or point.score > best_per_research[research_id]["score"]:
            best_per_research[research_id] = {
                "point": point,
                "score": point.score,
                "title": payload.get("title", "Sin título"),
                "chunk": payload.get("chunk_text", ""),
                "user_id": payload.get("user_id"),
            }

    sorted_results = sorted(best_per_research.values(), key=lambda x: x["score"], reverse=True)[:MAX_SOURCES]

    chunks_text = []
    sources = {}
    for item in sorted_results:
        rid = item["point"].payload.get("research_id")
        if item["chunk"]:
            chunks_text.append(f"[{item['title']}]: {item['chunk']}")
        sources[rid] = {
            "research_id": rid,
            "title": item["title"],
            "user_id": item["user_id"],
            "score": round(item["score"], 4),
        }

    return chunks_text, sources


def _get_user_interests(db: Session, user_id: int) -> list[int]:
    likes = ResearchLikesRepository.list_recent_active_by_user(db, user_id=user_id, limit=5)
    liked_ids = {like.research_id for like in likes}
    visits = ResearchVisitsRepository.list_recent_by_user(db, user_id=user_id, limit=5)
    visit_ids = {v.research_id for v in visits}
    return list(liked_ids | visit_ids)


def _get_personalized_context(interest_ids: list[int]) -> tuple[list[str], dict]:
    if not interest_ids or not qdrant_service.is_enabled:
        return [], {}

    results = qdrant_service.search_by_research_ids(
        research_ids=interest_ids,
        limit=QDRANT_FETCH_LIMIT,
        exclude_research_ids=set(interest_ids),
    )

    if not results:
        return [], {}

    rag_results = qdrant_service.query_by_vector_for_rag(
        vector=qdrant_service.get_weighted_centroid(interest_ids),
        limit=QDRANT_FETCH_LIMIT,
    )

    return _deduplicate_and_filter(rag_results)


CLASSIFY_PROMPT = (
    "Clasifica la siguiente pregunta del usuario en una de estas categorías. "
    "Responde SOLO con la categoría, sin explicación.\n\n"
    "Categorías:\n"
    "- SEARCH: si pregunta sobre un tema académico, investigación, o quiere buscar información específica\n"
    "- RECOMMEND: si pide recomendaciones, sugerencias, o algo que le pueda interesar\n"
    "- GENERAL: si es un saludo, pregunta sobre la plataforma, o no requiere buscar investigaciones\n\n"
    "Pregunta: {question}"
)


def _classify_question(question: str) -> str:
    client = _get_chat_client()
    response = client.responses.create(
        model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        instructions="Responde SOLO con una palabra: SEARCH, RECOMMEND o GENERAL.",
        input=CLASSIFY_PROMPT.format(question=question),
    )
    result = (response.output_text or "").strip().upper()
    if result in ("SEARCH", "RECOMMEND", "GENERAL"):
        return result
    return "SEARCH"


class RAGService:
    @staticmethod
    def ask(question: str, db: Session | None = None, user_id: int | None = None, history: list[dict] | None = None) -> dict:
        if not settings.AZURE_OPENAI_CHAT_DEPLOYMENT:
            raise ValueError("Chat deployment is not configured")

        intent = _classify_question(question)

        # General questions — no search needed
        if intent == "GENERAL":
            general_prompt = (
                "Eres un asistente académico de la plataforma Red de Mujeres Investigadoras de la UNA. "
                "Responde en español de forma amable y breve (máximo 2-3 oraciones). "
                "Puedes ayudar al usuario a explorar investigaciones y recomendar temas. "
                "No menciones fragmentos, fuentes, ni aspectos técnicos internos. "
                "No respondas preguntas fuera de contexto (cálculos, trivia, etc). "
                "Si preguntan algo así, redirige brevemente hacia investigaciones. "
                "No repitas lo que ya dijiste en la conversación."
            )
            client = _get_chat_client()
            conversation_input = []
            if history:
                for msg in history[-MAX_HISTORY:]:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        conversation_input.append({"role": role, "content": content})
            conversation_input.append({"role": "user", "content": question})
            response = client.responses.create(
                model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                instructions=general_prompt,
                input=conversation_input,
            )
            return {
                "answer": response.output_text or "¡Hola! ¿En qué puedo ayudarte?",
                "sources": [],
            }

        # Recommendations — use user interests
        if intent == "RECOMMEND" and user_id and db:
            interest_ids = _get_user_interests(db, user_id)
            if interest_ids:
                personal_chunks, personal_sources = _get_personalized_context(interest_ids)
                if personal_chunks:
                    context = "\n\n".join(personal_chunks)
                    titles = ", ".join(f'"{s["title"]}"' for s in personal_sources.values())
                    conversation_input = []
                    if history:
                        for msg in history[-MAX_HISTORY:]:
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if role in ("user", "assistant") and content:
                                conversation_input.append({"role": role, "content": content})
                    conversation_input.append({
                        "role": "user",
                        "content": (
                            f"El usuario ha mostrado interés en ciertas investigaciones. "
                            f"Basándote en sus gustos, recomiéndale las siguientes investigaciones "
                            f"explicando por qué podrían interesarle.\n\n"
                            f"Investigaciones recomendadas: {titles}\n\n{context}\n\n"
                            f"---\nPregunta: {question}"
                        ),
                    })
                    client = _get_chat_client()
                    response = client.responses.create(
                        model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                        instructions=SYSTEM_PROMPT,
                        input=conversation_input,
                    )
                    return {
                        "answer": response.output_text or "No pude generar recomendaciones.",
                        "sources": list(personal_sources.values()),
                    }

        # Search — embed question and search Qdrant
        query_vector = _embed_query(question)
        results = qdrant_service.query_by_vector_for_rag(vector=query_vector, limit=QDRANT_FETCH_LIMIT)
        chunks_text, sources = _deduplicate_and_filter(results)

        # 2. If user_id provided and few results, add personalized context
        user_context = ""
        if user_id and db:
            interest_ids = _get_user_interests(db, user_id)
            if interest_ids:
                personal_chunks, personal_sources = _get_personalized_context(interest_ids)
                for rid, src in personal_sources.items():
                    if rid not in sources:
                        sources[rid] = src
                if personal_chunks:
                    user_context = (
                        "\n\nContexto adicional — Investigaciones relacionadas con los intereses del usuario "
                        "(basado en su historial de visitas y likes):\n\n"
                        + "\n\n".join(personal_chunks)
                    )

        # 3. Build conversation
        conversation_input = []

        if history:
            for msg in history[-MAX_HISTORY:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    conversation_input.append({"role": role, "content": content})

        if chunks_text:
            titles = ", ".join(f'"{s["title"]}"' for s in sources.values())
            context_block = (
                f"Contexto — Fragmentos de las siguientes investigaciones: {titles}\n\n"
                + "\n\n".join(chunks_text)
                + user_context
            )
        elif user_context:
            context_block = user_context.lstrip("\n")
        else:
            available = _get_available_titles()
            if available:
                titles_list = ", ".join(f'"{t}"' for t in available)
                context_block = (
                    f"No se encontró información relevante sobre la pregunta del usuario. "
                    f"Investigaciones disponibles en la plataforma: {titles_list}"
                )
            else:
                context_block = "No se encontró información relevante en la base de investigaciones."

        conversation_input.append({
            "role": "user",
            "content": f"{context_block}\n\n---\nPregunta: {question}",
        })

        # 4. Call GPT
        client = _get_chat_client()

        response = client.responses.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            instructions=SYSTEM_PROMPT,
            input=conversation_input,
        )

        answer = response.output_text or ""

        if not answer:
            answer = "No pude generar una respuesta. ¿Podrías reformular tu pregunta?"

        return {
            "answer": answer,
            "sources": list(sources.values()),
        }
