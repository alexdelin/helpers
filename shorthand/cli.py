#!/usr/bin/env/python

import argparse
import logging

from shorthand.utils.config import get_notes_config
from shorthand.utils.logging import setup_logging
from shorthand.todo_tools import stamp_notes, get_todos


SHORTHAND_CONFIG = get_notes_config()
setup_logging(SHORTHAND_CONFIG)
log = logging.getLogger(__name__)


def run():
    args = parse_args()
    main(args)


def main(args):
    """Main method
    """

    notes_config = get_notes_config()
    notes_directory = notes_config['notes_directory']

    if args.action == 'stamp':
        log.info('Stamping Notes')
        print(stamp_notes(notes_directory))
    elif args.action == 'list':
        log.info('Listing Todos')
        print(get_todos(notes_directory, args.status))


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', required=True,
                        choices=['stamp', 'list'],
                        help='Action to take')
    parser.add_argument('--status', required=False,
                        choices=['completed', 'incomplete', 'skipped'],
                        default='incomplete',
                        help='To-Do Status to show')
    return parser.parse_args()


if __name__ == '__main__':
    run()
