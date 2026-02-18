#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TDD tests for Gift Leads List Pipeline.

Tests cover:
- Prospect research parsing
- Search query format validation
- Signal note generation and length
- CSV/JSON output structure
- Dynamic ICP passthrough
- Fallback behavior when APIs unavailable

Run: pytest tests/test_gift_leads_list.py -v
"""

import pytest
import os
import sys
import json
import csv
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_prospect_profile():
    """Sample LinkedIn profile for a prospect."""
    return {
        "linkedinUrl": "https://www.linkedin.com/in/johndoe",
        "firstName": "John",
        "lastName": "Doe",
        "fullName": "John Doe",
        "headline": "CEO at OutboundPro | Helping B2B companies scale outbound",
        "jobTitle": "CEO",
        "companyName": "OutboundPro",
        "companyIndustry": "Technology",
        "addressCountryOnly": "United States",
        "addressWithCountry": "Austin, Texas, United States",
        "about": "Building AI-powered outbound tools for B2B SaaS companies.",
        "experiences": [
            {"title": "CEO", "company": "OutboundPro", "duration": "3 years"},
            {"title": "VP Sales", "company": "SalesForce", "duration": "5 years"},
        ],
        "experiencesCount": 2,
    }


@pytest.fixture
def sample_research_output():
    """Sample output from research_prospect_business."""
    return {
        "icp_description": "B2B SaaS founders and sales leaders with 10-100 employees looking to scale outbound",
        "target_titles": ["CEO", "Founder", "VP Sales", "Head of Growth"],
        "target_industries": ["SaaS", "Technology", "Agency"],
        "target_verticals": ["SaaS", "marketing agency", "recruiting"],
        "pain_points": ["scaling outbound", "lead generation", "cold email deliverability"],
        "buying_signals": ["discussing outbound challenges", "hiring SDRs", "evaluating sales tools"],
        "buyer_intent_phrases": ["struggling with outbound", "how to scale sales team"],
        "search_angles": ["outbound pain points", "SDR hiring", "sales tool discussions"],
    }


@pytest.fixture
def sample_qualified_leads():
    """Sample qualified leads with engagement context."""
    return [
        {
            "linkedinUrl": "https://www.linkedin.com/in/janesmith",
            "fullName": "Jane Smith",
            "jobTitle": "CEO",
            "companyName": "GrowthCo",
            "companyIndustry": "Software",
            "addressWithCountry": "Austin, Texas, United States",
            "addressCountryOnly": "United States",
            "headline": "CEO at GrowthCo | SaaS",
            "engagement_type": "LIKE",
            "source_post_url": "https://linkedin.com/posts/somepost",
            "icp_match": True,
            "icp_confidence": "high",
            "icp_reason": "B2B SaaS founder, 30 employees",
            "experiencesCount": 3,
            "experiences": [{"title": "CEO", "company": "GrowthCo"}],
        },
        {
            "linkedinUrl": "https://www.linkedin.com/in/bobwilson",
            "fullName": "Bob Wilson",
            "jobTitle": "Founder",
            "companyName": "ScaleTech",
            "companyIndustry": "Technology",
            "addressWithCountry": "Toronto, Ontario, Canada",
            "addressCountryOnly": "Canada",
            "headline": "Founder @ ScaleTech",
            "engagement_type": "CELEBRATE",
            "source_post_url": "https://linkedin.com/posts/anotherpost",
            "icp_match": True,
            "icp_confidence": "medium",
            "icp_reason": "Tech founder, evaluating outbound tools",
            "experiencesCount": 2,
            "experiences": [{"title": "Founder", "company": "ScaleTech"}],
        },
    ]


# =============================================================================
# MODULE 1: PROSPECT PROFILE SCRAPING
# =============================================================================

class TestProspectProfileScraping:
    """Tests for scraping prospect profiles."""

    @patch('gift_leads_list.load_profile_cache')
    def test_scrape_prospect_profile_returns_cached(self, mock_cache, sample_prospect_profile):
        """Test that cached profiles are returned without API call."""
        from gift_leads_list import scrape_prospect_profile

        mock_cache.return_value = {
            "https://www.linkedin.com/in/johndoe": sample_prospect_profile
        }

        result = scrape_prospect_profile("https://www.linkedin.com/in/johndoe")
        assert result is not None
        assert result["fullName"] == "John Doe"

    @patch('gift_leads_list.load_profile_cache')
    def test_scrape_prospect_profile_cache_miss_no_token(self, mock_cache):
        """Test graceful handling when profile not cached and no API token."""
        from gift_leads_list import scrape_prospect_profile

        mock_cache.return_value = {}
        with patch('gift_leads_list.APIFY_API_TOKEN', None):
            result = scrape_prospect_profile("https://www.linkedin.com/in/unknown")
            assert result is None


# =============================================================================
# MODULE 2: PROSPECT RESEARCH
# =============================================================================

class TestProspectResearch:
    """Tests for researching prospect's business."""

    def test_fallback_research_with_user_icp(self, sample_prospect_profile):
        """Test fallback research uses user-provided ICP."""
        from gift_leads_list import _fallback_research

        result = _fallback_research(
            sample_prospect_profile,
            user_icp="B2B SaaS founders, 10-50 employees",
            user_pain_points="lead gen,outbound",
        )

        assert result["icp_description"] == "B2B SaaS founders, 10-50 employees"
        assert "lead gen" in result["pain_points"]
        assert "outbound" in result["pain_points"]

    def test_fallback_research_without_user_input(self, sample_prospect_profile):
        """Test fallback research derives from profile."""
        from gift_leads_list import _fallback_research

        result = _fallback_research(sample_prospect_profile)

        assert "icp_description" in result
        assert "target_titles" in result
        assert len(result["target_titles"]) > 0
        assert "pain_points" in result
        assert "buying_signals" in result

    def test_fallback_research_has_search_angles(self, sample_prospect_profile):
        """Test fallback research includes search_angles."""
        from gift_leads_list import _fallback_research

        result = _fallback_research(sample_prospect_profile)
        assert "search_angles" in result
        assert len(result["search_angles"]) > 0

    def test_fallback_research_has_new_fields(self, sample_prospect_profile):
        """Test fallback research includes target_verticals and buyer_intent_phrases."""
        from gift_leads_list import _fallback_research

        result = _fallback_research(sample_prospect_profile)
        assert "target_verticals" in result
        assert "buyer_intent_phrases" in result
        assert isinstance(result["target_verticals"], list)
        assert isinstance(result["buyer_intent_phrases"], list)

    @patch('gift_leads_list.DEEPSEEK_API_KEY', None)
    def test_research_falls_back_without_api_key(self, sample_prospect_profile):
        """Test that research falls back gracefully without API key."""
        from gift_leads_list import research_prospect_business

        result = research_prospect_business(sample_prospect_profile)

        assert "icp_description" in result
        assert "pain_points" in result


