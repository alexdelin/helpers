import re
import json
import logging
import codecs

from shorthand.todo_tools import parse_todo
from shorthand.tag_tools import extract_tags
from shorthand.utils.rec import load_from_string
from shorthand.utils.patterns import DEFINITION_PATTERN, \
                                     INTERNAL_LINK_PATTERN, GPS_PATTERN

definition_regex = re.compile(DEFINITION_PATTERN)
internal_link_regex = re.compile(INTERNAL_LINK_PATTERN)
gps_regex = re.compile(GPS_PATTERN)


log = logging.getLogger(__name__)


def get_rendered_markdown(markdown_content):
    '''Pre-render all non-standard notes file
    elements into HTML
    '''

    html_content_lines = []
    toc_content_lines = []
    markdown_content_lines = markdown_content.split('\n')
    is_fenced_code_block = False
    is_diagram_block = False
    is_rec_data_block = False
    rec_data_lines = []

    for idx, markdown_line in enumerate(markdown_content_lines):

        line_number = idx + 1
        line_span = f'<span id="line-number-{line_number}"></span>'

        # Grab everything for record sets
        if markdown_line.strip()[:3] != '```' and is_rec_data_block:
            rec_data_lines.append(markdown_line)
            html_content_lines.append(line_span)
            continue

        # Special handling for diagram blocks
        if is_diagram_block and '```' not in markdown_line:
            if not markdown_line.strip():
                # Skip empty lines
                continue
            else:
                # Get rid of any indentation so it doesn't trip up the
                # Markdown parser into creating new paragraphs which
                # mess up mermaid
                html_content_lines.append(markdown_line.strip())
                continue

        # Handle empty or pseudo-empty lines
        if not markdown_line.strip():
            if not is_fenced_code_block:
                html_content_lines.append(line_span)
            html_content_lines.append(markdown_line)
            continue

        # Handle edges of fenced code blocks
        if markdown_line.strip()[:3] == '```':

            # Special handling for diagram blocks
            if markdown_line.strip()[:10] == '```mermaid':
                is_diagram_block = True
                html_content_lines.append(line_span)
                html_content_lines.append('<div class="mermaid">')
                continue
            elif is_diagram_block:
                is_diagram_block = False
                html_content_lines.append('</div>')
                continue

            # Special handling for record sets
            if markdown_line.strip()[:11] == '```rec-data':
                is_rec_data_block = True
                continue
            elif is_rec_data_block:
                is_rec_data_block = False
                record_set = load_from_string('\n'.join(rec_data_lines))
                record_set_data = json.dumps(list(record_set.all()))
                column_config = [{'title': field,
                                  'data': field,
                                  'defaultContent': ''}
                                 for field in record_set.get_fields()]
                record_set_name = record_set.get_config().get(
                    'rec', {}).get('name')
                if record_set_name:
                    html_content_lines.append(f'##### Record Set: '
                                              f'{record_set_name}')
                record_set_html = f'<div><div class="record-set-data">'\
                                  f'{record_set_data}'\
                                  f'</div><table class="table table-striped '\
                                  f'table-bordered record-set-table" '\
                                  f'style="width:100%" data-rec=\'\' '\
                                  f'data-cols='\
                                  f'\'{json.dumps(column_config)}\'>'\
                                  f'</table></div>'
                html_content_lines.append(record_set_html)
                html_content_lines.append(line_span)
                rec_data_lines = []
                continue

            is_fenced_code_block = not is_fenced_code_block
            html_content_lines.append(markdown_line)
            continue

        # Handle contents of fenced code blocks
        if is_fenced_code_block:
            html_content_lines.append(markdown_line)
            continue

        # Process internal links
        markdown_line = internal_link_regex.sub(
            '\\g<1>/render?path=\\g<2>\\g<3>',
            markdown_line)

        if gps_regex.search(markdown_line):
            markdown_line = gps_regex.sub(
                '<location lat="\\g<2>" lon="\\g<4>">'
                '<span class="location-name">\\g<6></span>'
                '(<span class="location-coordinates">\\g<2>, \\g<4></span>)'
                '</location>',
                markdown_line)

        # Process All to-dos
        if len(markdown_line) >= 4:
            if markdown_line.strip()[:4] in ['[ ] ', '[X] ', '[S] '] or \
                    markdown_line.strip()[:3] == '[] ':
                html_content_lines.append(line_span)
                todo_element = get_todo_element(markdown_line)
                html_content_lines.append(todo_element)
                continue

        # Process Questions & Answers
        if len(markdown_line) >= 2:
            if markdown_line.strip()[:2] in ['? ', '@ ']:
                html_content_lines.append(line_span)
                question_element = get_question_element(markdown_line)
                html_content_lines.append(question_element)
                continue

        # Process Definitions
        definition_match = definition_regex.match(markdown_line)
        if definition_match:
            html_content_lines.append(line_span)
            definition_element = get_definition_element(definition_match,
                                                        markdown_line)
            html_content_lines.append(definition_element)
            continue

        # Process Headings for Navigation
        if markdown_line[0] == '#':
            split_heading = markdown_line.split(' ', 1)
            heading_level = len(split_heading[0])
            element_id = split_heading[1].replace(' ', '-')
            heading_html_line = f'{markdown_line}<div id="{element_id}"></div>'
            toc_markdown_line = f'{"  " * (heading_level - 1)}- '\
                                f'[{split_heading[1]}](#{element_id})'
            html_content_lines.append(line_span)
            html_content_lines.append(heading_html_line)
            toc_content_lines.append(toc_markdown_line)
            continue

        # Special handling for display style equations
        if markdown_line.strip()[:2] == '$$' and \
                markdown_line.strip()[-2:] == '$$':
            html_content_lines.append(line_span)
            html_content_lines.append('')
            html_content_lines.append(markdown_line)
            html_content_lines.append('')
        else:
            # Catch-all for everything else
            html_content_lines.append(line_span)
            html_content_lines.append(markdown_line)

    html_content = '\n'.join(html_content_lines)
    toc_content = '\n'.join(toc_content_lines)
    return html_content, toc_content


