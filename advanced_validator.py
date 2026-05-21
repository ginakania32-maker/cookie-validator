"""
Advanced validator with async queue, worker pool, and concurrent processing.
Production-ready async architecture with proper resource management.
"""

import asyncio
import json
import logging
from typing import List, Optional, Dict, Set
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from validator import CookieValidator
from config import CONFIG, ValidationStatus, ValidationResult
from helpers.cookie_helpers import FileScanner
from helpers.logger import StatusIndicators


logger = logging.getLogger(__name__)


class ValidatorQueue:
    """Async queue for validation tasks."""
    
    def __init__(self, max_size: int = CONFIG.QUEUE_SIZE):
        """
        Initialize queue.
        
        Args:
            max_size: Maximum queue size
        """
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.completed: Set[str] = set()
        self.lock = asyncio.Lock()
    
    async def put(self, item: str):
        """Put item in queue."""
        await self.queue.put(item)
    
    async def get(self) -> str:
        """Get item from queue."""
        return await self.queue.get()
    
    def task_done(self):
        """Mark task as done."""
        self.queue.task_done()
    
    async def join(self):
        """Wait for all tasks to complete."""
        await self.queue.join()
    
    def qsize(self) -> int:
        """Get queue size."""
        return self.queue.qsize()
    
    async def mark_completed(self, item: str):
        """Mark item as completed."""
        async with self.lock:
            self.completed.add(item)


class WorkerPool:
    """Worker pool for concurrent validation."""
    
    def __init__(
        self,
        num_workers: int = CONFIG.MAX_WORKERS,
        timeout: int = CONFIG.TIMEOUT,
        proxies: Optional[List[str]] = None,
    ):
        """
        Initialize worker pool.
        
        Args:
            num_workers: Number of concurrent workers
            timeout: Request timeout
            proxies: List of proxies
        """
        self.num_workers = min(num_workers, CONFIG.MAX_WORKERS)
        self.timeout = timeout
        self.proxies = proxies
        
        self.queue = ValidatorQueue()
        self.results: List[ValidationResult] = []
        self.results_lock = asyncio.Lock()
        
        self.validator = CookieValidator(
            timeout=timeout,
            proxies=proxies,
            debug=CONFIG.DEBUG,
        )
        
        logger.info(f"Initialized WorkerPool with {self.num_workers} workers")
    
    async def worker(self, worker_id: int):
        """
        Worker coroutine.
        
        Args:
            worker_id: Worker identifier
        """
        logger.debug(f"Worker {worker_id} started")
        
        while True:
            try:
                # Get task with timeout
                try:
                    cookie_file = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Validate
                logger.debug(f"Worker {worker_id} processing: {cookie_file}")
                
                result = await self.validator.validate(cookie_file)
                
                # Store result
                async with self.results_lock:
                    self.results.append(result)
                
                # Print status
                indicator = StatusIndicators.get_indicator(result.status.value)
                filename = Path(cookie_file).name
                print(f"{indicator} {filename}")
                
                # Mark done
                self.queue.task_done()
                await self.queue.mark_completed(cookie_file)
            
            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_id} cancelled")
                break
            
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                self.queue.task_done()
    
    async def process(self, cookie_files: List[str]) -> List[ValidationResult]:
        """
        Process list of cookie files.
        
        Args:
            cookie_files: List of cookie file paths
            
        Returns:
            List of ValidationResult objects
        """
        # Add files to queue
        for cookie_file in cookie_files:
            await self.queue.put(cookie_file)
        
        logger.info(f"Queued {len(cookie_files)} files for validation")
        
        # Create workers
        workers = [
            asyncio.create_task(self.worker(i))
            for i in range(self.num_workers)
        ]
        
        # Wait for queue to be processed
        try:
            await self.queue.join()
        finally:
            # Cancel workers
            for worker in workers:
                worker.cancel()
            
            # Wait for cancellation
            await asyncio.gather(*workers, return_exceptions=True)
        
        logger.info(f"Completed processing {len(self.results)} results")
        return self.results


