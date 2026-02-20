#!/usr/bin/env python3
"""
Fix all Indeed applications by using job title patterns and common company name extraction.
"""

import asyncio
import sys
import re
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.application import JobApplication


# Common patterns to extract company names from job titles or stored data
def extract_company_from_job_title(job_title: str) -> str | None:
    """Try to extract company name from job title patterns."""
    if not job_title:
        return None
    
    # Look for patterns like "Company Name - Job Title" in stored data
    # This would need to be based on actual data patterns
    
    # For now, let's try some common Indeed patterns
    # This is a placeholder - we'd need to see actual data to improve this
    return None


async def fix_all_indeed():
    """Fix all Indeed applications with None company names."""
    print("🔧 Attempting to fix all Indeed applications...")
    
    async with AsyncSessionLocal() as db:
        # Get all Indeed applications with None company names
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name.is_(None)
            )
        )
        apps_to_fix = result.scalars().all()
        
        if not apps_to_fix:
            print("✅ No Indeed applications with unknown company names found!")
            return
        
        print(f"📊 Found {len(apps_to_fix)} Indeed applications to examine")
        
        # Let's look at a few examples to understand the data patterns
        sample_apps = apps_to_fix[:10]
        print("\n📋 Sample applications:")
        for app in sample_apps:
            print(f"   • {app.job_title}")
            print(f"     Location: {app.location}")
            print(f"     Email snippet: {app.raw_email_snippet[:100] if app.raw_email_snippet else 'None'}...")
            print()
        
        # Try to extract company names from email snippets
        fixed_count = 0
        
        for app in apps_to_fix:
            if not app.raw_email_snippet:
                continue
                
            # Look for company patterns in the snippet
            snippet = app.raw_email_snippet
            
            # Pattern: Company - Location
            m = re.search(r'([A-Z][A-Za-z0-9&\s\.]{2,60})\s*[-–]\s*([A-Za-z\s,\.]+)', snippet)
            if m:
                potential_company = m.group(1).strip()
                # Skip if it looks like a job title
                if not any(word in potential_company.lower() for word in ['engineer', 'developer', 'manager', 'analyst', 'designer', 'specialist']):
                    app.company_name = potential_company
                    print(f"   ✅ Fixed: {app.job_title} → {potential_company}")
                    fixed_count += 1
                    continue
            
            # Pattern: "sent to Company"
            m = re.search(r'sent to\s+([A-Z][A-Za-z0-9&\s\.]{2,60})', snippet, re.IGNORECASE)
            if m:
                potential_company = m.group(1).strip()
                app.company_name = potential_company
                print(f"   ✅ Fixed: {app.job_title} → {potential_company}")
                fixed_count += 1
                continue
        
        # Commit changes
        if fixed_count > 0:
            await db.commit()
            print(f"\n🎉 Successfully fixed {fixed_count} applications!")
        else:
            print(f"\n⚠️  Could not automatically fix any applications")
            print("   You may need to manually update company names based on the job titles above")


if __name__ == "__main__":
    try:
        asyncio.run(fix_all_indeed())
    except KeyboardInterrupt:
        print("\n⚠️  Fix cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        sys.exit(1)