# =============================================================================
# MODULE 3: SEARCH QUERY GENERATION
# =============================================================================

class TestSearchQueryGeneration:
    """Tests for generating search queries."""

    def test_fallback_queries_have_correct_format(self, sample_research_output):
        """Test fallback queries use site:linkedin.com/posts format."""
        from gift_leads_list import _fallback_search_queries

        queries = _fallback_search_queries(sample_research_output, days_back=14)

        assert len(queries) >= 1
        for q in queries:
            assert "site:linkedin.com/posts" in q
            assert "after:" in q

    def test_fallback_queries_include_verticals_or_pain_points(self, sample_research_output):
        """Test fallback queries include verticals when available, else pain points."""
        from gift_leads_list import _fallback_search_queries

        queries = _fallback_search_queries(sample_research_output, days_back=14)

        # With verticals present, should use verticals
        verticals = sample_research_output["target_verticals"]
        query_text = " ".join(queries)
        assert any(v in query_text for v in verticals)

    def test_fallback_queries_include_buyer_intent(self, sample_research_output):
        """Test fallback queries include buyer intent phrases when available."""
        from gift_leads_list import _fallback_search_queries

        queries = _fallback_search_queries(sample_research_output, days_back=14)

        intent_phrases = sample_research_output["buyer_intent_phrases"]
        query_text = " ".join(queries)
        assert any(phrase in query_text for phrase in intent_phrases)

    def test_fallback_queries_no_verticals_uses_pain_points(self):
        """Test fallback uses pain points when no verticals available."""
        from gift_leads_list import _fallback_search_queries

        research = {
            "pain_points": ["lead generation", "outbound sales"],
            "target_verticals": [],
            "buyer_intent_phrases": [],
        }
        queries = _fallback_search_queries(research, days_back=14)

        query_text = " ".join(queries)
        assert any(pp in query_text for pp in research["pain_points"])

    def test_fallback_queries_date_is_correct(self, sample_research_output):
        """Test fallback queries have correct date cutoff."""
        from gift_leads_list import _fallback_search_queries

        queries = _fallback_search_queries(sample_research_output, days_back=7)

        expected_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        for q in queries:
            assert expected_date in q

    @patch('gift_leads_list.DEEPSEEK_API_KEY', None)
    def test_generate_queries_falls_back_without_key(self, sample_research_output):
        """Test query generation falls back without API key."""
        from gift_leads_list import generate_search_queries

        queries = generate_search_queries(sample_research_output, days_back=14)

        assert len(queries) >= 1
        for q in queries:
            assert "site:linkedin.com/posts" in q

    def test_fallback_queries_reasonable_count(self, sample_research_output):
        """Test fallback produces a reasonable number of queries (up to ~5)."""
        from gift_leads_list import _fallback_search_queries

        queries = _fallback_search_queries(sample_research_output, days_back=14)
        # 2 intent + 3 verticals = 5 max
        assert 1 <= len(queries) <= 5


