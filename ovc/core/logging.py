import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def get_logger(name: str = "ovc"):
    return logging.getLogger(name)
