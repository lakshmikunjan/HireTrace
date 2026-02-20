#!/usr/bin/env python3
"""
Clear fake company names like "Various Companies" and revert to None.
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


async def clear_fake_companies():
    """Clear fake company names and revert to None."""
    print("🧹 Clearing fake company names...")
    
    async with AsyncSessionLocal() as db:
        # Find applications with fake company names
        fake_patterns = [
            "Various Companies",
            "Various Tech Companies", 
            "Various AI Companies",
            "Various Data Companies",
            "Various Frontend Companies",
            "Various Business Companies",
            "Various Design Companies",
            "Various Mobile Companies",
            "Various Startups",
            "Various IT Companies",
            "Various Full Stack Companies",
            "Various Engineering Companies",
            "Various Analytics Companies",
            "Various Manufacturing Companies",
            "Various Healthcare Companies",
            "Various Web Companies",
            "Various Programming Companies",
            "Various Database Companies",
            "Various DevOps Companies",
            "Various Cloud Companies",
            "Various Support Companies",
            "Various QA Companies",
            "Various Embedded Companies",
            "Various UX Companies",
            "Various Gaming Companies",
            "Various Defense Companies",
            "Various Financial Companies",
            "Various ERP Companies",
            "Various Systems Companies",
            "Various Security Companies",
            "Various Web Development Companies",
            "Various Robotics Companies",
            "Various MLOps Companies",
            "Various No-Code Companies",
            "Various Research Companies",
            "Various HVAC Companies",
            "Various WordPress Companies",
            "Various React Companies",
            "Various Java Companies",
            "Various React Native Companies",
            "Various Puerto Rican Companies",
            "Various North American Companies",
            "Various Pittsburgh Companies",
            "Various Instrumentation Companies",
            "Various Java Training Companies",
            "Various UI Companies",
            "Various Widget Companies",
            "Various AI/ML Companies",
            "Various ML Companies",
            "Various ML Security Companies",
            "Google Cloud Platform",
            "Ford Motor Company",
            "Microsoft",
            "MuleSoft",
            "Lovable",
            "Build Soft Solutions"
        ]
        
        total_cleared = 0
        
        for fake_name in fake_patterns:
            result = await db.execute(
                select(JobApplication).where(
                    JobApplication.company_name == fake_name
                )
            )
            apps = result.scalars().all()
            
            if apps:
                print(f"   🧹 Clearing {len(apps)} applications with '{fake_name}'")
                for app in apps:
                    app.company_name = None
                total_cleared += len(apps)
        
        # Commit changes
        if total_cleared > 0:
            await db.commit()
            print(f"\n🎉 Cleared fake company names from {total_cleared} applications!")
        else:
            print(f"\n✅ No fake company names found")


if __name__ == "__main__":
    try:
        asyncio.run(clear_fake_companies())
    except KeyboardInterrupt:
        print("\n⚠️  Clearing cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during clearing: {e}")
        sys.exit(1)
