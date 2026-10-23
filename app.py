import logging

import anthropic
import pandas as pd
import streamlit as st

from backend import config, llm
from backend.database import ErreurBase, ouvrir_base
from backend.securite import valider_requete

st.set_page_config(page_title="HotelBot", page_icon="🏨", layout="centered")
logging.basicConfig(level=logging.INFO)
journal = logging.getLogger("hotelbot")

MAX_QUESTIONS = config.lire_entier("MAX_QUESTIONS_PAR_SESSION", 10)
MAX_CARACTERES = 300
TABLES = ["HOTELS", "TYPESCHAMBRE", "CHAMBRES", "CLIENTS", "RESERVATIONS", "OCCUPATIONS"]
EXEMPLES = [
    "Quels sont les hôtels 5 étoiles à Paris ?",
    "Je cherche une chambre pour moins de 100 € par nuit à Marseille",
    "Quelle est la suite la moins chère à Nice ?",
    "Combien de réservations sont prévues dans les 30 prochains jours ?",
]


@st.cache_resource
def base():
    """Une seule connexion en lecture seule, partagée par les sessions."""
    return ouvrir_base()


def initialiser_session():
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("nb_questions", 0)


def tableau(resultat: dict) -> pd.DataFrame:
    return pd.DataFrame(resultat["lignes"], columns=resultat["colonnes"])


def afficher_details(details: dict):
    """Requête SQL, décision de sécurité et résultats bruts : la réponse est vérifiable."""
    if details.get("sql"):
        with st.expander("📋 Requête SQL générée"):
            st.code(details["sql"], language="sql")
    if details.get("refus"):
        st.caption(f"🔒 Requête bloquée : {details['refus']}")
    if details.get("resultat") is not None:
        with st.expander("🗂️ Résultats bruts de la base"):
            st.dataframe(tableau(details["resultat"]), width="stretch")


def traiter_question(question: str) -> tuple[str, dict]:
    """Question → SQL (LLM) → validation → exécution en lecture seule → réponse (LLM)."""
    db = base()
    details = {}

    sql = llm.generer_requete_sql(question, db.dialecte)
    details["sql"] = sql

    validation = valider_requete(sql)
    if not validation.autorisee:
        journal.warning("Requête bloquée (%s) : %r", validation.raison, sql)
        details["refus"] = validation.raison
        return (
            "Je ne peux répondre qu'à des **questions de consultation** sur les hôtels, "
            "les chambres, les prix et les réservations présents dans la base. "
            "Les modifications (réserver, annuler, supprimer) et les informations absentes "
            "de la base (équipements, avis…) ne sont pas disponibles dans cette démo.",
            details,
        )

    resultat = db.lire(validation.sql)
    details["resultat"] = resultat
    return llm.rediger_reponse(question, resultat), details


def page_chatbot():
    st.title("💬 HotelBot")
    st.markdown(
        "Posez une question en français : elle est traduite en SQL par un LLM, "
        "exécutée **en lecture seule** sur la base, puis reformulée."
    )
    initialiser_session()

    with st.sidebar:
        st.header("Conversation")
        compteur = st.empty()  # rempli à la fin, une fois la question comptée
        if st.button("🗑️ Effacer la conversation", width="stretch"):
            st.session_state.messages = []
            st.rerun()
        st.markdown("---")
        st.markdown("**💡 Exemples de questions**")
        for exemple in EXEMPLES:
            st.markdown(f"• {exemple}")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            afficher_details(message.get("details", {}))

    def afficher_compteur():
        restantes = max(MAX_QUESTIONS - st.session_state.nb_questions, 0)
        compteur.caption(f"Questions restantes pour cette session : **{restantes}/{MAX_QUESTIONS}**")

    if st.session_state.nb_questions >= MAX_QUESTIONS:
        afficher_compteur()
        st.info("Limite de questions atteinte pour cette session de démonstration. Merci de votre visite !")
        return

    question = st.chat_input("Posez votre question ici…", max_chars=MAX_CARACTERES)
    if not question:
        afficher_compteur()
        return

    st.session_state.nb_questions += 1
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Recherche en cours…"):
            details = {}
            try:
                reponse, details = traiter_question(question)
            except ErreurBase as e:
                journal.error("Erreur SQL : %s", e)
                reponse = "La requête générée n'a pas pu être exécutée. Essayez de reformuler votre question."
            except anthropic.APIError as e:
                journal.error("Erreur API Claude : %s", e)
                reponse = "Le service d'IA est momentanément indisponible. Réessayez dans quelques instants."
            except Exception:
                journal.exception("Erreur inattendue")
                reponse = "Une erreur inattendue s'est produite."
        st.markdown(reponse)
        afficher_details(details)

    st.session_state.messages.append({"role": "assistant", "content": reponse, "details": details})
    afficher_compteur()


def page_donnees():
    st.title("🗄️ Données de démonstration")
    st.markdown("Contenu de la base (lecture seule). Toutes les données sont fictives, sauf les noms et adresses d'hôtels.")
    table = st.selectbox("Table", TABLES)  # liste fermée : pas d'injection possible
    resultat = base().lire(f"SELECT * FROM {table}", max_lignes=200)
    st.dataframe(tableau(resultat), width="stretch")
    if resultat["tronque"]:
        st.caption("Affichage limité aux 200 premières lignes.")


def page_securite():
    st.title("🔒 Sécurité")
    st.markdown(
        """
Le SQL produit par le LLM n'est **jamais considéré comme fiable**. Deux barrières indépendantes :

1. **Base en lecture seule.** La démo ouvre le fichier SQLite en mode lecture seule (`mode=ro`, `PRAGMA query_only`) ;
   la version Oracle utilise un utilisateur qui n'a que le droit `SELECT`. Même si une requête de modification passait,
   la base la refuserait.
2. **Validation de la requête dans le code**, avant exécution : une seule instruction, de type `SELECT`,
   sans commentaires ni mots-clés de modification (`DROP`, `DELETE`, `INSERT`…), y compris s'ils sont cachés.

S'y ajoutent : un prompt qui traite la question comme une donnée (contre l'injection de prompt), une limite de durée
par requête, un nombre maximal de lignes, un nombre limité de questions par session, et une limite de dépenses
sur la clé API.

Ces protections réduisent les risques, elles ne les suppriment pas : voir la section Limites du README.
"""
    )


def main():
    page = st.sidebar.radio("Navigation", ["Chatbot", "Données", "Sécurité"])
    st.sidebar.markdown("---")
    if page == "Chatbot":
        page_chatbot()
    elif page == "Données":
        page_donnees()
    else:
        page_securite()


main()
