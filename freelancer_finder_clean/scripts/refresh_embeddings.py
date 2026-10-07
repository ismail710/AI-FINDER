"""Rebuild profile embeddings, then attach combined public-project vectors."""

from freelancer_finder.embeddings.profiles import refresh_profile_embeddings
from freelancer_finder.embeddings.projects import embed_projects


if __name__ == "__main__":
    profiles = refresh_profile_embeddings()
    projects, total = embed_projects()
    print(f"Profile embeddings: {profiles}")
    print(f"Project embeddings: {projects}/{total}")

