#!/usr/bin/env python3
"""
Fix specific Indeed application mentioned by user.
Staff Software Engineer - Integrations at HungerRush
"""

import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.application import JobApplication


async def fix_specific_indeed():
    """Fix the specific Indeed application mentioned by user."""
    print("🔧 Fixing specific Indeed application...")
    
    async with AsyncSessionLocal() as db:
        # Find the application with job title containing "Staff Software Engineer - Integrations"
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.job_title.ilike("%Staff Software Engineer - Integrations%")
            )
        )
        apps = result.scalars().all()
        
        if not apps:
            print("❌ Could not find the specific application")
            return
        
        for app in apps:
            print(f"📧 Found: {app.job_title}")
            print(f"   Current company: {app.company_name}")
            
            # Update company name to HungerRush
            app.company_name = "HungerRush"
            print(f"   ✅ Updated to: HungerRush")
        
        # Commit changes
        await db.commit()
        print(f"\n🎉 Fixed {len(apps)} application(s)!")


if __name__ == "__main__":
    try:
        asyncio.run(fix_specific_indeed())
    except KeyboardInterrupt:
        print("\n⚠️  Fix cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        sys.exit(1)
