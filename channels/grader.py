"""Run the application's optional offline reply reviewer.

    python -m channels.grader
"""
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-start", action="store_true")
    parser.parse_args()
    from . import settings as channel_settings
    from .app import create_application
    settings = channel_settings.load()
    application = create_application(settings=settings, data_dir=channel_settings.data_dir(settings))
    review = getattr(application, "review", None)
    if not callable(review):
        parser.error("The selected application has no reply reviewer")
    review()


if __name__ == "__main__":
    main()
