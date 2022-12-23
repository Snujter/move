import logging
import sys
from pathlib import Path


# Logging formatter supporting colorized output
class LogFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.CRITICAL: "\033[1;35m",  # bright/bold magenta
        logging.ERROR:    "\033[1;31m",  # bright/bold red
        logging.WARNING:  "\x1b[38;5;226m",  # bright/bold yellow
        logging.INFO:     "\x1b[38;5;39m",  # blue
        logging.DEBUG:    "\033[0;37m"   # grey
    }

    TEXT_STYLES = {
        "bold": "\u001b[1m",
        "underline": "\u001b[4m",
        "reverse": "\u001b[7m",
    }

    RESET_CODE = "\033[0m"

    def __init__(self, color, *args, **kwargs):
        super(LogFormatter, self).__init__(*args, **kwargs)
        self.color = color

    def format(self, record, *args, **kwargs):
        if self.color and record.levelno in self.COLOR_CODES:
            record.color_on = self.COLOR_CODES[record.levelno]
            record.color_off = self.RESET_CODE
            record.color_reverse = self.TEXT_STYLES.get("reverse")
        else:
            record.color_on = ""
            record.color_off = ""
            record.color_reverse = ""
        return super(LogFormatter, self).format(record, *args, **kwargs)


# Setup logging
def setup_logging(
    console_log_output,
    console_log_level,
    console_log_color,
    logfile_file,
    logfile_log_level,
    logfile_log_color,
    log_line_template,
    libraries_log_level=None
):
    # Create logger
    # For simplicity, we use the root logger, i.e. call 'logging.getLogger()'
    # without name argument. This way we can simply use module methods
    # for logging throughout the script. An alternative would be exporting
    # the logger, i.e. 'global logger; logger = logging.getLogger("<name>")'
    if libraries_log_level is None:
        libraries_log_level = {}

    # create parent directories for log file if needed
    log_path = Path(logfile_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()

    # Set global log level to 'debug' (required for handler levels to work)
    logger.setLevel(logging.DEBUG)

    # Create console handler
    console_log_output = console_log_output.lower()
    if console_log_output == "stdout":
        console_log_output = sys.stdout
    elif console_log_output == "stderr":
        console_log_output = sys.stderr
    else:
        print(f"Failed to set console output: invalid output: {console_log_output}")
        return False
    console_handler = logging.StreamHandler(console_log_output)

    # Set console log level
    try:
        console_handler.setLevel(console_log_level.upper())  # only accepts uppercase level names
    except:
        print(f"Failed to set console log level: invalid level: {console_log_level}")
        return False

    # Create and set formatter, add console handler to logger
    console_formatter = LogFormatter(fmt=log_line_template, color=console_log_color, style='{', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Create log file handler
    try:
        logfile_handler = logging.FileHandler(logfile_file)
    except Exception as exception:
        print(f"Failed to set up log file: {str(exception)}")
        return False

    # Set log file log level
    try:
        logfile_handler.setLevel(logfile_log_level.upper())  # only accepts uppercase level names
    except:
        print(f"Failed to set log file log level: invalid level: {logfile_log_level}")
        return False

    # Create and set formatter, add log file handler to logger
    logfile_formatter = LogFormatter(fmt=log_line_template, color=logfile_log_color, style='{', datefmt='%H:%M:%S')
    logfile_handler.setFormatter(logfile_formatter)
    logger.addHandler(logfile_handler)

    for (library, log_level) in libraries_log_level.items():
        try:
            logging.getLogger(library).setLevel(log_level)
        except:
            print(f"Failed to set {log_level} as log level for library {library}")
            return False

    # Success
    return True
