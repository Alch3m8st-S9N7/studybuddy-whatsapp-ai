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

    def log_interaction(self, user_phone: str, feature: str, details: str = ""):
        """Logs bot usage to the Supabase 'analytics' table."""
        if not self.client:
            return
            
        try:
            # User requested full visibility of users, so we insert raw phone number
            # (No masking)
            raw_phone = user_phone
            
            self.client.table('analytics').insert({
                "user_phone": raw_phone,
                "feature": feature,
                "details": details
            }).execute()
            logger.info(f"Analytics logged: {feature} - {details[:50]}")
        except Exception as e:
            logger.error(f"Failed to log to Supabase: {str(e)}")

db_logger = DBLogger()
