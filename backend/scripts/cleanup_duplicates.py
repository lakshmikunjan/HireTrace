#!/usr/bin/env python3
"""
Database cleanup script to remove duplicate job applications.

This script identifies and removes duplicate entries based on:
1. Same company name (fuzzy matching)
2. Same job title (fuzzy matching)  
3. Close application dates (within 48 hours)
4. Same platform

Keeps the most recent entry and removes older duplicates.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.application import JobApplication


def fuzzy_ratio(a: str | None, b: str | None) -> float:
    """Calculate fuzzy string similarity ratio."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def are_duplicates(app1: JobApplication, app2: JobApplication) -> bool:
    """Check if two applications are likely duplicates."""
    # Check platform match
    if app1.platform != app2.platform:
        return False
    
    # Check company similarity
    company_sim = fuzzy_ratio(app1.company_name, app2.company_name)
    if company_sim < 0.82:
        return False
    
    # Check job title similarity (if both exist)
    if app1.job_title and app2.job_title:
        title_sim = fuzzy_ratio(app1.job_title, app2.job_title)
        if title_sim < 0.75:
            return False
    
    # Check date proximity (within 48 hours)
    if app1.applied_at and app2.applied_at:
        time_diff = abs((app1.applied_at - app2.applied_at).total_seconds())
        if time_diff > 48 * 3600:  # 48 hours in seconds
            return False
    
    return True


async def find_duplicate_groups(db: AsyncSession) -> list[list[JobApplication]]:
    """Find groups of duplicate applications."""
    # Get all applications ordered by date
    result = await db.execute(
        select(JobApplication).order_by(JobApplication.applied_at.desc().nullslast())
    )
    all_apps = result.scalars().all()
    
    duplicate_groups = []
    processed = set()
    
    for i, app1 in enumerate(all_apps):
        if app1.id in processed:
            continue
            
        group = [app1]
        processed.add(app1.id)
        
        for j, app2 in enumerate(all_apps[i+1:], i+1):
            if app2.id in processed:
                continue
                
            if are_duplicates(app1, app2):
                group.append(app2)
                processed.add(app2.id)
        
        if len(group) > 1:
            duplicate_groups.append(group)
    
    return duplicate_groups


async def cleanup_duplicates():
    """Main cleanup function."""
    print("🔍 Starting duplicate cleanup...")
    
    async with AsyncSessionLocal() as db:
        # Find duplicate groups
        duplicate_groups = await find_duplicate_groups(db)
        
        if not duplicate_groups:
            print("✅ No duplicates found!")
            return
        
        print(f"📊 Found {len(duplicate_groups)} duplicate groups")
        
        total_to_remove = 0
        for i, group in enumerate(duplicate_groups, 1):
            # Sort by applied_at (most recent first) or created_at
            sorted_group = sorted(
                group, 
                key=lambda app: (app.applied_at or app.created_at), 
                reverse=True
            )
            
            # Keep the first (most recent) one, remove the rest
            to_keep = sorted_group[0]
            to_remove = sorted_group[1:]
            
            print(f"\n📁 Group {i}: {to_keep.company_name} - {to_keep.job_title}")
            print(f"   ✅ Keeping: {to_keep.applied_at or to_keep.created_at} (ID: {to_keep.id})")
            
            for app in to_remove:
                print(f"   🗑️  Removing: {app.applied_at or app.created_at} (ID: {app.id})")
                
                # Delete the duplicate
                await db.delete(app)
                total_to_remove += 1
        
        # Commit all deletions
        await db.commit()
        
        print(f"\n🎉 Cleanup complete! Removed {total_to_remove} duplicate entries.")


if __name__ == "__main__":
    try:
        asyncio.run(cleanup_duplicates())
    except KeyboardInterrupt:
        print("\n⚠️  Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        sys.exit(1)
