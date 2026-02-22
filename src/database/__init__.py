from src.config import settings
from .db import DB

db = DB(settings.db.db_path)