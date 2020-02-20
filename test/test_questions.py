import os
import unittest

from shorthand.question_tools import get_questions

from utils import setup_environment
from model import NoteparserModel


CONFIG = setup_environment()
MODEL = NoteparserModel()


# Helper function to simplify tests
def get_question_results(question_status='all', directory_filter=None):
    return get_questions(notes_directory=CONFIG['notes_directory'],
                         question_status=question_status,
                         directory_filter=directory_filter)


class TestQuestions(unittest.TestCase):
    """Test basic search functionality of the library"""

    def test_setup(self):

        test_dir = CONFIG['notes_directory']
        assert os.path.exists(test_dir)

    def test_get_unanswered_questions(self):
        args = {
            'question_status': 'unanswered'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))

        args = {
            'question_status': 'unanswered',
            'directory_filter': 'section'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))

    def test_get_answered_questions(self):
        args = {
            'question_status': 'answered'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))

        args = {
            'question_status': 'answered',
            'directory_filter': 'section'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))

    def test_get_all_questions(self):
        args = {
            'question_status': 'all'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))

        args = {
            'question_status': 'all',
            'directory_filter': 'section'
        }
        self.assertCountEqual(get_question_results(**args), MODEL.search_questions(**args))
