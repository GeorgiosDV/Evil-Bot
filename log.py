import logging
import os
from logging.handlers import RotatingFileHandler
import config

def setup_logging():
    # Get absolute path to logs directory from where the script is running
    # This is important when running as a service
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    
    # Try to create logs directory with explicit debugging
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            print(f"Created logs directory at: {log_dir}")  # Debug print
    except Exception as e:
        print(f"Failed to create logs directory: {e}")  # Debug print
        # Fall back to home directory if script directory isn't writable
        log_dir = os.path.join(os.path.expanduser('~'), 'Evil-Bot', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        print(f"Using fallback logs directory: {log_dir}")  # Debug print

    # Calculate size of each log file
    max_single_file = config.LOG_MAX_SIZE // (config.LOG_BACKUP_COUNT + 1)

    # Configure the main logger
    logger = logging.getLogger('evil_bot')
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)

    # File handler with detailed info
    log_file = os.path.join(log_dir, config.LOG_FILE_NAME)
    try:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_single_file,
            backupCount=config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_format)
        
        # Add both handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Log startup information
        logger.info('Logging system initialized')
        logger.info(f'Log directory: {log_dir}')
        logger.info(f'Log file: {log_file}')
        logger.info(f'Each log file size: {max_single_file / (1024*1024):.1f}MB')
        logger.info(f'Total log capacity: {config.LOG_MAX_SIZE / (1024*1024):.1f}MB')
    
    except Exception as e:
        print(f"Failed to set up file logging: {e}")  # Debug print
        # At least set up console logging if file logging fails
        logger.addHandler(console_handler)
        logger.error(f"Could not set up file logging: {e}")
    
    return logger