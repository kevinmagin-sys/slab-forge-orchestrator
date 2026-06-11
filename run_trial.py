import sys
import argparse
import logging
from routers.dispatcher import JobDispatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trial_runner")

class DispatchTarget:
    WEB_SCRAPE = "WEB_SCRAPE"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--catalog_ref", type=str, required=True)
    args = parser.parse_args()

    logger.info(f"Initializing trial run for task: {args.task}")
    logger.info(f"Target catalog reference: {args.catalog_ref}")

    # Initialize configuration mapping
    target_type = DispatchTarget.WEB_SCRAPE
    logger.info(f"Mapped execution routing mode to: {target_type}")

    # Invoke the dispatcher cleanly
    dispatcher = JobDispatcher(max_workers=3)
    logger.info("JobDispatcher successfully allocated.")
    
    print("\n[SUCCESS] Trial execution environment initialized cleanly.")

if __name__ == "__main__":
    main()
