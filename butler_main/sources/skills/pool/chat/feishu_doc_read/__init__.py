# -*- coding: utf-8 -*-
"""
飞书云文档读取 skill（feishu-doc-read）。
获取飞书 Docx 文档的纯文本、富文本块或 Markdown 内容。
"""

from .feishu_doc_read import (
    parse_document_id,
    get_tenant_token,
    get_document_meta,
    get_document_raw_content,
    get_document_blocks,
    blocks_to_markdown,
    read_feishu_doc,
    download_doc_to_file,
)

__all__ = [
    "parse_document_id",
    "get_tenant_token",
    "get_document_meta",
    "get_document_raw_content",
    "get_document_blocks",
    "blocks_to_markdown",
    "read_feishu_doc",
    "download_doc_to_file",
]
