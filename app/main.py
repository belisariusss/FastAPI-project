from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from app.db import SessionLocal, engine
from app.models import Base, User, Message, Ticket, Status
from app.crud import create_user, create_ticket, get_tickets
from app.schemas import (
    UserCreate, TicketCreate, TicketResponse, UserResponse, 
    MessageCreate, MessageResponse, TicketUpdate
)
from typing import Optional, List
from app.email_utils import send_email, read_emails_async
import asyncio
from app.tasks import send_email_task
from celery.result import AsyncResult
from app.tasks import read_emails_task

app = FastAPI()

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=UserResponse)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)

@app.post("/tickets/", response_model=TicketResponse)
async def create_new_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    created_ticket = create_ticket(db, ticket)
    user = db.query(User).filter(User.id == ticket.user_id).first()
    if user:
        asyncio.create_task(send_email(
            subject="Ваше обращение принято",
            recipient=user.email,
            body=f"Здравствуйте, {user.name or 'пользователь'}!\n\n"
                 f"Ваше обращение с темой '{created_ticket.subject}' принято и находится в обработке."
        ))
    return created_ticket

@app.get("/tickets", response_model=List[TicketResponse])
def get_tickets(
    status: Optional[Status] = Query(None, description="Фильтрация по статусу (например, OPEN, CLOSED)"),
    sort_by: Optional[str] = Query("created_at", description="Поле для сортировки (created_at)"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки: asc или desc"),
    db: Session = Depends(get_db),
):
    """
    Получение списка обращений с фильтрацией по статусу и сортировкой.
    """
    query = db.query(Ticket)

    
    if status:
        query = query.filter(Ticket.status == status)

    
    if sort_by == "created_at":
        if sort_order == "asc":
            query = query.order_by(asc(Ticket.created_at))
        elif sort_order == "desc":
            query = query.order_by(desc(Ticket.created_at))
        else:
            raise ValueError("Некорректный параметр sort_order. Допустимые значения: asc, desc")

    tickets = query.all()
    return tickets





@app.post("/messages/", response_model=MessageResponse)
async def send_message(message: MessageCreate, db: Session = Depends(get_db)):
    
    user = db.query(User).filter(User.id == message.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    
    ticket = db.query(Ticket).filter(Ticket.id == message.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    
    if ticket.status == Status.CLOSED:
        
        new_ticket = Ticket(
            user_id=message.user_id,
            subject=f"{ticket.subject} (новое обращение)",
            status=Status.NEW
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        ticket = new_ticket  
    
    
    new_message = Message(
        user_id=message.user_id,
        text=message.text,
        ticket_id=ticket.id,
        sender=message.sender
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

   
    operator = db.query(User).filter(User.id == ticket.operator_id).first() if ticket.operator_id else None
    if operator and operator.email and message.sender == "user":
        asyncio.create_task(send_email(
            subject=f"Новое сообщение по тикету #{ticket.id}",
            recipient=operator.email,
            body=f"Здравствуйте, {operator.name or 'Оператор'}!\n\n"
                 f"Пользователь {user.name or 'Неизвестный'} написал новое сообщение:\n\n"
                 f"{message.text}\n\n"
                 f"Пожалуйста, ответьте в системе."
        ))
    
    return new_message







@app.patch("/tickets/{ticket_id}", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: int,
    ticket_update: TicketUpdate,
    db: Session = Depends(get_db)
):
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    
    if ticket_update.status:
        ticket.status = ticket_update.status
    if ticket_update.message:
        ticket.message = ticket_update.message
    
    db.commit()
    db.refresh(ticket)
    
    
    if ticket.status == Status.CLOSED:
        user = db.query(User).filter(User.id == ticket.user_id).first()
        if user and user.email:
            
            asyncio.create_task(
                send_email(
                    subject="Ваше обращение закрыто",
                    recipient=user.email,
                    body=f"Здравствуйте, {user.name or 'пользователь'}!\n\n"
                         f"Ваше обращение с темой '{ticket.subject}' было успешно решено и закрыто.\n\n"
                         f"Если у вас возникнут дополнительные вопросы, пожалуйста, создайте новое обращение."
                )
            )
    
    return ticket



@app.patch("/tickets/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket_to_operator(
    ticket_id: int,
    operator_id: int,
    db: Session = Depends(get_db)
):
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    
    if ticket.status != Status.NEW:
        raise HTTPException(status_code=400, detail="Only new tickets can be assigned")

    
    operator = db.query(User).filter(User.id == operator_id, User.role == "operator").first()
    if not operator:
        raise HTTPException(status_code=404, detail="Operator not found")

    
    ticket.operator_id = operator_id
    db.commit()
    db.refresh(ticket)
    return ticket





@app.post("/tickets/{ticket_id}/reply")
async def reply_to_ticket(
    ticket_id: int,
    reply_message: str,
    db: Session = Depends(get_db)
):
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    
    if not ticket.operator_id:
        raise HTTPException(status_code=400, detail="Ticket is not assigned to any operator")

    
    user = db.query(User).filter(User.id == ticket.user_id).first()
    if not user or not user.email:
        raise HTTPException(status_code=404, detail="User or email not found")

    
    await send_email(
        subject=f"Ответ на ваше обращение: {ticket.subject}",
        recipient=user.email,
        body=reply_message
    )

    
    return {"message": "Reply sent successfully"}





@app.patch("/tickets/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(ticket_id: int, db: Session = Depends(get_db)):
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    
    if ticket.status == Status.CLOSED:
        raise HTTPException(status_code=400, detail="Ticket is already closed")
    
    
    ticket.status = Status.CLOSED
    db.commit()
    db.refresh(ticket)
    
    
    user = db.query(User).filter(User.id == ticket.user_id).first()
    if user and user.email:
        asyncio.create_task(send_email(
            subject="Ваше обращение закрыто",
            recipient=user.email,
            body=f"Здравствуйте, {user.name or 'пользователь'}!\n\n"
                 f"Ваше обращение с темой '{ticket.subject}' было успешно закрыто.\n\n"
                 f"Если у вас возникнут дополнительные вопросы, пожалуйста, создайте новое обращение."
        ))

    return ticket




    


@app.post("/emails/send_async/")
async def send_email_async(
    subject: str,
    recipient: str,
    body: str,
):
    """
    Эндпоинт для отправки email с использованием Celery.
    """
    task = send_email_task.delay(subject, recipient, body)
    return {"task_id": task.id, "message": "Email отправлен в очередь"}



@app.post("/emails/async/")
async def start_read_emails_task(limit: int = 5):
    """
    Эндпоинт для запуска задачи чтения писем с использованием Celery.
    """
    task = read_emails_task.delay(limit)
    return {"task_id": task.id, "status": "Task started"}

@app.get("/emails/async/{task_id}")
async def get_email_task_result(task_id: str):
    """
    Эндпоинт для проверки статуса задачи и получения результата с использованием Celery.
    """
    task_result = AsyncResult(task_id)
    if task_result.state == "PENDING":
        return {"status": "Task is pending"}
    elif task_result.state == "SUCCESS":
        return {"status": "Task completed", "result": task_result.result}
    elif task_result.state == "FAILURE":
        return {"status": "Task failed", "error": str(task_result.result)}
    return {"status": task_result.state}