"""Load an application adapter without imposing a model or domain dependency."""
from importlib.util import module_from_spec, spec_from_file_location
from functools import lru_cache
import os
import re
import sys

from .config import DATA, HOME, PLUGIN


def load_application(name, *, home, data_dir, settings):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise ValueError("Invalid application name")
    path = home / "plugins" / name / "__init__.py"
    spec = spec_from_file_location("qqbot_application_" + name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No application adapter at {path}")
    adapter = module_from_spec(spec)
    sys.modules[spec.name] = adapter
    try:
        spec.loader.exec_module(adapter)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    application = adapter.create_application(home=home, data_dir=data_dir, settings=settings)
    if not callable(getattr(application, "handle", None)):
        raise TypeError("Application must provide handle(request)")
    return application


@lru_cache(maxsize=1)
def get_application():
    return load_application(PLUGIN, home=HOME, data_dir=DATA, settings=dict(os.environ))
