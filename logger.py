import logging
import os

def set_logger(name, log_file):
    """Set up the logger with the given name and log file."""
    # Set up logging
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)

    # Create file handler
    log_file = "logs/" + log_file
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)  # Capture all levels

    # clear file
    open(log_file, 'w').close()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(fh)

    return logger