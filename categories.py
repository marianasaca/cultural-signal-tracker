"""Shared topic categories for the Cultural Signal Tracker.

Both the Google Trends collector and the NewsAPI collector import these,
so the two data sources stay aligned on the same categories/keywords.

The keywords are organized into three strategic pillars that frame how the
client views the US Hispanic consumer: economic resilience, bicultural
fusion, and heritage & milestones.
"""

KEYWORDS_BY_CATEGORY = {
    "economic_resilience": [
        "articulos de limpieza por galon",
        "cupones de walmart digitales",
        "marca equate opiniones",
        "envio de dinero sin comision",
        "walmart cash back policy",
        "comida congelada barata",
        "llantas usadas cerca de mi",
        "financiamiento de muebles sin credito",
        "precio del huevo por caja",
        "walmart delivery free trial",
        "apartamentos de un solo cuarto",
        "aplicaciones para ganar dinero facil",
        "seguro de auto mas barato",
        "herramientas hyper tough",
        "articulos de bebe usados",
        "gasolinera mas barata cerca de mi",
        "reparar pantalla de telefono precio",
        "tarjeta de debito para niños",
        "renta con todo incluido",
        "presupuesto mensual excel gratis",
    ],
    "bicultural_fusion": [
        "air fryer platanos maduros",
        "makeup routines for latina skin",
        "dupe de perfumes en walmart",
        "tacos de birria slow cooker",
        "best Hispanic creators on tiktok",
        "sneaker drops walmart",
        "organic baby food brands",
        "recetas de cocteles con mezcal",
        "smart home devices cheap",
        "protein powder para mujeres",
        "iced coffee en casa facil",
        "curled hair tutorials latinas",
        "gaming setup ideas",
        "sustainable clothing brands online",
        "keto diet alternatives spanish",
        "best budget soundbar for tv",
        "skincare minimalista pasos",
        "vlog de estilo de vida",
        "smartwatch fitness tracking cheap",
        "diy dorm room decor ideas",
    ],
    "heritage_milestones": [
        "dulces para piñata por mayoreo",
        "decoracion de mesa para boda civil",
        "traje de bautizo para niño walmart",
        "regalos de graduacion universitaria",
        "receta de tamales de puerco",
        "adornos para el dia de la madre",
        "rosca de reyes walmart",
        "vestidos de fiesta largos baratos",
        "velas de la virgen de guadalupe",
        "comida para baby shower moderna",
        "trajes tipicos de mexico",
        "regalos para el dia del padre",
        "musica para año nuevo bailable",
        "comida tipica de nochebuena",
        "arreglos de globos sencillos",
        "manteles de mesa elegantes",
        "receta de flan casero cremoso",
        "recuerdos para primera comunion",
        "maletas de mano para viajar",
        "disfraces de halloween familiares",
    ],
}

# Lookup from keyword -> category, and a flat list of every keyword.
KEYWORD_TO_CATEGORY = {
    kw: category
    for category, kws in KEYWORDS_BY_CATEGORY.items()
    for kw in kws
}
KEYWORDS = list(KEYWORD_TO_CATEGORY.keys())
