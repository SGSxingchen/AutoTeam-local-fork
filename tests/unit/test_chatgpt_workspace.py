from autoteam import chatgpt_api


def test_workspace_candidate_kind_filters_page_heading_and_legal_links():
    assert chatgpt_api._workspace_candidate_kind("Choose a workspace") is None
    assert chatgpt_api._workspace_candidate_kind("Terms of Use") is None
    assert chatgpt_api._workspace_candidate_kind("Privacy Policy") is None


def test_workspace_candidate_kind_keeps_real_workspace_and_marks_personal_fallback():
    assert chatgpt_api._workspace_candidate_kind("Idapro") == "preferred"
    assert chatgpt_api._workspace_candidate_kind("Personal account") == "fallback"
