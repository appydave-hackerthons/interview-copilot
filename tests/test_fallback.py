from interview_copilot.fallback import analyse_locally, build_local_report
from interview_copilot.models import AnalysisRequest, EvidenceItem, ReportRequest, TranscriptTurn


def test_local_analysis_extracts_pain_frequency_tool_and_questions() -> None:
    request = AnalysisRequest(
        transcript=[
            TranscriptTurn(
                id="turn-1",
                speaker="Participant",
                text="I hate the visa run. Every 60 days I lose six hours and track it in Google Calendar.",
            )
        ]
    )

    packet = analyse_locally(request)

    assert {item.type for item in packet.evidence} >= {"pain", "fact", "quote"}
    assert any(item.type == "tool" and item.text == "Google Calendar" for item in packet.evidence)
    assert any(item.agent == "Opportunity" for item in packet.suggestions)
    assert any(item.agent == "Research" for item in packet.suggestions)


def test_local_analysis_deduplicates_existing_evidence() -> None:
    turn = TranscriptTurn(id="turn-1", speaker="Participant", text="I use Wise every 60 days.")
    request = AnalysisRequest(
        transcript=[turn],
        evidence=[EvidenceItem(id="tool-wise", type="tool", text="Wise", confidence=1)],
    )

    packet = analyse_locally(request)

    assert not any(item.text == "Wise" for item in packet.evidence)


def test_local_report_scores_coverage_from_evidence() -> None:
    request = ReportRequest(
        transcript=[
            TranscriptTurn(
                id="turn-1",
                speaker="Participant",
                text="Every 60 days I pay 1500 baht for a visa run.",
            )
        ],
        evidence=[
            EvidenceItem(id="pain-1", type="pain", text="Visa runs waste a day", pinned=True),
            EvidenceItem(id="workflow-1", type="workflow", text="Leaves the country to renew"),
        ],
    )

    report = build_local_report(request)

    assert report.score == 100
    assert report.top_pains == ["Visa runs waste a day"]
    assert "concierge test" in report.next_step
