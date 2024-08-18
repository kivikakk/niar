import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

__all__ = ["logger", "logtime"]

logging.basicConfig(
    format="[%(asctime)s] %(name)s: %(levelname)s: %(message)s",
    level=logging.DEBUG,
)

logger = logging.getLogger("niar")


@contextmanager
def logtime(level: int, activity: str, /, fail_level: Optional[int] = None):
    global logger
    start = datetime.now()
    logger.log(level, "starting %s", activity)
    try:
        yield
    except:
        finish = datetime.now()
        logger.log(fail_level or level, "%s failed in %s", activity, finish - start)
        raise
    else:
        finish = datetime.now()
        logger.log(level, "%s finished in %s", activity, finish - start)
