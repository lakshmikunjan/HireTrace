import uuid
from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    last_scan_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
