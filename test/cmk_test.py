# pylint:disable=locally-disabled,line-too-long

import json
import logging
import sys
from types import ModuleType
from typing import List, Optional
from unittest import TestCase


class CMKTest(TestCase):
    type: str = 'prod'
    pre_flag: List[str] = []
    post_flag: List[str] = []
    api_url: List[str] = []

    block_number: int = 0
    test_n: int = 0
    start_n: int = 0
    test_main: ModuleType

    def title(self, title):
        logging.info(f'\n{title}\n')

    def run_model(self, model_slug, model_input, exit_code: Optional[int] = 0, block_number: Optional[int] = None):
        if self.type == 'test':
            cmd = 'python test/test.py'
        else:
            cmd = 'credmark-dev'
        sys.argv = ([cmd] +
                    self.pre_flag +
                    ['run', model_slug, '-j'] +
                    ['-i', json.dumps(model_input)] +
                    self.post_flag +
                    [f'-b {self.block_number if block_number is None else block_number}'])

        cmd_line = ' '.join(
            [cmd] +
            self.pre_flag +
            ['run', model_slug, '-j'] +
            ['-i', f"'{json.dumps(model_input)}'"] +
            self.post_flag +
            [f'-b {self.block_number if block_number is None else block_number}'])

        if self.start_n > CMKTest.test_n:
            logging.info(f'Skip ({CMKTest.test_n})')
            CMKTest.test_n += 1
            return

        logging.info(f'Running case ({CMKTest.test_n}): expected {exit_code=} {cmd_line}')

        succeed = False
        try:
            self.test_main.main()
        except SystemExit as err:
            logging.info(f'{err=}, {err.code=}, Expected {exit_code=}')
            self.assertTrue(err.code == exit_code)
            succeed = True
        finally:
            logging.info(f'{"Finished" if succeed else "Failed"} case ({CMKTest.test_n}): {cmd_line}')
            if not succeed:
                sys.exit()

        CMKTest.test_n += 1
