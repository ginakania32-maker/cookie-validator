"""
Main entry point with GUI folder picker.
Production-ready CLI with tkinter folder selection.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import filedialog, messagebox

from config import config
from helpers.logger import logger
from advanced_validator import AdvancedValidator


class FolderPickerGUI:
    """GUI for folder selection."""
    
    @staticmethod
    def select_folder() -> Optional[Path]:
        """Show folder picker dialog."""
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        folder_path = filedialog.askdirectory(
            title="Select folder containing cookie files",
            initialdir=str(Path.home() / "Downloads"),
        )
        
        root.destroy()
        
        if folder_path:
            return Path(folder_path)
        
        return None
    
    @staticmethod
    def confirm_folder(folder_path: Path, file_count: int) -> bool:
        """Confirm folder selection."""
        root = tk.Tk()
        root.withdraw()
        
        result = messagebox.askyesno(
            title="Confirm Folder",
            message=f"Selected folder: {folder_path}\n\n"
                    f"Found {file_count} cookie files.\n\n"
                    f"Start validation?",
        )
        
        root.destroy()
        return result


class ValidatorCLI:
    """Command-line interface for validator."""
    
    def __init__(self):
        """Initialize CLI."""
        self.validator = AdvancedValidator(max_workers=config.MAX_WORKERS)
    
    async def run_interactive(self) -> None:
        """Run interactive validation workflow."""
        logger.info("DigitalOcean Cookie Validator")
        logger.print_separator()
        print("\n🔍 DigitalOcean Cookie Validator\n")
        print(f"Configuration:")
        print(f"  Target: {config.BASE_URL}")
        print(f"  Workers: {config.MAX_WORKERS}")
        print(f"  Timeout: {config.TIMEOUT}s")
        print(f"  Max Retries: {config.MAX_RETRIES}")
        print(f"  Debug Mode: {config.DEBUG}")
        print()
        
        # Show folder picker
        logger.info("Opening folder picker...")
        folder_path = FolderPickerGUI.select_folder()
        
        if not folder_path:
            logger.warning("No folder selected. Exiting.")
            print("\n❌ No folder selected. Exiting.\n")
            return
        
        if not folder_path.exists():
            logger.error(f"Folder does not exist: {folder_path}")
            print(f"\n❌ Folder does not exist: {folder_path}\n")
            return
        
        # Scan folder
        from helpers.cookie_helpers import FileScanner
        cookie_files = FileScanner.scan_recursive(folder_path)
        
        if not cookie_files:
            logger.warning(f"No cookie files found in {folder_path}")
            print(f"\n❌ No cookie files found in {folder_path}\n")
            print("Looking for: cookies.txt, *.txt, *.json\n")
            return
        
        # Confirm
        if not FolderPickerGUI.confirm_folder(folder_path, len(cookie_files)):
            logger.info("Validation cancelled by user")
            print("\n⚠️  Validation cancelled.\n")
            return
        
        # Run validation
        print()
        logger.info(f"Starting validation of {len(cookie_files)} files...")
        
        try:
            results = await self.validator.validate_from_folder(folder_path)
            
            if results:
                print(f"\n✅ Validation complete!")
                print(f"\nResults saved to: {config.RESULTS_DIR}")
                print(f"  - valid.txt")
                print(f"  - invalid.txt")
                print(f"  - expired.txt")
                print(f"  - forbidden.txt")
                print(f"  - ratelimit.txt")
                print(f"  - results.json")
                print()
        
        except KeyboardInterrupt:
            logger.warning("Validation interrupted by user")
            print("\n\n⚠️  Validation interrupted.\n")
        
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            print(f"\n❌ Validation failed: {e}\n")
    
    async def run_from_path(self, path: str) -> None:
        """Run validation from specified path."""
        folder_path = Path(path)
        
        if not folder_path.exists():
            logger.error(f"Path does not exist: {path}")
            return
        
        logger.info(f"Starting validation from {path}")
        
        try:
            results = await self.validator.validate_from_folder(folder_path)
            
            if results:
                logger.info(f"Validation complete. Results saved to {config.RESULTS_DIR}")
        
        except Exception as e:
            logger.error(f"Validation failed: {e}")


async def main():
    """Main entry point."""
    cli = ValidatorCLI()
    
    # Check for command-line arguments
    if len(sys.argv) > 1:
        # Run from specified path
        await cli.run_from_path(sys.argv[1])
    else:
        # Run interactive
        await cli.run_interactive()


if __name__ == "__main__":
    # Ensure output directories exist
    for directory in [
        config.LOGS_DIR,
        config.RESULTS_DIR,
        config.VALID_DIR,
        config.INVALID_DIR,
        config.EXPIRED_DIR,
        config.DEBUG_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # Run async main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}\n")
        sys.exit(1)
