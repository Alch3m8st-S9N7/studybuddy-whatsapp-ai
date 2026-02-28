from app.config import settings
from app.utils.logger import logger

class DBLogger:
    """
    (Optional) Stub or boilerplate for logging interactions.
    If SUPABASE_URL and SUPABASE_KEY are provided, this connects to Supabase.
    """
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_KEY
        self.client = None
        
        if self.url and self.key:
            try:
                from supabase import create_client, Client
                self.client: Client = create_client(self.url, self.key)
                logger.info("Supabase client initialized.")
            except ImportError:
                logger.warning("Supabase python client not installed.")
            except Exception as e:
                logger.warning(f"Could not initialize Supabase: {str(e)}")

    def log_interaction(self, user_phone: str, document_name: str, status: str):
        """Logs document interaction to a hypothetical 'interactions' table."""
        if not self.client:
            return
            
        try:
            data, count = self.client.table('interactions').insert({
                "user_phone": user_phone,
                "document_name": document_name,
                "status": status
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log to DB: {str(e)}")

db_logger = DBLogger()
