#!/usr/bin/env python3
"""Ricalcolo batch progresso progetti e assegnazioni."""

from database import SessionLocal
from models import Assignment, Project
import crud


def main() -> int:
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.id.asc()).all()
        for project in projects:
            updated = crud.update_project_progress(db, project.id)
            if updated:
                print(
                    f"Project {updated.id}: "
                    f"ore_totali={updated.ore_totali}, "
                    f"ore_completate={updated.ore_completate}, "
                    f"progress={updated.progress_percentage:.2f}%"
                )

        assignments = db.query(Assignment).order_by(Assignment.id.asc()).all()
        for assignment in assignments:
            updated = crud.update_assignment_hours(db, assignment.id)
            if updated:
                print(
                    f"Assignment {updated.id}: "
                    f"completed_hours={updated.completed_hours}, "
                    f"progress={updated.progress_percentage:.2f}%"
                )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
