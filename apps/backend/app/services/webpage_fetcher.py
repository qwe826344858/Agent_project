"""通用网页抓取服务"""

import logging

import certifi
import httpx

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class WebpageFetcher:
    """抓取页面 HTML，供清洗与入库流程复用。"""

    async def fetch(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=8.0),
                follow_redirects=True,
                verify=certifi.where(),
            ) as client:
                response = await client.get(url, headers=_DEFAULT_HEADERS)
                response.raise_for_status()
                return response.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("抓取网页失败: %s - %s", url[:120], exc)
            return None


webpage_fetcher = WebpageFetcher()
