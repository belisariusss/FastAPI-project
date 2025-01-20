from sqlalchemy.orm import Session
from app.models import User, Ticket, Status
from app.schemas import UserCreate, TicketCreate, TicketUpdate


def create_user(db: Session, user: UserCreate):
    db_user = User(email=user.email, name=user.name, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def create_ticket(db: Session, ticket: TicketCreate):
    db_ticket = Ticket(
        subject=ticket.subject,
        message=ticket.message,
        user_id=ticket.user_id,
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def get_ticket(db: Session, ticket_id: int):
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()

def get_tickets(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Ticket).offset(skip).limit(limit).all()

def update_ticket(db: Session, ticket_id: int, ticket_update: TicketUpdate):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        return None

    for key, value in ticket_update.dict(exclude_unset=True).items():
        setattr(db_ticket, key, value)

    db.commit()
    db.refresh(db_ticket)
    return db_ticket





