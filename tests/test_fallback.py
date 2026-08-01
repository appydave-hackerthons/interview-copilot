from interview_copilot.fallback import analyse_locally, build_local_report
from interview_copilot.configuration import get_default_configuration
from interview_copilot.models import (
    AnalysisRequest,
    EvidenceItem,
    InterviewConfiguration,
    ReportRequest,
    TranscriptTurn,
)


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


def test_local_report_does_not_overstate_depth_coverage() -> None:
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

    assert 0 < report.score < 100
    assert report.top_pains == ["Visa runs waste a day"]
    assert "concierge test" in report.next_step


def test_local_fallback_respects_lenses_limits_and_report_sections() -> None:
    payload = get_default_configuration().model_dump()
    payload["copilot"]["lenses"]["research"] = False
    payload["copilot"]["limits"]["suggestions"] = 1
    payload["report"]["sections"]["quotes"] = False
    payload["report"]["sections"]["opportunity"] = False
    payload["report"]["score_against_success_metrics"] = False
    configuration = InterviewConfiguration.model_validate(payload)
    turn = TranscriptTurn(
        id="turn-1",
        speaker="Participant",
        text="I hate tracking this in Google Calendar every 60 days.",
    )

    packet = analyse_locally(AnalysisRequest(transcript=[turn], configuration=configuration))
    report = build_local_report(ReportRequest(
        transcript=[turn],
        evidence=packet.evidence,
        configuration=configuration,
    ))

    assert len(packet.suggestions) <= 1
    assert all(suggestion.agent != "Research" for suggestion in packet.suggestions)
    assert report.quotes == []
    assert report.opportunity == ""
    assert report.score == 0


def test_local_guidance_advances_the_depth_ladder_one_rung_at_a_time() -> None:
    request = AnalysisRequest(
        transcript=[
            TranscriptTurn(
                id="turn-1",
                speaker="Participant",
                text="I wanted to meet local people because I feel isolated at home.",
            ),
            TranscriptTurn(
                id="turn-2",
                speaker="Interviewer",
                text="How well are you getting that outcome right now—is it enough?",
            ),
            TranscriptTurn(
                id="turn-3",
                speaker="Participant",
                text="It is hit and miss, but I imagined it would happen naturally.",
            ),
        ]
    )

    packet = analyse_locally(request)

    assert packet.suggestions[0].priority == "high"
    assert "Where did it get stuck" in packet.suggestions[0].text
