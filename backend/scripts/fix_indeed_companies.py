#!/usr/bin/env python3
"""
Script to fix Indeed applications that have "Indeed Apply" as company name.

This script will:
1. Find all applications with platform="indeed" and company_name="Indeed Apply"
2. Re-parse their emails to extract the actual company name
3. Update the database with the correct company name
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
from app.services import gmail as gmail_service
from app.services.parser import parse_email


async def fix_indeed_companies():
    """Fix Indeed applications with placeholder company names."""
    print("🔧 Starting Indeed company name fixes...")
    
    async with AsyncSessionLocal() as db:
        # Find all Indeed applications with "Indeed Apply" as company name
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name == "Indeed Apply",
                JobApplication.email_message_id.isnot(None)
            )
        )
        apps_to_fix = result.scalars().all()
        
        if not apps_to_fix:
            print("✅ No Indeed applications with 'Indeed Apply' found!")
            return
        
        print(f"📊 Found {len(apps_to_fix)} Indeed applications to fix")
        
        fixed_count = 0
        
        for app in apps_to_fix:
            print(f"\n📧 Processing: {app.job_title or 'Unknown Role'}")
            
            try:
                # Get the user for this application
                user_result = await db.execute(
                    select(JobApplication).where(JobApplication.id == app.id)
                )
                user_id = app.user_id
                
                # Create a minimal user object for gmail service
                class MockUser:
                    def __init__(self, user_id, google_access_token):
                        self.id = user_id
                        self.google_access_token = google_access_token
                
                # We need the user's access token - let's get it from the user table
                from app.models.user import User
                user_result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user or not user.google_access_token:
                    print(f"   ⚠️  No user or access token found, skipping")
                    continue
                
                mock_user = MockUser(user_id, user.google_access_token)
                
                # Re-fetch the email details
                detail = gmail_service.get_message_detail(mock_user, app.email_message_id)
                
                # Re-parse the email with improved parser
                parsed = parse_email(
                    sender=detail["sender"],
                    subject=detail["subject"],
                    body=(detail["snippet"] or "") + "\n" + (detail["body"] or ""),
                )
                
                # Update if we found a better company name
                if parsed.company_name and parsed.company_name != "Indeed Apply":
                    old_name = app.company_name
                    app.company_name = parsed.company_name
                    print(f"   ✅ Updated: '{old_name}' → '{parsed.company_name}'")
                    fixed_count += 1
                else:
                    print(f"   ⚠️  Could not extract company name from email")
                    
            except Exception as e:
                print(f"   ❌ Error processing application: {e}")
                continue
        
        # Commit all changes
        if fixed_count > 0:
            await db.commit()
            print(f"\n🎉 Fixed {fixed_count} Indeed applications!")
        else:
            print(f"\n⚠️  No company names could be fixed")


if __name__ == "__main__":
    try:
        asyncio.run(fix_indeed_companies())
    except KeyboardInterrupt:
        print("\n⚠️  Fix cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        sys.exit(1)
