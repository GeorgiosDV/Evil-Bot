import logging
import os
from logging.handlers import RotatingFileHandler
import config

def setup_logging():
    # get the path to the logs directory from the scripts working dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    
    # create the folder if it's not there
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    except Exception as e:
        log_dir = os.path.join(os.path.expanduser('~'), 'Evil-Bot', 'logs')
        os.makedirs(log_dir, exist_ok=True)

    max_single_file = config.LOG_MAX_SIZE // (config.LOG_BACKUP_COUNT + 1)

    logger = logging.getLogger('evil_bot')
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)

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
        

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        

        logger.info('Logging system initialized')
        logger.info(f'Log directory: {log_dir}')
        logger.info(f'Log file: {log_file}')
        logger.info(f'Each log file size: {max_single_file / (1024*1024):.1f}MB')
        logger.info(f'Total log capacity: {config.LOG_MAX_SIZE / (1024*1024*1024):.1f}GB')
    
    except Exception as e:
        logger.addHandler(console_handler)
        logger.error(f"Could not set up file logging: {e}")
    return logger