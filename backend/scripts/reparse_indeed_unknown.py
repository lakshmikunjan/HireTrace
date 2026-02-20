#!/usr/bin/env python3
"""
Re-parse Indeed applications that have company_name = None to extract actual company names.
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
from app.models.user import User
from app.services import gmail as gmail_service
from app.services.parser import parse_email


async def reparse_indeed_unknown():
    """Re-parse Indeed applications with None company names."""
    print("🔧 Re-parsing Indeed applications with unknown company names...")
    
    async with AsyncSessionLocal() as db:
        # Find all Indeed applications with no company name but have email_message_id
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name.is_(None),
                JobApplication.email_message_id.isnot(None)
            )
        )
        apps_to_reparse = result.scalars().all()
        
        if not apps_to_reparse:
            print("✅ No Indeed applications with unknown company names found!")
            return
        
        print(f"📊 Found {len(apps_to_reparse)} Indeed applications to re-parse")
        
        fixed_count = 0
        
        for app in apps_to_reparse:
            print(f"\n📧 Processing: {app.job_title or 'Unknown Role'}")
            
            try:
                # Get user for this application
                user_result = await db.execute(
                    select(User).where(User.id == app.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user or not user.google_access_token:
                    print(f"   ⚠️  No user or access token found, skipping")
                    continue
                
                # Re-fetch email details
                detail = gmail_service.get_message_detail(user, app.email_message_id)
                
                # Re-parse with improved parser
                parsed = parse_email(
                    sender=detail["sender"],
                    subject=detail["subject"],
                    body=(detail["snippet"] or "") + "\n" + (detail["body"] or ""),
                )
                
                # Update if we found a company name
                if parsed.company_name:
                    app.company_name = parsed.company_name
                    print(f"   ✅ Found company: '{parsed.company_name}'")
                    fixed_count += 1
                else:
                    print(f"   ⚠️  Still could not extract company name")
                    
            except Exception as e:
                print(f"   ❌ Error processing application: {e}")
                continue
        
        # Commit all changes
        if fixed_count > 0:
            await db.commit()
            print(f"\n🎉 Successfully extracted company names for {fixed_count} applications!")
        else:
            print(f"\n⚠️  No company names could be extracted")


if __name__ == "__main__":
    try:
        asyncio.run(reparse_indeed_unknown())
    except KeyboardInterrupt:
        print("\n⚠️  Re-parsing cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during re-parsing: {e}")
        sys.exit(1)
