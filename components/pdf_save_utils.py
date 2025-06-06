import fitz
from typing import List, Union, NamedTuple


class PDFPageInfo(NamedTuple):
    pdf_path: str
    page_num: int


def save_pdf_pages(
    pages: List[Union[PDFPageInfo, dict]], save_path: str
) -> None:
    """
    指定したページ群を1つのPDFとして保存する。
    pages: PDFPageInfoまたは{'pdf_path': str, 'page_num': int}のリスト
    save_path: 保存先パス
    """
    pdf_writer = fitz.open()
    for info in pages:
        if isinstance(info, dict):
            pdf_path = info['pdf_path']
            page_num = info['page_num']
        else:
            pdf_path = info.pdf_path
            page_num = info.page_num
        with fitz.open(pdf_path) as src_doc:
            pdf_writer.insert_pdf(
                src_doc, from_page=page_num, to_page=page_num
            )
    pdf_writer.save(save_path)
    pdf_writer.close() 