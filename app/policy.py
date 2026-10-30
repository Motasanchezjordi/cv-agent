import base64
import re
from dataclasses import dataclass

from app.textutil import fold

_INJECTION = re.compile(
    r"("
    r"\bignora\b.{0,40}\b(instrucciones|reglas|prompt)\b|"
    r"\bignore\b.{0,40}\b(instructions|rules|prompt)\b|"
    r"\b(system prompt|prompt del sistema|prompt interno|instrucciones internas|developer message)\b|"
    r"\bmuestr\w*\b.{0,50}\b(prompt|instrucciones|reglas)\b|"
    r"\b(revela|muestra|repite|ensenam|print)\b.{0,35}\b(prompt|instrucciones)\b|"
    r"\b(instrucciones|reglas) que te (dio|dieron)\b|"
    r"\b(jailbreak|modo desarrollador|developer mode)\b|"
    r"\bolvida\b.{0,35}\b(reglas|instrucciones|lo anterior|el cv)\b|"
    r"\bno tienes restricciones\b|"
    r"\bactua como si no tuvieras reglas\b|"
    r"\bignora todo\b|"
    r"\b(decodifica|decode)\b.{0,60}\b(base64|instruccion)\b|"
    r"\bejecuta su instruccion\b"
    r")"
)

_INVENT = re.compile(
    r"("
    r"\b(inventa|inventame|inventar|miente|mienteme)\b|"
    r"\b(fabrica|fabricar|crea|agrega|anade|incluye|escribe)\b.{0,50}"
    r"\b(experiencia|empleo|puesto|trabajo)\b.{0,40}\b(falsa|falso|inventad|fictici|que no)\b|"
    r"\b(experiencia|empleo|puesto)\b.{0,25}\b(falsa|falso|inventad|fictici)\b|"
    r"\b(haz de cuenta|supongamos|supon que|suponte|imagina que)\b.{0,80}"
    r"\b(trabajo|experiencia|empleo|empresa|puesto)\b|"
    r"\bmake up\b|\bfake experience\b|\binvent (an|a)\b"
    r")"
)

_PHONE = re.compile(
    r"("
    r"\b(telefono|celular|whatsapp|movil|cel)\b|"
    r"\b(su|tu) numero\b(?!\s+de\s+\w)|"
    r"\b(numero|num)\b.{0,24}\b(contacto|celular|tel|whats)\b|"
    r"\bphone number\b"
    r")"
)

_PRIVATE = re.compile(
    r"("
    r"\b(salario|sueldo|pretension economica)\b|"
    r"\bcuanto (gana|cobra|percibe)\b|"
    r"\b(edad|cumpleanos|fecha de nacimiento|estado civil|curp|rfc)\b|"
    r"\b(cuantos anos tiene|que edad tiene|anos tiene)\b|"
    r"\b(direccion|domicilio)\b.{0,25}\b(casa|particular|hogar)\b"
    r")"
)

_FALSE_EXIT = re.compile(
    r"\b(dejo|renuncio|renuncia)\b.{0,60}\brocketel\b|"
    r"\brocketel\b.{0,60}\b(dejo|renuncio|renuncia)\b|"
    r"\bsalio de\b.{0,40}\brocketel\b"
)

_SECRETS = re.compile(
    r"system_admin|\bcredenciales\b|\bpretension salarial\b|\bcontacto privados\b"
)

_FALSE_STACK = re.compile(
    r"(laravel|java).{0,90}(plataforma de ia|arquitectura backend)|"
    r"(plataforma de ia|arquitectura backend).{0,90}(laravel|java)"
)

_FALSE_CERTS = re.compile(r"\b(scrum master|pmp)\b")

_NEGATIVE_LIST = re.compile(
    r"\bno domina\b|\bevita utilizar\b|\bexplicitamente evita\b|"
    r"\bno (conoce|maneja|usa)\b|\bque no (domina|usa|maneja)\b"
)

_BREACH = re.compile(r"\b(filtracion|fuga de datos|brecha de datos|data breach)\b")

_FALSE_ENGLISH = re.compile(
    r"ingles.{0,140}(no esta capacitado|no puede|no es capaz|incapaz)|"
    r"(no esta capacitado|no puede|no es capaz|incapaz).{0,100}ingles"
)

_FALSE_SUPABASE = re.compile(
    r"supabase.{0,80}(vector|rag)|(vector|rag).{0,80}supabase"
)

_FALSE_JOIN = re.compile(
    r"(call center|agente de ia).{0,90}(unam|puntos)|"
    r"(unam|puntos).{0,90}(call center|agente de ia)"
)

_ATTACK = re.compile(
    r"("
    r"\b(sql injection|inyeccion sql|xss|payload)\b|"
    r"\b(script|codigo|exploit|poc)\b.{0,80}\b(vulnerab|inyeccion|exploit)\b|"
    r"\b(vulnerab|inyeccion)\b.{0,50}\b(script|codigo|exploit)\b"
    r")"
)

