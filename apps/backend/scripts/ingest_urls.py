"""手动触发网页 RAG 入库脚本

示例：
    python scripts/ingest_urls.py --url https://example.com/a
    python scripts/ingest_urls.py --input-file data/urls.txt --namespace insurance_pages
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.ingestion_service import webpage_ingestion_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取网页并入库到 PostgreSQL + pgvector")
    parser.add_argument("--url", action="append", default=[], help="单个待抓取 URL，可重复传入")
    parser.add_argument("--input-file", help="包含 URL 列表的文本文件，每行一个 URL")
    parser.add_argument("--namespace", default=None, help="入库命名空间，默认使用配置 INGEST_NAMESPACE")
    parser.add_argument("--source-type", default="web_page", help="数据来源类型标记")
    parser.add_argument(
        "--metadata-json",
        default="{}",
        help="额外 metadata，JSON 字符串，例如 '{\"platform\":\"pingan\"}'",
    )
    return parser.parse_args()


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.url)
    if args.input_file:
        file_path = Path(args.input_file)
        lines = file_path.read_text(encoding="utf-8").splitlines()
        urls.extend(lines)
    return [url.strip() for url in urls if url.strip()]


async def main() -> None:
    args = parse_args()
    urls = load_urls(args)
    if not urls:
        raise SystemExit("未提供任何 URL，请使用 --url 或 --input-file")

    extra_metadata = json.loads(args.metadata_json)
    results = await webpage_ingestion_service.ingest_urls(
        urls=urls,
        namespace=args.namespace,
        source_type=args.source_type,
        extra_metadata=extra_metadata,
    )

    success = 0
    for item in results:
        print(
            f"[{item.status}] url={item.url} document_id={item.document_id} "
            f"chunks={item.chunk_count} message={item.message}"
        )
        if item.status == "success":
            success += 1

    print(f"done: success={success}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
