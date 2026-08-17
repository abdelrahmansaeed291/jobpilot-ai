"""Read-only portfolio components for the candidate profile page."""

from collections.abc import Iterable
from datetime import datetime
from html import escape
from urllib.parse import urlparse

import streamlit as st

from models.candidate_context import CandidateExtraInformation
from models.candidate_profile import CandidateProfile


def _text(value: object, fallback: str = "Not provided") -> str:
    """Return escaped display text for user-controlled profile values."""
    cleaned = str(value).strip() if value is not None else ""
    return escape(cleaned or fallback)


def _date(value: datetime | None) -> str:
    """Format a profile timestamp as a short local date."""
    return value.astimezone().strftime("%d %b %Y") if value else "Not saved"


def _safe_url(value: str) -> str | None:
    """Allow only normal web links in rendered project and credential cards."""
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    return escape(cleaned, quote=True) if parsed.scheme in {"http", "https"} else None


def _initials(name: str) -> str:
    """Build compact initials for the profile avatar."""
    parts = [part for part in name.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "JP"


def _pills(values: Iterable[str], css_class: str = "jp-pill") -> str:
    """Render a collection of values as safe HTML pills."""
    unique = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if not unique:
        return '<span class="jp-empty">Nothing added yet</span>'
    return "".join(
        f'<span class="{css_class}">{escape(value)}</span>' for value in unique
    )


def render_portfolio_styles() -> None:
    """Apply the responsive visual system used by the read-only portfolio."""
    st.markdown(
        """
        <style>
        @keyframes portfolioEnter {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .jp-portfolio { animation: portfolioEnter .45s ease-out; }
        .jp-profile-hero {
            position: relative; overflow: hidden; display: flex; align-items: center;
            gap: 1.4rem; padding: 2.1rem 2.2rem; margin-bottom: 1.1rem;
            border-radius: 26px; color: white;
            background: radial-gradient(circle at 88% 12%, rgba(255,255,255,.30), transparent 25%),
                        radial-gradient(circle at 8% 100%, rgba(34,211,238,.30), transparent 28%),
                        linear-gradient(125deg, #312e81 0%, #6d28d9 52%, #db2777 100%);
            box-shadow: 0 22px 55px rgba(79,70,229,.24);
        }
        .jp-avatar {
            flex: 0 0 auto; width: 92px; height: 92px; display: grid; place-items: center;
            border: 2px solid rgba(255,255,255,.55); border-radius: 28px;
            background: rgba(255,255,255,.16); backdrop-filter: blur(10px);
            font-size: 2rem; font-weight: 850; box-shadow: inset 0 0 25px rgba(255,255,255,.12);
        }
        .jp-eyebrow { font-size: .7rem; font-weight: 800; letter-spacing: .14em; opacity: .76; }
        .jp-profile-hero h1 { margin: .25rem 0 .25rem; color: white; font-size: clamp(2rem,4vw,3.15rem); line-height: 1.03; }
        .jp-profile-hero p { margin: 0; max-width: 760px; color: rgba(255,255,255,.86); font-size: 1rem; }
        .jp-contact-row { display: flex; flex-wrap: wrap; gap: .48rem; margin-top: .85rem; }
        .jp-contact { padding: .38rem .68rem; border: 1px solid rgba(255,255,255,.25); border-radius: 999px; background: rgba(255,255,255,.12); font-size: .8rem; }
        .jp-stats { display: grid; grid-template-columns: repeat(4,1fr); gap: .75rem; margin: 1rem 0 1.4rem; }
        .jp-stat { padding: 1rem 1.1rem; border: 1px solid rgba(124,58,237,.12); border-radius: 18px; background: linear-gradient(145deg,rgba(255,255,255,.96),rgba(245,243,255,.76)); box-shadow: 0 10px 30px rgba(76,29,149,.07); }
        .jp-stat-value { color: #4c1d95; font-size: 1.35rem; font-weight: 850; }
        .jp-stat-label { margin-top: .15rem; color: #6b7280; font-size: .72rem; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }
        .jp-section-title { display: flex; align-items: center; gap: .65rem; margin: 1.7rem 0 .75rem; color: #312e81; font-size: 1.3rem; font-weight: 850; }
        .jp-section-icon { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; background: linear-gradient(135deg,#ede9fe,#cffafe); }
        .jp-card { height: 100%; padding: 1.15rem 1.2rem; border: 1px solid rgba(124,58,237,.12); border-radius: 18px; background: rgba(255,255,255,.88); box-shadow: 0 9px 28px rgba(76,29,149,.06); }
        .jp-card-accent { border-top: 3px solid #8b5cf6; }
        .jp-card h3 { margin: 0 0 .25rem; color: #312e81; font-size: 1.02rem; }
        .jp-card h4 { margin: 0 0 .2rem; color: #4338ca; font-size: .88rem; }
        .jp-muted { color: #6b7280; font-size: .82rem; }
        .jp-body { margin-top: .65rem; color: #374151; font-size: .9rem; line-height: 1.58; white-space: pre-line; }
        .jp-pill-wrap { display: flex; flex-wrap: wrap; gap: .5rem; }
        .jp-pill { display: inline-flex; padding: .42rem .72rem; border: 1px solid #ddd6fe; border-radius: 999px; color: #5b21b6; background: linear-gradient(135deg,#f5f3ff,#ecfeff); font-size: .8rem; font-weight: 700; }
        .jp-pill-manual { display: inline-flex; padding: .42rem .72rem; border: 1px solid #a7f3d0; border-radius: 999px; color: #047857; background: #ecfdf5; font-size: .8rem; font-weight: 700; }
        .jp-timeline { position: relative; padding-left: 1.5rem; }
        .jp-timeline:before { content: ''; position: absolute; left: .35rem; top: .5rem; bottom: .5rem; width: 2px; background: linear-gradient(#8b5cf6,#22d3ee); }
        .jp-timeline-item { position: relative; margin-bottom: .8rem; }
        .jp-timeline-item:before { content: ''; position: absolute; left: -1.48rem; top: 1.25rem; width: 10px; height: 10px; border: 3px solid white; border-radius: 50%; background: #7c3aed; box-shadow: 0 0 0 2px #c4b5fd; }
        .jp-link { display: inline-block; margin-top: .7rem; color: #6d28d9; font-size: .82rem; font-weight: 750; text-decoration: none; }
        .jp-empty { color: #9ca3af; font-size: .86rem; font-style: italic; }
        .jp-note { padding: 1.1rem 1.2rem; border-radius: 18px; color: #134e4a; background: linear-gradient(135deg,#ecfdf5,#ecfeff); border: 1px solid #a7f3d0; line-height: 1.55; white-space: pre-line; }
        @media (max-width: 780px) {
            .jp-profile-hero { align-items: flex-start; flex-direction: column; padding: 1.6rem; }
            .jp-avatar { width: 72px; height: 72px; border-radius: 22px; font-size: 1.5rem; }
            .jp-stats { grid-template-columns: repeat(2,1fr); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_profile_hero(profile: CandidateProfile) -> None:
    """Render the candidate identity header without exposing private storage data."""
    contacts = [
        f"✉ {_text(profile.email)}" if profile.email else "",
        f"⌖ {_text(profile.location)}" if profile.location else "",
    ]
    contact_html = "".join(
        f'<span class="jp-contact">{item}</span>' for item in contacts if item
    )
    summary = profile.professional_summary or "Your professional story, ready for every opportunity."
    st.markdown(
        f"""
        <div class="jp-portfolio jp-profile-hero">
          <div class="jp-avatar">{escape(_initials(profile.name))}</div>
          <div>
            <div class="jp-eyebrow">JOBPILOT AI · CANDIDATE PORTFOLIO</div>
            <h1>{_text(profile.name, "Your Profile")}</h1>
            <p>{_text(summary)}</p>
            <div class="jp-contact-row">{contact_html}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_profile_stats(
    profile: CandidateProfile, extra: CandidateExtraInformation
) -> None:
    """Render quick portfolio totals in four colorful summary cards."""
    skill_count = len(
        set(profile.technical_skills)
        | {skill.skill_name for skill in extra.skills if skill.skill_name}
    )
    latest = max(
        (value for value in (profile.updated_at, extra.updated_at) if value),
        default=None,
    )
    cards = (
        (str(skill_count), "Skills"),
        (str(len(profile.work_experience) + len(extra.additional_experience)), "Experiences"),
        (str(len(profile.projects) + len(extra.projects)), "Projects"),
        (_date(latest), "Last updated"),
    )
    html = "".join(
        f'<div class="jp-stat"><div class="jp-stat-value">{_text(value)}</div>'
        f'<div class="jp-stat-label">{_text(label)}</div></div>'
        for value, label in cards
    )
    st.markdown(f'<div class="jp-stats">{html}</div>', unsafe_allow_html=True)


def render_section_title(icon: str, title: str) -> None:
    """Render a consistent portfolio section heading."""
    st.markdown(
        f'<div class="jp-section-title"><span class="jp-section-icon">{escape(icon)}</span>{escape(title)}</div>',
        unsafe_allow_html=True,
    )


def render_skills(profile: CandidateProfile, extra: CandidateExtraInformation) -> None:
    """Render CV and manually supplied skills as colorful pills."""
    render_section_title("⚡", "Skills & expertise")
    cv_skills = list(profile.technical_skills)
    cv_names = {value.casefold() for value in cv_skills}
    manual_skills = [
        skill.skill_name
        for skill in extra.skills
        if skill.skill_name.casefold() not in cv_names
    ]
    manual_html = _pills(manual_skills, "jp-pill-manual") if manual_skills else ""
    st.markdown(
        f'<div class="jp-card"><div class="jp-pill-wrap">{_pills(cv_skills)}{manual_html}</div></div>',
        unsafe_allow_html=True,
    )


def render_experience(profile: CandidateProfile, extra: CandidateExtraInformation) -> None:
    """Render professional and additional experience as a visual timeline."""
    render_section_title("💼", "Experience")
    blocks: list[str] = []
    for item in profile.work_experience:
        period = " — ".join(part for part in (item.start_date, item.end_date) if part)
        meta = " · ".join(part for part in (item.company, item.location, period) if part)
        blocks.append(
            f'<div class="jp-timeline-item"><div class="jp-card jp-card-accent">'
            f'<h3>{_text(item.job_title, "Role")}</h3><div class="jp-muted">{_text(meta, "Details not provided")}</div>'
            f'<div class="jp-body">{_text(item.description, "No description added.")}</div></div></div>'
        )
    for item in extra.additional_experience:
        tech = _pills(item.technologies, "jp-pill-manual")
        blocks.append(
            f'<div class="jp-timeline-item"><div class="jp-card jp-card-accent">'
            f'<h3>{_text(item.title)}</h3><div class="jp-muted">{_text(item.date, "Additional experience")}</div>'
            f'<div class="jp-body">{_text(item.description, "No description added.")}</div>'
            f'<div class="jp-pill-wrap" style="margin-top:.7rem">{tech}</div></div></div>'
        )
    content = "".join(blocks) or '<div class="jp-card"><span class="jp-empty">No experience added yet.</span></div>'
    st.markdown(f'<div class="jp-timeline">{content}</div>', unsafe_allow_html=True)


def render_education(profile: CandidateProfile) -> None:
    """Render education records as responsive cards."""
    render_section_title("🎓", "Education")
    if not profile.education:
        st.markdown('<div class="jp-card"><span class="jp-empty">No education added yet.</span></div>', unsafe_allow_html=True)
        return
    columns = st.columns(2)
    for index, item in enumerate(profile.education):
        period = " — ".join(part for part in (item.start_date, item.end_date) if part)
        with columns[index % 2]:
            description = _text(item.description, "") if item.description else ""
            st.markdown(
                f'<div class="jp-card jp-card-accent"><h3>{_text(item.degree, item.field_of_study or "Education")}</h3>'
                f'<h4>{_text(item.institution)}</h4><div class="jp-muted">{_text(period, "Date not provided")}</div>'
                f'<div class="jp-body">{description}</div></div>',
                unsafe_allow_html=True,
            )


def render_projects(profile: CandidateProfile, extra: CandidateExtraInformation) -> None:
    """Render CV and manually supplied projects as portfolio cards."""
    render_section_title("🚀", "Featured projects")
    projects: list[tuple[str, str, list[str], str, str]] = [
        (item.name, item.description, item.technologies, item.url, "")
        for item in profile.projects
    ] + [
        (item.project_name, item.description, item.technologies, item.url, item.github_url)
        for item in extra.projects
    ]
    if not projects:
        st.markdown('<div class="jp-card"><span class="jp-empty">No projects added yet.</span></div>', unsafe_allow_html=True)
        return
    columns = st.columns(2)
    for index, (name, description, technologies, url, github_url) in enumerate(projects):
        links: list[str] = []
        if safe_url := _safe_url(url):
            links.append(f'<a class="jp-link" href="{safe_url}" target="_blank">View project ↗</a>')
        if safe_github := _safe_url(github_url):
            links.append(f'<a class="jp-link" style="margin-left:1rem" href="{safe_github}" target="_blank">GitHub ↗</a>')
        with columns[index % 2]:
            st.markdown(
                f'<div class="jp-card jp-card-accent"><h3>{_text(name, "Project")}</h3>'
                f'<div class="jp-body">{_text(description, "No description added.")}</div>'
                f'<div class="jp-pill-wrap" style="margin-top:.75rem">{_pills(technologies)}</div>{"".join(links)}</div>',
                unsafe_allow_html=True,
            )


def render_more(profile: CandidateProfile, extra: CandidateExtraInformation) -> None:
    """Render languages, certifications, and free-form context."""
    left, right = st.columns(2)
    with left:
        render_section_title("🌍", "Languages")
        language_html = "".join(
            f'<div style="display:flex;justify-content:space-between;gap:1rem;padding:.55rem 0;border-bottom:1px solid #ede9fe">'
            f'<strong>{_text(item.name)}</strong><span class="jp-muted">{_text(item.proficiency, "Not specified")}</span></div>'
            for item in profile.languages
        ) or '<span class="jp-empty">No languages added yet.</span>'
        st.markdown(f'<div class="jp-card">{language_html}</div>', unsafe_allow_html=True)
    with right:
        render_section_title("🏅", "Certifications")
        certifications = [
            (item.name, item.issuer, item.date, item.credential_url)
            for item in profile.certifications
        ] + [
            (item.name, item.issuer, item.date, "") for item in extra.certifications
        ]
        certification_blocks: list[str] = []
        for name, issuer, date, url in certifications:
            link = ""
            if safe := _safe_url(url):
                link = f'<a class="jp-link" href="{safe}" target="_blank">View credential ↗</a>'
            details = " · ".join(part for part in (issuer, date) if part)
            certification_blocks.append(
                f'<div style="padding:.45rem 0 .65rem;border-bottom:1px solid #ede9fe"><strong>{_text(name)}</strong>'
                f'<div class="jp-muted">{_text(details, "Details not provided")}</div>{link}</div>'
            )
        certification_html = "".join(certification_blocks) or '<span class="jp-empty">No certifications added yet.</span>'
        st.markdown(f'<div class="jp-card">{certification_html}</div>', unsafe_allow_html=True)
    if extra.other_information:
        render_section_title("✦", "More about me")
        st.markdown(f'<div class="jp-note">{_text(extra.other_information)}</div>', unsafe_allow_html=True)


def render_candidate_portfolio(
    profile: CandidateProfile, extra: CandidateExtraInformation
) -> None:
    """Render the complete read-only candidate portfolio."""
    render_portfolio_styles()
    render_profile_hero(profile)
    render_profile_stats(profile, extra)
    render_skills(profile, extra)
    render_experience(profile, extra)
    render_education(profile)
    render_projects(profile, extra)
    render_more(profile, extra)
