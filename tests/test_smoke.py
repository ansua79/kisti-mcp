def test_import_smoke(kisti_server_module):
    # Sentinel: module loaded and key symbols exist.
    assert hasattr(kisti_server_module, "FastMCP")
    assert hasattr(kisti_server_module, "mcp")


def test_tools_registered(kisti_server_module):
    # Tool functions are defined even if service init fails.
    expected = [
        "search_scienceon_papers",
        "search_scienceon_paper_details",
        "search_scienceon_patents",
        "search_scienceon_patent_details",
        "search_scienceon_patent_citations",
        "search_scienceon_reports",
        "search_scienceon_report_details",
        "search_ntis_rnd_projects",
        "search_ntis_science_tech_classifications",
        "search_ntis_related_content_recommendations",
        "search_dataon_research_data",
        "search_dataon_research_data_details",
    ]
    for name in expected:
        assert hasattr(kisti_server_module, name)
