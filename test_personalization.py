#!/usr/bin/env python3
"""
Quick test of the new ChatGPT 5.2 LinkedIn personalization
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Add execution directory to path to import prompts module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'execution'))
from prompts import get_linkedin_5_line_prompt

load_dotenv()

# Test with a few sample leads
test_leads = [
    {
        "first_name": "Brian",
        "company_name": "Rabben Hood Ventures",
        "title": "Founding Partner",
        "location": "United States"
    },
    {
        "first_name": "Carlos",
        "company_name": "Peoplebound",
        "title": "Managing Partner",
        "location": "Tucson, Arizona"
    },
    {
        "first_name": "Laura",
        "company_name": "HVM Communications",
        "title": "Founder / CEO",
        "location": "New York, New York"
    }
]

def test_personalization(lead):
    """Test the personalization for one lead"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in .env")
        return None

    client = OpenAI(api_key=api_key)

    # Get formatted prompt from central source
    prompt = get_linkedin_5_line_prompt(
        first_name=lead["first_name"],
        company_name=lead["company_name"],
        title=lead["title"],
        location=lead["location"]
    )

    try:
        print(f"\n{'='*80}")
        print(f"Testing: {lead['first_name']} - {lead['title']} at {lead['company_name']}")
        print(f"{'='*80}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at creating personalized LinkedIn DMs following strict template rules."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )

        message = response.choices[0].message.content.strip()

        # Clean up any quotes or formatting
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        message = message.replace("```", "").strip()

        print("\nGENERATED MESSAGE:")
        print("-" * 80)
        print(message)
        print("-" * 80)

        return message

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print("\nTesting ChatGPT 5.2 LinkedIn Personalization")
    print("=" * 80)

    for lead in test_leads:
        result = test_personalization(lead)
        if not result:
            print("Test failed!")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)
