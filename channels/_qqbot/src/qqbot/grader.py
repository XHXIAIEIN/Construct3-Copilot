"""Run the configured application's optional offline reply reviewer."""
import argparse

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-start", action="store_true")
    parser.parse_args()
    from .qq import get_application
    application = get_application()
    review = getattr(application, "review", None)
    if not callable(review):
        parser.error("The selected application has no reply reviewer")
    review()

if __name__ == "__main__":
    main()