def get_todo_element(raw_todo):
    '''Get a rendered HTML element for a todo given
    its properties
    '''

    todo = parse_todo(raw_todo.strip())
    leading_spaces = len(raw_todo) - len(raw_todo.lstrip(' '))

    status = todo['status']
    text = todo['todo_text']
    start = todo['start_date']
    end = todo['end_date']
    tags = todo['tags']
    tag_elements = ''.join([f'<span class="badge badge-secondary">{tag}</span>'
                            for tag in tags])
    if status == 'incomplete':
        icon = '<i class="material-icons">check_box_outline_blank</i>'
    elif status == 'complete':
        icon = '<i class="material-icons">check_box</i>'
    else:
        icon = '<i class="material-icons">indeterminate_check_box</i>'

    todo_element = f'- <span style="display: none;">a</span>'\
                   f'<div class="row todo-element todo-{status}">'\
                   f'<div class="col-md-1">{icon}</div>'\
                   f'<div class="col-md-7">{text}</div>'\
                   f'<div class="col-md-4 todo-meta">{tag_elements}<br />'\
                   f'{start} -> {end}</div>'\
                   f'</div>'

    todo_element = (' ' * leading_spaces) + todo_element
    return todo_element


def get_question_element(raw_question):
    '''Get rendered HTML for a question given its properties
    '''

    if raw_question.strip()[:2] == '? ':
        element_type = 'question'
        icon = '<i class="material-icons">help_outline</i>'
    if raw_question.strip()[:2] == '@ ':
        element_type = 'answer'
        icon = '<i class="material-icons">subdirectory_arrow_right</i>'

    text = raw_question.strip()[2:]
    tags, text = extract_tags(text)
    tag_elements = ''.join([f'<span class="badge badge-secondary">{tag}</span>'
                            for tag in tags])

    leading_spaces = len(raw_question) - len(raw_question.lstrip(' '))

    question_element = f'- <span style="display: none;">a</span>'\
                       f'<div class="row qa-element qa-{element_type}">'\
                       f'<div class="col-md-1">{icon}</div>'\
                       f'<div class="col-md-9">{text}</div>'\
                       f'<div class="col-md-2 question-meta">{tag_elements}'\
                       f'</div></div>'

    question_element = (' ' * leading_spaces) + question_element
    return question_element


def get_definition_element(definition_match, markdown_line):
    term = definition_match.group(2)
    term = term.strip().strip('{}')
    definition = definition_match.group(3)

    leading_spaces = len(markdown_line) - len(markdown_line.lstrip(' '))

    element = f'- <div class="row definition-element">'\
              f'<div class="col-md-2 definition-term">{term}</div>'\
              f'<div class="col-md-10 definition-text">{definition}'\
              f'</div></div>'

    element = (' ' * leading_spaces) + element
    return element


def get_file_content(file_path):
    '''Get the raw unmodified contents of a
    note file
    '''

    with codecs.open(file_path, mode='r', encoding="utf-8") as file_object:
        file_content = file_object.read()

    return file_content
