#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD tests for Competitor Post Pipeline.

This pipeline:
1. Searches Google for LinkedIn posts about "CEOs" (last 7 days)
2. Filters posts with 50+ reactions
3. Scrapes post engagers via Apify
4. Scrapes LinkedIn profiles of engagers
5. Filters for US/Canada prospects
6. Qualifies leads via ICP filter (DeepSeek)
7. Generates personalized LinkedIn DMs (DeepSeek)
8. Uploads to HeyReach

Run tests: pytest tests/test_competitor_post_pipeline.py -v
"""

import pytest
import os
import sys
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_google_search_results():
    """Sample results from Google Search for LinkedIn posts."""
    return [
        {
            "url": "https://www.linkedin.com/posts/johndoe_ceos-leadership-activity-1234567890",
            "title": "John Doe on LinkedIn: CEOs need to focus on...",
            "description": "CEOs need to focus on building great teams...",
            "followersAmount": "150+ reactions"
        },
        {
            "url": "https://www.linkedin.com/posts/janedoe_startup-founders-activity-0987654321",
            "title": "Jane Doe on LinkedIn: As a CEO, I've learned...",
            "description": "As a CEO, I've learned that leadership is...",
            "followersAmount": "300+ reactions"
        },
        {
            "url": "https://www.linkedin.com/posts/lowengagement_ceo-activity-1111111111",
            "title": "Low engagement post",
            "description": "This post has low engagement",
            "followersAmount": "25+ reactions"
        }
    ]


@pytest.fixture
def sample_post_engagers():
    """Sample LinkedIn post engagers data."""
    return [
        {
            "reactor": {
                "profile_url": "https://www.linkedin.com/in/ACoAAA123456",
                "name": "Mike Johnson",
                "headline": "CEO at TechStartup Inc"
            },
            "reaction_type": "LIKE"
        },
        {
            "reactor": {
                "profile_url": "https://www.linkedin.com/in/ACoAAA789012",
                "name": "Sarah Williams",
                "headline": "Founder at Growth Agency"
            },
            "reaction_type": "CELEBRATE"
        },
        {
            "reactor": {
                "profile_url": "https://www.linkedin.com/in/ACoAAA345678",
                "name": "Carlos Garcia",
                "headline": "Student at University"
            },
            "reaction_type": "LIKE"
        }
    ]


@pytest.fixture
def sample_linkedin_profiles():
    """Sample scraped LinkedIn profile data."""
    return [
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA123456",
            "firstName": "Mike",
            "lastName": "Johnson",
            "fullName": "Mike Johnson",
            "headline": "CEO at TechStartup Inc",
            "jobTitle": "CEO",
            "companyName": "TechStartup Inc",
            "companyIndustry": "Software",
            "addressCountryOnly": "United States",
            "addressWithCountry": "San Francisco, California, United States",
            "about": "Building the future of tech...",
            "email": "mike@techstartup.com"
        },
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA789012",
            "firstName": "Sarah",
            "lastName": "Williams",
            "fullName": "Sarah Williams",
            "headline": "Founder at Growth Agency",
            "jobTitle": "Founder",
            "companyName": "Growth Agency",
            "companyIndustry": "Marketing",
            "addressCountryOnly": "Canada",
            "addressWithCountry": "Toronto, Ontario, Canada",
            "about": "Helping businesses grow...",
            "email": "sarah@growthagency.com"
        },
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA345678",
            "firstName": "Carlos",
            "lastName": "Garcia",
            "fullName": "Carlos Garcia",
            "headline": "Student at University",
            "jobTitle": "Student",
            "companyName": "University of Texas",
            "companyIndustry": "Education",
            "addressCountryOnly": "Mexico",
            "addressWithCountry": "Mexico City, Mexico",
            "about": "Studying business...",
            "email": None
        },
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA901234",
            "firstName": "David",
            "lastName": "Brown",
            "fullName": "David Brown",
            "headline": "Branch Manager at Santander",
            "jobTitle": "Branch Manager",
            "companyName": "Santander Bank",
            "companyIndustry": "Banking",
            "addressCountryOnly": "United States",
            "addressWithCountry": "Miami, Florida, United States",
            "about": "Banking professional...",
            "email": "david.brown@santander.com"
        }
    ]


@pytest.fixture
def sample_icp_qualified_leads():
    """Sample leads that pass ICP qualification."""
    return [
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA123456",
            "firstName": "Mike",
            "lastName": "Johnson",
            "fullName": "Mike Johnson",
            "headline": "CEO at TechStartup Inc",
            "jobTitle": "CEO",
            "companyName": "TechStartup Inc",
            "companyIndustry": "Software",
            "addressCountryOnly": "United States",
            "addressWithCountry": "San Francisco, California, United States",
            "about": "Building the future of tech...",
            "email": "mike@techstartup.com",
            "icp_qualified": True,
            "icp_reason": "CEO at tech company - clear decision maker"
        },
        {
            "linkedinUrl": "https://www.linkedin.com/in/ACoAAA789012",
            "firstName": "Sarah",
            "lastName": "Williams",
            "fullName": "Sarah Williams",
            "headline": "Founder at Growth Agency",
            "jobTitle": "Founder",
            "companyName": "Growth Agency",
            "companyIndustry": "Marketing",
            "addressCountryOnly": "Canada",
            "addressWithCountry": "Toronto, Ontario, Canada",
            "about": "Helping businesses grow...",
            "email": "sarah@growthagency.com",
            "icp_qualified": True,
            "icp_reason": "Founder at B2B agency"
        }
    ]


# =============================================================================
# MODULE 1: GOOGLE LINKEDIN POST SEARCH
# =============================================================================

class TestGoogleLinkedInPostSearch:
    """Tests for searching Google for LinkedIn posts."""

    def test_build_search_query(self):
        """Test building the Google search query."""
        from competitor_post_pipeline import build_google_search_query

        query = build_google_search_query(
            keywords="ceos",
            days_back=7
        )

        assert "site:linkedin.com/posts" in query
        assert "ceos" in query.lower()
        assert "after:" in query  # Date filter

    def test_filter_posts_by_reactions_removes_low_engagement(self, sample_google_search_results):
        """Test filtering posts with < 50 reactions."""
        from competitor_post_pipeline import filter_posts_by_reactions

        filtered = filter_posts_by_reactions(sample_google_search_results, min_reactions=50)

        assert len(filtered) == 2  # Only 2 posts have 50+ reactions
        assert all("25+ reactions" not in p["followersAmount"] for p in filtered)

    def test_filter_posts_by_reactions_keeps_high_engagement(self, sample_google_search_results):
        """Test that high engagement posts are kept."""
        from competitor_post_pipeline import filter_posts_by_reactions

        filtered = filter_posts_by_reactions(sample_google_search_results, min_reactions=50)

        urls = [p["url"] for p in filtered]
        assert "https://www.linkedin.com/posts/johndoe_ceos-leadership-activity-1234567890" in urls
        assert "https://www.linkedin.com/posts/janedoe_startup-founders-activity-0987654321" in urls

    def test_extract_reaction_count(self):
        """Test extracting reaction count from string."""
        from competitor_post_pipeline import extract_reaction_count

        assert extract_reaction_count("150+ reactions") == 150
        assert extract_reaction_count("1,234+ reactions") == 1234
        assert extract_reaction_count("50+ reactions") == 50
        assert extract_reaction_count("") == 0
        assert extract_reaction_count(None) == 0


# =============================================================================
# MODULE 2: POST ENGAGERS SCRAPER
# =============================================================================

class TestPostEngagersScraper:
    """Tests for scraping LinkedIn post engagers."""

    def test_aggregate_profile_urls(self, sample_post_engagers):
        """Test aggregating profile URLs from engagers."""
        from competitor_post_pipeline import aggregate_profile_urls

        urls = aggregate_profile_urls(sample_post_engagers)

        assert len(urls) == 3
        assert "https://www.linkedin.com/in/ACoAAA123456" in urls
        assert "https://www.linkedin.com/in/ACoAAA789012" in urls

    def test_deduplicate_profile_urls(self):
        """Test deduplicating profile URLs."""
        from competitor_post_pipeline import deduplicate_profile_urls

        urls = [
            "https://www.linkedin.com/in/user1",
            "https://www.linkedin.com/in/user2",
            "https://www.linkedin.com/in/user1",  # duplicate
            "https://www.linkedin.com/in/user3",
            "https://www.linkedin.com/in/user2",  # duplicate
        ]

        unique = deduplicate_profile_urls(urls)

        assert len(unique) == 3
        assert set(unique) == {
            "https://www.linkedin.com/in/user1",
            "https://www.linkedin.com/in/user2",
            "https://www.linkedin.com/in/user3"
        }


# =============================================================================
# MODULE 3: LOCATION FILTER
# =============================================================================

class TestLocationFilter:
    """Tests for filtering leads by location."""

    def test_filter_us_canada_keeps_us_leads(self, sample_linkedin_profiles):
        """Test that US leads are kept."""
        from competitor_post_pipeline import filter_by_location

        filtered = filter_by_location(
            sample_linkedin_profiles,
            allowed_countries=["United States", "Canada", "USA", "America"]
        )

        us_leads = [p for p in filtered if p["addressCountryOnly"] == "United States"]
        assert len(us_leads) >= 1

    def test_filter_us_canada_keeps_canada_leads(self, sample_linkedin_profiles):
        """Test that Canada leads are kept."""
        from competitor_post_pipeline import filter_by_location

        filtered = filter_by_location(
            sample_linkedin_profiles,
            allowed_countries=["United States", "Canada", "USA", "America"]
        )

        canada_leads = [p for p in filtered if p["addressCountryOnly"] == "Canada"]
        assert len(canada_leads) == 1

    def test_filter_us_canada_removes_other_countries(self, sample_linkedin_profiles):
        """Test that non-US/Canada leads are filtered out."""
        from competitor_post_pipeline import filter_by_location

        filtered = filter_by_location(
            sample_linkedin_profiles,
            allowed_countries=["United States", "Canada", "USA", "America"]
        )

        mexico_leads = [p for p in filtered if p["addressCountryOnly"] == "Mexico"]
        assert len(mexico_leads) == 0


# =============================================================================
# MODULE 4: ICP QUALIFICATION
# =============================================================================

class TestICPQualification:
    """Tests for ICP (Ideal Customer Profile) qualification."""

    def test_qualifies_ceo(self):
        """Test that CEO role qualifies."""
        from competitor_post_pipeline import check_icp_authority

        lead = {
            "jobTitle": "CEO",
            "companyName": "TechStartup Inc",
            "companyIndustry": "Software"
        }

        result = check_icp_authority(lead)
        assert result["qualified"] == True

    def test_qualifies_founder(self):
        """Test that Founder role qualifies."""
        from competitor_post_pipeline import check_icp_authority

        lead = {
            "jobTitle": "Founder",
            "companyName": "Growth Agency",
            "companyIndustry": "Marketing"
        }

        result = check_icp_authority(lead)
        assert result["qualified"] == True

    def test_rejects_student(self):
        """Test that Student role is rejected."""
        from competitor_post_pipeline import check_icp_authority

        lead = {
            "jobTitle": "Student",
            "companyName": "University",
            "companyIndustry": "Education"
        }

        result = check_icp_authority(lead)
        assert result["qualified"] == False

    def test_rejects_junior_role(self):
        """Test that Junior roles are rejected."""
        from competitor_post_pipeline import check_icp_authority

        lead = {
            "jobTitle": "Junior Marketing Associate",
            "companyName": "Marketing Agency",
            "companyIndustry": "Marketing"
        }

        result = check_icp_authority(lead)
        assert result["qualified"] == False

    def test_rejects_banking_institution(self):
        """Test that traditional banking is rejected."""
        from competitor_post_pipeline import check_icp_industry

        lead = {
            "jobTitle": "Branch Manager",
            "companyName": "Santander Bank",
            "companyIndustry": "Banking"
        }

        result = check_icp_industry(lead)
        assert result["qualified"] == False

    def test_qualifies_saas_industry(self):
        """Test that SaaS industry qualifies."""
        from competitor_post_pipeline import check_icp_industry

        lead = {
            "jobTitle": "CEO",
            "companyName": "SaaS Company",
            "companyIndustry": "Software"
        }

        result = check_icp_industry(lead)
        assert result["qualified"] == True

    def test_qualifies_agency_industry(self):
        """Test that Agency industry qualifies."""
        from competitor_post_pipeline import check_icp_industry

        lead = {
            "jobTitle": "CEO",
            "companyName": "Marketing Agency",
            "companyIndustry": "Marketing Services"
        }

        result = check_icp_industry(lead)
        assert result["qualified"] == True


# =============================================================================
# MODULE 5: PERSONALIZATION
# =============================================================================

class TestPersonalization:
    """Tests for LinkedIn DM personalization."""

    def test_personalized_message_has_greeting(self):
        """Test that personalized message starts with greeting."""
        from competitor_post_pipeline import generate_mock_personalization

        lead = {
            "firstName": "Mike",
            "companyName": "TechStartup Inc",
            "jobTitle": "CEO",
            "addressWithCountry": "San Francisco, California, United States"
        }

        message = generate_mock_personalization(lead)

        assert message.startswith("Hey Mike")

    def test_personalized_message_has_company_hook(self):
        """Test that personalized message mentions company."""
        from competitor_post_pipeline import generate_mock_personalization

        lead = {
            "firstName": "Mike",
            "companyName": "TechStartup Inc",
            "jobTitle": "CEO",
            "addressWithCountry": "San Francisco, California, United States"
        }

        message = generate_mock_personalization(lead)

        assert "looks interesting" in message.lower()

    def test_personalized_message_has_location_hook(self):
        """Test that personalized message mentions location."""
        from competitor_post_pipeline import generate_mock_personalization

        lead = {
            "firstName": "Sarah",
            "companyName": "Growth Agency",
            "jobTitle": "Founder",
            "addressWithCountry": "Toronto, Ontario, Canada"
        }

        message = generate_mock_personalization(lead)

        assert "Toronto" in message or "Canada" in message


# =============================================================================
# MODULE 6: HEYREACH UPLOAD
# =============================================================================

class TestHeyReachUpload:
    """Tests for HeyReach lead upload."""

    def test_format_lead_for_heyreach(self):
        """Test formatting a lead for HeyReach API."""
        from competitor_post_pipeline import format_lead_for_heyreach

        lead = {
            "firstName": "Mike",
            "lastName": "Johnson",
            "linkedinUrl": "https://www.linkedin.com/in/mikej",
            "companyName": "TechStartup Inc",
            "email": "mike@techstartup.com",
            "addressWithCountry": "San Francisco, CA",
            "about": "Building the future...",
            "personalized_message": "Hey Mike..."
        }

        formatted = format_lead_for_heyreach(lead, custom_fields=["personalized_message"])

        assert formatted["firstName"] == "Mike"
        assert formatted["lastName"] == "Johnson"
        assert formatted["profileUrl"] == "https://www.linkedin.com/in/mikej"
        assert len(formatted.get("customUserFields", [])) >= 1

    def test_format_lead_includes_custom_fields(self):
        """Test that custom fields are included in formatted lead."""
        from competitor_post_pipeline import format_lead_for_heyreach

        lead = {
            "firstName": "Mike",
            "lastName": "Johnson",
            "linkedinUrl": "https://www.linkedin.com/in/mikej",
            "personalized_message": "Hey Mike, your company looks interesting!"
        }

        formatted = format_lead_for_heyreach(lead, custom_fields=["personalized_message"])

        custom_fields = formatted.get("customUserFields", [])
        pm_field = next((f for f in custom_fields if f["name"] == "personalized_message"), None)

        assert pm_field is not None
        assert pm_field["value"] == "Hey Mike, your company looks interesting!"


# =============================================================================
# MODULE 7: FULL PIPELINE INTEGRATION
# =============================================================================

class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    def test_pipeline_config_has_required_fields(self):
        """Test that pipeline config has all required fields."""
        from competitor_post_pipeline import get_default_config

        config = get_default_config()

        required_fields = [
            "search_keywords",
            "days_back",
            "min_reactions",
            "allowed_countries",
            "heyreach_list_id"
        ]

        for field in required_fields:
            assert field in config, f"Missing required field: {field}"

    def test_pipeline_processes_leads_end_to_end(self, sample_linkedin_profiles):
        """Test that pipeline processes leads from start to finish."""
        from competitor_post_pipeline import process_leads_pipeline

        # Mock the pipeline to use sample data
        result = process_leads_pipeline(
            profiles=sample_linkedin_profiles,
            allowed_countries=["United States", "Canada"],
            skip_api_calls=True  # Use local filtering only
        )

        # Should filter out Mexico and potentially banking leads
        assert len(result) <= len(sample_linkedin_profiles)
        assert all(p["addressCountryOnly"] in ["United States", "Canada"] for p in result)


# =============================================================================
# UTILITY TESTS
# =============================================================================

class TestUtilities:
    """Tests for utility functions."""

    def test_casualize_company_name_removes_suffix(self):
        """Test removing company suffixes."""
        from competitor_post_pipeline import casualize_company_name

        assert casualize_company_name("TechStartup Inc") == "TechStartup"
        assert casualize_company_name("Growth Agency, LLC") == "Growth Agency"
        assert casualize_company_name("Marketing LTD") == "Marketing"

    def test_casualize_company_name_creates_abbreviation(self):
        """Test creating abbreviations for long names."""
        from competitor_post_pipeline import casualize_company_name

        # Multi-word names should be abbreviated
        result = casualize_company_name("Immersion Data Solutions, LTD")
        assert result == "IDS" or "Immersion" in result

    def test_extract_city_from_location(self):
        """Test extracting city from full location string."""
        from competitor_post_pipeline import extract_city_from_location

        assert extract_city_from_location("San Francisco, California, United States") == "San Francisco"
        assert extract_city_from_location("Toronto, Ontario, Canada") == "Toronto"
        assert extract_city_from_location("London") == "London"


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
