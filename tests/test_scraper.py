"""Tests de scraping de ofertas (con mocks)."""

import pytest

from jobhunter.config import SearchConfig, ExperienceLevel, DatePosted, JobType, SortBy
from jobhunter.linkedin.scraper import build_search_url


class TestBuildSearchUrl:
    def test_basic_keywords_and_location(self):
        """URL básica con keywords y location."""
        search = SearchConfig(keywords="python", location="Chile")
        url = build_search_url(search)
        assert "keywords=python" in url
        assert "location=Chile" in url
        assert url.startswith("https://www.linkedin.com/jobs/search/")

    def test_url_encoding(self):
        """Keywords con espacios se codifican correctamente."""
        search = SearchConfig(keywords="python developer", location="New York")
        url = build_search_url(search)
        assert "keywords=python+developer" in url or "keywords=python%20developer" in url

    def test_date_posted_past_week(self):
        """date_posted = past_week genera f_TPR=r604800."""
        search = SearchConfig(
            keywords="test",
            date_posted=DatePosted.past_week,
        )
        url = build_search_url(search)
        assert "f_TPR=r604800" in url

    def test_date_posted_past_24h(self):
        """date_posted = past_24h genera f_TPR=r86400."""
        search = SearchConfig(
            keywords="test",
            date_posted=DatePosted.past_24h,
        )
        url = build_search_url(search)
        assert "f_TPR=r86400" in url

    def test_date_posted_past_month(self):
        """date_posted = past_month genera f_TPR=r2592000."""
        search = SearchConfig(
            keywords="test",
            date_posted=DatePosted.past_month,
        )
        url = build_search_url(search)
        assert "f_TPR=r2592000" in url

    def test_experience_level_single(self):
        """Un experience_level se mapea correctamente."""
        search = SearchConfig(
            keywords="test",
            experience_level=[ExperienceLevel.mid_senior],
        )
        url = build_search_url(search)
        assert "f_E=3" in url

    def test_experience_level_multiple(self):
        """Múltiples experience_level se unen con coma."""
        search = SearchConfig(
            keywords="test",
            experience_level=[ExperienceLevel.associate, ExperienceLevel.mid_senior],
        )
        url = build_search_url(search)
        assert "f_E=2%2C3" in url or "f_E=2,3" in url

    def test_job_type_full_time(self):
        """job_type full_time genera f_JT=F."""
        search = SearchConfig(
            keywords="test",
            job_type=[JobType.full_time],
        )
        url = build_search_url(search)
        assert "f_JT=F" in url

    def test_job_type_multiple(self):
        """Múltiples job_type se unen con coma."""
        search = SearchConfig(
            keywords="test",
            job_type=[JobType.full_time, JobType.contract],
        )
        url = build_search_url(search)
        assert "f_JT=F%2CC" in url or "f_JT=F,C" in url

    def test_remote(self):
        """remote=True genera f_WT=2."""
        search = SearchConfig(keywords="test", remote=True)
        url = build_search_url(search)
        assert "f_WT=2" in url

    def test_no_remote_when_false(self):
        """remote=False no incluye f_WT."""
        search = SearchConfig(keywords="test", remote=False)
        url = build_search_url(search)
        assert "f_WT" not in url

    def test_sort_by_recent(self):
        """sort_by=recent genera sortBy=DD."""
        search = SearchConfig(keywords="test", sort_by=SortBy.recent)
        url = build_search_url(search)
        assert "sortBy=DD" in url

    def test_sort_by_relevant(self):
        """sort_by=relevant genera sortBy=R."""
        search = SearchConfig(keywords="test", sort_by=SortBy.relevant)
        url = build_search_url(search)
        assert "sortBy=R" in url

    def test_full_filters(self):
        """URL con todos los filtros contiene todos los parámetros."""
        search = SearchConfig(
            keywords="data scientist",
            location="Spain",
            experience_level=[ExperienceLevel.mid_senior],
            date_posted=DatePosted.past_week,
            job_type=[JobType.full_time],
            remote=False,
            max_results=50,
            sort_by=SortBy.recent,
        )
        url = build_search_url(search)
        assert "keywords=data+scientist" in url or "keywords=data%20scientist" in url
        assert "location=Spain" in url
        assert "f_TPR=r604800" in url
        assert "f_E=3" in url
        assert "f_JT=F" in url
        assert "sortBy=DD" in url

    def test_minimal_config(self):
        """Config mínimo (solo keywords) genera URL válida sin filtros extra."""
        search = SearchConfig(keywords="python")
        url = build_search_url(search)
        assert "keywords=python" in url
        assert "f_TPR" not in url
        assert "f_E" not in url
        assert "f_JT" not in url
        assert "f_WT" not in url
