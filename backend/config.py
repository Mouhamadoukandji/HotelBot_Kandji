"""Lecture de la configuration : secrets Streamlit en ligne, variables d'environnement en local."""
import os

from dotenv import load_dotenv

load_dotenv()


def lire(nom: str, defaut: str | None = None) -> str | None:
    """Cherche d'abord dans st.secrets (Streamlit Cloud), puis dans l'environnement (.env, Docker)."""
    try:
        import streamlit as st

        if nom in st.secrets:
            return str(st.secrets[nom])
    except Exception:
        # Pas de fichier secrets.toml, ou Streamlit absent (tests, scripts).
        pass
    return os.getenv(nom, defaut)


def lire_entier(nom: str, defaut: int) -> int:
    valeur = lire(nom)
    try:
        return int(valeur) if valeur is not None else defaut
    except ValueError:
        return defaut
