import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List

import markdown2
from bs4 import Tag, NavigableString, BeautifulSoup

logger = logging.getLogger(__name__)


class TelegramMarkdownV2FormattedText(str):

    raw_text: str

    def __new__(cls, text: str):
        obj = str.__new__(cls, format_markdownV2(text))
        obj.raw_text = text
        return obj


def format_markdownV2(text: str) -> str:
    try:
        splits = _split_by_quotes2(text)
        code_base = _extract_code(splits)
        text = ''.join(splits)
        html = markdown2.markdown(text, extras=['strike'])
        soup = BeautifulSoup(html, 'lxml')
        content = handle_content(soup, {
            'padding': 0,
            'block_spacing': 2,
            'code_base': code_base
        })

        return content.format()
    except Exception as e:
        logger.exception('Error while formatting markdownV2: %s', e)
        return escape_markdownV2(text)


def escape_markdownV2(text: str) -> str:
    special_chars = r'[_*\[\]()~>#\+\-=\|\{\}\.\!\\]'
    return re.sub(special_chars, r'\\\g<0>', text)


def escape_markdownV2_with_quote(text: str) -> str:
    special_chars = r'[_*\[\]()~>#\+\-=\|\{\}\.\!\\`]'
    return re.sub(special_chars, r'\\\g<0>', text)


def _split_by_quotes(text):
    # Pattern to find strings enclosed in ` or ```, considering escaping
    pattern = r'((?<!\\)`{1,3}.*?(?<!\\)`{1,3})|([^`]+)'
    # Split the text by found matches
    parts = re.findall(pattern, text, flags=re.DOTALL)
    # Combine found groups and remove empty strings
    return [''.join(part)
            for part in parts if ''.join(part).strip()]

def _split_by_quotes2(text):
    parts = []
    pattern = r'(?<!\\)`{1,3}'
    while text:
        match = re.search(pattern, text)
        if not match:
            parts.append(text)
            break
        start = match.start()
        n = len(match.group())

        end_pattern = fr'(?<!\\)`{{{n}}}'
        offset = start + n
        end_search_text = text[offset:]
        if n < 3:
            first_line = end_search_text.splitlines()[0]
            match_end = re.search(end_pattern, first_line)
            if not match_end:
                start = offset + len(first_line)
                end = start
            else:
                end = match_end.end() + offset
        else:
            match_end = re.search(end_pattern, end_search_text)
            if not match_end:
                parts.append(text)
                break
            end = match_end.end() + offset

        parts.append(text[:start])
        parts.append(text[start:end])
        text = text[end:]

    return parts


def _extract_code(splits: List) -> List:
    code_base = []
    for i, split in enumerate(splits):
        if split.startswith('```'):
            code_base.append(split)
            splits[i] = f'```{len(code_base) - 1}```'
        elif split.startswith('`'):
            code_base.append(split)
            splits[i] = f'`{len(code_base) - 1}`'
    return code_base


class TelegramMD2Formatter(ABC):

    @abstractmethod
    def format(self):
        raise NotImplementedError()


class TextTelegramMD2Formatter(TelegramMD2Formatter):

    def __init__(self, text: str):
        self.text = text

    def format(self):
        return escape_markdownV2_with_quote(self.text)

    def __repr__(self):
        return 'TextTelegramMD2Formatter(text={})'.format(self.text)


class SeqTelegramMD2Formatter(TelegramMD2Formatter):

    def __init__(self, content: List[TelegramMD2Formatter], block_spacing: int = 2):
        self.content = content
        self.block_spacing = block_spacing
        # self.strip()

    def format(self):
        strings = []
        last_is_block = False
        last_is_inline = False

        def expand_content(seq):
            for item in seq:
                if isinstance(item, SeqTelegramMD2Formatter):
                    yield from expand_content(item.content)
                else:
                    yield item

        for c in expand_content(self.content):
            if isinstance(c, BlockTelegramMD2Formatter):
                if strings:
                    strings.append('\n' * self.block_spacing)
                strings.append(c.format())
                last_is_block = True
                last_is_inline = False
            else:
                if last_is_block:
                    strings.append('\n' * self.block_spacing)
                if last_is_inline:
                    strings.append(' ')
                strings.append(c.format().strip())
                last_is_block = False
                last_is_inline = True
        return ''.join(strings)

    # def strip(self):
    #     while self.content and isinstance(self.content[0], TextTelegramMD2Formatter) and not self.content[0].text.strip():
    #         self.content.pop(0)
    #     while self.content and isinstance(self.content[-1], TextTelegramMD2Formatter) and not self.content[-1].text.strip():
    #         self.content.pop(-1)

    def __repr__(self):
        return 'SeqTelegramMD2Formatter(content={})'.format(self.content)

