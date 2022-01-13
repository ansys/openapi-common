import logging
import sys

Log_Format = "%(levelname)s %(asctime)s - %(message)s"

logging.basicConfig(stream=sys.stdout, format=Log_Format, level=logging.DEBUG)
