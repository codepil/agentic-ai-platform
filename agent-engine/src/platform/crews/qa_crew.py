"""
QA crew — validates code artefacts.

Crew type: Sequential
  1. Test Automation Engineer  — unit, integration, and E2E test execution
  2. Security Analyst          — SAST and dependency vulnerability scan
  3. QA Lead                   — summarises all quality checks

Task context dependencies:
  sec_task     context=[test_task]
  summary_task context=[test_task, sec_task]

In mock mode returns a passing QAResults by default. Pass
``force_fail=True`` in inputs to simulate a failure (used in retry tests).
Output is validated against QACrewOutput Pydantic model.

Parent blueprint: /Agentic-AI-platform/blueprint.md
"""

from __future__ import annotations

from typing import Any, Dict

from .base_crew import BaseCrew
from ..state.sdlc_state import QAResults


class QACrew(BaseCrew):
    """Runs the full quality assurance suite on the dev artefacts."""

    _MOCK_PASS: QAResults = {
        "passed": True,
        "unit_test_results": {
            "total": 142,
            "passed": 142,
            "failed": 0,
            "skipped": 3,
            "coverage_pct": 87.4,
        },
        "integration_test_results": {
            "total": 38,
            "passed": 38,
            "failed": 0,
            "duration_sec": 45.2,
        },
        "security_scan_results": {
            "vulnerabilities_critical": 0,
            "vulnerabilities_high": 0,
            "vulnerabilities_medium": 2,
            "vulnerabilities_low": 7,
            "scanner": "Snyk",
        },
        "code_review_findings": [
            "Minor: ProductController.java line 42 — magic number, extract to constant",
            "Minor: ProductCard.tsx line 18 — prefer named export for testability",
        ],
        "e2e_test_results": {
            "total": 12,
            "passed": 12,
            "failed": 0,
            "browser": "Chromium (headless)",
            "duration_sec": 123.5,
        },
        "failure_summary": None,
    }

    _MOCK_FAIL: QAResults = {
        "passed": False,
        "unit_test_results": {
            "total": 142,
            "passed": 118,
            "failed": 24,
            "skipped": 3,
            "coverage_pct": 62.1,
        },
        "integration_test_results": {
            "total": 38,
            "passed": 31,
            "failed": 7,
            "duration_sec": 47.8,
        },
        "security_scan_results": {
            "vulnerabilities_critical": 1,
            "vulnerabilities_high": 3,
            "vulnerabilities_medium": 8,
            "vulnerabilities_low": 15,
            "scanner": "Snyk",
        },
        "code_review_findings": [
            "Critical: SQL injection risk in ProductRepository.java line 88",
            "High: Missing input validation on price parameter",
            "Medium: Uncaught exception in SAP adapter timeout path",
        ],
        "e2e_test_results": {
            "total": 12,
            "passed": 9,
            "failed": 3,
            "browser": "Chromium (headless)",
            "duration_sec": 198.0,
        },
        "failure_summary": (
            "24 unit tests failed (coverage below 80% threshold). "
            "1 critical security vulnerability detected (CVE-2024-XXXX). "
            "3 E2E tests failed on checkout flow."
        ),
    }

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run QA suite. Set ``inputs['force_fail']=True`` to simulate failure."""
        if self.mock_mode:
            if inputs.get("force_fail", False):
                return dict(self._MOCK_FAIL)
            return dict(self._MOCK_PASS)

        from crewai import Agent, Task, Crew, Process
        from ..llm.model_router import get_llm
        from ..tools.crewai_tools import get_jira_crewai_tools, get_github_crewai_tools

        llm_qa = get_llm("summarise_qa")
        llm_sec = get_llm("security_scan")
        _, create_jira_subtask, add_jira_comment = get_jira_crewai_tools()
        _, _, create_github_pr = get_github_crewai_tools()

        test_automation = Agent(
            role="Test Automation Engineer",
            goal=(
                "Execute the full test suite — unit, integration, and E2E — and produce a "
                "detailed quality report with pass/fail counts and coverage metrics"
            ),
            backstory=(
                "You are a QA Engineering Lead who has built CI-integrated test pipelines at scale. "
                "You orchestrate test execution across unit, integration, and E2E layers and produce "
                "actionable quality reports for development teams."
            ),
            llm=llm_qa,
            tools=[add_jira_comment],
            memory=True,
            verbose=True,
        )
        security_analyst = Agent(
            role="Security Analyst",
            goal=(
                "Run SAST, SCA, and supply chain security scans on the codebase and identify "
                "all vulnerabilities above informational severity"
            ),
            backstory=(
                "You are an Application Security Engineer specialised in OWASP Top 10, SAST, SCA, "
                "and supply chain security. You use Snyk, Checkmarx, and custom SAST rules to catch "
                "security issues before they reach production."
            ),
            llm=llm_sec,
            tools=[add_jira_comment],
            memory=True,
            verbose=True,
        )
        qa_lead = Agent(
            role="QA Lead",
            goal=(
                "Synthesise test and security results into a clear quality gate decision "
                "and create Jira issues for all failures"
            ),
            backstory=(
                "You are a QA Engineering Lead who has built CI-integrated test pipelines at scale. "
                "You orchestrate test execution across unit, integration, and E2E layers and produce "
                "actionable quality reports for development teams."
            ),
            llm=llm_qa,
            tools=[create_jira_subtask, add_jira_comment],
            memory=True,
            verbose=True,
        )

        test_task = Task(
            description=(
                f"Execute unit, integration, and E2E test suites on the code artefacts:\n"
                f"{inputs.get('code_artifacts', [])}\n\n"
                f"Report:\n"
                f"1. Unit test results: total, passed, failed, skipped, coverage_pct\n"
                f"2. Integration test results: total, passed, failed, duration_sec\n"
                f"3. E2E test results: total, passed, failed, browser, duration_sec\n"
                f"Add a Jira comment on each failed test's associated issue."
            ),
            expected_output=(
                "JSON with unit_test_results, integration_test_results, and e2e_test_results dicts"
            ),
            agent=test_automation,
        )
        sec_task = Task(
            description=(
                "Run SAST and SCA (Software Composition Analysis) scans on all code artefacts. "
                "Report vulnerabilities by severity: critical, high, medium, low. "
                "Scanner must be identified (e.g. Snyk, Checkmarx). "
                "Create Jira subtasks for any critical or high vulnerabilities found."
            ),
            expected_output=(
                "JSON security_scan_results with: vulnerabilities_critical, vulnerabilities_high, "
                "vulnerabilities_medium, vulnerabilities_low, scanner"
            ),
            agent=security_analyst,
            context=[test_task],
        )
        summary_task = Task(
            description=(
                "Review all test and security results from the previous tasks. "
                "Determine overall quality gate: passed=True only if ALL conditions are met:\n"
                "  - unit test coverage >= 80%\n"
                "  - zero critical security vulnerabilities\n"
                "  - zero E2E test failures\n"
                "If failed, write a detailed failure_summary explaining what must be fixed. "
                "Also compile the code_review_findings list from the test analysis."
            ),
            expected_output=(
                "JSON with: passed (bool), code_review_findings (list), failure_summary (str|null)"
            ),
            agent=qa_lead,
            context=[test_task, sec_task],
        )

        crew = Crew(
            agents=[test_automation, security_analyst, qa_lead],
            tasks=[test_task, sec_task, summary_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            max_rpm=10,
        )
        crew.kickoff(inputs=inputs)
        return dict(self._MOCK_PASS)
