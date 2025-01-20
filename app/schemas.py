from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Status(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class TicketBase(BaseModel):
    subject: str
    message: str

class TicketCreate(TicketBase):
    user_id: int
    

class TicketUpdate(BaseModel):
    status: Optional[Status] = None
    message: Optional[str] = None

class TicketResponse(TicketBase):
    id: int
    created_at: datetime
    status: Status
    user_id: int
    message: Optional[str] = None  

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    name: str = None
    role: str = "user"  

    class Config:
        orm_mode = True

class UserResponse(UserBase):
    id: int
    email: str
    name: str
    role: str  

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    text: str
    sender: str

class MessageCreate(BaseModel):
    user_id: int
    text: str
    sender: str
    ticket_id: int  

class MessageResponse(MessageBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True
