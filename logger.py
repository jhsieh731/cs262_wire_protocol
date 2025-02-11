import logging

def set_logger(name, log_file):
    """Set up the logger with the given name and log file."""
    # Set up logging
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create file handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # clear file
    open(log_file, 'w').close()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(fh)

    return logger