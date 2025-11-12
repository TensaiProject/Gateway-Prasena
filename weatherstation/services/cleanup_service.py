#!/usr/bin/env python3
"""
Data Cleanup Service
Cleans up uploaded data older than specified days
"""

import time
import argparse
from datetime import datetime
from typing import Dict, Any

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class CleanupService:
    """
    Service to cleanup old uploaded data from database
    """

    def __init__(
        self,
        db_path: str = './data/weatherstation.db',
        days_old: int = 7,
        run_once: bool = False
    ):
        """
        Initialize cleanup service

        Args:
            db_path: Path to database
            days_old: Delete data older than this many days
            run_once: If True, run once and exit. If False, run continuously
        """
        self.db = DatabaseManager(db_path)
        self.days_old = days_old
        self.run_once = run_once
        self.running = False

        logger.info(f"Cleanup Service initialized")
        logger.info(f"Database: {db_path}")
        logger.info(f"Cleanup threshold: {days_old} days")
        logger.info(f"Mode: {'One-time' if run_once else 'Continuous'}")

    def print_stats(self) -> Dict[str, Any]:
        """Print current database statistics"""
        logger.info("=" * 60)
        logger.info("Database Statistics")
        logger.info("=" * 60)

        stats = self.db.get_cleanup_stats()

        logger.info(f"Total Uploaded: {stats['total_uploaded']} records")
        logger.info(f"Total Pending:  {stats['total_pending']} records")
        logger.info("")

        for data_type, type_stats in stats['by_data_type'].items():
            logger.info(f"{data_type.upper()}:")
            logger.info(f"  Uploaded: {type_stats['uploaded']}")
            logger.info(f"  Pending:  {type_stats['pending']}")
            if type_stats['oldest_uploaded']:
                logger.info(f"  Oldest:   {type_stats['oldest_uploaded']}")
            logger.info("")

        logger.info("=" * 60)

        return stats

    def run_cleanup(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run cleanup operation

        Args:
            dry_run: If True, only show what would be deleted
        """
        logger.info("=" * 60)
        logger.info(f"Starting Cleanup Operation")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        if dry_run:
            logger.info("DRY RUN MODE - No data will be deleted")
        logger.info("=" * 60)

        # Get stats before cleanup
        logger.info("\nBefore Cleanup:")
        stats_before = self.db.get_cleanup_stats()
        logger.info(f"  Total uploaded records: {stats_before['total_uploaded']}")

        # Run cleanup
        results = self.db.cleanup_all_uploaded_data(
            days_old=self.days_old,
            dry_run=dry_run
        )

        # Get stats after cleanup
        if not dry_run:
            logger.info("\nAfter Cleanup:")
            stats_after = self.db.get_cleanup_stats()
            logger.info(f"  Total uploaded records: {stats_after['total_uploaded']}")
            logger.info(f"  Records deleted: {results['total_records_deleted']}")

        logger.info("\nCleanup Summary:")
        for data_type, result in results['data_types'].items():
            deleted = result.get('records_deleted', 0)
            if deleted > 0:
                logger.info(f"  {data_type}: {deleted} records deleted")

        logger.info("=" * 60)
        logger.info("Cleanup Complete")
        logger.info("=" * 60)

        return results

    def run(self, interval: int = 3600, dry_run: bool = False) -> int:
        """
        Main service loop

        Args:
            interval: Cleanup interval in seconds (default: 3600 = 1 hour)
            dry_run: If True, only show what would be deleted

        Returns:
            Exit code (0 for success)
        """
        logger.info("=" * 60)
        logger.info("Cleanup Service Starting...")
        logger.info("=" * 60)

        if self.run_once:
            # Run once and exit
            logger.info("Running one-time cleanup...")
            self.print_stats()
            self.run_cleanup(dry_run=dry_run)
            logger.info("One-time cleanup complete")
            return 0

        # Continuous mode
        self.running = True
        logger.info(f"Running in continuous mode")
        logger.info(f"Cleanup interval: {interval} seconds ({interval/3600:.1f} hours)")
        logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                try:
                    self.run_cleanup(dry_run=dry_run)

                except Exception as e:
                    logger.error(f"Error during cleanup: {e}", exc_info=True)

                # Sleep until next cleanup
                if self.running:
                    logger.info(f"Next cleanup in {interval} seconds...")
                    time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
        finally:
            self.stop()

        return 0

    def stop(self) -> None:
        """Stop the service"""
        logger.info("Cleanup Service stopping...")
        self.running = False
        logger.info("Cleanup Service stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Data Cleanup Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show statistics only
  %(prog)s --stats

  # Dry run (show what would be deleted)
  %(prog)s --dry-run

  # Run cleanup once (delete data older than 7 days)
  %(prog)s --once

  # Run cleanup once (delete data older than 30 days)
  %(prog)s --once --days 30

  # Run continuously (cleanup every hour)
  %(prog)s --interval 3600

  # Run continuously with custom database
  %(prog)s --db /path/to/db.sqlite --interval 3600
        """
    )

    parser.add_argument(
        '--db',
        default='./data/weatherstation.db',
        help='Path to database file'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Delete data older than this many days (default: 7)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run cleanup once and exit'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Cleanup interval in seconds (default: 3600 = 1 hour)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics and exit'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    parser.add_argument(
        '--log-file',
        default='./logs/cleanup_service.log',
        help='Log file path'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(
        log_level=args.log_level,
        log_file=args.log_file
    )

    try:
        # Create service
        service = CleanupService(
            db_path=args.db,
            days_old=args.days,
            run_once=args.once
        )

        # Show stats only
        if args.stats:
            logger.info("Fetching database statistics...")
            service.print_stats()
            return 0

        # Run cleanup
        return service.run(
            interval=args.interval,
            dry_run=args.dry_run
        )

    except Exception as e:
        logger.error(f"Failed to start cleanup service: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