class NodeTelegramMD2Formatter(TelegramMD2Formatter, ABC):

    def __init__(self, content: TelegramMD2Formatter):
        self.content = content

    def __repr__(self):
        return f'{self.__class__.__name__}(content={self.content})'


class BlockTelegramMD2Formatter(NodeTelegramMD2Formatter, ABC):

    def __init__(self, content: TelegramMD2Formatter, padding: int):
        super().__init__(content)
        self.padding = padding


class ParagraphBlock(BlockTelegramMD2Formatter):

    def format(self):
        return f'{" " * self.padding}{self.content.format().strip()}'


class MonoBlock(NodeTelegramMD2Formatter):

    def format(self):
        return f'`{self.content.format()}`'


class CodeBlock(BlockTelegramMD2Formatter):

    def __init__(self, content: TelegramMD2Formatter):
        super().__init__(content, 0)

    def format(self):
        return f'```{self.content.format().strip(" ")}```'


class BlockQuoteBlock(BlockTelegramMD2Formatter):

    def __init__(self, content: TelegramMD2Formatter):
        super().__init__(content, 0)

    def format(self):
        content = self.content.format()
        if not content.startswith('\n'):
            content = '\n' + content
        return f'```{content}```'


class BoldText(NodeTelegramMD2Formatter):

    def format(self):
        return f'*{self.content.format()}*'


class ItalicText(NodeTelegramMD2Formatter):

    def format(self):
        return f'_{self.content.format()}_'


class BoldItalicText(NodeTelegramMD2Formatter):

    def format(self):
        return f'*{self.content.format()}*'


class StrikethroughText(NodeTelegramMD2Formatter):

    def format(self):
        return f'~{self.content.format()}~'


class ListItem(BlockTelegramMD2Formatter):

    point = '\\-'

    def format(self):
        padding = self.padding

        delimiter = ' '
        first_block = None
        if isinstance(self.content, BlockTelegramMD2Formatter):
            first_block = self.content

        elif isinstance(self.content, SeqTelegramMD2Formatter) and isinstance(self.content.content[0], BlockTelegramMD2Formatter):
            first_block = self.content.content[0]
        if first_block:
            first_block.padding = 0
            if isinstance(first_block, CodeBlock):
                delimiter = '\n'
        text = f'{" " * padding}{self.point}{delimiter}{self.content.format()}'
        if first_block and isinstance(first_block, CodeBlock):
            text = '\n' + text

        # if not text.endswith('\n'):
        #     text += '\n'
        # if isinstance(self.content, ParagraphBlock) and not text.endswith('\n\n'):
        #     text += '\n'
        return text

class NumberedListItem(ListItem):

    def __init__(self, content: TelegramMD2Formatter, padding: int, number: int):
        super().__init__(content, padding)
        self.number = number

    @property
    def point(self):
        return f'{self.number}\\.'


class Hyperlink(NodeTelegramMD2Formatter):

    def __init__(self, content: TelegramMD2Formatter, url: str):
        super().__init__(content)
        self.url = url

    def format(self):
        return f'[{self.content.format()}]({self.url})'


class BlockQuote(BlockTelegramMD2Formatter):

    def format(self):
        padding = self.padding
        if isinstance(self.content, BlockTelegramMD2Formatter):
            self.content.padding = 0
        elif isinstance(self.content, SeqTelegramMD2Formatter) and isinstance(self.content.content[0], BlockTelegramMD2Formatter):
            self.content.content[0].padding = 0
        return f'{" " * padding}> {self.content.format()}'


