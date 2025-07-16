# app/logging_config.py
import logging
import sys

def setup_logging():
    """
    Configures the root logger for the application.
    This is more robust than basicConfig and works with Uvicorn/Gunicorn.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set the level for the root logger.
    # All module loggers will inherit this unless they set their own.
    root_logger.setLevel(logging.INFO)

    # Check if handlers are already configured to avoid duplicates
    if not root_logger.handlers:
        # Create a handler to write log messages to the console (standard output)
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Create a formatter to define the log mes	sage format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set the formatter for the handler
        console_handler.setFormatter(formatter)
        
        # Add the handler to the root logger
        root_logger.addHandler(console_handler)
        
        root_logger.info("Logging configured successfully.")
    else:
        root_logger.info("Logging already configured.")