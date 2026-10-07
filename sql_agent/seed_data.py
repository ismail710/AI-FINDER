"""Populate the local freelancer database with deterministic sample data.

Run: ``python sql_agent/seed_data.py``
The seed is repeatable; existing records are not replaced.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

try:  # Supports both ``python sql_agent/seed_data.py`` and package imports.
    from .database import database_session, initialize_database
except ImportError:
    from database import database_session, initialize_database


SPECIALTIES = [
    ("Software development", ["Python", "Django", "PostgreSQL"], ["English", "Portuguese"]),
    ("Software development", ["React", "TypeScript", "Next.js"], ["English", "Spanish"]),
    ("Product design", ["Figma", "UX research", "Design systems"], ["English", "French"]),
    ("Digital marketing", ["SEO", "Google Ads", "Analytics"], ["English", "German"]),
    ("Data and AI", ["Python", "SQL", "Machine learning"], ["English", "Arabic"]),
    ("Mobile development", ["Flutter", "Dart", "Firebase"], ["English", "Italian"]),
    ("Content writing", ["Copywriting", "Content strategy", "SEO"], ["English", "Portuguese"]),
    ("Brand design", ["Illustrator", "Brand strategy", "Packaging"], ["English", "Spanish"]),
    ("DevOps", ["Docker", "Kubernetes", "AWS"], ["English", "Polish"]),
    ("Video production", ["Premiere Pro", "After Effects", "Storytelling"], ["English", "French"]),
    ("Cybersecurity", ["Security audit", "OWASP", "Python"], ["English", "Hindi"]),
    ("E-commerce", ["Shopify", "Liquid", "Conversion optimization"], ["English", "Dutch"]),
]

PEOPLE = [
    ("Amina Silva", "Lisbon, Portugal"), ("Liam Carter", "London, United Kingdom"),
    ("Sofia Martinez", "Madrid, Spain"), ("Noah Williams", "Toronto, Canada"),
    ("Maya Patel", "Bengaluru, India"), ("Lucas Moreau", "Paris, France"),
    ("Olivia Brown", "Melbourne, Australia"), ("Mateo Rossi", "Milan, Italy"),
    ("Zara Ahmed", "Dubai, United Arab Emirates"), ("Ethan Kim", "Seoul, South Korea"),
    ("Chloe Martin", "Montreal, Canada"), ("Daniel Costa", "Porto, Portugal"),
    ("Emma Johnson", "New York, United States"), ("Ravi Shah", "Mumbai, India"),
    ("Isla Thompson", "Edinburgh, United Kingdom"), ("Leo Garcia", "Mexico City, Mexico"),
    ("Nora Weber", "Berlin, Germany"), ("Samir Hassan", "Cairo, Egypt"),
    ("Ava Wilson", "Auckland, New Zealand"), ("Diego Fernandez", "Buenos Aires, Argentina"),
    ("Hana Novak", "Prague, Czech Republic"), ("Jack ONeill", "Dublin, Ireland"),
    ("Yuki Tanaka", "Tokyo, Japan"), ("Elena Popov", "Sofia, Bulgaria"),
    ("Amir Khan", "Karachi, Pakistan"), ("Mia Anderson", "Stockholm, Sweden"),
    ("Theo Dupont", "Lyon, France"), ("Layla Ibrahim", "Amman, Jordan"),
    ("Ben Foster", "Vancouver, Canada"), ("Camila Reyes", "Santiago, Chile"),
    ("Jonas Becker", "Hamburg, Germany"), ("Grace Chen", "Singapore"),
    ("Omar Farouk", "Casablanca, Morocco"), ("Ella Wright", "Manchester, United Kingdom"),
    ("Victor Santos", "Sao Paulo, Brazil"), ("Ana Kowalska", "Warsaw, Poland"),
]
TIMEZONES = ["Europe/Lisbon", "Europe/London", "Europe/Madrid", "America/Toronto", "Asia/Kolkata", "Europe/Paris"]
AVAILABILITY = ["available", "available", "partial", "available", "partial", "unavailable"]
PROJECT_SUFFIXES = ["platform refresh", "growth campaign", "customer portal", "analytics dashboard"]
INDUSTRIES = ["SaaS", "Healthcare", "Education", "Hospitality", "Retail", "Financial services"]


def as_json(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def build_freelancers() -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for index, (name, location) in enumerate(PEOPLE, start=1):
        work_field, skills, languages = SPECIALTIES[(index - 1) % len(SPECIALTIES)]
        availability = AVAILABILITY[(index - 1) % len(AVAILABILITY)]
        email = name.lower().replace(" ", ".") + "@example.test"
        rows.append((
            f"freelancer_{index:03d}", name, email, 22 + (index % 18),
            f"{work_field} specialist helping ambitious teams deliver reliable, measurable work.",
            f"https://portfolio.example.test/{index:03d}", f"https://images.example.test/profiles/{index:03d}.jpg",
            as_json([work_field.lower(), "startups", "remote work"]), as_json(languages), as_json(skills),
            work_field, 2 + (index % 12), location, TIMEZONES[(index - 1) % len(TIMEZONES)],
            float(30 + (index % 10) * 10), "USD", availability,
            (date(2026, 10, 1) + timedelta(days=index % 21)).isoformat() if availability != "unavailable" else None,
            10 + (index % 4) * 10, 1 if index % 5 == 0 else 0,
        ))
    return rows


def build_projects() -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for freelancer_index in range(1, len(PEOPLE) + 1):
        work_field, skills, _ = SPECIALTIES[(freelancer_index - 1) % len(SPECIALTIES)]
        for project_number, suffix in enumerate(PROJECT_SUFFIXES, start=1):
            industry = INDUSTRIES[(freelancer_index + project_number) % len(INDUSTRIES)]
            rows.append((
                f"project_{freelancer_index:03d}_{project_number:02d}", f"freelancer_{freelancer_index:03d}",
                f"{work_field} {suffix.title()}",
                f"Delivered a {suffix} for a {industry.lower()} client with clear outcomes and maintainable delivery.",
                as_json([f"https://images.example.test/projects/{freelancer_index:03d}-{project_number}.jpg"]),
                f"https://projects.example.test/{freelancer_index:03d}/{project_number}", work_field, as_json(skills),
                f"Lead {work_field} specialist", industry,
                date(2024 + (project_number % 2), ((freelancer_index + project_number) % 12) + 1, min(28, freelancer_index)).isoformat(),
                0 if project_number == 4 and freelancer_index % 7 == 0 else 1,
            ))
    return rows


def seed() -> tuple[int, int]:
    """Insert 36 freelancers and 144 projects, preserving existing records."""
    initialize_database()
    with database_session() as connection:
        before = connection.total_changes
        connection.executemany(
            """INSERT OR IGNORE INTO freelancers (
                id, name, email, age, bio, portfolio, photo, interests_json, languages_json,
                skills_json, work_field, experience_years, location, timezone, hourly_rate,
                currency, availability_status, available_from, weekly_capacity_hours, is_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            build_freelancers(),
        )
        freelancer_count = connection.total_changes - before
        before = connection.total_changes
        connection.executemany(
            """INSERT OR IGNORE INTO projects (
                id, freelancer_id, title, detail, photos_json, project_url, work_field,
                skills_used_json, role, client_industry, completed_at, is_public
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            build_projects(),
        )
        project_count = connection.total_changes - before
    return freelancer_count, project_count


if __name__ == "__main__":
    freelancers, projects = seed()
    print(f"Seed complete: {freelancers} freelancers and {projects} projects inserted.")
