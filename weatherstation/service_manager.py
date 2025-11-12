#!/usr/bin/env python3
"""
Production-Quality Multi-Threaded Service Manager
Manages all gateway services in a single process with proper threading
"""

import sys
import time
import signal
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime

from weatherstation.utils.logger import get_logger

logger = get_logger(__name__)


class ServiceThread:
    """
    Wrapper for a service thread with monitoring and auto-restart
    """

    def __init__(
        self,
        name: str,
        target: Callable,
        args: tuple = (),
        auto_restart: bool = True,
        restart_delay: int = 10
    ):
        """
        Args:
            name: Service name
            target: Function to run in thread
            args: Arguments for target function
            auto_restart: Auto-restart on failure
            restart_delay: Seconds to wait before restart
        """
        self.name = name
        self.target = target
        self.args = args
        self.auto_restart = auto_restart
        self.restart_delay = restart_delay

        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.stop_event = threading.Event()
        self.restart_count = 0
        self.last_start = None
        self.last_error = None

    def start(self):
        """Start the service thread"""
        if self.thread and self.thread.is_alive():
            logger.warning(f"Service {self.name} already running")
            return

        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run_with_monitoring,
            name=self.name,
            daemon=False  # Non-daemon for graceful shutdown
        )
        self.thread.start()
        self.last_start = datetime.now()
        logger.info(f"Service {self.name} started")

    def _run_with_monitoring(self):
        """Run target with exception monitoring"""
        while self.running and not self.stop_event.is_set():
            try:
                logger.info(f"[{self.name}] Starting service...")
                self.target(*self.args)

                # If target returns normally (not expected for services)
                if self.running:
                    logger.warning(f"[{self.name}] Service exited normally")
                    if self.auto_restart:
                        logger.info(f"[{self.name}] Restarting in {self.restart_delay}s...")
                        self.stop_event.wait(self.restart_delay)
                    else:
                        break

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"[{self.name}] Service crashed: {e}", exc_info=True)

                if self.running and self.auto_restart:
                    self.restart_count += 1
                    logger.info(
                        f"[{self.name}] Auto-restart #{self.restart_count} "
                        f"in {self.restart_delay}s..."
                    )
                    self.stop_event.wait(self.restart_delay)
                else:
                    break

        logger.info(f"[{self.name}] Thread stopped")

    def stop(self, timeout: int = 10):
        """
        Stop the service thread gracefully

        Args:
            timeout: Seconds to wait for graceful shutdown
        """
        if not self.thread or not self.thread.is_alive():
            return

        logger.info(f"Stopping service {self.name}...")
        self.running = False
        self.stop_event.set()

        # Wait for thread to finish
        self.thread.join(timeout=timeout)

        if self.thread.is_alive():
            logger.warning(f"Service {self.name} did not stop gracefully")
        else:
            logger.info(f"Service {self.name} stopped")

    def is_alive(self) -> bool:
        """Check if thread is running"""
        return self.thread is not None and self.thread.is_alive()

    def get_status(self) -> Dict:
        """Get service status"""
        return {
            'name': self.name,
            'running': self.is_alive(),
            'restart_count': self.restart_count,
            'last_start': self.last_start.isoformat() if self.last_start else None,
            'last_error': self.last_error
        }


class ServiceManager:
    """
    Production-quality service manager for multi-threaded execution
    """

    def __init__(self):
        self.services: Dict[str, ServiceThread] = {}
        self.running = False
        self._shutdown_event = threading.Event()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info("ServiceManager initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.stop_all()

    def register_service(
        self,
        name: str,
        target: Callable,
        args: tuple = (),
        auto_restart: bool = True
    ):
        """
        Register a service to be managed

        Args:
            name: Service name
            target: Service main function
            args: Arguments for service function
            auto_restart: Enable auto-restart on failure
        """
        if name in self.services:
            logger.warning(f"Service {name} already registered")
            return

        service = ServiceThread(
            name=name,
            target=target,
            args=args,
            auto_restart=auto_restart
        )
        self.services[name] = service
        logger.info(f"Registered service: {name}")

    def start_all(self):
        """Start all registered services"""
        if self.running:
            logger.warning("Services already running")
            return

        self.running = True
        logger.info("=" * 60)
        logger.info("Starting all services...")
        logger.info("=" * 60)

        for name, service in self.services.items():
            try:
                service.start()
                time.sleep(0.5)  # Stagger startup
            except Exception as e:
                logger.error(f"Failed to start {name}: {e}")

        logger.info(f"Started {len(self.services)} services")

    def stop_all(self, timeout: int = 10):
        """
        Stop all services gracefully

        Args:
            timeout: Seconds to wait per service
        """
        if not self.running:
            return

        logger.info("=" * 60)
        logger.info("Stopping all services...")
        logger.info("=" * 60)

        self.running = False
        self._shutdown_event.set()

        # Stop all services
        for name, service in self.services.items():
            try:
                service.stop(timeout=timeout)
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        logger.info("All services stopped")

    def monitor_loop(self, check_interval: int = 30):
        """
        Monitor services and print status

        Args:
            check_interval: Seconds between status checks
        """
        logger.info("Service monitor started (Ctrl+C to stop)")

        try:
            while self.running and not self._shutdown_event.is_set():
                # Wait for interval or shutdown
                if self._shutdown_event.wait(timeout=check_interval):
                    break

                # Check service health
                all_alive = True
                for name, service in self.services.items():
                    if not service.is_alive():
                        all_alive = False
                        logger.warning(f"Service {name} is not running!")

                if all_alive:
                    logger.debug("All services running normally")

        except KeyboardInterrupt:
            logger.info("Monitor interrupted")

    def get_status_all(self) -> List[Dict]:
        """Get status of all services"""
        return [service.get_status() for service in self.services.values()]

    def print_status(self):
        """Print status of all services"""
        logger.info("=" * 60)
        logger.info("Service Status:")
        logger.info("=" * 60)

        for service in self.services.values():
            status = service.get_status()
            running_str = "RUNNING" if status['running'] else "STOPPED"
            logger.info(
                f"  {status['name']}: {running_str} "
                f"(restarts: {status['restart_count']})"
            )
            if status['last_error']:
                logger.info(f"    Last error: {status['last_error']}")

        logger.info("=" * 60)

    def run(self):
        """
        Start all services and run monitoring loop
        Returns when shutdown is requested
        """
        try:
            self.start_all()
            time.sleep(2)  # Let services initialize
            self.print_status()
            self.monitor_loop()

        except Exception as e:
            logger.error(f"ServiceManager error: {e}", exc_info=True)

        finally:
            self.stop_all()
