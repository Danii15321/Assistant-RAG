"""Annotations du corpus Iris ; lot final réservé, sans mesure lors du cadrage."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "evaluation"
rows = [
    ("factual", "Quelles deux opérations le RAG combine-t-il ?", ["R01"], ["recherche de passages", "génération fondée sur les passages"]),
    ("factual", "Quelle est la taille des passages dans l'atelier Iris ?", ["R02"], ["220 tokens"]),
    ("factual", "Quel chevauchement utilise l'atelier Iris ?", ["R02"], ["40 tokens"]),
    ("factual", "Combien de dimensions ont les vecteurs du cours Iris ?", ["R03"], ["384"]),
    ("factual", "Combien de passages la recherche Iris renvoie-t-elle ?", ["R04"], ["5"]),
    ("factual", "Quel seuil a été fixé dans le banc pédagogique Iris ?", ["R05"], ["0,78", "propre au banc pédagogique"]),
    ("factual", "Quelles informations une citation Iris affiche-t-elle ?", ["R06"], ["fichier", "page physique", "extrait"]),
    ("factual", "Quand ferment les inscriptions au parcours Iris 2026 ?", ["P01"], ["8 novembre 2026", "18 heures"]),
    ("factual", "Quelle part de la note dépend du projet final ?", ["P02"], ["40 pour cent"]),
    ("factual", "Où et quand se tient la permanence du cours Iris ?", ["P03"], ["mardi", "14 à 16 heures", "B214"]),
    ("factual", "Quelle adresse et quel TTL utilise le DNS du laboratoire ?", ["N02"], ["192.0.2.10", "120 secondes"]),
    ("factual", "Quel port utilise HTTPS dans le laboratoire ?", ["N03"], ["8443"]),
    ("factual", "Quel est l'ordre des vérifications pour un diagnostic réseau Iris ?", ["N04"], ["DNS", "port", "certificat TLS"]),
    ("factual", "Quelle est la taille maximale des fichiers du portail pédagogique Iris ?", ["R09"], ["12 Mio"]),
    ("factual", "Qui est responsable du parcours Iris 2026 ?", ["P06"], ["Léa Martin"]),
    ("multi_hop", "Quelle conservation prévaut en 2026 et que disait l'archive 2025 ?", ["P04", "A01"], ["45 jours", "30 jours auparavant", "règle du 1er septembre 2026 remplace 2025"]),
    ("multi_hop", "Pourquoi vérifier les références ne suffit-il pas à prouver la qualité des citations ?", ["R06", "R08"], ["références attribuées par le serveur", "fidélité : extrait justifie l'affirmation"]),
    ("multi_hop", "Quels ports HTTP et HTTPS utilise le laboratoire et comment diagnostiquer une panne HTTPS ?", ["N03", "N04"], ["8080", "8443", "DNS puis port puis certificat"]),
    ("multi_hop", "Combien d'étudiants peuvent former un groupe et que doivent-ils remettre à quelle date ?", ["P03", "P05"], ["trois maximum", "20 novembre 2026", "rapport dix pages", "démonstration cinq minutes"]),
    ("multi_hop", "Faut-il compter un quota épuisé comme une abstention et que mesure Recall@5 ?", ["R07", "R08"], ["erreur technique", "fraction des passages pertinents dans cinq premiers"]),
    ("out_of_corpus", "Quel est le prix d'inscription au parcours Iris ?", [], ["information absente"]),
    ("out_of_corpus", "Quel est le numéro de téléphone de Léa Martin ?", [], ["information absente"]),
    ("out_of_corpus", "Quelle version de PostgreSQL utilise le portail Iris ?", [], ["information absente"]),
    ("out_of_corpus", "Quelle est la capitale de la France ?", [], ["information absente du corpus, même si connue du modèle"]),
    ("out_of_corpus", "Dans les notes réseau sélectionnées, quand ferment les inscriptions Iris ?", [], ["information absente de la sélection"]),
    ("follow_up", "Et combien de modules y a-t-il ?", ["P01"], ["six"]),
    ("follow_up", "Et pour UDP ?", ["N01"], ["datagrammes", "sans garantie de livraison ni d'ordre"]),
    ("follow_up", "Et à combien s'élève le chevauchement ?", ["R02"], ["40 tokens"]),
    ("follow_up", "Combien de jours avant faut-il demander un report ?", ["P06"], ["deux jours"]),
    ("follow_up", "Et combien dure la démonstration ?", ["P05"], ["cinq minutes"]),
]
passages = {p["id"]: p for p in json.loads((root / "reference_passages.json").read_text(encoding="utf-8"))}
histories = {
    26: [("user", "Quand ferment les inscriptions au parcours Iris 2026 ?"), ("assistant", "Le 8 novembre 2026 à 18 heures [S1].")],
    27: [("user", "Que garantit TCP ?"), ("assistant", "Un flux ordonné avec retransmission [S1].")],
    28: [("user", "Quelle taille de passages utilise l'atelier Iris ?"), ("assistant", "220 tokens [S1].")],
    29: [("user", "Quand faut-il remettre le projet Iris ?"), ("assistant", "Le 20 novembre 2026 [S1].")],
    30: [("user", "Quel rapport faut-il remettre pour le projet Iris ?"), ("assistant", "Un rapport de dix pages maximum [S1].")],
}
# Stratification explicite avant toute mesure : 5 factuelles, 2 multi-passage,
# 2 hors corpus, 1 suivi. Ces dix cas ne sont pas évalués par le probe local.
reserved = {3, 7, 10, 12, 15, 17, 19, 22, 24, 30}
questions = []
for i, (kind, question, sources, elements) in enumerate(rows, 1):
    documents = None  # Bibliothèque entière par défaut ; pas de filtre issu du corrigé.
    if i == 25:
        documents = ["reseau"]
    questions.append({"id": f"Q{i:02}", "split": "final" if i in reserved else "development", "category": kind, "question": question, "history": [{"role": role, "content": text} for role, text in histories.get(i, [])], "document_ids": documents, "expected_state": "insufficient_context" if kind == "out_of_corpus" else "answered", "relevant_passage_ids": sources, "expected_elements": elements})
(root / "questions.jsonl").write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8")
print("30 annotations écrites : 20 réglage, 10 validation finale réservée.")
