'''
A model to use for testing noteparser functionality
This model works by computing _expected_ results for test runs
    which can then be compared to the results returned by the system
This model relies on the raw structured elements in the file `results_unstamped.py`
'''

import shlex
from datetime import datetime

from results_unstamped import ALL_INCOMPLETE_TODOS, ALL_SKIPPED_TODOS, \
                              ALL_COMPLETE_TODOS, ALL_QUESTIONS


class NoteparserModel(object):
    """The noteparser model base class"""

    def __init__(self):
        super(NoteparserModel, self).__init__()

    def search_todos(self, notes_directory=None, todo_status='incomplete',
                     directory_filter=None, query_string=None, sort_by=None,
                     suppress_future=False, stamp=False):

        # Get base todos
        if todo_status == 'incomplete':
            todos = ALL_INCOMPLETE_TODOS['items']
        elif todo_status == 'skipped':
            todos = ALL_SKIPPED_TODOS['items']
        elif todo_status == 'complete':
            todos = ALL_COMPLETE_TODOS['items']
        else:
            raise ValueError('Invalid todo status ' + todo_status)

        # Apply directory filter
        if directory_filter:
            filtered_todos = []
            for todo in todos:
                if directory_filter in todo['file_path']:
                    filtered_todos.append(todo)
            todos = filtered_todos

        # Apply query string
        if query_string:
            components = shlex.split(query_string)
            filtered_todos = []
            for todo in todos:
                if all([component in todo['todo_text'] for component in components]):
                    filtered_todos.append(todo)
            todos = filtered_todos

        # Apply sort
        if sort_by:
            todos = sorted(todos, key=lambda k: k[sort_by], reverse=True)

        # Apply suppress future
        if suppress_future:
            filtered_todos = []
            for todo in todos:
                if todo['start_date'] > datetime.now().isoformat()[:10]:
                    continue
                else:
                    filtered_todos.append(todo)
            todos = filtered_todos

        # Emulate Stamping
        if stamp:
            for todo in todos:
                if not todo['start_date']:
                    todo['start_date'] = datetime.now().isoformat()[:10]
                if todo_status in ['skipped', 'complete']:
                    if not todo['end_date']:
                        todo['end_date'] = datetime.now().isoformat()[:10]


        formatted_todos = {
            'count': len(todos),
            'items': todos
        }

        return formatted_todos

    def search_questions(self, question_status='all', directory_filter=None):

        # Filter on question status
        questions = ALL_QUESTIONS['items']
        if question_status == 'all':
            pass
        elif question_status == 'answered':
            filtered_questions = []
            for question in questions:
                if question['answer']:
                    filtered_questions.append(question)
            questions = filtered_questions
        elif question_status == 'unanswered':
            filtered_questions = []
            for question in questions:
                if not question['answer']:
                    filtered_questions.append(question)
            questions = filtered_questions
        else:
            raise ValueError('Invalid question status ' + question_status)

        # Apply directory filter
        if directory_filter:
            filtered_questions = []
            for question in questions:
                if directory_filter in question['file_path']:
                    filtered_questions.append(question)
            questions = filtered_questions

        formatted_questions = {
            'count': len(questions),
            'items': questions
        }
        return formatted_questions
