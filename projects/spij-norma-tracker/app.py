from __future__ import annotations

import difflib
import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests
import streamlit as st
from bs4 import BeautifulSoup

DB_PATH = Path(__file__).with_name("normas.db")


@dataclass
class NormaVersion:
    id: int
    norma_id: str
    fetched_at: str
    source_url: str
    content_hash: str
    content_text: str


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS norma_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                norma_id TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                content_text TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_norma_versions_lookup
            ON norma_versions(norma_id, fetched_at)
            """
        )


def normalize_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text)
    return compact.strip()


def extract_norma_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for selector in ["script", "style", "nav", "footer", "header"]:
        for node in soup.select(selector):
            node.decompose()

    text = soup.get_text("\n")
    lines = [normalize_text(line) for line in text.splitlines()]
    cleaned_lines = [line for line in lines if len(line) > 2]
    return "\n".join(cleaned_lines)


def hash_content(content_text: str) -> str:
    return hashlib.sha256(content_text.encode("utf-8")).hexdigest()


def fetch_norma(url: str, timeout_s: int = 30) -> str:
    response = requests.get(url, timeout=timeout_s)
    response.raise_for_status()
    return extract_norma_text(response.text)


def get_latest_version(norma_id: str) -> NormaVersion | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT *
            FROM norma_versions
            WHERE norma_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (norma_id,),
        ).fetchone()

    if not row:
        return None

    return NormaVersion(**dict(row))


def save_if_changed(norma_id: str, source_url: str, content_text: str) -> tuple[bool, str]:
    new_hash = hash_content(content_text)
    latest = get_latest_version(norma_id)

    if latest and latest.content_hash == new_hash:
        return False, new_hash

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO norma_versions(norma_id, fetched_at, source_url, content_hash, content_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                norma_id,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                source_url,
                new_hash,
                content_text,
            ),
        )

    return True, new_hash


def list_versions(norma_id: str) -> list[NormaVersion]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM norma_versions
            WHERE norma_id = ?
            ORDER BY fetched_at ASC
            """,
            (norma_id,),
        ).fetchall()

    return [NormaVersion(**dict(row)) for row in rows]


def html_diff(old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    differ = difflib.HtmlDiff(tabsize=2, wrapcolumn=120)
    return differ.make_table(old_lines, new_lines, context=True, numlines=4)


def iter_changes(old_text: str, new_text: str) -> Iterable[str]:
    for line in difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile="versión anterior",
        tofile="versión nueva",
        lineterm="",
    ):
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            yield line


def main() -> None:
    st.set_page_config(page_title="SPIJ Tracker", layout="wide")
    init_db()

    st.title("SPIJ Tracker de normas")
    st.caption(
        "Monitorea versiones de una norma y resalta cambios históricos. "
        "Úsalo con URLs públicas y respetando los términos de uso del portal."
    )

    norma_id = st.text_input("ID interno de la norma", placeholder="ej. LEY-26842")
    norma_url = st.text_input(
        "URL de la norma en SPIJ",
        placeholder="https://spijweb.minjus.gob.pe/...",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Capturar versión actual", type="primary"):
            if not norma_id or not norma_url:
                st.error("Debes ingresar ID y URL.")
            else:
                with st.spinner("Descargando y procesando contenido..."):
                    try:
                        content = fetch_norma(norma_url)
                        inserted, content_hash = save_if_changed(norma_id, norma_url, content)
                        if inserted:
                            st.success(f"Nueva versión guardada. Hash: {content_hash[:12]}")
                        else:
                            st.info("No hubo cambios respecto de la última versión guardada.")
                    except requests.RequestException as exc:
                        st.error(f"Error al descargar la norma: {exc}")

    versions = list_versions(norma_id) if norma_id else []

    st.subheader("Historial de versiones")
    if not versions:
        st.info("Aún no hay versiones para este ID.")
        return

    for idx, version in enumerate(versions, start=1):
        st.write(f"{idx}. {version.fetched_at} — hash {version.content_hash[:12]}")

    if len(versions) < 2:
        st.warning("Se necesitan al menos 2 versiones para mostrar diferencias.")
        return

    st.subheader("Comparador")
    left_col, right_col = st.columns(2)

    with left_col:
        old_idx = st.selectbox(
            "Versión base",
            options=range(len(versions)),
            format_func=lambda i: f"{i + 1}. {versions[i].fetched_at}",
            index=len(versions) - 2,
        )

    with right_col:
        new_idx = st.selectbox(
            "Versión nueva",
            options=range(len(versions)),
            format_func=lambda i: f"{i + 1}. {versions[i].fetched_at}",
            index=len(versions) - 1,
        )

    if old_idx >= new_idx:
        st.error("La versión base debe ser anterior a la versión nueva.")
        return

    old_version = versions[old_idx]
    new_version = versions[new_idx]

    st.markdown("#### Cambios relevantes (resumen)")
    changes = list(iter_changes(old_version.content_text, new_version.content_text))
    if not changes:
        st.info("No se detectaron cambios de texto.")
    else:
        for line in changes[:200]:
            if line.startswith("+"):
                st.markdown(f"<span style='color:#008000'>{line}</span>", unsafe_allow_html=True)
            elif line.startswith("-"):
                st.markdown(f"<span style='color:#cc0000'>{line}</span>", unsafe_allow_html=True)

        if len(changes) > 200:
            st.caption(f"Se muestran 200 de {len(changes)} cambios detectados.")

    st.markdown("#### Vista detallada")
    diff_html = html_diff(old_version.content_text, new_version.content_text)
    st.components.v1.html(diff_html, height=600, scrolling=True)


if __name__ == "__main__":
    main()
