"""Create the schema and insert deterministic sample freelancers/projects."""

from freelancer_finder.data.database import initialize_database
from freelancer_finder.data.seed import seed


if __name__ == "__main__":
    database = initialize_database()
    freelancers, projects = seed()
    print(f"Database: {database}")
    print(f"Inserted: {freelancers} freelancers, {projects} projects")

