import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    last_scan_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
