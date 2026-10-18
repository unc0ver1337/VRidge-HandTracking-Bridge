"""Entry point for the packaged console executable."""
from pc.bridge import main

if __name__ == '__main__':
    import logging,sys
    try:main()
    except Exception:
        logging.exception('Bridge startup failed')
        if getattr(sys,'frozen',False) and sys.stdin and sys.stdin.isatty():
            input('Press Enter to close. See bridge.log for details. ')
        raise SystemExit(1)
