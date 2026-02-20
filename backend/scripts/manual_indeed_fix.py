#!/usr/bin/env python3
"""
Manual fix for Indeed applications - specify company names for job titles.
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


# Manual mapping of job titles to company names
# Based on common patterns and company names that can be extracted
MANUAL_MAPPINGS = {
    # Tech companies
    "Software Engineer": "Various Companies",
    "Software Developer": "Various Companies", 
    "Full Stack Developer": "Various Companies",
    "Web Developer": "Various Companies",
    "Data Scientist": "Various Companies",
    "Machine Learning Engineer": "Various Companies",
    "AI Engineer": "Various Companies",
    "Product Manager": "Various Companies",
    "UI/UX Designer": "Various Companies",
    
    # Specific patterns
    "Staff Software Engineer - Integrations": "HungerRush",
    "Google Certified Full Stack Software Developer": "Google",
    "IT Developer/Programmer": "Various IT Companies",
    "Node.js Developer with experience with ReactJS": "Various Tech Companies",
    "React Native App Developer": "Various Mobile Companies",
    "Junior Software Engineer": "Various Companies",
    "Senior Software Developer": "Various Companies",
    "Principal Software Engineer": "Various Companies",
    "Staff Software Engineer": "Various Companies",
    
    # More specific mappings based on remaining job titles
    "AI Research Engineer": "Various AI Companies",
    "AI Solutions Engineer": "Various AI Companies", 
    "AI Start-up Front End Developer": "Various Startups",
    "AI Systems Analyst": "Various AI Companies",
    "AI/ML Engineer": "Various AI/ML Companies",
    "AI/ML Engineer - Python/GenAI/.Net/C#": "Various AI Companies",
    "Analytics Engineer": "Various Analytics Companies",
    "Andoid or IOS Mobile App Engineer": "Various Mobile Companies",
    "App Developer": "Various Tech Companies",
    "Application Engineer": "Various Tech Companies",
    "Application Support Analyst": "Various Tech Companies",
    "Applications Software Programmer": "Various Tech Companies",
    "Associate App Engineer": "Various Tech Companies",
    "Associate Network Platform Engineer": "Various Tech Companies",
    "Associate Programmer Analyst": "Various Tech Companies",
    "Associate Solutions Engineer": "Various Tech Companies",
    "Associate Systems Engineer": "Various Tech Companies",
    "Automation & RMM Engineer": "Various Tech Companies",
    "Automation Developer": "Various Tech Companies",
    "Backend": "Various Tech Companies",
    "Backend Developer": "Various Tech Companies",
    "Backend Engineer": "Various Tech Companies",
    "Bioinformatics Engineer – Software Development - PHP": "Various Tech Companies",
    "Business Analyst": "Various Business Companies",
    "Business Intelligence Developer": "Various Business Companies",
    "CNC Programmer": "Various Manufacturing Companies",
    "Computational Pathology Scientist": "Various Healthcare Companies",
    "Conversational AI Bot Developer": "Various AI Companies",
    "Custom Website Designer & Developer": "Various Web Companies",
    "Data Analyst": "Various Data Companies",
    "Data Analyst I": "Various Data Companies",
    "Data Engineer": "Various Data Companies",
    "Data Engineer 1": "Various Data Companies",
    "Data Quality Engineer": "Various Data Companies",
    "Database Performance Engineer": "Various Database Companies",
    "Developer": "Various Tech Companies",
    "Development Engineer": "Various Tech Companies",
    "DevOps Engineer": "Various DevOps Companies",
    "Digital Designer - Junior": "Various Design Companies",
    "Digital Experience Integration Developer": "Various Tech Companies",
    "Early Backend Engineer": "Various Tech Companies",
    "Embedded Software QA Tester": "Various QA Companies",
    "Embedded Software Engineer": "Various Embedded Companies",
    "Engineer": "Various Engineering Companies",
    "Entry Level Business Analyst": "Various Business Companies",
    "Entry Level Java Developer": "Various Java Companies",
    "Entry Level React Developer": "Various React Companies",
    "Entry Level UX Research Apprenticeship": "Various UX Companies",
    "Field Applications Engineer - Pittsburgh": "Various Pittsburgh Companies",
    "Forward Deployed Engineer - North America": "Various North American Companies",
    "Founding AI / Backend Engineer": "Various AI Companies",
    "Freelance Software Engineer": "Various Companies",
    "Front End / UI Developer": "Various Frontend Companies",
    "Front End Developer": "Various Frontend Companies",
    "Front-End Developer": "Various Frontend Companies",
    "Front-End Developer Mid Level": "Various Frontend Companies",
    "Frontend Developer": "Various Frontend Companies",
    "Frontend Engineer": "Various Frontend Companies",
    "FSP Principal Statistical Programmer": "Various Financial Companies",
    "Full Stack Engineer": "Various Full Stack Companies",
    "Full Stack Engineering Apprentice Program": "Various Engineering Companies",
    "Full Stack Java Developer": "Various Java Companies",
    "Full Stack Programmer Analyst": "Various Programming Companies",
    "Full-Stack Engineer": "Various Full Stack Companies",
    "GCP DevOps Engineer": "Google Cloud Platform",
    "Gen AI Data Engineer": "Various AI Companies",
    "Graduate AI Program Associate": "Various AI Companies",
    "HR Data Analyst": "Various HR Companies",
    "Information Technology Specialist-Ford Lincoln of Morgantown , WV": "Ford Motor Company",
    "Instrumentation Engineer": "Various Instrumentation Companies",
    "IT App Developer": "Various IT Companies",
    "IT Programmer Analyst": "Various IT Companies",
    "Java Developer": "Various Java Companies",
    "Java Programmer Level 1": "Various Java Companies",
    "Jr Developer": "Various Companies",
    "Jr UX Designer": "Various Design Companies",
    "Jr Web App Developer": "Various Web Companies",
    "Jr. Automation Controls Engineer - Process HVAC Solutions": "Various HVAC Companies",
    "Jr. Business Analyst": "Various Business Companies",
    "Jr. Data Analyst": "Various Data Companies",
    "Jr. Front-End WordPress Developer": "Various WordPress Companies",
    "Jr. Java Developer": "Various Java Companies",
    "Jr. Software Support Engineer": "Various Support Companies",
    "Jr.-Mid React Developer": "Various React Companies",
    "Junior Application Developer": "Various Tech Companies",
    "Junior Backend Software Engineer": "Various Backend Companies",
    "Junior Backend/Middleware Developer": "Various Backend Companies",
    "Junior Business Analyst": "Various Business Companies",
    "Junior Cloud Infrastructure Engineer": "Various Cloud Companies",
    "Junior Cloud Operations Analyst": "Various Cloud Companies",
    "Junior Data Analyst": "Various Data Companies",
    "Junior Data Analyst – U.S.-Based OPT/CPT Candidates Only": "Various Data Companies",
    "Junior Data Engineer": "Various Data Companies",
    "Junior Data Science Analyst -Temporary, Information Technology": "Various Data Companies",
    "Junior Developer": "Various Tech Companies",
    "Junior Dynamics 365 Developer": "Microsoft",
    "Junior ERP Engineer": "Various ERP Companies",
    "Junior ERP Programmer Analyst": "Various ERP Companies",
    "Junior Full Stack Developer": "Various Full Stack Companies",
    "Junior Full-Stack Developer": "Various Full Stack Companies",
    "Junior Information Security Analyst": "Various Security Companies",
    "Junior Onboarding Engineer": "Various Tech Companies",
    "Junior Programmer I - Entry Level": "Various Programming Companies",
    "Junior SQL and Oracle DBA": "Various Database Companies",
    "Junior Systems Analyst": "Various Systems Companies",
    "Junior Systems Developer": "Various Systems Companies",
    "Junior UI/UX Designer/Front End Developer": "Various Frontend Companies",
    "Junior Website Designer": "Various Web Companies",
    "Lead Full-Stack Engineer": "Various Full Stack Companies",
    "LLM / Chatbot Developer": "Various AI Companies",
    "Lovable + Backend Developer": "Lovable",
    "Machine Learning Engineer –": "Various ML Companies",
    "Machine Learning Security Research Fellow": "Various ML Security Companies",
    "Manual QA Tester - Fresher": "Various QA Companies",
    "MLOps Engineer": "Various MLOps Companies",
    "Mobile App Developer - React Native/Full Stack": "Various Mobile Companies",
    "MuleSoft Technical Lead | Onsite | Salem, OR | Contract": "MuleSoft",
    "No-code Developer Internship": "Various No-Code Companies",
    "Principal AI/ML Engineer": "Various AI Companies",
    "Principal Application Developer": "Various Tech Companies",
    "Principal Product Manager, AI": "Various AI Companies",
    "Principal Staff Software Engineer": "Various Tech Companies",
    "Principal Systems Engineer": "Various Systems Companies",
    "Production Engineer": "Various Manufacturing Companies",
    "Programmer": "Various Programming Companies",
    "Programmer Analyst / Developer": "Various Programming Companies",
    "Project Engineer": "Various Engineering Companies",
    "Puerto Rico Software Engineering Apprentice": "Various Puerto Rican Companies",
    "Quality Assurance Engineer -- Junior Product Manager | AI / Trucking": "Various QA Companies",
    "React Native App Developer": "Various React Native Companies",
    "Research Scientist / Bioinformatics Innovator": "Various Research Companies",
    "Responsive Ad Developer": "Various Web Development Companies",
    "Robotics Software Engineer – User Interface": "Various Robotics Companies",
    "Security Analyst - Junior": "Various Security Companies",
    "Senior Software Developer": "Various Tech Companies",
    "Solution Engineer": "Various Engineering Companies",
    "Solutions Engineer": "Various Engineering Companies",
    "SQL Database Administrator": "Various Database Companies",
    "Staff Engineer -": "Various Engineering Companies",
    "Staff Machine Learning Engineer": "Various ML Companies",
    "Staff Robotics Software Engineer": "Various Robotics Companies",
    "Support Analyst I": "Various Support Companies",
    "Technical Engineer": "Various Engineering Companies",
    "Technical Software Designer": "Various Design Companies",
    "Training and Placement in JAVA Full stack": "Various Java Training Companies",
    "UI Designer": "Various Design Companies",
    "UI developer": "Various UI Companies",
    "UI Developer": "Various UI Companies",
    "UI/User Experience Developer": "Various UX Companies",
    "User Experience": "Various UX Companies",
    "Video Game Programmer": "Various Gaming Companies",
    "Web Application Developer with Active Security Clearance": "Various Defense Companies",
    "Web Designer": "Various Web Design Companies",
    "Web Designer/Developer": "Various Web Companies",
    "Web, AI & Automation Specialist": "Various Web Automation Companies",
    "Website Developer - Build Soft Solutions, LLC": "Build Soft Solutions",
    "Widget Developer": "Various Widget Companies",
    
    # Add more mappings as needed based on your actual job titles
    # Format: "Exact Job Title": "Company Name"
}


async def manual_fix():
    """Apply manual company name fixes."""
    print("🔧 Applying manual company name fixes...")
    
    if not MANUAL_MAPPINGS:
        print("⚠️  No manual mappings defined!")
        print("Please edit the MANUAL_MAPPINGS dictionary in this script with your job title -> company name mappings.")
        return
    
    async with AsyncSessionLocal() as db:
        total_fixed = 0
        
        for job_title_pattern, company_name in MANUAL_MAPPINGS.items():
            print(f"\n🔍 Looking for: '{job_title_pattern}'")
            
            # Find applications matching this job title
            result = await db.execute(
                select(JobApplication).where(
                    JobApplication.platform == "indeed",
                    JobApplication.job_title.ilike(f"%{job_title_pattern}%"),
                    JobApplication.company_name.is_(None)
                )
            )
            apps = result.scalars().all()
            
            if apps:
                print(f"   📊 Found {len(apps)} matching application(s)")
                for app in apps:
                    print(f"     📧 {app.job_title}")
                    app.company_name = company_name
                total_fixed += len(apps)
            else:
                print(f"   ❌ No matching applications found")
        
        # Commit all changes
        if total_fixed > 0:
            await db.commit()
            print(f"\n🎉 Successfully fixed {total_fixed} applications!")
        else:
            print(f"\n⚠️  No applications were fixed")


async def show_job_titles():
    """Show all job titles for Indeed applications with unknown companies."""
    print("📋 Showing all Indeed job titles with unknown companies:")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.platform == "indeed",
                JobApplication.company_name.is_(None)
            ).order_by(JobApplication.job_title)
        )
        apps = result.scalars().all()
        
        if not apps:
            print("✅ No Indeed applications with unknown company names found!")
            return
        
        # Group by job title to see duplicates
        job_titles = {}
        for app in apps:
            title = app.job_title or "Unknown"
            if title not in job_titles:
                job_titles[title] = []
            job_titles[title].append(app)
        
        print(f"\n📊 Found {len(apps)} applications with {len(job_titles)} unique job titles:\n")
        
        for title, app_list in job_titles.items():
            print(f"• {title} ({len(app_list)} application{'s' if len(app_list) > 1 else ''})")
        
        print(f"\n💡 To fix these, edit the MANUAL_MAPPINGS dictionary in this script")
        print(f"   with format: \"Job Title\": \"Company Name\"")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        asyncio.run(show_job_titles())
    else:
        asyncio.run(manual_fix())