# =============================================================================
# MODULE 4: SIGNAL NOTE GENERATION
# =============================================================================

class TestSignalNoteGeneration:
    """Tests for generating signal notes."""

    def test_fallback_signal_note_length(self, sample_qualified_leads):
        """Test fallback signal notes are max 100 chars."""
        from gift_leads_list import _fallback_signal_notes

        leads = _fallback_signal_notes(sample_qualified_leads)

        for lead in leads:
            assert "signal_note" in lead
            assert len(lead["signal_note"]) <= 100

    def test_fallback_signal_note_content(self, sample_qualified_leads):
        """Test fallback signal notes reference engagement."""
        from gift_leads_list import _fallback_signal_notes

        leads = _fallback_signal_notes(sample_qualified_leads)

        # First lead has LIKE engagement type
        assert "Liked" in leads[0]["signal_note"] or "Engaged" in leads[0]["signal_note"]

    def test_fallback_single_signal_note(self):
        """Test single fallback signal note."""
        from gift_leads_list import _fallback_single_signal_note

        lead = {
            "engagement_type": "LIKE",
            "jobTitle": "CEO",
            "companyName": "TestCo",
        }

        note = _fallback_single_signal_note(lead)
        assert len(note) <= 100
        assert "CEO" in note or "TestCo" in note

    @patch('gift_leads_list.DEEPSEEK_API_KEY', None)
    def test_generate_signal_notes_falls_back(self, sample_qualified_leads):
        """Test signal note generation falls back without API key."""
        from gift_leads_list import generate_signal_notes

        leads = generate_signal_notes(sample_qualified_leads, "B2B SaaS founders")

        for lead in leads:
            assert "signal_note" in lead
            assert len(lead["signal_note"]) <= 100

    def test_generate_signal_notes_empty_list(self):
        """Test signal notes with empty leads list."""
        from gift_leads_list import generate_signal_notes

        result = generate_signal_notes([], "some ICP")
        assert result == []


