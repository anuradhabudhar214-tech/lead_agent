from crunchbase_tracker import run_tracker, load_config
import logging

if __name__ == "__main__":
    logging.info("🛠️ Running single test cycle...")
    try:
        run_tracker()
    except Exception as e:
        logging.error(f"❌ Test run failed: {e}")
