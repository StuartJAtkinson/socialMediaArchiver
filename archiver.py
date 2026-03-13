#!/usr/bin/env python3
"""
Social Media Archiver - Command line entry point

Usage:
    archiver.py              # Run archiving based on config
    archiver.py --config FILE       # Use custom config file
    archiver.py --stats             # Show archive statistics
    archiver.py --help              # Show help
"""

import sys
import os
import argparse

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import SocialMediaArchiver


def show_stats(archiver):
    """Show statistics for archived accounts."""
    print("\n" + "="*60)
    print("ARCHIVE STATISTICS")
    print("="*60)
    
    archives_path = archiver.storage.root_path
    if not archives_path.exists():
        print("No archives found.")
        return
    
    for platform_dir in archives_path.iterdir():
        if not platform_dir.is_dir():
            continue
        
        platform = platform_dir.name
        print(f"\n{platform.upper()}")
        print("-" * 40)
        
        for account_dir in platform_dir.iterdir():
            if not account_dir.is_dir():
                continue
            
            account = account_dir.name
            stats = archiver.storage.get_stats(platform, account)
            
            print(f"  {account}:")
            print(f"    Posts: {stats['post_count']}")
            print(f"    Images: {stats['image_count']}")
            print(f"    Videos: {stats['video_count']}")
            if stats['latest_post']:
                print(f"    Latest: {stats['latest_post']}")
            if stats['earliest_post']:
                print(f"    Earliest: {stats['earliest_post']}")


def main():
    parser = argparse.ArgumentParser(
        description="Archive social media posts to local storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python archiver.py                    # Run with default config
  python archiver.py --stats            # Show archive statistics
  python archiver.py --config ~/my.json # Use custom config file
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='./config/config.json',
        help='Path to configuration file (default: ./config/config.json)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show archive statistics and exit'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Social Media Archiver v0.1.0'
    )
    
    args = parser.parse_args()
    
    # Create archiver instance
    archiver = SocialMediaArchiver(config_path=args.config)
    
    if args.stats:
        show_stats(archiver)
    else:
        archiver.run_all()


if __name__ == '__main__':
    main()
