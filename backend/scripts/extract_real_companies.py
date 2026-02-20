#!/usr/bin/env python3
"""
Extract REAL company names from Indeed emails by re-fetching full email content.
This will actually parse the email content instead of making up company names.
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
from app.models.user import User
from app.services import gmail as gmail_service


def extract_company_from_email_content(subject: str, body: str) -> str | None:
    """Extract company name from Indeed email content using better patterns."""
    
    # Pattern 1: "The following items were sent to [Company]. Good luck!"
    m = re.search(r"items\s+were\s+sent\s+to\s+([A-Z][A-Za-z0-9&\s\.\,\-]{2,80}?)(?:\.|\n|Good)", body, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    
    # Pattern 2: "Application submitted to [Company]"
    m = re.search(r"application\s+submitted\s+to\s+([A-Z][A-Za-z0-9&\s\.\,\-]{2,80}?)(?:\.|\n|$)", subject, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    
    # Pattern 3: Look for company name in body lines
    lines = body.split('\n')
    for line in lines:
        # Skip lines that are clearly boilerplate
        if any(word in line.lower() for word in ['indeed', 'application', 'submitted', 'sent to', 'good luck']):
            continue
        
        # Look for company names (capitalized, longer than 2 chars)
        words = re.findall(r'\b[A-Z][a-z]{2,}\b', line)
        for word in words:
            if len(word) > 2 and word not in ['Indeed', 'Good', 'Luck']:
                return word
    
    return None


async def extract_real_companies():
    """Extract actual company names from Indeed emails."""
    print("🔧 Extracting REAL company names from Indeed emails...")
    
    async with AsyncSessionLocal() as db:
        # Get Indeed applications with None company names that have email_message_id
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name.is_(None),
                JobApplication.email_message_id.isnot(None)
            ).limit(50)  # Process in batches to avoid overwhelming Gmail API
        )
        apps_to_process = result.scalars().all()
        
        if not apps_to_process:
            print("✅ No Indeed applications with unknown companies found!")
            return
        
        print(f"📊 Processing {len(apps_to_process)} applications...")
        
        fixed_count = 0
        
        for app in apps_to_process:
            print(f"\n📧 Processing: {app.job_title or 'Unknown'}")
            
            try:
                # Get user for this application
                user_result = await db.execute(
                    select(User).where(User.id == app.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user or not user.google_access_token:
                    print(f"   ⚠️  No user or access token, skipping")
                    continue
                
                # Re-fetch the full email
                detail = gmail_service.get_message_detail(user, app.email_message_id)
                
                # Extract company name from full email content
                company_name = extract_company_from_email_content(
                    detail["subject"], 
                    (detail["snippet"] or "") + "\n" + (detail["body"] or "")
                )
                
                if company_name:
                    app.company_name = company_name
                    print(f"   ✅ Extracted: '{company_name}'")
                    fixed_count += 1
                else:
                    print(f"   ⚠️  Could not extract company name")
                    # Keep as None rather than making up a name
                    
            except Exception as e:
                print(f"   ❌ Error processing application: {e}")
                continue
        
        # Commit changes
        if fixed_count > 0:
            await db.commit()
            print(f"\n🎉 Successfully extracted company names for {fixed_count} applications!")
        else:
            print(f"\n⚠️  No company names could be extracted")


if __name__ == "__main__":
    try:
        asyncio.run(extract_real_companies())
    except KeyboardInterrupt:
        print("\n⚠️  Extraction cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during extraction: {e}")
        sys.exit(1)
