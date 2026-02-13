def test_scienceon_parse_invalid_xml_returns_error(kisti_server_module):
    client = kisti_server_module.ScienceONClient()
    result = client._parse_xml_response("not xml")
    assert result.get("error") is True
