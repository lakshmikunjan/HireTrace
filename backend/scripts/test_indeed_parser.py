#!/usr/bin/env python3
"""
Test the Indeed parser with the specific email example provided.
"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.parser.indeed import parse

# Test email from user's example
subject = "Indeed Application: Staff Software Engineer - Integrations"
body = """
Indeed

o'clock	
Application submitted

Staff Software Engineer - Integrations
HungerRush - Houston, TX

star rating 2.8	
9 reviews

 	 	 
The following items were sent to HungerRush. Good luck!

•

Application 
"""

print("🧪 Testing Indeed parser with your email example...")
print(f"Subject: {subject}")
print(f"Body preview: {body[:100]}...")

result = parse(subject, body)

print(f"\n📊 Results:")
print(f"  Company: {result.company_name}")
print(f"  Job Title: {result.job_title}")
print(f"  Location: {result.location}")
print(f"  Platform: {result.platform}")
print(f"  Confidence: {result.confidence}")

if result.company_name == "HungerRush":
    print("\n✅ SUCCESS: Parser correctly extracted 'HungerRush' as company!")
else:
    print(f"\n❌ ISSUE: Parser got '{result.company_name}' instead of 'HungerRush'")

if result.job_title == "Staff Software Engineer - Integrations":
    print("✅ SUCCESS: Parser correctly extracted job title!")
else:
    print(f"❌ ISSUE: Parser got '{result.job_title}' as job title")
