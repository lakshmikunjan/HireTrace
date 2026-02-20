#!/usr/bin/env python3
"""
Simple script to clear Indeed applications that have "Indeed Apply" as company name.

This will set company_name to None for Indeed applications where the company name
couldn't be parsed, so they show as "Unknown" instead of "Indeed Apply".
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.application import JobApplication


async def fix_indeed_companies():
    """Clear 'Indeed Apply' company names to None."""
    print("🔧 Clearing 'Indeed Apply' company names...")
    
    async with AsyncSessionLocal() as db:
        # Find all Indeed applications with "Indeed Apply" as company name
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name == "Indeed Apply"
            )
        )
        apps_to_fix = result.scalars().all()
        
        if not apps_to_fix:
            print("✅ No Indeed applications with 'Indeed Apply' found!")
            return
        
        print(f"📊 Found {len(apps_to_fix)} Indeed applications to fix")
        
        for app in apps_to_fix:
            print(f"   🧹 Clearing: {app.job_title or 'Unknown Role'}")
            app.company_name = None
        
        # Commit all changes
        await db.commit()
        
        print(f"\n🎉 Cleared company names for {len(apps_to_fix)} Indeed applications!")
        print("   These will now show as 'Unknown' instead of 'Indeed Apply'")


if __name__ == "__main__":
    try:
        asyncio.run(fix_indeed_companies())
    except KeyboardInterrupt:
        print("\n⚠️  Fix cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        sys.exit(1)
