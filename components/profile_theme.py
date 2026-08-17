"""Visual components for the My Profile page."""

import streamlit as st


def render_profile_styles() -> None:
    """Apply a lightweight, colorful visual system to the profile page."""
    st.markdown(
        """
        <style>
        .profile-hero {
            position: relative;
            overflow: hidden;
            padding: 2.1rem 2.25rem;
            margin-bottom: 1.25rem;
            border-radius: 24px;
            color: white;
            background:
                radial-gradient(circle at 90% 15%, rgba(103,232,249,.42), transparent 30%),
                linear-gradient(125deg, #4f46e5 0%, #7c3aed 48%, #db2777 100%);
            box-shadow: 0 18px 45px rgba(79, 70, 229, .24);
        }
        .profile-hero-badge {
            display: inline-block;
            padding: .35rem .7rem;
            margin-bottom: .75rem;
            border: 1px solid rgba(255,255,255,.35);
            border-radius: 999px;
            background: rgba(255,255,255,.14);
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .11em;
        }
        .profile-hero h1 {
            margin: 0 0 .45rem 0;
            color: white;
            font-size: clamp(2rem, 4vw, 3rem);
            line-height: 1.05;
        }
        .profile-hero p {
            max-width: 650px;
            margin: 0;
            color: rgba(255,255,255,.88);
            font-size: 1rem;
        }
        .profile-status-card {
            min-height: 112px;
            padding: 1rem 1.1rem;
            border: 1px solid rgba(124, 58, 237, .13);
            border-radius: 18px;
            background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(245,243,255,.9));
            box-shadow: 0 8px 24px rgba(76, 29, 149, .08);
        }
        .profile-status-icon {
            font-size: 1.25rem;
            line-height: 1;
        }
        .profile-status-label {
            margin-top: .55rem;
            color: #6b7280;
            font-size: .75rem;
            font-weight: 700;
            letter-spacing: .06em;
            text-transform: uppercase;
        }
        .profile-status-value {
            margin-top: .12rem;
            color: #312e81;
            font-size: 1.08rem;
            font-weight: 750;
        }
        .profile-section-heading {
            margin: 1.45rem 0 .25rem;
            color: #312e81;
            font-size: 1.35rem;
            font-weight: 800;
        }
        div[data-testid="stFileUploaderDropzone"] {
            border: 1.5px dashed rgba(124, 58, 237, .5);
            border-radius: 16px;
            background: rgba(245, 243, 255, .55);
        }
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            border-radius: 12px;
            font-weight: 700;
        }
        div.stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
            border: 0;
            background: linear-gradient(100deg, #4f46e5, #9333ea);
            box-shadow: 0 7px 18px rgba(79, 70, 229, .2);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(124, 58, 237, .13);
            border-radius: 18px;
        }
        button[data-baseweb="tab"] {
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_profile_hero() -> None:
    """Render the colorful profile-page introduction."""
    st.markdown(
        """
        <div class="profile-hero">
            <div class="profile-hero-badge">JOBPILOT AI · CANDIDATE PROFILE</div>
            <h1>My Profile</h1>
            <p>One trusted profile for every job analysis, application, and interview.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_card(icon: str, label: str, value: str) -> None:
    """Render a compact profile status card."""
    st.markdown(
        f"""
        <div class="profile-status-card">
            <div class="profile-status-icon">{icon}</div>
            <div class="profile-status-label">{label}</div>
            <div class="profile-status-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(icon: str, title: str) -> None:
    """Render a colorful section heading."""
    st.markdown(
        f'<div class="profile-section-heading">{icon}&nbsp;&nbsp;{title}</div>',
        unsafe_allow_html=True,
    )
