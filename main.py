"""
Main entry point with GUI folder picker and validation orchestration.
"""

import sys
import asyncio
import logging
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

from config import CONFIG
from advanced_validator import AdvancedValidator
from helpers.logger import setup_logger, StatusIndicators


# Setup logging
logger = setup_logger(
    name='cookie-validator',
    log_file=str(CONFIG.LOGS_DIR / 'validator.log'),
    verbose=CONFIG.VERBOSE,
)


class FolderPickerGUI:
    """Simple GUI for folder selection."""
    
    @staticmethod
    def pick_folder(title: str = "Select Folder with Cookies") -> str:
        """
        Show folder picker dialog.
        
        Args:
            title: Dialog title
            
        Returns:
            Selected folder path or empty string if cancelled
        """
        if not GUI_AVAILABLE:
            logger.warning("tkinter not available, using command line input")
            path = input("Enter path to cookies folder: ").strip()
            return path
        
        try:
            root = tk.Tk()
            root.withdraw()  # Hide root window
            
            folder = filedialog.askdirectory(title=title)
            root.destroy()
            
            return folder
        except Exception as e:
            logger.error(f"Error in GUI: {e}")
            return ""


def validate_directory(directory: str) -> bool:
    """
    Validate directory exists and is accessible.
    
    Args:
        directory: Directory path
        
    Returns:
        True if valid
    """
    path = Path(directory)
    
    if not path.exists():
        logger.error(f"Directory not found: {directory}")
        return False
    
    if not path.is_dir():
        logger.error(f"Not a directory: {directory}")
        return False
    
    if not path.is_dir() or not list(path.rglob("*")):
        logger.warning(f"Directory appears empty: {directory}")
    
    return True


async def main():
    """Main entry point."""
    
    print("\n" + "=" * 60)
    print("DigitalOcean Cookie Validator")
    print("=" * 60 + "\n")
    
    # Pick folder
    logger.info("Starting folder picker...")
    folder = FolderPickerGUI.pick_folder()
    
    if not folder:
        logger.error("No folder selected")
        return
    
    if not validate_directory(folder):
        logger.error("Invalid directory")
        return
    
    logger.info(f"Selected folder: {folder}")
    
    try:
        # Create validator
        validator = AdvancedValidator(
            num_workers=CONFIG.MAX_WORKERS,
            timeout=CONFIG.TIMEOUT,
        )
        
        # Run validation
        results = await validator.validate_directory(folder)
        
        logger.info(f"Validation complete: {len(results)} results")
        print(f"\n{StatusIndicators.SUCCESS} Validation complete!")
        print(f"Results saved to: {CONFIG.RESULTS_DIR}\n")
    
    except KeyboardInterrupt:
        logger.warning("Validation cancelled by user")
        print(f"\n{StatusIndicators.ERROR} Validation cancelled\n")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n{StatusIndicators.ERROR} Fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        # Run async main
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        print("\n")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Uncaught error: {e}", exc_info=True)
        print(f"\n{StatusIndicators.ERROR} Uncaught error: {e}\n")
        sys.exit(1)
