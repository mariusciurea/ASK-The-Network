"""Artifact browser for the current session."""

import base64
import json
import logging
from typing import Any

import streamlit as st

from frontend import state
from frontend.services.adk_service import ADKError, ADKService
from frontend.settings import settings


logger = logging.getLogger(__name__)

PREFERRED_ARTIFACT = "sql_command_output.json"
BINARY_MIME_PREFIXES = (
    "image/",
    "application/vnd.",
    "application/octet-stream",
    "application/pdf",
    "application/zip",
)


def _decode_artifact(artifact: dict[str, Any]) -> tuple[Any, bytes, str]:
    """Extract display data, raw bytes, and MIME type from an ADK Part.

    Raises:
        ValueError: The artifact is larger than the configured budget.
    """

    inline_data = artifact.get("inlineData") or artifact.get("inline_data")

    if inline_data:
        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or ""
        raw_data = base64.b64decode(inline_data.get("data", ""))

        if len(raw_data) > settings.MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"The artifact is {len(raw_data) // 1024} KB, over the "
                f"{settings.MAX_ARTIFACT_BYTES // 1024} KB display limit."
            )

        if any(mime_type.startswith(prefix) for prefix in BINARY_MIME_PREFIXES):
            return raw_data, raw_data, mime_type

        text_data = raw_data.decode("utf-8", errors="replace")

        if "json" in mime_type:
            try:
                return json.loads(text_data), raw_data, mime_type
            except json.JSONDecodeError:
                return text_data, raw_data, mime_type

        return text_data, raw_data, mime_type

    if "text" in artifact:
        text_data = artifact["text"]
        raw_data = text_data.encode("utf-8")
        try:
            return json.loads(text_data), raw_data, "application/json"
        except json.JSONDecodeError:
            return text_data, raw_data, "text/plain"

    raw_data = json.dumps(artifact, indent=2).encode("utf-8")
    return artifact, raw_data, "application/json"


def _render_payload(payload: Any, mime_type: str = "") -> None:
    """Render artifact content in the most useful available format."""

    if isinstance(payload, bytes) and mime_type.startswith("image/"):
        st.image(payload, use_container_width=True)
        return

    if isinstance(payload, bytes):
        st.info(
            f"Binary artifact ({len(payload) // 1024} KB, type: {mime_type}). "
            f"Use the download button above."
        )
        return

    if isinstance(payload, list):
        st.caption(f"{len(payload)} rows")
        preview = payload[: settings.MAX_ARTIFACT_PREVIEW_ROWS]
        if len(preview) < len(payload):
            st.caption(f"Showing the first {len(preview)} rows - download for the full set.")
        if all(isinstance(item, dict) for item in preview):
            st.dataframe(preview, use_container_width=True)
        else:
            st.json(preview)
        return

    if isinstance(payload, dict):
        st.json(payload)
        return

    st.markdown(str(payload))


def _artifact_names(client: ADKService, session_id: str, force_refresh: bool) -> list[str]:
    """Return the artifact names of a session, cached in the browser session."""

    cache_is_valid = (
        st.session_state[state.CACHED_ARTIFACTS_SESSION_ID] == session_id
        and st.session_state[state.CACHED_ARTIFACT_NAMES] is not None
    )
    if cache_is_valid and not force_refresh:
        return st.session_state[state.CACHED_ARTIFACT_NAMES]

    artifact_names = client.list_artifacts(session_id)
    st.session_state[state.CACHED_ARTIFACTS_SESSION_ID] = session_id
    st.session_state[state.CACHED_ARTIFACT_NAMES] = artifact_names
    return artifact_names


def render_artifacts(client: ADKService) -> None:
    """Render the artifacts attached to the current session."""

    session_id = st.session_state[state.CURRENT_SESSION_ID]
    if not session_id:
        return

    with st.expander("Artifacts", expanded=False):
        refresh = st.button("Refresh Artifacts", key=f"refresh_artifacts_{session_id}")

        try:
            artifact_names = _artifact_names(client, session_id, refresh)
        except ADKError as error:
            st.warning(f"Could not load artifacts: {error}")
            return

        if not artifact_names:
            st.info("No artifacts saved for this session yet")
            return

        default_index = (
            artifact_names.index(PREFERRED_ARTIFACT)
            if PREFERRED_ARTIFACT in artifact_names
            else 0
        )
        artifact_name = st.selectbox(
            "Artifact",
            options=artifact_names,
            index=default_index,
            key=f"artifact_selector_{session_id}",
        )

        try:
            versions_metadata = client.get_artifact_versions(session_id, artifact_name)
        except ADKError as error:
            st.warning(f"Could not load artifact versions: {error}")
            return

        if not versions_metadata:
            st.info("No versions available for this artifact")
            return

        version_options = [
            metadata.get("version")
            for metadata in sorted(
                versions_metadata,
                key=lambda item: item.get("version", 0),
                reverse=True,
            )
        ]
        selected_version = st.selectbox(
            "Version",
            options=version_options,
            key=f"artifact_version_selector_{session_id}_{artifact_name}",
        )

        selected_metadata = next(
            (
                metadata
                for metadata in versions_metadata
                if metadata.get("version") == selected_version
            ),
            {},
        )
        mime_type = selected_metadata.get("mimeType") or selected_metadata.get("mime_type")
        if mime_type:
            st.caption(f"Type: {mime_type}")

        if st.button(
            "Load Artifact",
            key=f"load_artifact_{session_id}_{artifact_name}_{selected_version}",
        ):
            try:
                artifact = client.get_artifact_version(
                    session_id, artifact_name, selected_version
                )
                payload, raw_data, loaded_mime_type = _decode_artifact(artifact)
            except (ADKError, ValueError) as error:
                st.error(f"Could not load artifact: {error}")
                return

            st.session_state[state.LOADED_ARTIFACT] = {
                "session_id": session_id,
                "artifact_name": artifact_name,
                "version": selected_version,
                "payload": payload,
                "raw_data": raw_data,
                "mime_type": loaded_mime_type,
            }

        loaded_artifact = st.session_state[state.LOADED_ARTIFACT]
        if not loaded_artifact:
            return

        matches_selection = (
            loaded_artifact["session_id"] == session_id
            and loaded_artifact["artifact_name"] == artifact_name
            and loaded_artifact["version"] == selected_version
        )
        if not matches_selection:
            return

        st.download_button(
            label="Download Artifact",
            data=loaded_artifact["raw_data"],
            file_name=artifact_name,
            mime=loaded_artifact["mime_type"] or "application/octet-stream",
            key=f"download_artifact_{session_id}_{artifact_name}_{selected_version}",
        )
        _render_payload(loaded_artifact["payload"], loaded_artifact["mime_type"])
