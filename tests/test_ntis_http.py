import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
@respx.mock
async def test_ntis_search_invalid_xml_returns_error(kisti_server_module):
    respx.get("https://www.ntis.go.kr/rndopen/openApi/public_project").mock(
        return_value=Response(200, text="not xml")
    )
    client = kisti_server_module.NTISClient()
    result = await client.search("test", "PROJECT", max_results=1)
    assert result.get("error") is True
