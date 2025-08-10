import logging
import sys

# ANSI escape codes for colors
COLORS = {
    'DEBUG': '\033[36m',    # Cyan
    'INFO': '\033[32m',     # Green
    'WARNING': '\033[33m',  # Yellow
    'ERROR': '\033[31m',    # Red
    'CRITICAL': '\033[35m', # Magenta
    'RESET': '\033[0m'      # Reset
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Add spacing to match INFO alignment
        if record.levelname == 'DEBUG':
            record.levelname = 'DEBUG '  # Add space to align with "INFO "

        # Add color to the level name
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"

        return super().format(record)

def setup_logging():
    """Set up logging with colors and proper formatting"""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Create console handler with color formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(levelname)s:%(name)s:[%(funcName)s] %(message)s'
    )

    # Add formatter to handler
    console_handler.setFormatter(formatter)

    # Remove any existing handlers to avoid duplicates
    logger.handlers = []

    # Add handler to logger
    logger.addHandler(console_handler)

    # Suppress verbose HTTP/2 logs from supabase/httpx/hpack
    logging.getLogger('hpack').setLevel(logging.WARNING)  # Covers all hpack submodules
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('supabase').setLevel(logging.INFO)

    return logger