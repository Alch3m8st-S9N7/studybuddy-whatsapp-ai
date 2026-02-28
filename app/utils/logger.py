import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    """Provides a configured logger instance."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate logs if the logger is already setup
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create console handler with formatting
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger("whatsapp_bot")