# =============================================================================
# MODULE 5: OUTPUT FORMATTING
# =============================================================================

class TestOutputFormatting:
    """Tests for JSON and CSV output formatting."""

    def test_format_gift_leads_json_structure(self, sample_qualified_leads):
        """Test JSON output has correct top-level structure."""
        from gift_leads_list import format_gift_leads_json, CostTracker

        ct = CostTracker()
        result = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        assert "prospect" in result
        assert "generated_at" in result
        assert "lead_count" in result
        assert "cost" in result
        assert "leads" in result

    def test_format_gift_leads_json_prospect_info(self, sample_qualified_leads):
        """Test JSON output has correct prospect info."""
        from gift_leads_list import format_gift_leads_json, CostTracker

        ct = CostTracker()
        result = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        assert result["prospect"]["name"] == "John Doe"
        assert result["prospect"]["url"] == "https://linkedin.com/in/johndoe"
        assert result["prospect"]["icp"] == "B2B SaaS founders"

    def test_format_gift_leads_json_lead_fields(self, sample_qualified_leads):
        """Test each lead has required fields."""
        from gift_leads_list import format_gift_leads_json, CostTracker

        ct = CostTracker()
        result = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        required_fields = [
            "name", "title", "company", "linkedin_url", "location",
            "signal_note", "source_post_url", "engagement_type",
            "icp_confidence", "icp_reason",
        ]

        for lead in result["leads"]:
            for field in required_fields:
                assert field in lead, f"Missing field: {field}"

    def test_format_gift_leads_json_lead_count(self, sample_qualified_leads):
        """Test lead_count matches actual leads."""
        from gift_leads_list import format_gift_leads_json, CostTracker

        ct = CostTracker()
        result = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        assert result["lead_count"] == len(result["leads"])
        assert result["lead_count"] == 2

    def test_format_gift_leads_json_cost_info(self, sample_qualified_leads):
        """Test cost info is included."""
        from gift_leads_list import format_gift_leads_json, CostTracker

        ct = CostTracker()
        ct.add_profile_scrape(5)
        ct.add_icp_check(3)

        result = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        assert result["cost"]["total"] > 0
        assert "breakdown" in result["cost"]

    def test_export_csv_creates_file(self, sample_qualified_leads):
        """Test CSV export creates a valid file."""
        from gift_leads_list import export_gift_leads_csv, format_gift_leads_json, CostTracker

        ct = CostTracker()
        json_output = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            export_gift_leads_csv(json_output["leads"], csv_path)

            assert os.path.exists(csv_path)

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["name"] == "Jane Smith"
            assert rows[1]["name"] == "Bob Wilson"
        finally:
            os.unlink(csv_path)

    def test_export_csv_has_correct_columns(self, sample_qualified_leads):
        """Test CSV has correct column headers."""
        from gift_leads_list import export_gift_leads_csv, format_gift_leads_json, CostTracker

        ct = CostTracker()
        json_output = format_gift_leads_json(
            leads=sample_qualified_leads,
            prospect_name="John Doe",
            prospect_url="https://linkedin.com/in/johndoe",
            icp_description="B2B SaaS founders",
            cost_tracker_instance=ct,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            export_gift_leads_csv(json_output["leads"], csv_path)

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

            expected = [
                "name", "title", "company", "linkedin_url", "location",
                "signal_note", "source_post_url", "engagement_type",
                "icp_confidence", "icp_reason",
            ]
            assert fieldnames == expected
        finally:
            os.unlink(csv_path)

    def test_export_csv_empty_leads(self):
        """Test CSV export handles empty leads list."""
        from gift_leads_list import export_gift_leads_csv

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            export_gift_leads_csv([], csv_path)
            # Should not create file or create empty file
        finally:
            if os.path.exists(csv_path):
                os.unlink(csv_path)


# =============================================================================
# MODULE 6: DYNAMIC ICP PASSTHROUGH
# =============================================================================

class TestDynamicICPPassthrough:
    """Tests for dynamic ICP criteria passing to qualification."""

    def test_icp_criteria_passed_to_deepseek(self, sample_qualified_leads):
        """Test that custom ICP criteria is passed through."""
        from gift_leads_list import qualify_leads_with_deepseek

        custom_icp = "B2B SaaS founders with 10-50 employees scaling outbound"

        # Mock check_icp_match_deepseek to capture args
        with patch('competitor_post_pipeline.check_icp_match_deepseek') as mock_check:
            mock_check.return_value = {"match": True, "confidence": "high", "reason": "test"}

            qualify_leads_with_deepseek(sample_qualified_leads[:1], icp_criteria=custom_icp)

            # Verify the custom ICP was passed
            mock_check.assert_called_once()
            args, kwargs = mock_check.call_args
            assert kwargs.get("icp_criteria") == custom_icp or args[1] == custom_icp


# =============================================================================
# PROMPT TESTS
# =============================================================================

class TestPrompts:
    """Tests for prompt templates."""

    def test_prospect_research_prompt_format(self):
        """Test prospect research prompt fills in all fields."""
        from prompts import get_prospect_research_prompt

        prompt = get_prospect_research_prompt(
            name="John Doe",
            headline="CEO at TestCo",
            about="Building cool stuff",
            company="TestCo",
            industry="Technology",
            experiences="CEO at TestCo (3 years)",
            user_icp="B2B SaaS founders",
            user_pain_points="lead gen, outbound",
        )

        assert "John Doe" in prompt
        assert "CEO at TestCo" in prompt
        assert "B2B SaaS founders" in prompt
        assert "lead gen, outbound" in prompt

    def test_prospect_research_prompt_includes_new_fields(self):
        """Test research prompt includes target_verticals and buyer_intent_phrases in output spec."""
        from prompts import get_prospect_research_prompt

        prompt = get_prospect_research_prompt(
            name="Test",
            headline="CEO",
            about="",
            company="TestCo",
            industry="Tech",
            experiences="",
        )

        assert "target_verticals" in prompt
        assert "buyer_intent_phrases" in prompt

    def test_prospect_research_prompt_no_user_input(self):
        """Test prospect research prompt works without user ICP."""
        from prompts import get_prospect_research_prompt

        prompt = get_prospect_research_prompt(
            name="John Doe",
            headline="CEO",
            about="",
            company="TestCo",
            industry="Tech",
            experiences="",
        )

        assert "derive from profile" in prompt

    def test_gift_search_query_prompt_format(self):
        """Test search query prompt includes ICP and new fields."""
        from prompts import get_gift_search_query_prompt

        prompt = get_gift_search_query_prompt(
            icp_description="B2B SaaS founders",
            pain_points=["lead gen", "outbound"],
            buying_signals=["hiring SDRs"],
            target_verticals=["SaaS", "marketing agency"],
            prospect_name="John Doe",
            prospect_headline="CEO at TestCo",
            prospect_company="TestCo",
        )

        assert "B2B SaaS founders" in prompt
        assert "lead gen" in prompt
        assert "SaaS, marketing agency" in prompt
        assert "John Doe" in prompt
        assert "CEO at TestCo" in prompt

    def test_gift_search_query_prompt_without_prospect_info(self):
        """Test search query prompt works without prospect profile info."""
        from prompts import get_gift_search_query_prompt

        prompt = get_gift_search_query_prompt(
            icp_description="B2B SaaS founders",
            pain_points=["lead gen"],
            buying_signals=["hiring SDRs"],
        )

        assert "B2B SaaS founders" in prompt
        assert "Unknown" in prompt  # default prospect_name

    def test_gift_search_query_prompt_3_angle_structure(self):
        """Test search query prompt contains all 3 angle sections."""
        from prompts import get_gift_search_query_prompt

        prompt = get_gift_search_query_prompt(
            icp_description="test",
            pain_points=["test"],
            buying_signals=["test"],
        )

        assert "Founder Pain" in prompt
        assert "Vertical-Specific" in prompt
        assert "Advisor/Thought-Leader Bait" in prompt
        assert "exactly 9" in prompt

    def test_gift_search_query_prompt_no_site_prefix_instruction(self):
        """Test prompt instructs LLM to NOT include site: prefix."""
        from prompts import get_gift_search_query_prompt

        prompt = get_gift_search_query_prompt(
            icp_description="test",
            pain_points=["test"],
            buying_signals=["test"],
        )

        assert "No site: prefix" in prompt or "Do NOT include" in prompt

    def test_gift_signal_note_prompt_format(self):
        """Test signal note prompt includes lead data."""
        from prompts import get_gift_signal_note_prompt

        leads = [
            {"linkedinUrl": "https://linkedin.com/in/test", "fullName": "Test User",
             "jobTitle": "CEO", "companyName": "TestCo", "engagement_type": "LIKE"},
        ]

        prompt = get_gift_signal_note_prompt("B2B SaaS founders", leads)

        assert "B2B SaaS founders" in prompt
        assert "Test User" in prompt
        assert "TestCo" in prompt

    def test_gift_signal_note_prompt_max_100_chars_instruction(self):
        """Test signal note prompt instructs max 100 chars."""
        from prompts import get_gift_signal_note_prompt

        prompt = get_gift_signal_note_prompt("test", [])
        assert "100" in prompt


# =============================================================================
# CLI TESTS
# =============================================================================

class TestCLI:
    """Tests for CLI argument parsing."""

    def test_cli_requires_prospect_url(self):
        """Test CLI requires --prospect-url."""
        from gift_leads_list import main
        import argparse

        with pytest.raises(SystemExit):
            # No args should fail
            with patch('sys.argv', ['gift_leads_list.py']):
                main()

    def test_cli_skip_research_requires_icp(self):
        """Test --skip-research requires --icp."""
        from gift_leads_list import main

        with pytest.raises(SystemExit):
            with patch('sys.argv', [
                'gift_leads_list.py',
                '--prospect-url', 'https://linkedin.com/in/test',
                '--skip-research',
            ]):
                main()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestPipelineIntegration:
    """Integration tests for the pipeline."""

    def test_pipeline_results_dict_structure(self):
        """Test pipeline returns correct results dict structure."""
        from gift_leads_list import run_gift_leads_pipeline

        # Run with dry-run and no cached data -> should return quickly
        results = run_gift_leads_pipeline(
            prospect_url="https://linkedin.com/in/nonexistent",
            dry_run=True,
        )

        expected_keys = [
            "prospect_url", "prospect_name", "icp_description",
            "queries_generated", "posts_found", "posts_filtered",
            "engagers_found", "prefilter_kept", "profiles_scraped",
            "location_filtered", "complete_profiles", "icp_qualified",
            "leads_with_notes", "final_leads",
        ]

        for key in expected_keys:
            assert key in results, f"Missing key: {key}"


# =============================================================================
# ACTIVITY SCORE TESTS
# =============================================================================

class TestComputeActivityScore:
    """Tests for compute_activity_score formula."""

    def test_compute_activity_score_full(self):
        """Test full activity score with all fields populated."""
        from gift_leads_list import compute_activity_score

        profile = {
            "connectionsCount": 500,
            "followersCount": 1000,
            "isCreator": True,
            "engagement_type": "LIKE",
        }
        score = compute_activity_score(profile)
        assert score == 100.0

    def test_compute_activity_score_partial(self):
        """Test partial score with some fields."""
        from gift_leads_list import compute_activity_score

        profile = {
            "connectionsCount": 250,
            "followersCount": 0,
            "isCreator": False,
        }
        score = compute_activity_score(profile)
        # 250/500 * 30 = 15, rest = 0
        assert score == 15.0

    def test_compute_activity_score_missing_fields(self):
        """Test score with all missing/null fields returns 0."""
        from gift_leads_list import compute_activity_score

        profile = {}
        score = compute_activity_score(profile)
        assert score == 0.0

    def test_compute_activity_score_string_connections(self):
        """Test score handles string connection count."""
        from gift_leads_list import compute_activity_score

        profile = {"connectionsCount": "500+"}
        score = compute_activity_score(profile)
        assert score == 30.0

    def test_compute_activity_score_capped_at_max(self):
        """Test score doesn't exceed component maximums."""
        from gift_leads_list import compute_activity_score

        profile = {
            "connectionsCount": 10000,
            "followersCount": 50000,
            "isCreator": True,
            "engagement_type": "COMMENT",
        }
        score = compute_activity_score(profile)
        assert score == 100.0  # Capped at 30+30+20+20

    def test_compute_activity_score_uses_alternative_keys(self):
        """Test score works with alternative field names."""
        from gift_leads_list import compute_activity_score

        profile = {
            "connection_count": 500,
            "follower_count": 1000,
            "is_creator": True,
            "engagement_type": "LIKE",
        }
        score = compute_activity_score(profile)
        assert score == 100.0


class TestExtractActivityFields:
    """Tests for extract_activity_fields helper."""

    def test_extract_activity_fields_complete(self):
        """Test extraction with all fields present."""
        from gift_leads_list import extract_activity_fields

        profile = {
            "connectionsCount": 300,
            "followersCount": 500,
            "isCreator": True,
        }
        fields = extract_activity_fields(profile)
        assert fields["connection_count"] == 300
        assert fields["follower_count"] == 500
        assert fields["is_creator"] is True
        assert fields["activity_score"] > 0

    def test_extract_activity_fields_empty(self):
        """Test extraction with empty profile."""
        from gift_leads_list import extract_activity_fields

        fields = extract_activity_fields({})
        assert fields["connection_count"] is None
        assert fields["follower_count"] is None
        assert fields["is_creator"] is None
        assert fields["activity_score"] == 0.0


# =============================================================================
# DB CHECK TESTS
# =============================================================================

class TestCheckDbForExistingLeads:
    """Tests for check_db_for_existing_leads."""

    @patch('requests.get')
    def test_check_db_returns_leads_when_enough(self, mock_get):
        """Test returns leads when DB has enough matches."""
        from gift_leads_list import check_db_for_existing_leads

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "pool_size": 100,
            "matches": 12,
            "prospects": [{"full_name": f"Lead {i}", "linkedin_url": f"url{i}"} for i in range(12)],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = check_db_for_existing_leads(["naturopath", "ND"], min_leads=10)
        assert result is not None
        assert len(result) == 12

    @patch('requests.get')
    def test_check_db_returns_none_when_not_enough(self, mock_get):
        """Test returns None when DB doesn't have enough matches."""
        from gift_leads_list import check_db_for_existing_leads

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "pool_size": 50,
            "matches": 3,
            "prospects": [{"full_name": f"Lead {i}"} for i in range(3)],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = check_db_for_existing_leads(["naturopath"], min_leads=10)
        assert result is None

    @patch('requests.get')
    def test_check_db_graceful_on_error(self, mock_get):
        """Test returns None gracefully on network error."""
        from gift_leads_list import check_db_for_existing_leads

        mock_get.side_effect = Exception("Connection refused")

        result = check_db_for_existing_leads(["naturopath"], min_leads=10)
        assert result is None


# =============================================================================
# PIPELINE RUN TRACKING TESTS
# =============================================================================

class TestPipelineRunTracking:
    """Tests for pipeline run tracking (POST to /api/pipeline-runs)."""

    def test_build_run_data_has_all_fields(self):
        """Test _build_run_data returns all required fields for the API."""
        from gift_leads_list import _build_run_data, CostTracker

        ct = CostTracker()
        ct.add_google_search(10)
        ct.add_profile_scrape(5)
        ct.add_icp_check(3)
        ct.add_personalization(2)

        results = {
            "prospect_url": "https://linkedin.com/in/test",
            "prospect_name": "Test User",
            "icp_description": "B2B SaaS founders",
            "queries_generated": 9,
            "posts_found": 20,
            "engagers_found": 100,
            "profiles_scraped": 50,
            "location_filtered": 30,
            "icp_qualified": 15,
            "final_leads": 12,
        }

        run_data = _build_run_data(results, ct, "completed", 120.5)

        # Required fields
        assert run_data["run_type"] == "gift_leads"
        assert run_data["status"] == "completed"
        assert run_data["prospect_url"] == "https://linkedin.com/in/test"
        assert run_data["prospect_name"] == "Test User"
        assert run_data["duration_seconds"] == 120

        # Pipeline metrics
        assert run_data["queries_generated"] == 9
        assert run_data["final_leads"] == 12
        assert run_data["profiles_scraped"] == 50

    def test_build_run_data_cost_fields(self):
        """Test cost breakdown fields are correctly mapped from CostTracker."""
        from gift_leads_list import _build_run_data, CostTracker

        ct = CostTracker()
        ct.add_google_search(5)
        ct.add_post_reactions(3)
        ct.add_profile_scrape(10)
        ct.add_icp_check(8)
        ct.add_personalization(4)

        results = {"prospect_url": "", "prospect_name": "", "icp_description": ""}
        run_data = _build_run_data(results, ct, "completed", 60.0)

        # All cost fields should be present and > 0
        assert run_data["cost_apify_google"] > 0
        assert run_data["cost_apify_reactions"] > 0
        assert run_data["cost_apify_profiles"] > 0
        assert run_data["cost_deepseek_icp"] > 0
        assert run_data["cost_deepseek_personalize"] > 0
        assert run_data["cost_total"] > 0
        assert run_data["cost_total"] == ct.get_total()

        # Count fields
        assert run_data["count_google_searches"] == 5
        assert run_data["count_posts_scraped"] == 3
        assert run_data["count_profiles_scraped"] == 10
        assert run_data["count_icp_checks"] == 8
        assert run_data["count_personalizations"] == 4

    def test_build_run_data_failed_status(self):
        """Test _build_run_data with failed status includes error message."""
        from gift_leads_list import _build_run_data, CostTracker

        ct = CostTracker()
        results = {"prospect_url": "url", "prospect_name": "Test", "icp_description": ""}

        run_data = _build_run_data(results, ct, "failed", 5.0, error_message="API timeout")

        assert run_data["status"] == "failed"
        assert run_data["error_message"] == "API timeout"
        assert run_data["duration_seconds"] == 5

    @patch('requests.post')
    def test_post_pipeline_run_success(self, mock_post):
        """Test _post_pipeline_run calls API correctly."""
        from gift_leads_list import _post_pipeline_run

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test-uuid", "status": "created"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        run_data = {"run_type": "gift_leads", "status": "completed"}
        _post_pipeline_run(run_data)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/api/pipeline-runs" in call_args[0][0] or "/api/pipeline-runs" in str(call_args)
        assert call_args[1]["json"] == run_data

    @patch('requests.post')
    def test_post_pipeline_run_graceful_on_error(self, mock_post):
        """Test _post_pipeline_run doesn't raise on API error."""
        from gift_leads_list import _post_pipeline_run

        mock_post.side_effect = Exception("Connection refused")

        # Should not raise
        _post_pipeline_run({"run_type": "gift_leads", "status": "completed"})


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
