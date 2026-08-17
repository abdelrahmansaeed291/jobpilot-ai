"""Shared visual system for JobPilot AI pages."""

from html import escape

import streamlit as st


def render_global_theme() -> None:
    """Apply the app-wide color palette, surfaces, and subtle motion."""
    st.markdown(
        """
        <style>
        @keyframes jobpilotFadeUp {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        [data-testid="stMainBlockContainer"] {
            animation: jobpilotFadeUp .38s ease-out;
            max-width: 1380px;
            padding-top: 2rem;
        }
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 90% 4%, rgba(196,181,253,.17), transparent 24%),
                radial-gradient(circle at 12% 92%, rgba(103,232,249,.12), transparent 25%);
        }
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(124,58,237,.12);
            background: linear-gradient(180deg, rgba(245,243,255,.97), rgba(255,255,255,.96));
        }
        [data-testid="stSidebarNavLink"] {
            margin: .18rem .45rem;
            border-radius: 11px;
            transition: transform .18s ease, background .18s ease;
        }
        [data-testid="stSidebarNavLink"]:hover {
            transform: translateX(3px);
            background: rgba(124,58,237,.09);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255,255,255,.76);
            box-shadow: 0 8px 28px rgba(76,29,149,.055);
            backdrop-filter: blur(10px);
        }
        div[data-testid="stMetric"] {
            padding: .9rem 1rem;
            border: 1px solid rgba(124,58,237,.12);
            border-radius: 16px;
            background: rgba(255,255,255,.82);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_feature_hero(
    eyebrow: str,
    title: str,
    description: str,
    icon: str,
    colors: tuple[str, str] = ("#4f46e5", "#9333ea"),
) -> None:
    """Render a reusable colorful hero for feature pages."""
    start, end = colors
    st.markdown(
        f"""
        <div style="padding:1.8rem 2rem;margin-bottom:1.25rem;border-radius:22px;
          color:white;overflow:hidden;position:relative;
          background:radial-gradient(circle at 90% 10%,rgba(255,255,255,.25),transparent 28%),
                     linear-gradient(120deg,{start},{end});
          box-shadow:0 16px 38px rgba(79,70,229,.2);">
          <div style="font-size:2rem;float:right">{escape(icon)}</div>
          <div style="font-size:.72rem;font-weight:800;letter-spacing:.12em;opacity:.82">
            {escape(eyebrow.upper())}
          </div>
          <div style="font-size:2.25rem;font-weight:850;line-height:1.15;margin:.35rem 0">
            {escape(title)}
          </div>
          <div style="max-width:700px;opacity:.88">{escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