_OUT_OF_SCOPE = re.compile(
    r"("
    r"\bprecio\b.{0,30}\bacciones\b|"
    r"\b(cotizacion|stock price)\b|"
    r"\b(clima|pronostico del tiempo|poema|chiste|essay|ensayo)\b|"
    r"\bpresidente\b|"
    r"\bescribe(me)?\b.{0,20}\b(codigo|poema|chiste)\b"
    r")"
)

_GREETING_WORDS = {
    "hola", "hey", "hello", "hi", "saludos", "que", "tal", "onda", "buen",
    "dia", "buenos", "dias", "buenas", "tardes", "noches", "good", "morning",
    "afternoon", "evening", "jordi",
}
_GREETING_ANCHORS = (
    "hola", "hey", "hello", "hi", "saludos", "buenas", "buenos", "buen dia",
    "que tal", "que onda", "good morning", "good afternoon", "good evening",
)


@dataclass(frozen=True)
class PolicyDecision:
    kind: str
    message: str


def is_greeting(user_text: str) -> bool:
    folded = fold(user_text)
    folded = re.sub(r"[^a-z\s]", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    if not folded or not any(anchor in folded for anchor in _GREETING_ANCHORS):
        return False
    return all(word in _GREETING_WORDS for word in folded.split())


def _with_decoded(text: str) -> str:
    extra = []
    for token in re.findall(r"[A-Za-z0-9+/]{24,}={0,2}", text):
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.strip():
            extra.append(decoded)
    if not extra:
        return text
    return text + "\n" + "\n".join(extra)


def classify(user_text: str) -> PolicyDecision:
    folded = fold(_with_decoded(user_text))
    if _INJECTION.search(folded):
        return PolicyDecision(
            "refuse_injection",
            "No puedo compartir las instrucciones internas ni credenciales. "
            "Puedo ayudarte con la trayectoria profesional de Jordi.",
        )
    if _INVENT.search(folded):
        return PolicyDecision(
            "refuse_invent",
            "No voy a inventar experiencia, métricas ni empleos que no estén en el CV. "
            "Si quieres, te resumo lo que sí está documentado.",
        )
    if _SECRETS.search(folded):
        return PolicyDecision(
            "refuse_secrets",
            "No voy a generar credenciales, pretensión salarial ni datos de contacto privados.",
        )
    if _FALSE_STACK.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El backend documentado del CRM y el portal en Rocketel es Node.js y FastAPI, con PostgreSQL. "
            "Laravel y Java aparecen en el stack general. El CV no dice que la plataforma de IA empresarial esté hecha con ellos.",
        )
    if _FALSE_CERTS.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El CV lista Agile/Scrum, Kanban y Scaling Up como metodologías. "
            "No registra certificaciones de Scrum Master ni de PMP, ni un año en que las haya obtenido.",
        )
    if _NEGATIVE_LIST.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El CV lista lo que sí aparece en su stack. No dice qué lenguajes, bases o frameworks no domina ni cuáles evita. No voy a inventar esa lista.",
        )
    if _BREACH.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El CV no describe una filtración de PostgreSQL ni de ninguna otra base en 2024. "
            "Sí lista respuesta a incidentes como parte de su formación en ciberseguridad.",
        )
    if _FALSE_ENGLISH.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El CV dice que su inglés es intermedio. No dice que no pueda comunicarse con equipos internacionales ni leer documentación en inglés.",
        )
    if _FALSE_SUPABASE.search(folded):
        return PolicyDecision(
            "correct_premise",
            "El CV lista Supabase entre las bases de datos y describe un agente RAG interno en Rocketel. "
            "No dice que ese agente use una base vectorial en Supabase.",
        )
    if _FALSE_EXIT.search(folded):
        return PolicyDecision(
            "correct_premise",
            "Jordi no dejó Rocketel. El CV lo ubica como CTO y Full Stack desde 2024, "
            "y ese puesto sigue vigente. No hay una etapa en 2022 ni uso de AWS.",
        )
    if _FALSE_JOIN.search(folded):
        return PolicyDecision(
            "correct_premise",
            "Son dos cosas distintas. El agente de IA de call center es de Rocketel "
            "y el CV no dice en qué año se lanzó. En la UNAM, en 2023, Jordi trabajó "
            "en el sistema de puntos: incidencias y mejoras de interfaz, no en ese agente.",
        )
    if _ATTACK.search(folded):
        return PolicyDecision(
            "refuse_attack",
            "No genero código de ataque ni ejemplos de vulnerabilidades. "
            "Puedo hablar de la formación y la experiencia de Jordi en ciberseguridad.",
        )
    if _PHONE.search(folded):
        return PolicyDecision("sensitive_phone", "")
    if _PRIVATE.search(folded):
        return PolicyDecision(
            "private",
            "Eso no está en el CV y no lo voy a inferir.",
        )
    if _OUT_OF_SCOPE.search(folded):
        return PolicyDecision(
            "out_of_scope",
            "Este agente solo habla del perfil profesional de Jordi Adrián Mota Sánchez. "
            "Puedo contarte su experiencia, habilidades y proyectos.",
        )
    return PolicyDecision("allow", "")