def handle_content(content, context: Dict) -> TelegramMD2Formatter:
    results = []
    for child in content:
        if isinstance(child, Tag):
            result = handle_tag(child, context)
            if result:
                results.append(result)
        elif isinstance(child, NavigableString):
            text = handle_text(child, context)
            if text.text.strip():
                results.append(text)
    if len(results) == 1:
        return results[0]

    block_spacing = context.get('block_spacing', 2)
    return SeqTelegramMD2Formatter(results, block_spacing=block_spacing)


def handle_tag(tag, context: Dict) -> TelegramMD2Formatter:
    handler = globals().get(f'handle_{tag.name}')
    if handler:
        return handler(tag, context)
    else:
        logger.warning(f'No handler for tag {tag.name}')
        return handle_content(tag.contents, context)

def handle_text(text, context: Dict) -> TelegramMD2Formatter:
    return TextTelegramMD2Formatter(text)


def handle_strong(tag, context: Dict) -> TelegramMD2Formatter:
    return BoldText(handle_content(tag.contents, context))


def handle_s(tag, context: Dict) -> TelegramMD2Formatter:
    return StrikethroughText(handle_content(tag.contents, context))


def handle_em(tag, context: Dict) -> TelegramMD2Formatter:
    return ItalicText(handle_content(tag.contents, context))


def handle_del(tag, context: Dict) -> TelegramMD2Formatter:
    return StrikethroughText(handle_content(tag.contents, context))


def handle_code(tag, context: Dict) -> TelegramMD2Formatter:
    assert len(tag.contents) == 1
    content = str(tag.contents[0])
    try:
        num = int(content.strip())
        code = context['code_base'][num]
    except ValueError:
        code = content.strip()
    if code.startswith('```'):
        return CodeBlock(TextTelegramMD2Formatter(code[3:-3]))
    elif code.startswith('`'):
        return MonoBlock(TextTelegramMD2Formatter(code[1:-1]))


def handle_h1(tag, context: Dict) -> TelegramMD2Formatter:
    return ParagraphBlock(
        BoldText(handle_content(tag.contents, context)),
        padding=context['padding']
    )

handle_h2 = handle_h1
handle_h3 = handle_h1


def handle_blockquote(tag, context: Dict) -> TelegramMD2Formatter:
    context = dict(context)
    context['padding'] = 0
    content = handle_content(tag.contents, context)
    return BlockQuoteBlock(content)


def handle_ul(tag, context: Dict) -> TelegramMD2Formatter:
    items = []
    padding = context['padding']
    context = dict(context)
    context['padding'] = padding + 2
    context['block_spacing'] = max(1, context['block_spacing'] - 1)
    for li in tag.find_all('li', recursive=False):
        items.append(ListItem(handle_content(li.contents, context), padding=padding))
    return SeqTelegramMD2Formatter(items, block_spacing=context['block_spacing'])


def handle_ol(tag, context: Dict) -> TelegramMD2Formatter:
    items = []
    padding = context['padding']
    block_spacing = context['block_spacing']
    new_block_spacing = max(1, block_spacing - 1)
    start_id = int(tag['start']) if 'start' in tag.attrs else 1
    for i, li in enumerate(tag.find_all('li', recursive=False), start=start_id):
        context = dict(context)
        context['padding'] = padding + 2 + len(str(i))
        context['block_spacing'] = new_block_spacing
        items.append(NumberedListItem(handle_content(li.contents, context), padding=padding, number=i))
    return SeqTelegramMD2Formatter(items, block_spacing=new_block_spacing)


def handle_li(tag, context: Dict) -> TelegramMD2Formatter:
    padding = context['padding']
    return ListItem(handle_content(tag.contents, context), padding=padding)


def handle_a(tag, context: Dict) -> TelegramMD2Formatter:
    url = tag.get('href', '')
    return Hyperlink(handle_content(tag.contents, context), url)


def handle_p(tag, context: Dict) -> TelegramMD2Formatter:
    padding = context['padding']
    return ParagraphBlock(handle_content(tag.contents, context), padding=padding)


def handle_html(content, context: Dict) -> TelegramMD2Formatter:
    return handle_content(content, context)


def handle_body(content, context: Dict) -> TelegramMD2Formatter:
    return handle_content(content, context)