class ResultsManager:
    """Manage validation results."""
    
    @staticmethod
    def save_results(results: List[ValidationResult]):
        """
        Save results to files.
        
        Args:
            results: List of ValidationResult objects
        """
        # Group by status
        grouped = defaultdict(list)
        for result in results:
            grouped[result.status.value].append(result)
        
        # Save by status
        for status in [
            ValidationStatus.VALID.value,
            ValidationStatus.INVALID.value,
            ValidationStatus.EXPIRED.value,
            ValidationStatus.FORBIDDEN.value,
            ValidationStatus.RATE_LIMIT.value,
        ]:
            if status in grouped:
                ResultsManager._save_status_file(
                    status,
                    grouped[status],
                )
        
        # Save JSON results
        ResultsManager._save_json_results(results)
        
        # Print summary
        ResultsManager.print_summary(grouped)
    
    @staticmethod
    def _save_status_file(status: str, results: List[ValidationResult]):
        """Save results for specific status to file."""
        filename_map = {
            'VALID': 'valid.txt',
            'INVALID': 'invalid.txt',
            'EXPIRED': 'expired.txt',
            'FORBIDDEN': 'forbidden.txt',
            'RATE_LIMIT': 'ratelimit.txt',
        }
        
        filename = filename_map.get(status, f'{status.lower()}.txt')
        filepath = CONFIG.RESULTS_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for result in results:
                    f.write(f"{Path(result.cookie_file).name}\n")
            
            logger.info(f"Saved {len(results)} {status} results to {filename}")
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")
    
    @staticmethod
    def _save_json_results(results: List[ValidationResult]):
        """Save all results to JSON file."""
        filepath = CONFIG.RESULTS_DIR / 'results.json'
        
        try:
            data = [result.to_dict() for result in results]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Saved {len(results)} results to results.json")
        except Exception as e:
            logger.error(f"Error saving results.json: {e}")
    
    @staticmethod
    def print_summary(grouped: Dict[str, List[ValidationResult]]):
        """Print validation summary."""
        total = sum(len(v) for v in grouped.values())
        
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        for status in [
            ValidationStatus.VALID.value,
            ValidationStatus.INVALID.value,
            ValidationStatus.EXPIRED.value,
            ValidationStatus.FORBIDDEN.value,
            ValidationStatus.RATE_LIMIT.value,
        ]:
            count = len(grouped.get(status, []))
            if count > 0:
                indicator = StatusIndicators.get_indicator(status)
                percentage = (count / total * 100) if total > 0 else 0
                print(f"{indicator} {count} ({percentage:.1f}%)")
        
        print("=" * 60)
        print(f"Total: {total}")
        print("=" * 60 + "\n")


class AdvancedValidator:
    """Advanced validator with full async pipeline."""
    
    def __init__(
        self,
        num_workers: int = CONFIG.MAX_WORKERS,
        timeout: int = CONFIG.TIMEOUT,
        proxies: Optional[List[str]] = None,
    ):
        """
        Initialize advanced validator.
        
        Args:
            num_workers: Number of concurrent workers
            timeout: Request timeout
            proxies: List of proxies
        """
        self.worker_pool = WorkerPool(
            num_workers=num_workers,
            timeout=timeout,
            proxies=proxies,
        )
    
    async def validate_directory(self, directory: str) -> List[ValidationResult]:
        """
        Validate all cookies in directory.
        
        Args:
            directory: Directory path
            
        Returns:
            List of validation results
        """
        # Scan directory
        logger.info(f"Scanning directory: {directory}")
        cookie_files = FileScanner.scan_recursive(directory)
        
        if not cookie_files:
            logger.warning(f"No cookie files found in {directory}")
            return []
        
        print(f"\nFound {len(cookie_files)} cookie files\n")
        
        # Process files
        results = await self.worker_pool.process(cookie_files)
        
        # Save results
        ResultsManager.save_results(results)
        
        return results
    
    async def validate_files(self, cookie_files: List[str]) -> List[ValidationResult]:
        """
        Validate specific list of files.
        
        Args:
            cookie_files: List of file paths
            
        Returns:
            List of validation results
        """
        logger.info(f"Validating {len(cookie_files)} files")
        
        # Process files
        results = await self.worker_pool.process(cookie_files)
        
        # Save results
        ResultsManager.save_results(results)
        
        return results
