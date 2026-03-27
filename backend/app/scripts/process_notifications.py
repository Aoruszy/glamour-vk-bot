from app.db.session import SessionLocal, init_db
from app.services.notifications import process_due_notifications


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = process_due_notifications(db)
    print(result)


if __name__ == "__main__":
    main()
