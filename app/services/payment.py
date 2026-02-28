from app.config import settings
from app.utils.logger import logger

class PaymentService:
    """
    (Optional) Setup for razorpay to lock full-book functionality.
    """
    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.client = None
        
        if self.key_id and self.key_secret:
            try:
                import razorpay
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
                logger.info("Razorpay client initialized.")
            except ImportError:
                logger.warning("Razorpay library not installed.")
            except Exception as e:
                logger.warning(f"Could not initialize Razorpay: {str(e)}")

    def check_premium_status(self, user_phone: str) -> bool:
        """
        Check if the user has premium access via your DB.
        Stubbed to False by default to demonstrate lock context.
        """
        return False

    def generate_payment_link(self, amount: int = 9900, description: str = "Premium Document Processing") -> str:
        """Generates a payment link if client is enabled."""
        if not self.client:
            return "Payment system not configured. Contact admin."
            
        try:
            # AMOUNT IN PAISE (e.g., 9900 = 99 INR)
            payment_link = self.client.payment_link.create({
                "amount": amount,
                "currency": "INR",
                "accept_partial": False,
                "description": description,
                "customer": {
                    "name": "WhatsApp User",
                    "email": "user@example.com",
                    "contact": ""
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
            })
            return payment_link.get('short_url', "Error generating link.")
        except Exception as e:
            logger.error(f"Razorpay link error: {str(e)}")
            return "Failed to generate payment link due to server error."

payment_service = PaymentService()
